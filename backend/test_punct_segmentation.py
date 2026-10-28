# -*- coding: utf-8 -*-
"""离线验证语意断句：用缓存的真实转录数据测试 punct_segmentation"""
import sys
import json

sys.path.insert(0, r"D:\ASR_Server\backend")

from app.utils.punct_segmentation import segment_subtitles

CACHE = r"D:\ASR_Server\cache\5_195036421\transcription.json"


def load_case():
    with open(CACHE, encoding="utf-8") as f:
        data = json.load(f)
    full_text = data["full_text"]
    # 旧 segments 的 words 还原出词级 timestamps
    timestamps = []
    for seg in data["segments"]:
        for w in seg.get("words") or []:
            timestamps.append((w["start"], w["end"], w["word"]))
    timestamps.sort(key=lambda t: t[0])
    return full_text, timestamps, data["segments"]


def main():
    full_text, timestamps, old_segments = load_case()
    print(f"full_text 长度: {len(full_text)} 字符, 词级时间戳: {len(timestamps)} 个")
    print(f"旧 VAD 分段数: {len(old_segments)}")
    print("=" * 70)

    segs = segment_subtitles(full_text, timestamps, max_duration_s=10.0)
    assert segs is not None, "对齐失败！不应回退"
    print(f"新语意分段数: {len(segs)}")
    print("=" * 70)

    # 1) 段文本必须都是 full_text 的子串（除中文空格处理）
    stripped = "".join(full_text.split())
    for i, s in enumerate(segs):
        compact = "".join(s["text"].split())
        assert compact in stripped, f"seg {i} 文本不是 full_text 子串: {s['text']!r}"
    print("[OK] 所有段文本均来自 full_text")

    # 2) 时间戳单调、递增覆盖
    for i in range(1, len(segs)):
        assert segs[i]["start"] >= segs[i - 1]["start"] - 1e-6, f"seg {i} 时间回退"
        assert segs[i - 1]["end"] <= segs[i]["start"] + 0.6, \
            f"seg {i-1}/{i} 时间重叠过大: {segs[i-1]['end']:.2f} vs {segs[i]['start']:.2f}"
    print("[OK] 段时间戳单调且基本无重叠")

    # 3) 所有词都被分配
    total_words = sum(len(s["words"]) for s in segs)
    assert total_words == len(timestamps), f"词数不匹配 {total_words} != {len(timestamps)}"
    print(f"[OK] 词数守恒 {total_words}")

    # 4) 断句应以句末标点结尾（长句二次切分的除外）
    bad_ends = [s["text"][-25:] for s in segs
                if s["text"] and s["text"][-1] not in "。！？!?；;….,：:）)”\"'」』]"]
    print(f"[统计] 段数 {len(segs)}，其中 {len(bad_ends)} 段不以标点结尾（超长句切分处）")
    for t in bad_ends[:5]:
        print("   ...", repr(t))

    print("=" * 70)
    print("前 14 段效果预览（对照旧 VAD 断句的句中切断）:")
    for s in segs[:14]:
        print(f"  [{s['start']:8.2f} - {s['end']:8.2f}] {s['text']}")

    print("=" * 70)
    print("desync 回退测试（打乱 full_text 应返回 None）:")
    corrupted = full_text[: len(full_text) // 2] + "完全无关的乱序文本" + full_text[len(full_text) // 2:]
    assert segment_subtitles(corrupted, timestamps) is None, "损坏文本应对齐失败"
    print("[OK] desync 检测生效，将回退旧逻辑")

    print("=" * 70)
    print("空输入测试:")
    assert segment_subtitles("", timestamps) is None
    assert segment_subtitles(full_text, []) is None
    print("[OK] 空输入安全")

    print("\n全部通过 ✔")


if __name__ == "__main__":
    main()
