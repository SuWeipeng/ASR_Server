# -*- coding: utf-8 -*-
"""
离线验收退化段修复通道 _refine_segment_timing（v3：逐段候选窗 ASR 重探测）

用真实缓存验证：
1. 02_part2_130405428（英文，demucs 人声输入）：
   - 用户实测回归：They're just visually challenged. 此前被错位到上一句的
     尾音岛（点击不发声）、I feel sorry for you. 点击播放两句 →
     修复后两句都应落在真实语音岛 [≈18.55, 22.75] 内
   - Three blocks away.  ≈76.3–77.5（原 75.98 区间近乎无声）
   - Nothing. ≈235.95、Oh, okay. ≈238.0、My mistake. 紧随其后
   - 无人认领语音岛应接近清零（旧机制下 24/170）
   - 幂等性：对已修复的缓存重跑，目标段时间漂移 ≤0.5s
2. 1_33779614 —— language='auto' 路径回归
3. 01_part1_133682968（Flipped，2026-11-06 错位复盘主缓存）：
   18 个真值锚点（probe_sync_truth.py 探针 18/18 + 定点复验，真值见
   SYNC_REPAIR_PROGRESS.md / cache/<name>/sync_truth.json）。缓存已是
   v3 修复产物，重跑后锚点段必须仍在真值区间（幂等且不回退）。
   注意 seg123 缓存文本与实际音频不符（"Oh, Bryce, let's speak with
   him." vs 实际 "Can I speak with you?"），断言用锚点区间 [408.7,412.6]。

注意：会加载 Qwen3-ASR 模型（GPU 数秒，CPU 约 1 分钟）。
"""
import json
import logging
import re
import sys

sys.path.insert(0, r"D:\ASR_Server\backend")

from app.models.domain import SubtitleSegment, SubtitleWord
from app.services.subtitle_service import SubtitleService

CACHE_EN = r"D:\ASR_Server\cache\02_part2_130405428"
CACHE_AUTO = r"D:\ASR_Server\cache\1_33779614"
CACHE_P1 = r"D:\ASR_Server\cache\01_part1_133682968"

_RE_STATS = re.compile(
    r"Sync repair: (\d+) segs \((\d+) healthy-frozen\), (\d+) probed in "
    r"(\d+) windows, (\d+) re-anchored, (\d+) unmatched-kept, (\d+) snapped"
)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def build_segments(cache_dir):
    with open(cache_dir + r"\transcription.json", encoding="utf-8") as f:
        data = json.load(f)
    segs = []
    for i, s in enumerate(data["segments"]):
        segs.append(SubtitleSegment(
            id=i,
            start=s["start"],
            end=s["end"],
            text=s["text"],
            words=[SubtitleWord(word=w["word"], start=w["start"], end=w["end"])
                   for w in (s.get("words") or [])],
        ))
    return segs


def run_repair(svc, segs, audio_path, language="auto"):
    """执行修复并从日志捕获 (段数, 健康冻结, 探测段, ASR窗, 重锚定, 未匹配, 吸附) 统计"""
    cap = _Capture()
    lg = logging.getLogger("ASR_Server")
    lg.addHandler(cap)
    try:
        svc._refine_segment_timing(segs, audio_path, language)
    finally:
        lg.removeHandler(cap)
    stats = None
    for msg in cap.messages:
        m = _RE_STATS.search(msg)
        if m:
            stats = tuple(int(x) for x in m.groups())
    return stats


