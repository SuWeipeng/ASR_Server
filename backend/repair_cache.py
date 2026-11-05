# -*- coding: utf-8 -*-
"""
对已有缓存重跑同步修复并落盘

用法：
    python repair_cache.py <cache_dir> [cache_dir2 ...]
    python repair_cache.py            # 无参数 = 处理 cache/ 下全部缓存

对 cache/<name>/transcription.json 的 segments 重跑 _refine_segment_timing，
回写 transcription.json 并重新生成 subtitle.srt / subtitle.vtt。
音频输入使用缓存内的 audio.mp3（即 ASR 实际输入的人声）。
适用于：修复管线升级后，不想完整重新生成（demucs + ASR）的旧缓存。

注意：完整重新生成（前端强制刷新）的转录文本可能与此不同（ASR 非确定性），
本脚本只在现有词序列上重排时间戳。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.domain import SubtitleSegment, SubtitleWord
from app.services.subtitle_service import subtitle_service


def repair_one(cache_dir: str) -> bool:
    cache = Path(cache_dir)
    tj = cache / "transcription.json"
    audio = cache / "audio.mp3"
    if not tj.exists() or not audio.exists():
        print(f"[skip] {cache.name}: 缺 transcription.json 或 audio.mp3")
        return False

    data = json.loads(tj.read_text(encoding="utf-8"))
    segs = [
        SubtitleSegment(
            id=i, start=s["start"], end=s["end"], text=s["text"],
            words=[SubtitleWord(word=w["word"], start=w["start"], end=w["end"])
                   for w in (s.get("words") or [])],
        )
        for i, s in enumerate(data["segments"])
    ]

    subtitle_service._refine_segment_timing(segs, str(audio), "auto")

    for s, sj in zip(segs, data["segments"]):
        sj["start"], sj["end"] = round(s.start, 3), round(s.end, 3)
        for w, wj in zip(s.words or [], sj.get("words") or []):
            wj["start"], wj["end"] = round(w.start, 3), round(w.end, 3)
    tj.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    srt = subtitle_service.export_srt(segs)
    vtt = subtitle_service.export_vtt(segs)
    (cache / "subtitle.srt").write_text(srt, encoding="utf-8-sig")
    (cache / "subtitle.vtt").write_text(vtt, encoding="utf-8")
    print(f"[done] {cache.name}: {len(segs)} segments repaired & saved")
    return True


def main():
    base = Path(__file__).resolve().parent.parent / "cache"
    targets = sys.argv[1:] or [str(p) for p in sorted(base.iterdir()) if p.is_dir()]
    for t in targets:
        repair_one(t)


if __name__ == "__main__":
    main()
