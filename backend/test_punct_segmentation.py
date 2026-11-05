# -*- coding: utf-8 -*-
"""离线验证语意断句：用缓存的真实转录数据 + 合成引号用例测试 punct_segmentation"""
import json
import sys

sys.path.insert(0, r"D:\ASR_Server\backend")

from app.utils.punct_segmentation import segment_subtitles

CACHE = r"D:\ASR_Server\cache\5_195036421\transcription.json"
CACHE_QUOTES = r"D:\ASR_Server\cache\7_32554575\transcription.json"


def load_case(path=CACHE):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    full_text = data["full_text"]
    # 旧 segments 的 words 还原出词级 timestamps
    timestamps = []
    for seg in data["segments"]:
        for w in seg.get("words") or []:
            timestamps.append((w["start"], w["end"], w["word"]))
    timestamps.sort(key=lambda t: t[0])
    return full_text, timestamps, data["segments"]


def _ts_for(words, t0=0.0, dur=0.4, gap=0.1):
    """合成词级时间戳"""
    ts = []
    t = t0
    for w in words:
        ts.append((t, t + dur, w))
        t += dur + gap
    return ts


def case_closed_quote_pair():
    """闭引号收尾：`I asked, "Is everything okay?"` 整段成对，不把闭引号移到下一段"""
    text = 'I asked, "Is everything okay?" She said yes and left quickly.'
    words = ["I", "asked", "Is", "everything", "okay", "She", "said", "yes", "and", "left", "quickly"]
    segs = segment_subtitles(text, _ts_for(words))
    assert segs is not None, "对齐失败"
    assert len(segs) == 2, f"应切为 2 段，实际 {len(segs)}: {[s['text'] for s in segs]}"
    assert segs[0]["text"] == 'I asked, "Is everything okay?"', repr(segs[0]["text"])
    assert segs[1]["text"].startswith("She said"), repr(segs[1]["text"])
    print("[OK] 闭引号收尾整段成对，次段以 She said 开头")


def case_straight_quote_not_moved():
    """直引号闭引号不再被当开引号移动：不产生 `" Right.` 孤立段"""
    text = 'He asked, "Was that 15 or 50?" Right, exactly fifty.'
    words = ["He", "asked", "Was", "that", "15", "or", "50", "Right", "exactly", "fifty"]
    segs = segment_subtitles(text, _ts_for(words))
    assert segs is not None
    texts = [s["text"] for s in segs]
    assert all(not t.startswith('"') for t in texts), f"出现引号开头的孤立段: {texts}"
    assert not any(t.strip() == '" Right.' for t in texts), f"出现孤立段: {texts}"
    closing = next(t for t in texts if "50?" in t)
    assert closing.endswith('50?"'), f"引号对未完整收尾: {closing!r}"
    print(f"[OK] 直引号成对收尾: {texts}")


def case_chinese_quotes():
    """中文弯引号与书名号成对不移动"""
    text = "他问：“今天好吗？”她说：“很好。”"
    words = list("他问今天好吗她说很好")  # CJK 按字对齐
    segs = segment_subtitles(text, _ts_for(words))
    assert segs is not None
    texts = [s["text"] for s in segs]
    assert texts[0] == "他问：“今天好吗？”", repr(texts[0])
    assert texts[1] == "她说：“很好。”", repr(texts[1])
    print(f"[OK] 中文引号: {texts}")

    text2 = "《三体》是一部科幻小说。刘慈欣写了它。"
    words2 = list("三体是一部科幻小说刘慈欣写了它")
    segs2 = segment_subtitles(text2, _ts_for(words2))
    assert segs2 is not None
    assert segs2[0]["text"] == "《三体》是一部科幻小说。", repr(segs2[0]["text"])
    assert len(segs2) == 2
    print("[OK] 书名号成对不拆散")


def case_unclosed_quote_guard():
    """未闭合引号保护：超 300 字符强制归零深度，后续句子恢复正常切分"""
    words = ["He", "said"] + [f"w{i:02d}" for i in range(1, 41)] + [f"x{i:02d}" for i in range(1, 11)]
    # 引号在 "and" 前张开，w 系列一路不闭合（>300 字符触发保护），
    # x 系列每 5 词一句号，归零后按句切分
    text = 'He said, "' + " ".join(words[2:42]) + ". " + \
        " ".join(words[42:47]) + ". " + " ".join(words[47:]) + "."
    ts = _ts_for(words, dur=0.5, gap=0.05)
    segs = segment_subtitles(text, ts)
    assert segs is not None
    total = sum(len(s["words"]) for s in segs)
    assert total == len(words), f"词数不守恒 {total} != {len(words)}"
    x_only = [s for s in segs if s["text"].startswith("x") and "w0" not in s["text"]]
    assert x_only, f"保护未生效，x 系列仍被粘在未闭合引号内: {[s['text'] for s in segs]}"
    assert x_only[-1]["text"].endswith("x10."), repr(x_only[-1]["text"])
    n_segs = len(segs)
    print(f"[OK] 未闭合保护生效：{n_segs} 段，x 系列独立成段")


def case_long_quote_soft_split():
    """超长引语在引语内句边界（soft 候选）拆分，词数守恒，允许拆开引号对"""
    text = '"Blah blah one two three. More words follow here now. Final words close it out."'
    words = ["Blah", "blah", "one", "two", "three", "More", "words", "follow",
             "here", "now", "Final", "words", "close", "it", "out"]
    segs = segment_subtitles(text, _ts_for(words, dur=0.9, gap=0.05), max_duration_s=10.0)
    assert segs is not None
    total = sum(len(s["words"]) for s in segs)
    assert total == len(words), f"词数不守恒 {total} != {len(words)}"
    assert len(segs) >= 2, f"超长引语应被拆分，实际 {len(segs)} 段"
    assert segs[-1]["text"].endswith('out."'), repr(segs[-1]["text"])
    print(f"[OK] 长引语 soft 拆分: {[s['text'] for s in segs]}")


def case_real_cache_quotes():
    """真实缓存 7_32554575 回归：不再出现 `" ` 开头的孤立字幕段"""
    full_text, timestamps, old_segments = load_case(CACHE_QUOTES)
    segs = segment_subtitles(full_text, timestamps, max_duration_s=10.0)
    assert segs is not None, "对齐失败！不应回退"
    orphans = [s["text"] for s in segs if s["text"].startswith('" ')]
    assert not orphans, f"出现孤立引号段: {orphans[:5]}"
    paired = [s["text"] for s in segs if s["text"].endswith('?"')]
    print(f"[OK] 缓存 7 回归: {len(segs)} 段，无孤立引号段，{len(paired)} 段以 ?\" 成对收尾")
    for t in paired[:3]:
        print("   ...", repr(t))


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
    print("引号感知断句用例:")
    case_closed_quote_pair()
    case_straight_quote_not_moved()
    case_chinese_quotes()
    case_unclosed_quote_guard()
    case_long_quote_soft_split()
    case_real_cache_quotes()

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
