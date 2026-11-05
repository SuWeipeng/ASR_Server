"""
语音岛（speech island）检测 — 纯 numpy 实现，无模型依赖，可离线测试

语音岛 = 由静音分隔的连续语音区间。用于退化段时间戳修复：
forced aligner 在含多个句间停顿的长窗口上不稳定（句尾短句时间戳被
压缩/前移到静音里），而在语音岛边界的紧窗口上重对齐结果准确。

典型用法：
    wav, sr = sf.read(path)
    envelope, frame_samples = compute_rms_envelope(wav, sr)
    thr = speech_threshold(envelope)
    islands = detect_speech_islands(envelope, frame_samples / sr, threshold=thr)
"""
from typing import List, Optional, Tuple

import numpy as np

# RMS 帧长（秒）：50ms 足以分辨句间停顿，帧数也不至于过大
FRAME_S = 0.05
# 间隔小于此值的相邻活动帧桥接成同一个岛（句间微停顿不算断开）
BRIDGE_GAP_S = 0.3
# 短于此的岛丢弃（呼吸声、背景噪声毛刺）
MIN_ISLAND_S = 0.15
# 自适应阈值：p20 + 0.10 * (p95 - p20)。用整条音频的百分位，
# 避免局部 p95 把相邻岛粘连
THRESHOLD_P20 = 20
THRESHOLD_P95 = 95
THRESHOLD_K = 0.10


def compute_rms_envelope(wav, sr: int, frame_s: float = FRAME_S) -> Tuple[np.ndarray, int]:
    """
    计算 RMS 包络

    Args:
        wav: mono 波形（float）
        sr: 采样率
        frame_s: 帧长（秒），帧间不重叠

    Returns:
        (envelope, frame_samples)：包络数组与每帧样本数。
        末尾不足一帧的样本被舍弃。
    """
    wav = np.asarray(wav, dtype=np.float64)
    frame = max(1, int(frame_s * sr))
    n_frames = len(wav) // frame
    if n_frames == 0:
        return np.zeros(0, dtype=np.float64), frame
    frames = wav[: n_frames * frame].reshape(n_frames, frame)
    envelope = np.sqrt(np.mean(frames * frames, axis=1))
    return envelope, frame


def speech_threshold(envelope: np.ndarray) -> float:
    """全局自适应语音阈值：p20 + K * (p95 - p20)"""
    if len(envelope) == 0:
        return 0.0
    p20, p95 = np.percentile(envelope, [THRESHOLD_P20, THRESHOLD_P95])
    return float(p20 + THRESHOLD_K * (p95 - p20))


def detect_speech_islands(
    envelope: np.ndarray,
    frame_dur: float,
    threshold: Optional[float] = None,
    bridge_gap_s: float = BRIDGE_GAP_S,
    min_island_s: float = MIN_ISLAND_S,
) -> List[Tuple[float, float]]:
    """
    从 RMS 包络检测语音岛

    Args:
        envelope: compute_rms_envelope 的输出
        frame_dur: 每帧时长（秒）= frame_samples / sr
        threshold: 语音阈值，None 时用 speech_threshold(envelope)
        bridge_gap_s: 相邻活动帧间隔小于此值则桥接
        min_island_s: 短于此的岛丢弃

    Returns:
        [(start_s, end_s), ...] 按时间升序
    """
    if len(envelope) == 0:
        return []
    if threshold is None:
        threshold = speech_threshold(envelope)

    active = envelope > threshold
    idx = np.flatnonzero(active)
    if len(idx) == 0:
        return []

    # 连续活动帧的 run 列表 [(fi, fj_exclusive), ...]
    splits = np.where(np.diff(idx) > 1)[0]
    starts = np.concatenate([[idx[0]], idx[splits + 1]])
    ends = np.concatenate([idx[splits] + 1, [idx[-1] + 1]])

    # 桥接小间隙
    merged: List[Tuple[int, int]] = []
    cur_s, cur_e = int(starts[0]), int(ends[0])
    for s, e in zip(starts[1:], ends[1:]):
        if (s - cur_e) * frame_dur < bridge_gap_s:
            cur_e = int(e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = int(s), int(e)
    merged.append((cur_s, cur_e))

    # 帧号 → 秒，丢弃过短岛
    return [
        (s * frame_dur, e * frame_dur)
        for s, e in merged
        if (e - s) * frame_dur >= min_island_s
    ]


def speech_ratio(
    envelope: np.ndarray,
    frame_dur: float,
    threshold: float,
    t_start: float,
    t_end: float,
) -> float:
    """[t_start, t_end] 区间内超过阈值的帧占比；区间无效返回 0.0"""
    if len(envelope) == 0 or t_end <= t_start:
        return 0.0
    i0 = max(0, int(t_start / frame_dur))
    i1 = min(len(envelope), max(i0 + 1, int(np.ceil(t_end / frame_dur))))
    seg = envelope[i0:i1]
    if len(seg) == 0:
        return 0.0
    return float(np.mean(seg > threshold))


def is_silence(
    envelope: np.ndarray,
    frame_dur: float,
    threshold: float,
    t_start: float,
    t_end: float,
    max_ratio: float = 0.25,
) -> bool:
    """区间基本无语音（语音帧占比低于 max_ratio）时返回 True"""
    return speech_ratio(envelope, frame_dur, threshold, t_start, t_end) < max_ratio


def snap_start_forward(
    islands: List[Tuple[float, float]],
    t: float,
    max_snap: float = 0.7,
    lead_pad: float = 0.10,
) -> Optional[float]:
    """
    在 t 前方 max_snap 秒内找最近的语音岛起点，返回 岛start - lead_pad
    作为新的段起点（略微提前留出起音）。若吸附不产生前移或无岛可吸附，
    返回 None（保持原起点）。
    """
    best: Optional[float] = None
    for s, _e in islands:
        if s < t:
            continue
        if s - t > max_snap:
            break
        cand = s - lead_pad
        if cand > t:  # 必须产生前移
            if best is None or cand < best:
                best = cand
    return best


def split_islands(
    islands: List[Tuple[float, float]],
    envelope: np.ndarray,
    frame_dur: float,
    max_unit_s: float = 10.0,
    search_s: float = 1.5,
) -> List[Tuple[float, float]]:
    """
    把宽岛切成 ≤ max_unit_s 的虚拟 utterance 单元，作为词分配的粒度

    切点取目标位置附近 search_s 窗口内 RMS 最低的帧（近似句间停顿），
    避免把句子拦腰切开。短岛原样保留，输出按时间升序。
    """
    units: List[Tuple[float, float]] = []
    for s, e in islands:
        width = e - s
        if width <= max_unit_s:
            units.append((s, e))
            continue
        n_parts = int(np.ceil(width / max_unit_s))
        cuts = [s]
        for p in range(1, n_parts):
            target = s + width * p / n_parts
            lo = max(s, target - search_s)
            hi = min(e, target + search_s)
            i0 = max(0, int(lo / frame_dur))
            i1 = min(len(envelope), max(i0 + 1, int(np.ceil(hi / frame_dur))))
            seg_env = envelope[i0:i1]
            if len(seg_env) == 0:
                cuts.append(target)
                continue
            valley = int(np.argmin(seg_env))
            cuts.append(max(s + 0.1, min(e - 0.1, (i0 + valley) * frame_dur)))
        cuts.append(e)
        units.extend((a, b) for a, b in zip(cuts, cuts[1:]) if b - a > 0.05)
    return units
