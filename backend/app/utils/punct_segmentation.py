"""
基于标点的语意断句（subtitle semantic segmentation）

Qwen3-ASR 输出带完整标点的 full_text，而 ForcedAligner 返回的词级 timestamps
不含标点。此前字幕段直接沿用 VAD 段边界，导致语速快时断在句子中间。

本模块把 full_text 中的标点按顺序挂回对齐 token，然后按句末标点切分字幕段，
完全无视 VAD 段边界 —— 跨 VAD 块的半句话会自然合并为同一段字幕。
超长句在子句标点（逗号等）或最大词间隙处递归二次切分。

若 full_text 与 timestamps 无法顺序对齐（desync），返回 None，
由调用方回退到原有的 VAD 分组 / 固定时长分组逻辑。

渲染文本直接从 full_text 切片得到，保证与 ASR 原文格式（混排空格、
引号方向等）完全一致。
"""
from typing import Dict, List, Optional, Tuple

# 句末标点：在此处切分字幕段
_TERMINAL_PUNCT = set("。！？!?；;….")
# 子句标点：仅用于切分超长句
_CLAUSE_PUNCT = set("，,、：:")
# 前引号/前括号：跨段边界时移到下一段开头
_OPENING_PUNCT = set("《〈（(【〔『「“‘\"'")

# CJK 码点区间（用于识别中文之间的多余空白）：
# 0x4E00-0x9FFF  CJK 统一表意文字
# 0x3400-0x4DBF  CJK 扩展 A 区
# 0x3000-0x303F  CJK 符号和标点
# 0xFF00-0xFFEF  全角 ASCII 及全角标点
_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
)


def _is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _strip_cjk_inner_spaces(text: str) -> str:
    """去除相邻 CJK 字符之间的空白（多由 ASR 分块拼接引入的空格）"""
    out: List[str] = []
    for i, ch in enumerate(text):
        if ch.isspace() and out and _is_cjk_char(out[-1]):
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and _is_cjk_char(text[j]):
                continue  # 两侧都是 CJK，丢弃该空白
        out.append(ch)
    return "".join(out)


def attach_punctuation(
    full_text: str,
    timestamps: List[Tuple[float, float, str]]
) -> Optional[List[Dict]]:
    """
    将 full_text 中的标点按顺序挂回对齐 token

    Args:
        full_text: ASR 输出的带标点完整文本
        timestamps: 词级时间戳列表 [(start, end, word), ...]（不含标点）

    Returns:
        token 列表，每项含:
        - word/start/end: token 文本与音频时间
        - punct: 该 token 之后、下一 token 之前的标点串（已去空白）
        - word_start/word_end: token 首字符/尾字符在 full_text 中的索引
        - punct_end: 标点串末尾在 full_text 中的索引（无标点时等于 word_end）
        - lead_start: 段渲染起始索引（含移入的前引号时小于 word_start）
        对齐失败（字符不匹配/剩余未消费的正文）返回 None
    """
    if not full_text or not timestamps:
        return None

    items: List[Dict] = []
    n = len(full_text)
    pos = 0  # 当前 full_text 指针

    def skip_ws(p: int) -> int:
        while p < n and full_text[p].isspace():
            p += 1
        return p

    for ts_start, ts_end, raw_word in timestamps:
        word = raw_word.strip()
        if not word:
            continue
        # 对齐器会把 token 内部的连字符/撇号等去掉（如 real-life → reallife），
        # 因此按"仅字母数字"的压缩形式逐字符对齐
        condensed = [c for c in word if c.isalnum()]
        if not condensed:
            continue

        # 收集上一 token 与当前 token 之间的标点（归入上一 token）
        ws = skip_ws(pos)
        p = ws
        while p < n and not full_text[p].isalnum():
            p += 1
        if p > ws:
            if not items:
                # 正文以标点开头（如前引号），归入首个 token 之前
                items.append({
                    "word": "", "start": ts_start, "end": ts_end,
                    "punct": "", "word_start": ws, "word_end": ws,
                    "punct_end": ws, "lead_start": 0,
                })
            run = full_text[ws:p]
            items[-1]["punct"] += "".join(run.split())
            items[-1]["punct_end"] = ws + len(run.rstrip())

        # 压缩匹配：跳过正文中的空白与 token 内被删除的标点；大小写不敏感
        matched = True
        word_start = None
        word_end = None
        for tch in condensed:
            while p < n and not full_text[p].isalnum():
                p += 1
            if p >= n or full_text[p].casefold() != tch.casefold():
                matched = False
                break
            if word_start is None:
                word_start = p
            word_end = p + 1
            p += 1
        if not matched:
            return None

        items.append({
            "word": word,
            "start": ts_start,
            "end": ts_end,
            "punct": "",
            "word_start": word_start,
            "word_end": word_end,
            "punct_end": word_end,
        })
        pos = word_end

    # 剩余部分必须只是标点/空白，否则视为 desync
    pos = skip_ws(pos)
    if any(full_text[i].isalnum() for i in range(pos, n)):
        return None
    if n > pos and items:
        run = full_text[pos:n]
        items[-1]["punct"] += "".join(run.split())
        items[-1]["punct_end"] = pos + len(run.rstrip())

    # 全程未匹配到任何 token
    if not items:
        return None

    return items


