# -*- coding: utf-8 -*-
"""
对已有缓存重跑同步修复并落盘（CLI 入口）

核心逻辑在 SubtitleService.repair_cached_timing（与设置页
POST /api/transcription/repair/{file_id} 共用同一实现）：
读缓存 transcription.json + audio.mp3 → _refine_segment_timing →
回写 transcription.json + srt/vtt + presnap（首次）。不重跑 demucs/ASR。
适用于：修复管线参数调整后，不想完整重新生成的旧缓存。

用法：
    python repair_cache.py <cache_dir> [cache_dir2 ...]
    python repair_cache.py            # 无参数 = 处理 cache/ 下全部缓存
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.subtitle_service import subtitle_service


def repair_one(cache_dir: str) -> bool:
    cache = Path(cache_dir)
    mj = cache / "metadata.json"
    if not mj.exists():
        print(f"[skip] {cache.name}: 缺 metadata.json")
        return False
    try:
        meta = json.loads(mj.read_text(encoding="utf-8"))
        filename = meta["original_filename"]
        file_size = int(meta["file_size"])
    except Exception as e:
        print(f"[skip] {cache.name}: metadata.json 解析失败: {e}")
        return False
    file_id = (meta.get("file_ids") or [""])[0]

    result = subtitle_service.repair_cached_timing(file_id, filename, file_size)
    if not result:
        print(f"[skip] {cache.name}: 缺 transcription.json 或 audio.mp3")
        return False
    if not (result.metadata or {}).get("sync_repair_applied"):
        print(f"[skip] {cache.name}: 同步修复总开关已关闭，未改写")
        return False
    print(f"[done] {cache.name}: {len(result.segments)} segments repaired & saved")
    return True


def main():
    base = Path(__file__).resolve().parent.parent / "cache"
    targets = sys.argv[1:] or [str(p) for p in sorted(base.iterdir()) if p.is_dir()]
    for t in targets:
        repair_one(t)


if __name__ == "__main__":
    main()
