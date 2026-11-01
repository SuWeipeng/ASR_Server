"""
split_movie.py - 把长电影按句子边界切成 5~8 分钟的练习小段

流程：
  1. ffmpeg 提取整条音轨（16kHz mono）
  2. （默认开启）demucs 分离人声，消除背景音乐/音效对识别的干扰
  3. Qwen3-ASR 整体转写（VAD 切分 + 词级时间戳），结果缓存到输出目录，中断重跑不重复识别
  4. 按标点语意断句得到句子边界，贪心装箱成 5~8 分钟的段——切点只落在句子之间，绝不断句
  5. ffmpeg 重编码精确切割（-c copy 会在关键帧处切，仍可能切进句子，故不用）
  6. 每段附带平移过时间轴的 SRT 字幕

用法（需在 qwen3-asr conda 环境中，任意目录运行）：
  python split_movie.py <电影文件> [选项]

输出：电影同目录下以电影名命名的文件夹，内含 01_part1.mp4、02_part2.mp4 ... 及对应 .srt
"""
import sys
from pathlib import Path

# 项目模块在 backend/ 下，根目录脚本需要手动加入 sys.path
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import argparse
import json
import subprocess
import time

from app.config import settings
from app.utils.logger import logger
from app.utils.ffmpeg import extract_audio, get_audio_duration, get_ffmpeg_path, get_ffmpeg_env
from app.utils.punct_segmentation import segment_subtitles
from app.services.asr_service import asr_service
from app.services.subtitle_service import subtitle_service
from app.models.domain import SubtitleSegment
from app.core.demucs_config import get_demucs_config
from app.utils.demucs import check_demucs_available, separate_vocals_to_16k_mono


# ---------- 命令行参数 ----------

def parse_args():
    parser = argparse.ArgumentParser(
        description="把长电影按句子边界切成 5~8 分钟的练习小段（附带每段 SRT 字幕）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("movie", help="电影文件路径（mp4/mkv 等）")
    parser.add_argument("--language", default="auto", help="转写语言：auto / English / Chinese")
    parser.add_argument("--min", type=float, default=5.0, help="每段最短时长（分钟）")
    parser.add_argument("--max", type=float, default=8.0, help="每段最长时长（分钟）")
    parser.add_argument("--no-demucs", action="store_true", help="跳过 demucs 人声分离（默认开启，电影背景音乐多）")
    parser.add_argument("--copy", action="store_true", help="用 -c copy 流拷贝切割（快但切点吸附关键帧，可能不精确）")
    parser.add_argument("--force", action="store_true", help="忽略已缓存的转写结果，重新识别")
    return parser.parse_args()


# ---------- ffmpeg 切割 ----------

_nvenc_probe_result = None


def nvenc_works() -> bool:
    """真实探测 h264_nvenc 可用性（仅查 -encoders 不够：ffmpeg 9.0 的 nvenc
    要求 NVIDIA 驱动 610.00+（nvenc API 13.1），驱动旧会初始化失败）。
    探测一次并缓存结果，以后驱动升级会自动恢复 GPU 编码。"""
    global _nvenc_probe_result
    if _nvenc_probe_result is None:
        try:
            test_out = Path(settings.TEMP_DIR) / "_nvenc_probe.mp4"
            result = subprocess.run(
                [get_ffmpeg_path(), "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=15",
                 "-c:v", "h264_nvenc", "-y", str(test_out)],
                capture_output=True, text=True, timeout=30, env=get_ffmpeg_env(),
            )
            _nvenc_probe_result = result.returncode == 0 and test_out.exists()
            test_out.unlink(missing_ok=True)
            if not _nvenc_probe_result:
                stderr_tail = (result.stderr or "").strip().splitlines()[-1] if result.stderr else ""
                logger.warning(f"h264_nvenc 探测失败，改用 CPU 编码（libx264）。原因: {stderr_tail}")
        except Exception as e:
            logger.warning(f"h264_nvenc 探测异常，改用 CPU 编码（libx264）: {e}")
            _nvenc_probe_result = False
    return _nvenc_probe_result


def cut_video(input_path: str, output_path: str, start: float, duration: float, use_copy: bool):
    """按 [start, start+duration) 精确切割。-ss 放在 -i 前快速定位，重编码保证帧级精确"""
    if use_copy:
        codec_args = ["-c", "copy"]
    elif nvenc_works():
        codec_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "0", "-c:a", "aac", "-b:a", "192k"]
    else:
        codec_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "192k"]

    command = [
        get_ffmpeg_path(),
        "-ss", f"{start:.3f}",
        "-i", input_path,
        "-t", f"{duration:.3f}",
        *codec_args,
        "-avoid_negative_ts", "make_zero",
        "-y",
        output_path,
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=3600, env=get_ffmpeg_env(),
    )
    if result.returncode != 0 or not Path(output_path).exists():
        raise RuntimeError(f"ffmpeg 切割失败: {result.stderr[-500:]}")