def _has_terminal(punct: str) -> bool:
    return any(ch in _TERMINAL_PUNCT for ch in punct)


def _has_clause(punct: str) -> bool:
    return any(ch in _CLAUSE_PUNCT for ch in punct)


def _split_long_group(group: List[Dict], max_duration_s: float) -> List[List[Dict]]:
    """递归切分超长句：优先在靠近中点的子句标点处，否则在最大词间隙处"""
    duration = group[-1]["end"] - group[0]["start"]
    if duration <= max_duration_s or len(group) < 2:
        return [group]

    # 候选切点：子句标点处，取使两段最均衡的一个
    candidates = [i for i in range(len(group) - 1) if _has_clause(group[i]["punct"])]
    if candidates:
        start_t = group[0]["start"]
        best = min(
            candidates,
            key=lambda i: abs((group[i]["end"] - start_t) - duration / 2)
        )
        left = group[:best + 1]
        right = group[best + 1:]
        if (left[-1]["end"] - left[0]["start"]) >= 0.5 and \
           (right[-1]["end"] - right[0]["start"]) >= 0.5:
            return _split_long_group(left, max_duration_s) + \
                   _split_long_group(right, max_duration_s)

    # 兜底：在靠近中点的最大词间隙处切开
    mid = (len(group) - 1) / 2
    best_i = max(
        range(len(group) - 1),
        key=lambda i: (group[i + 1]["start"] - group[i]["end"]) - 0.05 * abs(i - mid)
    )
    left = group[:best_i + 1]
    right = group[best_i + 1:]
    if not left or not right:
        return [group]
    return _split_long_group(left, max_duration_s) + \
           _split_long_group(right, max_duration_s)


def group_by_punctuation(
    items: List[Dict],
    max_duration_s: float = 10.0
) -> List[List[Dict]]:
    """
    按句末标点把 token 分组成字幕段，超长句递归二次切分；
    并把句末前引号/前括号移到下一段开头
    """
    # 1) 句末标点切段
    groups: List[List[Dict]] = []
    current: List[Dict] = []
    for idx, item in enumerate(items):
        current.append(item)
        if _has_terminal(item["punct"]) or idx == len(items) - 1:
            groups.append(current)
            current = []

    # 2) 超长句二次切分
    result: List[List[Dict]] = []
    for group in groups:
        result.extend(_split_long_group(group, max_duration_s))

    # 3) 段末前引号/前括号移到下一段（调整切片索引）
    for a, b in zip(result, result[1:]):
        last = a[-1]
        moved = ""
        while last["punct"] and last["punct"][-1] in _OPENING_PUNCT:
            moved = last["punct"][-1] + moved
            last["punct"] = last["punct"][:-1]
        if moved:
            # 前引号在正文中紧邻标点串末尾，切片索引回退相应字符数
            last["punct_end"] -= len(moved)
            b[0]["lead_start"] = last["punct_end"]

    return result


def render_segment_text(full_text: str, group: List[Dict]) -> str:
    """从 full_text 切片渲染段文本（保留 ASR 原文格式），并去掉中文间空格"""
    start = group[0].get("lead_start", group[0]["word_start"])
    end = group[-1]["punct_end"]
    text = _strip_cjk_inner_spaces(full_text[start:end])
    return text.replace("\n", " ").strip()


def segment_subtitles(
    full_text: str,
    timestamps: List[Tuple[float, float, str]],
    max_duration_s: float = 10.0
) -> Optional[List[Dict]]:
    """
    语意断句主入口：标点挂回 + 按句切分 + 渲染

    Args:
        full_text: ASR 带标点完整文本
        timestamps: 词级时间戳 [(start, end, word), ...]
        max_duration_s: 单段最大时长，超长句会被二次切分

    Returns:
        [{"start", "end", "text", "words": [{"word","start","end"}]}, ...]
        对齐失败返回 None（调用方回退旧逻辑）
    """
    items = attach_punctuation(full_text, timestamps)
    if items is None:
        return None

    groups = group_by_punctuation(items, max_duration_s)

    segments = []
    for group in groups:
        seg_words = [w for w in group if w["word"]]
        if not seg_words:
            continue
        segments.append({
            "start": seg_words[0]["start"],
            "end": seg_words[-1]["end"],
            "text": render_segment_text(full_text, group),
            "words": [
                {"word": w["word"], "start": w["start"], "end": w["end"]}
                for w in seg_words
            ],
        })

    return segments or None
