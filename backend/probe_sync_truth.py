# -*- coding: utf-8 -*-
"""
地面真值探针：疑点簇紧窗裁剪 → qwen3-ASR 逐窗转写，产出"每个语音岛里到底是谁在说话"。

用途（README_sync_repair.md 2026-11-06 01_part1 复盘）：
  1. 对审计发现的"无人认领语音岛 + 疑似错位簇"逐窗转写，判定各岛是真实语音还是
     demucs 音乐残留（bleed）/ ASR 漏听，为修复通道的锚定/回收逻辑提供真值夹具。
  2. A/B 验证"demucs 后带通"对转写质量的影响（raw / 噪声配置频段 / 温和语音频段），
     决定 ASR 输入预处理默认值。

用法：
    python probe_sync_truth.py [cache_dir] [--device cpu|cuda]
结果落盘 <cache>/sync_truth.json，并在 stdout 打印人读报告。
时间均为全量音频绝对秒。窗口词时间 = 转写词时间 + 窗口起点偏移。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.asr_model import get_asr_model  # noqa: E402
from app.utils.audio import apply_noise_reduction  # noqa: E402
from app.utils.logger import logger  # noqa: E402
from app.utils.speech_islands import (  # noqa: E402
    compute_rms_envelope,
    detect_speech_islands,
    speech_threshold,
)

# 疑点簇窗口（全量音频绝对秒）。来源：2026-11-06 对 01_part1 的
# 岛级审计（无人认领岛 + 词落静音/速率异常段）。每窗 ±pad 秒裁剪。
PROBE_WINDOWS = [
    ("opening_0_16",      0.0,  16.5),   # 开头 4 岛无人认领：配乐 bleed 还是漏听旁白？
    ("movingin_27_34",   27.2,  34.6),   # 5.65s 无人认领（seg3/seg4 之间）
    ("narr_35_42",       35.5,  41.9),   # seg5 声称 38.2-41.9 vs 岛 35.9-40.5
    ("bryce_69_79",      69.0,  79.5),   # 用户报告 1:15 错位簇核心
    ("aftermath_80_88",  80.0,  88.0),   # "I mean nothing..." vs seg26 重叠区
    ("finally_100_112", 100.4, 112.6),  # 用户报告 1:51：seg35 挤扁 + 4.9s 无人认领
    ("school_118_127",  118.5, 127.0),  # 岛 118.85-119.65 / 124.7-126.45 无人认领
    ("troubles_139_143", 139.2, 143.0),  # 岛 139.55-142.6 无人认领
    ("sherry_191_199",  191.6, 199.3),  # 岛 191.9-192.45 / 196.95-198.55
    ("sniff_241_244",   241.0, 244.0),  # 岛 241.3-243.65
    ("chase_271_278",   271.5, 278.1),  # 4.95s 无人认领（seg85 前）
    ("stalls_325_330",  325.7, 330.0),  # 岛 326.05-329.6
    ("watermelon_367_379", 367.9, 370.7),  # 岛 368.2-370.35
    ("kiss_377_379",    377.2, 379.2),  # 岛 377.55-378.8
    ("newspaper_400_402", 400.9, 402.1),  # 岛 401.15-401.8
    ("letsspeak_408_413", 408.4, 413.0),  # 岛 408.7-409.15 + seg123/125（cps 异常）
    ("tree_447_460",    447.5, 460.5),  # seg134-139 区散点
    ("fix_464_465",     464.1, 465.2),  # 岛 464.4-464.9
]

# 带通 A/B 方案：(名称, lowcut, highcut, order)
BP_VARIANTS = [
    ("bp_config", 450.0, 3100.0, 6),    # noise_config.json 现值（偏电话频段）
    ("bp_speech", 80.0, 5500.0, 4),     # 温和语音频段
]


def decode_wav(path: str, sr: int = 16000) -> np.ndarray:
    wav, in_sr = sf.read(path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if in_sr != sr:  # 缓存内 audio.mp3（实为 wav 字节）通常已是 16k，防御性重采样
        import torch  # 局部 import，避免无谓依赖
        import torchaudio
        wav = torchaudio.functional.resample(torch.from_numpy(wav), in_sr, sr).numpy()
    return wav


def transcribe_window(model, seg_wav: np.ndarray, sr: int, offset: float) -> dict:
    result = model.transcribe((seg_wav, sr), language=None, return_time_stamps=True)
    item = result[0] if isinstance(result, list) else result
    if isinstance(item, dict):
        text = str(item.get("text") or "").strip()
        raw_ts = item.get("timestamps") or item.get("time_stamps") or []
    else:  # qwen_asr ASRTranscription：.text / .time_stamps
        text = str(getattr(item, "text", "") or "").strip()
        raw_ts = getattr(item, "time_stamps", None) or []
    words = []
    for t in raw_ts:
        if isinstance(t, dict):
            s, e, w = t.get("start"), t.get("end"), t.get("word", "")
        elif isinstance(t, (list, tuple)):
            s, e, w = t[0], t[1], t[2]
        else:  # ForcedAligner 词对象：.start_time / .end_time / .text
            s = getattr(t, "start_time", None)
            e = getattr(t, "end_time", None)
            w = getattr(t, "text", getattr(t, "word", ""))
        if s is None or e is None:
            continue
        words.append({"word": str(w), "start": round(float(s) + offset, 3),
                      "end": round(float(e) + offset, 3)})
    return {"text": text, "words": words}


def variant_wav(wav: np.ndarray, sr: int, lowcut: float, highcut: float, order: int) -> np.ndarray:
    return apply_noise_reduction(
        wav, sr,
        enabled=True, lowcut=lowcut, highcut=highcut,
        order=order, filter_type="bandpass",
        normalize_after_filter=False,  # ASR 输入不做归一化，保持 demucs 人声电平
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir", nargs="?", default=r"D:\ASR_Server\cache\01_part1_133682968")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--windows", default="", help="逗号分隔的窗口名过滤，默认全部")
    args = ap.parse_args()

    cache = Path(args.cache_dir)
    audio_path = cache / "audio.mp3"  # 即 demucs 人声 wav 字节拷贝
    if not audio_path.exists():
        print(f"not found: {audio_path}")
        return

    if args.device == "cpu":
        settings.USE_CPU = True
        settings.DEVICE = "cpu"

    wav = decode_wav(str(audio_path))
    sr = 16000
    duration = len(wav) / sr

    envelope, frame = compute_rms_envelope(wav, sr)
    fdur = frame / sr
    thr = speech_threshold(envelope)
    islands = detect_speech_islands(envelope, fdur, threshold=thr)

    wanted = {w.strip() for w in args.windows.split(",") if w.strip()}
    windows = [(n, s, e) for n, s, e in PROBE_WINDOWS if not wanted or n.strip() in wanted]

    model = get_asr_model().model  # 懒加载（device 由 settings 决定）
    print(f"device={settings.DEVICE}, windows={len(windows)}, islands={len(islands)}, dur={duration:.1f}s")

    out = {"cache": cache.name, "device": settings.DEVICE, "islands": [
        {"start": round(s, 3), "end": round(e, 3)} for s, e in islands
    ], "windows": []}

    for name, start, end in windows:
        start = max(0.0, start)
        end = min(duration, end)
        entry = {"id": name, "start": round(start, 3), "end": round(end, 3)}
        i0, i1 = int(start * sr), int(end * sr)
        entry["raw"] = transcribe_window(model, wav[i0:i1], sr, start)
        print(f"[{name}] raw: {entry['raw']['text'][:90]}")
        for vname, lo, hi, order in BP_VARIANTS:
            vwav = variant_wav(wav, sr, lo, hi, order)
            entry[vname] = transcribe_window(model, vwav[i0:i1], sr, start)
            print(f"[{name}] {vname}: {entry[vname]['text'][:90]}")
        out["windows"].append(entry)

    out_path = cache / "sync_truth.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved: {out_path}")

    # ---- 人读报告：词 → 岛覆盖 ----
    claimed = {}
    tj = cache / "transcription.json"
    if tj.exists():
        data = json.loads(tj.read_text(encoding="utf-8"))
        for seg in data["segments"]:
            claimed[seg["id"]] = (seg["start"], seg["end"], seg["text"])

    print("\n==== 窗口 × 岛覆盖报告（raw 转写词落在哪些岛） ====")
    for entry in out["windows"]:
        print(f"\n-- {entry['id']} [{entry['start']}, {entry['end']}]")
        for key in ["raw", "bp_config", "bp_speech"]:
            words = entry.get(key, {}).get("words") or []
            if not words:
                print(f"   {key}: (无词) text='{entry.get(key, {}).get('text', '')[:60]}'")
                continue
            by_island = {}
            for w in words:
                mid = (w["start"] + w["end"]) / 2
                hit = next(((s, e) for s, e in islands if s - 0.05 <= mid <= e + 0.05), None)
                label = f"{hit[0]:.2f}-{hit[1]:.2f}" if hit else "岛外"
                by_island.setdefault(label, []).append(w["word"])
            for label, ws in by_island.items():
                print(f"   {key}: {label}: {' '.join(ws)[:80]}")


if __name__ == "__main__":
    logger.setLevel("WARNING")  # 探针输出走 stdout，服务日志降噪
    main()