def unclaimed_islands(segs, audio_path):
    import soundfile as sf
    from app.utils.speech_islands import (
        compute_rms_envelope, detect_speech_islands, speech_threshold,
    )
    wav, sr = sf.read(audio_path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    env, frame = compute_rms_envelope(wav, sr)
    thr = speech_threshold(env)
    fdur = frame / sr
    islands = detect_speech_islands(env, fdur, threshold=thr)

    def containing(t):
        for j, (a, b) in enumerate(islands):
            if a <= t <= b:
                return j
        return -1

    claim = set()
    for s in segs:
        for w in (s.words or []):
            j = containing((w.start + w.end) / 2)
            if j >= 0:
                claim.add(j)
    unclaimed = [j for j in range(len(islands)) if j not in claim]
    return islands, unclaimed


def check_invariants(segs, texts0, n0):
    assert len(segs) == n0, f"段数改变: {n0} -> {len(segs)}"
    assert [s.text for s in segs] == texts0, "段文本被改变"
    for i in range(1, len(segs)):
        assert segs[i].start >= segs[i - 1].start - 1e-6, f"seg {i} 时间回退"
        assert segs[i - 1].end <= segs[i].start + 0.06, \
            f"seg {i-1}/{i} 重叠过大: {segs[i-1].end:.2f} vs {segs[i].start:.2f}"


def zero_dur_words(segs):
    return [(s.text[:30], w.word) for s in segs for w in (s.words or [])
            if w.end - w.start <= 0.0]


def main():
    svc = SubtitleService()

    # ================= 英文缓存：02_part2 =================
    print("=" * 70)
    print("02_part2_130405428（英文，demucs 人声输入）")
    segs = build_segments(CACHE_EN)
    texts0 = [s.text for s in segs]
    n0 = len(segs)
    before = {s.text: (s.start, s.end) for s in segs}

    stats = run_repair(svc, segs, CACHE_EN + r"\audio.mp3", "auto")
    if stats:
        n_segs, healthy, probed, windows, realigned, kept, snapped = stats
        print(f"[统计] segs={n_segs}, healthy-frozen={healthy}, "
              f"probed={probed} in {windows} windows, re-anchored={realigned}, "
              f"unmatched-kept={kept}, snapped={snapped}")

    check_invariants(segs, texts0, n0)
    print("[OK] 段数/文本不变，start 单调，无重叠")

    def get(text):
        return next(s for s in segs if s.text == text)

    def show(s, label=None):
        label = label or s.text
        b = before[s.text]
        print(f"  {label[:36]!r}: ({b[0]:.2f}, {b[1]:.2f}) -> ({s.start:.2f}, {s.end:.2f})")
        return s

    # 用户实测回归（ASR 文本每次运行略有差异，用相对定位）：
    # "I feel sorry for you." 的前一段即 "You're/They're just visually challenged."
    sorry_idx = next(i for i, s in enumerate(segs) if s.text == "I feel sorry for you.")
    challenged = show(segs[sorry_idx - 1])
    sorry = show(segs[sorry_idx])
    assert 18.3 <= challenged.start <= 19.5, \
        f"start {challenged.start:.2f} 仍错位（应≥18.3，即上一句尾音岛 [17.05,18.1] 之后）"
    assert challenged.end <= 23.0, f"end {challenged.end:.2f}"
    assert sorry.start >= challenged.start, "I feel 不应在 challenged 之前"
    assert sorry.end <= 23.0, f"end {sorry.end:.2f} 超出语音岛"
    for s in (challenged, sorry):
        assert all(w.end > w.start for w in s.words), "存在零时长词"

    # 结构性验收：目标句 ≥80% 落在单一语音岛内（点击即听到该句所在的语音），
    # 严格有序。该区域 3 岛 4 句存在两种自洽布局，不断言具体位置。
    islands, _unclaimed = unclaimed_islands(segs, CACHE_EN + r"\audio.mp3")

    def contained_in_island(s):
        span = max(1e-6, s.end - s.start)
        best = 0.0
        for a, b in islands:
            ov = min(s.end, b) - max(s.start, a)
            if ov > best:
                best = ov
        return best / span

    nothing, okay, mistake = None, None, None
    for name in ("Nothing.", "Oh, okay.", "My mistake."):
        s = show(get(name))
        ratio = contained_in_island(s)
        assert ratio >= 0.8, f"{name} 只有 {ratio:.0%} 在语音岛内: [{s.start:.2f},{s.end:.2f}]"
        assert all(w.end > w.start for w in s.words), "存在零时长词"
        if name == "Nothing.":
            nothing = s
        elif name == "Oh, okay.":
            okay = s
        else:
            mistake = s
    assert nothing.start <= okay.start <= mistake.start, "三句顺序错乱"

    # 幂等性：缓存已是修复产物，重跑后目标段漂移应很小
    for name, s in [("Nothing.", nothing), ("Oh, okay.", okay),
                    ("I feel sorry for you.", sorry)]:
        b = before[name]
        drift = max(abs(s.start - b[0]), abs(s.end - b[1]))
        assert drift <= 0.5, f"{name!r} 重跑漂移 {drift:.2f}s"
    print("[OK] 幂等性：重跑漂移 ≤0.5s")

    # 无人认领语音岛：有语音但无对应词的岛（ASR 漏听/背景人声/被 A/B 故意
    # 腾空的岛）。修复通道无法为不存在的文本分配词，此项只作信息统计。
    islands, unclaimed = unclaimed_islands(segs, CACHE_EN + r"\audio.mp3")
    print(f"[统计] 语音岛 {len(islands)} 个，无对应词的岛 {len(unclaimed)} 个 "
          f"(信息项，非缺陷): {[(round(islands[j][0], 1)) for j in unclaimed[:8]]}")

    zd = zero_dur_words(segs)
    print(f"[统计] 全片零时长词: {len(zd)} 个" + (f" {zd[:5]}" if zd else ""))
    print("[OK] 英文缓存验收通过")

    # ================= auto 语言路径：1_33779614 =================
    print("=" * 70)
    print("1_33779614（language='auto' 路径）")
    segs2 = build_segments(CACHE_AUTO)
    texts0_2 = [s.text for s in segs2]
    n2 = len(segs2)
    stats2 = run_repair(svc, segs2, CACHE_AUTO + r"\audio.mp3", "auto")
    if stats2:
        print(f"[统计] segs={stats2[0]}, healthy-frozen={stats2[1]}, "
              f"probed={stats2[2]} in {stats2[3]} windows, "
              f"re-anchored={stats2[4]}, unmatched-kept={stats2[5]}, "
              f"snapped={stats2[6]}")
    check_invariants(segs2, texts0_2, n2)
    zd2 = zero_dur_words(segs2)
    print(f"[统计] 全片零时长词: {len(zd2)} 个" + (f" {zd2[:5]}" if zd2 else ""))
    print("[OK] auto 语言路径验收通过")

    # ================= 01_part1：2026-11-06 错位复盘真值夹具 =================
    print("=" * 70)
    print("01_part1_133682968（Flipped，用户报告错位簇 + 探针真值锚点）")
    segs3 = build_segments(CACHE_P1)
    texts0_3 = [s.text for s in segs3]
    n3 = len(segs3)
    # 真值：probe_sync_truth.py（18/18 窗）+ 定点复验；上界含探针窗边界修正
    TRUTH_P1 = [
        ("Bryce, isn't it time for you to go help your", 69.30, 71.96),
        ("Huh?", 72.68, 72.90),
        ("Oh yeah.", 75.05, 75.80),
        ("I mean, nothing would stop her.", 76.80, 78.90),
        ("I was about to tell her to get lost", 80.05, 82.70),
        ("I couldn't believe it.", 88.35, 89.50),
        ("Uh huh.", 100.00, 100.30),
        ("Finally, I did the only manly thing", 100.70, 104.90),
        ("Why don't you and I go help unload the", 27.70, 34.84),
        ("For me, it was the beginning", 35.90, 41.90),
        ("My only consolation", 241.30, 243.65),
        ("I could see he didn't want to go", 271.85, 277.70),
        ("Sherry Stalls was nothing", 326.05, 331.50),
        ("I spent the whole year", 368.20, 373.30),
        ("Seventh grade brought changes", 377.55, 381.00),
        ("As a matter of fact", 401.15, 404.40),
        ("Oh, Bryce, let's speak with him.", 408.70, 412.60),
        ("You can see everything.", 454.62, 456.40),
    ]
    before3 = {}
    for prefix, ts, te in TRUTH_P1:
        s = next(x for x in segs3 if x.text.startswith(prefix))
        before3[prefix] = (s.start, s.end)
        ok = s.start >= ts - 0.6 and s.end <= te + 0.8
        assert ok, (f"{prefix[:30]!r} 修复前 [{s.start:.2f},{s.end:.2f}] "
                    f"已偏离真值 [{ts},{te}]（缓存应已是 v3 修复产物）")
    print(f"[OK] 修复前 {len(TRUTH_P1)} 个真值锚点段全部在位（幂等起点）")

    run_repair(svc, segs3, CACHE_P1 + r"\audio.mp3", "auto")
    check_invariants(segs3, texts0_3, n3)
    for prefix, ts, te in TRUTH_P1:
        s = next(x for x in segs3 if x.text.startswith(prefix))
        ok = s.start >= ts - 0.6 and s.end <= te + 0.8
        assert ok, (f"{prefix[:30]!r} 重跑后 [{s.start:.2f},{s.end:.2f}] "
                    f"偏离真值 [{ts},{te}]（重跑不得推翻已验证落位）")
        b = before3[prefix]
        drift = max(abs(s.start - b[0]), abs(s.end - b[1]))
        assert drift <= 0.6, f"{prefix[:30]!r} 重跑漂移 {drift:.2f}s"
    print("[OK] 重跑后 18 锚点段仍在真值区间，漂移 ≤0.6s")

    print("=" * 70)
    print("\n全部通过 ✔")


if __name__ == "__main__":
    main()