# ---------- 转写与断句 ----------

_TIMESTAMPS_PLACEHOLDER = "__TIMESTAMPS_PLACEHOLDER__"


def format_cache_json(data: dict) -> str:
    """缓存 JSON 排版：顶层字段多行缩进便于阅读；timestamps（上万词）压成单行，
    避免逐行缩进把文件膨胀到几十万行"""
    head = {k: v for k, v in data.items() if k != "timestamps"}
    content = json.dumps({**head, "timestamps": _TIMESTAMPS_PLACEHOLDER},
                         ensure_ascii=False, indent=2)
    compact = json.dumps(data.get("timestamps", []), ensure_ascii=False,
                         separators=(", ", ": "))
    return content.replace(json.dumps(_TIMESTAMPS_PLACEHOLDER), compact)


def write_cache(cache_path: Path, data: dict):
    cache_path.write_text(format_cache_json(data), encoding="utf-8")


def transcribe_movie(audio_path: str, language: str, cache_path: Path, force: bool) -> dict:
    """整体转写，结果缓存为 JSON（词级时间戳），避免长电影重复识别"""
    if cache_path.exists() and not force:
        logger.info(f"使用缓存的转写结果: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.info("加载 Qwen3-ASR 模型...")
    asr_service.model_manager.load_model()

    logger.info(f"开始整体转写（语言={language}），长电影可能需要 10~30 分钟...")
    t0 = time.time()
    result = asr_service.transcribe_long_audio(
        audio_path=audio_path,
        language=language,
        generate_timestamps=True,
        use_vad=True,
    )
    if not result:
        raise RuntimeError("转写失败")

    data = {
        "text": result.get("text", ""),
        "timestamps": [[s, e, w] for (s, e, w) in result.get("timestamps", [])],
        "language": language,
    }
    write_cache(cache_path, data)
    logger.info(f"转写完成: {time.time() - t0:.0f}s，{len(data['timestamps'])} 个词，已缓存到 {cache_path}")
    return data


def _fixed_windows(timestamps, cap: float):
    """断句兜底：按时间窗聚合词"""
    windows, cur, cur_start = [], [], None
    for s, e, w in timestamps:
        if cur_start is None:
            cur_start = s
        cur.append((s, e, w))
        if e - cur_start >= cap:
            windows.append({"start": cur_start, "end": e, "text": " ".join(x[2] for x in cur)})
            cur, cur_start = [], None
    if cur:
        windows.append({"start": cur_start, "end": cur[-1][1], "text": " ".join(x[2] for x in cur)})
    return windows


def build_segments(transcription: dict):
    """标点语意断句。返回 (句子段列表, 字幕段列表)：
    句子段（上限放宽到 30s）用于选切点——电影里偶尔有长句，打包单位太碎会在句中切；
    字幕段（默认 10s）用于生成每段的 SRT。两者源自同一份词级时间戳。
    """
    timestamps = [(s, e, w) for (s, e, w) in transcription.get("timestamps", [])]
    text = transcription.get("text", "")
    if not timestamps:
        raise RuntimeError("转写结果里没有词级时间戳，无法确定句子边界")

    try:
        sentence_segments = segment_subtitles(text, timestamps, max_duration_s=30.0)
    except Exception as e:
        logger.warning(f"语意断句失败（{e}），退化为固定 30s 窗口")
        sentence_segments = _fixed_windows(timestamps, 30.0)

    try:
        srt_segments = segment_subtitles(text, timestamps, max_duration_s=10.0)
    except Exception:
        srt_segments = _fixed_windows(timestamps, 10.0)

    if not sentence_segments:
        raise RuntimeError("断句结果为空")
    return sentence_segments, srt_segments


# ---------- 装箱 ----------

def plan_parts(sentence_segments, max_s: float, min_s: float):
    """贪心装箱：累加句子直到下一句会超出上限，就在它前面切。切点必然落在句子之间。"""
    parts, current = [], [sentence_segments[0]]
    for seg in sentence_segments[1:]:
        if seg["end"] - current[0]["start"] > max_s:
            parts.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        parts.append(current)

    # 尾部残余过短则并入前一段（可能略超上限，避免产生过短小段）
    if len(parts) >= 2 and parts[-1][-1]["end"] - parts[-1][0]["start"] < min_s:
        parts[-2].extend(parts[-1])
        parts.pop()
    return parts


# ---------- 输出 ----------

def segs_to_srt(segments, start_offset: float) -> str:
    """把（平移过时间轴的）字幕段写成 SRT"""
    shifted = [
        SubtitleSegment(
            id=i,
            start=round(s["start"] - start_offset, 3),
            end=round(s["end"] - start_offset, 3),
            text=s["text"],
        )
        for i, s in enumerate(segments)
    ]
    return subtitle_service.export_srt(shifted)


def segs_in_range(srt_segments, start: float, end: float):
    """取时间范围覆盖到的字幕段（按起点归属）"""
    return [s for s in srt_segments if start <= s["start"] < end]


def main():
    args = parse_args()
    min_s, max_s = args.min * 60, args.max * 60

    movie_path = Path(args.movie).resolve()
    if not movie_path.exists():
        print(f"电影文件不存在: {movie_path}")
        sys.exit(1)

    out_dir = movie_path.parent / movie_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"输入: {movie_path}")
    logger.info(f"输出目录: {out_dir}")

    duration = get_audio_duration(movie_path)
    logger.info(f"总时长: {duration / 60:.1f} 分钟")

    # 1. 提取音轨
    work_audio = out_dir / "_movie_audio.wav"
    if not work_audio.exists():
        logger.info("提取音轨（16kHz mono）...")
        extract_audio(str(movie_path), str(work_audio),
                      sample_rate=settings.AUDIO_SAMPLE_RATE, channels=settings.AUDIO_CHANNELS)

    # 2. demucs 人声分离（默认开启，电影背景音乐是常态）
    asr_input = str(work_audio)
    demucs_used = False
    if args.no_demucs:
        logger.info("已跳过 demucs（--no-demucs）")
    elif check_demucs_available():
        cfg = get_demucs_config().get_config()
        vocals_path = out_dir / "_movie_vocals.wav"
        if not vocals_path.exists():
            logger.info(f"demucs 分离人声（model={cfg.model_name}），约为时长的 1/40~1/70...")
            # 注意：必须喂提取好的 wav 而不是 mkv 原片——demucs 自带的容器解码器
            # 在长视频上会丢样本导致人声轨时间轴漂移（实测 90 分钟电影偏移数十秒）
            ok = separate_vocals_to_16k_mono(
                file_id=f"split_{movie_path.stem[:20]}",
                input_path=asr_input,
                output_path=str(vocals_path),
                model_name=cfg.model_name,
                repo_path=cfg.repo_path,
                duration=duration,
            )
            if not ok:
                logger.warning("demucs 分离失败，改用原声继续")
        if vocals_path.exists():
            asr_input = str(vocals_path)
            demucs_used = True
            logger.info("使用分离出的人声进行识别")

    # 3. 整体转写（带缓存）
    transcription = transcribe_movie(asr_input, args.language, out_dir / "asr_result.json", args.force)
    transcription["demucs_used"] = demucs_used

    # 4. 断句与装箱
    sentence_segments, srt_segments = build_segments(transcription)
    logger.info(f"断句完成: {len(sentence_segments)} 个句子段, {len(srt_segments)} 个字幕段")

    parts = plan_parts(sentence_segments, max_s, min_s)
    logger.info(f"装箱完成: {len(parts)} 段")

    # 5. 切割 + 每段 SRT
    total_parts = len(parts)
    for i, part in enumerate(parts, 1):
        start, end = part[0]["start"], part[-1]["end"]
        dur = end - start
        part_name = f"{i:02d}_part{i}"
        out_file = out_dir / f"{part_name}.mp4"

        if out_file.exists() and out_file.stat().st_size > 0:
            logger.info(f"[{i}/{total_parts}] {part_name} 已存在，跳过切割")
        else:
            logger.info(f"[{i}/{total_parts}] {part_name}: {start:.1f}s -> {end:.1f}s ({dur / 60:.1f} 分钟)")
            t0 = time.time()
            # 先写临时文件，成功后改名：中断/失败不会留下半截文件被当成成品
            part_tmp = out_dir / f"{part_name}.part.mp4"
            cut_video(str(movie_path), str(part_tmp), start, dur, use_copy=args.copy)
            part_tmp.replace(out_file)
            logger.info(f"[{i}/{total_parts}] 切割完成: {time.time() - t0:.0f}s")

        srt_file = out_dir / f"{part_name}.srt"
        part_srt = segs_in_range(srt_segments, start, end)
        srt_file.write_text(segs_to_srt(part_srt, start), encoding="utf-8")

    # 6. 清理中间音频与写清单
    manifest = {
        "movie": str(movie_path),
        "duration": duration,
        "demucs_used": demucs_used,
        "parts": [
            {
                "name": f"{i:02d}_part{i}",
                "start": round(p[0]["start"], 3),
                "end": round(p[-1]["end"], 3),
                "minutes": round((p[-1]["end"] - p[0]["start"]) / 60, 2),
                "sentences": len(p),
                "first_sentence": p[0]["text"][:60],
            }
            for i, p in enumerate(parts, 1)
        ],
    }
    (out_dir / "parts.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for tmp in (work_audio, out_dir / "_movie_vocals.wav"):
        if tmp.exists():
            tmp.unlink()

    logger.info(f"全部完成: {total_parts} 段 -> {out_dir}")


if __name__ == "__main__":
    main()
