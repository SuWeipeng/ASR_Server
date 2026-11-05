"""
Subtitle generation and processing service
"""
import time
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.services.asr_service import asr_service
from app.services.alignment_service import alignment_service
from app.services.media_service import media_service
from app.services.cache_service import cache_service
from app.config import settings
from app.core.demucs_config import get_demucs_config
from app.utils import logger, extract_audio_segment, check_demucs_available
from app.utils.punct_segmentation import segment_subtitles
from app.models.domain import SubtitleSegment, SubtitleWord, TranscriptionResult


class SubtitleService:
    """Service for subtitle generation and processing"""

    def generate_subtitles(
        self,
        file_id: str,
        language: Optional[str] = None,  # 默认 None，让 ASR 自动检测语言
        use_alignment: bool = True,
        use_vad: bool = True,
        force_refresh: bool = False  # 强制刷新，跳过缓存
    ) -> Optional[TranscriptionResult]:
        """
        Generate subtitles from media file

        Args:
            file_id: Media file ID
            language: Language code
            use_alignment: Whether to use forced aligner for timestamps
            use_vad: Whether to use VAD for long audio processing

        Returns:
            TranscriptionResult or None if failed
        """
        start_time = time.time()

        logger.info(f"Generating subtitles for file: {file_id}")

        try:
            # Get media file for filename and size
            media_file = media_service.get_file(file_id)
            if not media_file:
                logger.error(f"Media file not found: {file_id}")
                return None

            # Extract filename (without extension) and file size for cache key
            filename = Path(media_file.original_filename).stem
            file_size = media_file.file_size

            # Check cache first (skip if force_refresh is True)
            if not force_refresh and cache_service.is_cached(filename, file_size):
                logger.info(f"Cache hit for {filename}_{file_size}, loading from cache")
                cached_result = cache_service.load_transcription(filename, file_size)
                if cached_result:
                    cache_service.link_file_id(filename, file_size, file_id)
                    return cached_result
                else:
                    logger.warning("Cache marked as present but failed to load, will regenerate")
            elif force_refresh and cache_service.is_cached(filename, file_size):
                logger.info(f"Force refresh requested, deleting old cache for {filename}_{file_size}")
                # 删除旧缓存目录
                import shutil
                cache_dir = cache_service._get_cache_dir(filename, file_size)
                if cache_dir.exists():
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    logger.info(f"Deleted cache directory: {cache_dir}")
            # Extract audio from media
            audio_path = media_service.extract_audio_from_media(file_id)
            if not audio_path:
                logger.error("Failed to extract audio")
                return None

            # Get media file for duration
            media_file = media_service.get_file(file_id)
            if not media_file:
                logger.error(f"Media file not found: {file_id}")
                return None

            # demucs 人声分离：勾选后用分离出的人声作为 ASR 输入，失败自动回退原声
            asr_audio_path = audio_path
            used_demucs = False
            demucs_cfg = get_demucs_config().get_config()
            if demucs_cfg.enabled:
                if check_demucs_available():
                    logger.info(f"Applying demucs vocal separation: model={demucs_cfg.model_name}")
                    vocals_path = media_service.separate_vocals_from_media(
                        file_id,
                        demucs_cfg.model_name,
                        demucs_cfg.repo_path,
                        duration=media_file.duration
                    )
                    if vocals_path:
                        asr_audio_path = vocals_path
                        used_demucs = True
                    else:
                        logger.warning("Demucs separation failed, falling back to original audio")
                else:
                    logger.warning("Demucs enabled but not available, falling back to original audio")

            # Determine if VAD should be used for long audio
            audio_duration = media_file.duration or 0.0
            should_use_vad = (
                use_vad and
                settings.VAD_ENABLED and
                audio_duration > settings.VAD_THRESHOLD_DURATION
            )

            if should_use_vad:
                logger.info(f"Long audio detected ({audio_duration:.2f}s), using VAD splitting")
                # Use long audio transcription with VAD
                transcription_result = asr_service.transcribe_long_audio(
                    audio_path=asr_audio_path,
                    language=language,
                    generate_timestamps=True,
                    use_vad=True
                )
            else:
                # Use standard transcription for shorter files
                transcription_result = asr_service.transcribe_file(
                    audio_path=asr_audio_path,
                    language=language,
                    generate_timestamps=True
                )

            if not transcription_result:
                logger.error("Transcription failed")
                return None

            # Extract text
            full_text = transcription_result.get("text", "")

            # Generate subtitle segments
            segments = self._create_subtitle_segments(
                transcription_result,
                media_file.duration or 0.0
            )

            # 退化段时间戳修复：补偿 aligner 在长窗口上的漂移/钉死
            # （VAD/非 VAD 两条路径统一作用，仅改写被判定退化的段）
            if use_alignment and settings.SUBTITLE_SYNC_REPAIR and segments:
                self._refine_segment_timing(segments, asr_audio_path, language)

            processing_time = time.time() - start_time

            result = TranscriptionResult(
                file_id=file_id,
                language=language,
                segments=segments,
                full_text=full_text,
                duration=media_file.duration or 0.0,
                processing_time=processing_time
            )

            # Add metadata about demucs/VAD usage
            metadata = {}
            if used_demucs:
                metadata["used_demucs"] = True
                metadata["demucs_model"] = demucs_cfg.model_name
            if should_use_vad:
                metadata["vad_enabled"] = True
                metadata["num_segments"] = transcription_result.get("num_segments", 0)
            result.metadata = metadata or None

            # Save to cache
            logger.info(f"Saving to cache: {filename}_{file_size}")
            cache_service.save_transcription(filename, file_size, result, asr_audio_path)
            cache_service.generate_subtitle_files(filename, file_size, segments)
            cache_service.link_file_id(filename, file_size, file_id)

            logger.info(f"Subtitle generation completed: {len(segments)} segments")
            return result

        except Exception as e:
            logger.error(f"Subtitle generation failed: {e}")
            return None

    def _create_subtitle_segments(
        self,
        transcription_result: Dict[str, Any],
        total_duration: float
    ) -> List[SubtitleSegment]:
        """
        Create subtitle segments from transcription result

        Args:
            transcription_result: Raw transcription from ASR
            total_duration: Total audio duration

        Returns:
            List of SubtitleSegment
        """
        segments = []
        segment_id = 0

        # Check if we have VAD segment information
        vad_segments = transcription_result.get("vad_segments")

        if "timestamps" in transcription_result:
            # 优先：基于标点的语意断句（无视 VAD 段边界，跨块半句自动合并）
            timestamps = transcription_result.get("timestamps") or []
            if timestamps:
                semantic_segments = segment_subtitles(
                    transcription_result.get("text", ""),
                    timestamps,
                    max_duration_s=settings.SUBTITLE_MAX_SEGMENT_DURATION
                )
                if semantic_segments:
                    logger.info(
                        f"Semantic segmentation by punctuation: "
                        f"{len(semantic_segments)} segments"
                    )
                    for seg in semantic_segments:
                        segments.append(SubtitleSegment(
                            id=segment_id,
                            start=seg["start"],
                            end=seg["end"],
                            text=seg["text"],
                            words=[
                                SubtitleWord(
                                    word=w["word"],
                                    start=w["start"],
                                    end=w["end"]
                                )
                                for w in seg["words"]
                            ]
                        ))
                        segment_id += 1
                    logger.info(f"Created {len(segments)} subtitle segments")
                    return segments

                # 对齐失败，回退到旧的分组逻辑
                logger.warning(
                    "Punctuation alignment failed, "
                    "falling back to legacy segmentation"
                )

            if vad_segments:
                # Use VAD segments to group words
                logger.info(f"Using {len(vad_segments)} VAD segments for subtitle generation")

                timestamps = transcription_result["timestamps"]
                logger.info(f"[SUBTITLE] Total timestamps from ASR: {len(timestamps)}")
                word_index = 0

                for vad_seg in vad_segments:
                    seg_start = vad_seg["start"]
                    seg_end = vad_seg["end"]

                    # Collect words that fall within this VAD segment
                    seg_words = []
                    while word_index < len(timestamps):
                        word_start, word_end, word_text = timestamps[word_index]

                        # Check if word belongs to this segment
                        # Allow some tolerance (overlap handling)
                        if word_start < seg_end + 0.5:
                            seg_words.append(SubtitleWord(word=word_text, start=word_start, end=word_end))
                            word_index += 1
                        else:
                            break

                    if seg_words:
                        # Create subtitle segment from VAD segment words
                        segment_text = " ".join([w.word for w in seg_words])
                        logger.info(f"[SUBTITLE] Created segment {segment_id}: '{segment_text[:50]}...' ({len(seg_words)} words)")
                        segments.append(SubtitleSegment(
                            id=segment_id,
                            start=seg_words[0].start,
                            end=seg_words[-1].end,
                            text=segment_text,
                            words=seg_words
                        ))
                        segment_id += 1

                logger.info(f"[SUBTITLE] After VAD loop: word_index={word_index}, total timestamps={len(timestamps)}")

                # Handle any remaining words
                while word_index < len(timestamps):
                    word_start, word_end, word_text = timestamps[word_index]
                    seg_words = [SubtitleWord(word=word_text, start=word_start, end=word_end)]
                    word_index += 1

                    # Collect consecutive remaining words
                    while word_index < len(timestamps):
                        w_start, w_end, w_text = timestamps[word_index]
                        if w_end - seg_words[0].start <= 10.0:  # Max 10s for leftover
                            seg_words.append(SubtitleWord(word=w_text, start=w_start, end=w_end))
                            word_index += 1
                        else:
                            break

                    if seg_words:
                        segment_text = " ".join([w.word for w in seg_words])
                        segments.append(SubtitleSegment(
                            id=segment_id,
                            start=seg_words[0].start,
                            end=seg_words[-1].end,
                            text=segment_text,
                            words=seg_words
                        ))
                        segment_id += 1

            else:
                # No VAD segments, group words into sentences/phrases with fixed duration
                logger.info("No VAD segments, using fixed duration grouping (10s max)")
                current_words = []
                sentence_start = None
                max_segment_duration = 10.0  # Max 10 seconds per segment
                min_segment_duration = 2.0   # Min 2 seconds per segment

                for start, end, word in transcription_result["timestamps"]:
                    word_obj = SubtitleWord(word=word, start=start, end=end)

                    if sentence_start is None:
                        sentence_start = start

                    current_words.append(word_obj)
                    current_duration = end - sentence_start

                    # Create segment when conditions are met
                    if (current_duration >= max_segment_duration or
                        word.endswith(('.', '?', '!', ',')) and
                        current_duration >= min_segment_duration):

                        # Create segment
                        segment_text = " ".join([w.word for w in current_words])
                        segments.append(SubtitleSegment(
                            id=segment_id,
                            start=sentence_start,
                            end=end,
                            text=segment_text,
                            words=current_words.copy()
                        ))

                        # Reset
                        current_words = []
                        sentence_start = None
                        segment_id += 1

                # Add remaining words as final segment
                if current_words:
                    segment_text = " ".join([w.word for w in current_words])
                    segments.append(SubtitleSegment(
                        id=segment_id,
                        start=current_words[0].start,
                        end=current_words[-1].end,
                        text=segment_text,
                        words=current_words
                    ))

        else:
            # Fallback: create single segment with full text
            segments.append(SubtitleSegment(
                id=0,
                start=0.0,
                end=total_duration,
                text=transcription_result.get("text", ""),
                words=None
            ))

        logger.info(f"Created {len(segments)} subtitle segments")
        return segments

    def _refine_segment_timing(
        self,
        segments: List[SubtitleSegment],
        audio_path: str,
        language: Optional[str]
    ):
        """
        字幕-语音全局再对齐：词 → 语音岛（utterance 单元）的全局 DP 分配
        + 逐单元紧窗重对齐。

        背景：ASR 内部对齐会把文本系统性向块首压缩（实测 14% 语音岛无人认领、
        多段文本挤进早期岛），且错位是全局序列问题——词与错误岛的时间可以
        完美吻合，局部启发式（退化判据/岛归属游标）无法发现。因此对全量词做
        "预算（单元宽×自校准语速）+ 顺序约束" 的全局最优分配，再在每个单元的
        紧窗口内用 aligner 精化；验收失败的单元按字符数加权插值
        （单元即归属，插值安全）。

        Args:
            segments: 语义断句后的字幕段（原地修改）
            audio_path: ASR 实际输入的人声音频路径
            language: 语言代码（None 按 auto 处理）
        """
        from collections import deque

        import soundfile as sf
        from app.utils.speech_islands import (
            compute_rms_envelope,
            detect_speech_islands,
            is_silence,
            snap_start_forward,
            speech_ratio,
            speech_threshold,
            split_islands,
        )

        try:
            wav, sr = sf.read(audio_path, dtype="float32")
        except Exception as e:
            logger.warning(f"Sync repair: cannot read audio {audio_path}: {e}")
            return
        if wav.ndim > 1:
            wav = wav.mean(axis=1)

        envelope, frame_samples = compute_rms_envelope(wav, sr)
        if len(envelope) == 0:
            return
        frame_dur = frame_samples / sr
        thr = speech_threshold(envelope)
        islands = detect_speech_islands(envelope, frame_dur, threshold=thr)
        if not islands:
            return
        units = split_islands(islands, envelope, frame_dur)
        if not units:
            return
        audio_dur = len(wav) / sr

        snap_window = settings.SYNC_REPAIR_SNAP_WINDOW
        ratio_floor = settings.SYNC_REPAIR_SPEECH_RATIO
        max_word_dur = settings.SYNC_REPAIR_MAX_WORD_DUR

        # 修复前快照：单调性兜底回退用
        snapshot = [
            (
                seg.start,
                seg.end,
                [(w.start, w.end) for w in (seg.words or [])],
            )
            for seg in segments
        ]

        # ---- 1) 展平词序列（按漂移时间排序，稳定）----
        word_locs = []  # (seg_idx, word_idx, 漂移中点, 字符数)
        for si, seg in enumerate(segments):
            for wi, w in enumerate(seg.words or []):
                word_locs.append((si, wi, (w.start + w.end) / 2.0, max(1, len(w.word))))
        word_locs.sort(key=lambda t: (t[2], t[0], t[1]))
        n_words = len(word_locs)
        if n_words == 0:
            return
        n_units = len(units)

        # ---- 2) 全局 DP 分配：f(i, j) = 前 i 个词分给前 j 个单元的最小代价。
        #         cost(k..i → 单元 j) = |单元宽×rate − 词字符数|
        #                               + W_TIME × Σ 词漂移中点到单元的距离
        #         语速全局自校准（语言/语速自适应）；漂移时间在压缩数据上是
        #         误导，只作轻先验，预算 + 顺序约束才是主裁决。----
        total_chars = sum(c for _, _, _, c in word_locs)
        total_width = sum(e - s for s, e in units)
        rate = total_chars / max(1e-6, total_width)
        W_TIME = 0.05 * rate  # 秒 → 字符当量的折算系数

        C = [0.0] * (n_words + 1)  # 字符前缀和（单调，支撑阈值分裂）
        for i, (_, _, _, c) in enumerate(word_locs):
            C[i + 1] = C[i] + c

        INF = float("inf")
        f_prev = [0.0] + [INF] * n_words  # j = 0
        back = [None] * n_units
        for j, (us, ue) in enumerate(units):
            budget = (ue - us) * rate
            # 词漂移中点到单元 j 的距离前缀和
            D = [0.0] * (n_words + 1)
            acc = 0.0
            for i, (_, _, mid, _) in enumerate(word_locs):
                if mid < us:
                    acc += us - mid
                elif mid > ue:
                    acc += mid - ue
                D[i + 1] = acc

            f_cur = [INF] * (n_words + 1)
            bk = [0] * (n_words + 1)
            pre_min = INF      # k ∈ [0, pk) 的 min(f_prev[k] − C[k] − W_TIME·D[k])
            pre_min_k = -1
            dq_suf = deque()   # k ∈ [pk, i] 的单调队列，值 f_prev[k] + C[k] − W_TIME·D[k]
            pk = 0
            for i in range(n_words + 1):
                v_suf = f_prev[i] + C[i] - W_TIME * D[i]
                while dq_suf and dq_suf[-1][1] >= v_suf:
                    dq_suf.pop()
                dq_suf.append((i, v_suf))
                thr = C[i] - budget
                while pk <= i and C[pk] < thr:
                    v_pre = f_prev[pk] - C[pk] - W_TIME * D[pk]
                    if v_pre < pre_min:
                        pre_min = v_pre
                        pre_min_k = pk
                    if dq_suf and dq_suf[0][0] == pk:
                        dq_suf.popleft()
                    pk += 1
                best = INF
                best_k = -1
                if dq_suf:
                    v = dq_suf[0][1] + (budget - C[i]) + W_TIME * D[i]
                    if v < best:
                        best, best_k = v, dq_suf[0][0]
                if pre_min < INF:
                    v = pre_min + (C[i] - budget) + W_TIME * D[i]
                    if v < best:
                        best, best_k = v, pre_min_k
                f_cur[i] = best
                bk[i] = best_k
            f_prev = f_cur
            back[j] = bk

        # 回溯：单元 j 分得词 [k, i)
        alloc: List[List[int]] = [[] for _ in range(n_units)]
        i = n_words
        for j in range(n_units - 1, -1, -1):
            k = back[j][i]
            alloc[j] = list(range(k, i))
            i = k

        # ---- 3) 分组重对齐。段被 DP 拆到多个单元时（均匀语速假设在局部
        #         密度突变处的噪声，如句尾音拖进下一岛），把这些单元合并成
        #         一组联合重对齐——合并窗口内 aligner 的顺序匹配能自己找到
        #         正确落点。其余单元独立处理。----
        def _find(parent, x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        uparent = list(range(n_units))
        seg_units: Dict[int, List[int]] = {}
        for j in range(n_units):
            for t in alloc[j]:
                si = word_locs[t][0]
                seg_units.setdefault(si, []).append(j)
        for js in seg_units.values():
            js = sorted(set(js))
            for j in js[1:]:
                ra, rb = _find(uparent, js[0]), _find(uparent, j)
                if ra != rb:
                    uparent[max(ra, rb)] = min(ra, rb)

        groups: Dict[int, Dict[str, Any]] = {}
        for j in range(n_units):
            root = _find(uparent, j)
            g = groups.setdefault(root, {"units": [], "idxs": []})
            g["units"].append(j)
            g["idxs"].extend(alloc[j])
        group_list = sorted(groups.values(), key=lambda g: g["units"][0])

        def _timed_ok(aligned) -> bool:
            n_timed = sum(1 for w in aligned if w["end"] - w["start"] > 0.01)
            n = len(aligned)
            if n <= 8:
                return n_timed >= n - 1
            return n_timed >= (2 * n) // 3

        realigned = 0
        interpolated = 0
        skipped = 0

        def _realign_group(g):
            """组内词联合重对齐；验收失败则组首尾单元范围内插值。返回 (结果, 词表)"""
            us = units[g["units"][0]][0]
            ue = units[g["units"][-1]][1]
            words = [segments[si].words[wi] for si, wi, _, _ in
                     (word_locs[t] for t in g["idxs"])]
            win = (max(0.0, us - 0.15), min(audio_dur, ue + 0.15))
            text = " ".join(w.word for w in words)
            aligned = alignment_service.refine_alignment(wav, sr, text, win, language)
            if aligned is not None and len(aligned) == len(words) and _timed_ok(aligned):
                for w, w_new in zip(words, aligned):
                    w.start, w.end = w_new["start"], w_new["end"]
                return "realigned", words
            logger.debug(
                f"Sync repair: units {g['units'][0]}-{g['units'][-1]} fallback to "
                f"interpolation (aligned={0 if not aligned else len(aligned)}, "
                f"expected={len(words)})"
            )
            span = ue - us
            chars = [max(1, len(w.word)) for w in words]
            total = sum(chars)
            cursor = us
            for w, c in zip(words, chars):
                w.start = cursor
                cursor += c / total * span
                w.end = cursor
            return "interpolated", words

        for g in group_list:
            if not g["idxs"]:
                continue
            us = units[g["units"][0]][0]
            ue = units[g["units"][-1]][1]
            words = [segments[si].words[wi] for si, wi, _, _ in
                     (word_locs[t] for t in g["idxs"])]
            # 健康组跳过：词本就在组范围内、无零时长/超长词、语音占比正常
            healthy = all(
                us - 0.05 <= w.start and w.end <= ue + 0.05
                and 0.04 <= (w.end - w.start) <= max_word_dur
                for w in words
            )
            if healthy and speech_ratio(envelope, frame_dur, thr, us, ue) >= ratio_floor:
                skipped += 1
                continue
            outcome, _ = _realign_group(g)
            if outcome == "realigned":
                realigned += 1
            else:
                interpolated += 1

        # ---- 3b) 拆段 A/B 裁决：均匀语速预算在局部密度突变处会把一个段拆到
        #         多个单元（off-by-one 错位的典型信号——段的头部词被拉去填
        #         前一岛的预算坑，如 "You're just visually challenged." 的头
        #         两个词被分进上一句的尾音岛）。对每个被拆的段做对照实验：
        #         A=保持现状；B=把段的头部词移入最后一个单元、按新分配重建
        #         分组并重对齐受影响组。用「段内词间隙 + 时长/字符离散度 +
        #         单元语音未被词覆盖量」打分，B 明显更优才采纳
        #         （压缩对齐 LIS 平滑会抹平间隙，离散度项兜底）。----
        def _seg_score(si):
            ws = segments[si].words or []
            if len(ws) < 2:
                return 0.0
            gaps = [max(0.0, ws[k + 1].start - ws[k].end) for k in range(len(ws) - 1)]
            dpc = [(w.end - w.start) / max(1, len(w.word)) for w in ws]
            mean = sum(dpc) / len(dpc)
            std = (sum((x - mean) ** 2 for x in dpc) / len(dpc)) ** 0.5
            return max(gaps) + 3.0 * std

        def _coverage_miss(js, words):
            miss = 0.0
            for j in js:
                s, e = units[j]
                cov = 0.0
                for w in words:
                    ov = min(w.end, e) - max(w.start, s)
                    if ov > cov:
                        cov = ov
                miss += max(0.0, (e - s) - cov)
            return miss

        def _build_groups(alloc_map):
            """由分配表重建 seg_units / 并查集 / 分组（B 方案试算用）"""
            su = {}
            for j in range(n_units):
                for t in alloc_map[j]:
                    su.setdefault(word_locs[t][0], []).append(j)
            up = list(range(n_units))
            for js in su.values():
                js = sorted(set(js))
                for j in js[1:]:
                    ra, rb = _find(up, js[0]), _find(up, j)
                    if ra != rb:
                        up[max(ra, rb)] = min(ra, rb)
            gs = {}
            for j in range(n_units):
                r = _find(up, j)
                g = gs.setdefault(r, {"units": [], "idxs": []})
                g["units"].append(j)
                g["idxs"].extend(alloc_map[j])
            return up, su, gs

        def _plan_score(gs_map, up_map, roots):
            """受影响区域得分 = 受影响段分之和 + 0.5 × 单元语音覆盖缺失"""
            units_seen = []
            words = []
            segs_seen = set()
            for r in roots:
                g = gs_map[_find(up_map, r)]
                units_seen.extend(g["units"])
                for t in g["idxs"]:
                    si2, wi2 = word_locs[t][0], word_locs[t][1]
                    words.append(segments[si2].words[wi2])
                    segs_seen.add(si2)
            return sum(_seg_score(si2) for si2 in sorted(segs_seen)) \
                + 0.5 * _coverage_miss(units_seen, words)

        for si in sorted(seg_units):
            js = sorted(set(seg_units[si]))
            if len(js) < 2:
                continue
            last_unit = js[-1]
            head_idxs = [t for j in js[:-1] for t in alloc[j] if word_locs[t][0] == si]
            if not head_idxs:
                continue

            roots_a = sorted({_find(uparent, j) for j in js})
            # 捕获受影响词的当前时间（A 方案结果，回退用）
            touched_idxs = sorted({t for r in roots_a for t in groups[r]["idxs"]})
            saved = [
                (t, segments[word_locs[t][0]].words[word_locs[t][1]].start,
                 segments[word_locs[t][0]].words[word_locs[t][1]].end)
                for t in touched_idxs
            ]
            score_a = _plan_score(groups, uparent, roots_a)

            # B：移动头词 → 重建分组 → 试算重对齐
            alloc_b = [list(a) for a in alloc]
            for j in js[:-1]:
                alloc_b[j] = [t for t in alloc_b[j] if word_locs[t][0] != si]
            alloc_b[last_unit] = sorted(alloc_b[last_unit] + head_idxs)
            up_b, su_b, gs_b = _build_groups(alloc_b)
            roots_b = sorted({_find(up_b, j) for j in js})
            for r in roots_b:
                g = gs_b[_find(up_b, r)]
                if g["idxs"]:
                    _realign_group(g)
            score_b = _plan_score(gs_b, up_b, roots_b)

            if score_b < score_a * 0.9 - 0.05:
                # 采纳 B：提交分配与分组（时间已被试算写回）
                alloc = alloc_b
                uparent, seg_units, groups = up_b, su_b, gs_b
                realigned += 1
                logger.debug(f"Sync repair: segment {si} head words moved to unit {last_unit}")
            else:
                # 保持 A：恢复受影响词的时间
                for t, os_, oe in saved:
                    w = segments[word_locs[t][0]].words[word_locs[t][1]]
                    w.start, w.end = os_, oe

        # ---- 4) 段边界从词重建（段的词可跨单元）----
        for seg in segments:
            ws = seg.words or []
            if ws:
                seg.start = min(w.start for w in ws)
                seg.end = max(w.end for w in ws)

        # ---- 5) 起点静音吸附（全段遍历，只前移）：修正 aligner 残留的提前偏差 ----
        snapped = 0
        for i, seg in enumerate(segments):
            words = seg.words or []
            if not words or seg.end - seg.start <= 0.05:
                continue
            if not is_silence(envelope, frame_dur, thr, seg.start - 0.15, seg.start + 0.15):
                continue
            cand = snap_start_forward(islands, seg.start, max_snap=snap_window, lead_pad=0.10)
            if cand is None:
                continue
            if i + 1 < len(segments) and cand >= segments[i + 1].start - 0.02:
                continue
            if cand >= seg.end - 0.05:
                continue
            seg.start = cand
            words[0].start = cand
            if words[0].end - cand < 0.02:
                words[0].end = cand + 0.02
            snapped += 1

        # ---- 6) 单调性兜底（DP 输出本应单调，此为安全网）：起点倒挂时回退
        #         修复方，仍倒挂则钳位；回退会使起点后移、可能与更早邻段
        #         重新倒挂，故迭代至不动点 ----
        def _restore(seg, old):
            seg.start, seg.end = old[0], old[1]
            for w, (ws, we) in zip(seg.words or [], old[2]):
                w.start, w.end = ws, we

        for _round in range(5):
            violations = 0
            for i in range(1, len(segments)):
                a, b = segments[i - 1], segments[i]
                if b.start >= a.start - 1e-6:
                    continue
                violations += 1
                old_a, old_b = snapshot[i - 1], snapshot[i]
                if abs(old_a[0] - a.start) > 1e-9:
                    _restore(a, old_a)
                    logger.warning(f"Sync repair: segment {i - 1} reverted (start regression)")
                if b.start < a.start - 1e-6 and abs(old_b[0] - b.start) > 1e-9:
                    _restore(b, old_b)
                    logger.warning(f"Sync repair: segment {i} reverted (start regression)")
                if b.start < a.start - 1e-6:
                    b.start = a.start
                    if b.words:
                        b.words[0].start = a.start
                        if b.words[0].end - a.start < 0.02:
                            b.words[0].end = a.start + 0.02
            if violations == 0:
                break

        # ---- 7) 全局兜底：相邻段重叠 >0.05s 时把前段 end 钳到后段 start ----
        for a, b in zip(segments, segments[1:]):
            if a.end - b.start > 0.05:
                a.end = b.start
                if a.words:
                    last_w = a.words[-1]
                    last_w.end = max(last_w.start + 0.01, min(last_w.end, b.start))

        logger.info(
            f"Sync repair: {n_units} units, {realigned} realigned, "
            f"{interpolated} interpolated, {skipped} healthy-skipped, "
            f"{snapped} snapped"
        )

    def search_subtitles(
        self,
        segments: List[SubtitleSegment],
        query: str,
        case_sensitive: bool = False
    ) -> List[SubtitleSegment]:
        """
        Search subtitle segments

        Args:
            segments: List of subtitle segments
            query: Search query
            case_sensitive: Whether search is case sensitive

        Returns:
            List of matching segments
        """
        if not query:
            return []

        search_query = query if case_sensitive else query.lower()

        results = []
        for segment in segments:
            text = segment.text if case_sensitive else segment.text.lower()

            if search_query in text:
                results.append(segment)

        logger.info(f"Search '{query}' found {len(results)} results")
        return results

    def export_srt(self, segments: List[SubtitleSegment]) -> str:
        """
        Export subtitles to SRT format

        Args:
            segments: List of subtitle segments

        Returns:
            SRT formatted string
        """
        srt_lines = []

        for i, segment in enumerate(segments, 1):
            # Timestamp format: 00:00:00,000 --> 00:00:05,000
            start_time = self._format_srt_time(segment.start)
            end_time = self._format_srt_time(segment.end)

            srt_lines.append(str(i))
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(segment.text)
            srt_lines.append("")  # Empty line between segments

        return "\n".join(srt_lines)

    def export_vtt(self, segments: List[SubtitleSegment]) -> str:
        """
        Export subtitles to WebVTT format

        Args:
            segments: List of subtitle segments

        Returns:
            WebVTT formatted string
        """
        vtt_lines = ["WEBVTT", ""]

        for segment in segments:
            # Timestamp format: 00:00:00.000 --> 00:00:05.000
            start_time = self._format_vtt_time(segment.start)
            end_time = self._format_vtt_time(segment.end)

            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(segment.text)
            vtt_lines.append("")

        return "\n".join(vtt_lines)

    def _format_srt_time(self, seconds: float) -> str:
        """Format time to SRT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_time(self, seconds: float) -> str:
        """Format time to WebVTT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


# Global subtitle service instance
subtitle_service = SubtitleService()
