"""
Subtitle generation and processing service
"""
import json
import time
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

from app.services.asr_service import asr_service
from app.services.alignment_service import alignment_service
from app.services.media_service import media_service
from app.services.cache_service import cache_service
from app.config import settings
from app.core.sync_repair_config import get_sync_repair_config
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

            # 同步修复：健康锚定 + 不健康段局部重探测（补偿 aligner 在
            # 长窗口上的漂移/钉死）。返回修复前快照供落盘，便于事后区分
            # "ASR 本来就错"还是"修复推翻了正确时间"。
            presnap = None
            if use_alignment and get_sync_repair_config().get_config().enabled and segments:
                presnap = self._refine_segment_timing(segments, asr_audio_path, language)

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
            cache_service.save_transcription(filename, file_size, result, asr_audio_path, presnap=presnap)
            cache_service.generate_subtitle_files(filename, file_size, segments)
            cache_service.link_file_id(filename, file_size, file_id)

            logger.info(f"Subtitle generation completed: {len(segments)} segments")
            return result

        except Exception as e:
            logger.error(f"Subtitle generation failed: {e}")
            return None

    def repair_cached_timing(
        self,
        file_id: str,
        filename: str,
        file_size: int
    ) -> Optional[TranscriptionResult]:
        """
        对已有缓存轻量重跑同步修复并落盘（不重跑 demucs/ASR，GPU 约分钟级）。

        供设置页修改修复参数后即时生效（POST /api/transcription/repair/{file_id}）
        与 backend/repair_cache.py CLI 复用。transcription.json 的
        translation/confidence/metadata 经 load→save 往返保留；
        transcription.presnap.json 仅首次落盘（保留最早状态）。

        Args:
            file_id: 请求方文件 ID（用于缓存关联与响应）
            filename: 缓存 key 文件名（无扩展名）
            file_size: 缓存 key 文件大小

        Returns:
            TranscriptionResult（metadata.sync_repair_applied 标记是否实际
            执行了修复；总开关关闭时不改任何文件），缓存缺失返回 None
        """
        start_time = time.time()

        result = cache_service.load_transcription(filename, file_size)
        if not result:
            logger.warning(f"Repair cache: no transcription cache for {filename}_{file_size}")
            return None
        cache_dir = cache_service._get_cache_dir(filename, file_size)
        audio_path = cache_dir / "audio.mp3"
        if not audio_path.exists():
            logger.warning(f"Repair cache: audio.mp3 missing for {filename}_{file_size}")
            return None

        cfg = get_sync_repair_config().get_config()
        if not cfg.enabled:
            # 总开关关闭：不动缓存文件，幂等返回
            result.file_id = file_id
            result.metadata = {**(result.metadata or {}), "sync_repair_applied": False}
            return result

        presnap = self._refine_segment_timing(
            result.segments, str(audio_path), result.language or "auto")

        if presnap:
            snap_path = cache_dir / "transcription.presnap.json"
            try:
                if not snap_path.exists():
                    with open(snap_path, "w", encoding="utf-8") as f:
                        json.dump({"segments": presnap}, f, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Repair cache: presnap save failed: {e}")

        for seg in result.segments:
            seg.start, seg.end = round(seg.start, 3), round(seg.end, 3)
            for w in seg.words or []:
                w.start, w.end = round(w.start, 3), round(w.end, 3)
        result.file_id = file_id
        result.processing_time = time.time() - start_time
        result.metadata = {**(result.metadata or {}), "sync_repair_applied": True}
        cache_service.save_transcription(filename, file_size, result, None)
        cache_service.generate_subtitle_files(filename, file_size, result.segments)
        cache_service.link_file_id(filename, file_size, file_id)

        logger.info(
            f"Repair cache done: {filename}_{file_size} "
            f"({len(result.segments)} segments, {result.processing_time:.1f}s)")
        return result

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
        字幕-语音同步修复：健康锚定 + 不健康簇 ASR 重探测。

        2026-11-06 重构（01_part1 复盘，见 README_sync_repair.md）：旧"词→岛全局
        DP 分配"用均匀语速预算全量重排、ASR 词时间只作轻先验——语速离群的段
        （快喊话/慢旁白）被系统性挪到错误的岛组上，且验收（仅查词时长>0）与
        跨静音插值兜底会把错位"焊死"。实测 01_part1：整簇文本晚移一组岛约 4-7s
        （"Bryce, isn't it time..." 真实在 69.3-71.95，被钉到 75.05-78.99），
        26 个语音岛（16% 语音宽）无人认领。

        新策略（探针 probe_sync_truth.py 已在 18/18 疑点窗上验证）：
          1. 健康段冻结：词中点全在单元内 + 词时长正常 + 速率 ∈ [RATE_LO,
             RATE_HI] + 语音占比达标 → 一律不动。判健康即冻结保证重跑幂等；
             ASR 时间对的段绝不被预算模型推翻。
          2. 不健康段逐段紧窗重探测（不合并大簇——大窗内匹配会漂移）：
             每段候选窗 = 自身区间 ±0.8s + 搜索半径内无人认领语音单元组
             （≤MERGE_GAP 桥接合并）±0.5s，全局去重后批量 ASR
             （return_time_stamps=True，紧窗词级时间戳已被探针验证准确），
             再用 difflib 词块匹配做内容验证（cov≥0.5、锚点间隙≤3s、
             跨度速率合理），达标的段按 ASR 词时间落位，段内未匹配词按
             字符比例在锚点间小步插值。对不上（如缓存文本与实际语音不符）
             的段保留现状。
          3. 收尾安全网：段边界从词重建 → 起点静音吸附（只前移）→ 单调
             性钳位（只挪低信任方标签，不回退落位）→ 相邻段重叠钳位。

        为什么不用 forced aligner 做候选试配：forced alignment 会把任何文本
        拉伸铺到窗口内任何语音上——错文本对错语音同样"整齐、覆盖满分"，
        自洽错位无法靠打分区分；而 ASR 重转写天然校验"这里到底说的是不是
        这句话"。

        Args:
            segments: 语义断句后的字幕段（原地修改）
            audio_path: ASR 实际输入的人声音频路径
            language: 语言代码（None 按 auto 处理）

        Returns:
            修复前快照（list[dict]，JSON 可序列化）——供调用方落盘
            transcription.presnap.json，便于事后区分"ASR 本来就错"还是
            "修复推翻了正确时间"。
        """
        import difflib

        import soundfile as sf
        from app.core import get_asr_model
        from app.utils.speech_islands import (
            compute_rms_envelope,
            detect_speech_islands,
            is_silence,
            snap_start_forward,
            speech_ratio,
            speech_threshold,
            split_islands,
        )

        # 运行时配置（设置页可调，backend/sync_repair_config.json 持久化）
        cfg = get_sync_repair_config().get_config()

        try:
            wav, sr = sf.read(audio_path, dtype="float32")
        except Exception as e:
            logger.warning(f"Sync repair: cannot read audio {audio_path}: {e}")
            return None
        if wav.ndim > 1:
            wav = wav.mean(axis=1)

        # 可选：demucs 后温和带通（默认关，探针 A/B 无增益；特殊素材用）
        if cfg.bandpass:
            from app.utils.audio import apply_noise_reduction
            wav = apply_noise_reduction(
                wav, sr,
                enabled=True,
                lowcut=cfg.bandpass_lo,
                highcut=cfg.bandpass_hi,
                order=4, filter_type="bandpass",
                normalize_after_filter=False,
            )

        envelope, frame_samples = compute_rms_envelope(wav, sr)
        if len(envelope) == 0:
            return None
        frame_dur = frame_samples / sr
        thr = speech_threshold(envelope)
        islands = detect_speech_islands(envelope, frame_dur, threshold=thr)
        if not islands:
            return None
        units = split_islands(islands, envelope, frame_dur)
        if not units:
            return None
        audio_dur = len(wav) / sr

        snap_window = cfg.snap_window
        ratio_floor = cfg.speech_ratio
        max_word_dur = cfg.max_word_dur
        rate_lo = cfg.rate_lo
        rate_hi = cfg.rate_hi
        search_s = cfg.search_s

        # 修复前快照：单调性兜底回退 + 落盘供事后诊断
        snapshot = [
            {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in (seg.words or [])
                ],
            }
            for seg in segments
        ]

        # ---- 1) 健康分类与冻结 ----
        def _unit_at(t, tol=0.05):
            for j, (s, e) in enumerate(units):
                if s - tol <= t <= e + tol:
                    return j
            return -1

        def _speech_width(a, b):
            return sum(max(0.0, min(b, e) - max(a, s)) for s, e in units)

        def _healthy(seg):
            ws = seg.words or []
            if not ws:
                return False
            for w in ws:
                d = w.end - w.start
                if d < 0.04 or d > max_word_dur:
                    return False
                if _unit_at((w.start + w.end) / 2.0) < 0:
                    return False
            if speech_ratio(envelope, frame_dur, thr, seg.start, seg.end) < ratio_floor:
                return False
            chars = sum(max(1, len(w.word)) for w in ws)
            return rate_lo <= chars / max(0.3, _speech_width(seg.start, seg.end)) <= rate_hi

        healthy = [_healthy(seg) for seg in segments]
        occupied = set()  # 健康段词占据的单元
        for seg, ok in zip(segments, healthy):
            if not ok:
                continue
            for w in seg.words or []:
                j = _unit_at((w.start + w.end) / 2.0)
                if j >= 0:
                    occupied.add(j)

        unclaimed = [  # 无健康词覆盖、够宽的单元：错位文本的候选去处
            j for j, (s, e) in enumerate(units)
            if j not in occupied and e - s >= cfg.min_island_w
        ]

        # ---- 2) 不健康段按簇 ASR 重探测 ----
        def _norm(tok: str) -> str:
            return "".join(c for c in tok.lower() if c.isalnum())

        def _parse_asr_words(item) -> List[Dict[str, Any]]:
            if isinstance(item, dict):
                raw_ts = item.get("timestamps") or item.get("time_stamps") or []
            else:  # qwen_asr ASRTranscription：.time_stamps
                raw_ts = getattr(item, "time_stamps", None) or []
            words = []
            for t in raw_ts:
                if isinstance(t, dict):
                    s, e, w = t.get("start"), t.get("end"), t.get("word", "")
                elif isinstance(t, (list, tuple)):
                    s, e, w = t[0], t[1], t[2]
                else:
                    s = getattr(t, "start_time", None)
                    e = getattr(t, "end_time", None)
                    w = getattr(t, "text", getattr(t, "word", ""))
                if s is None or e is None:
                    continue
                words.append({"word": str(w), "start": float(s), "end": float(e)})
            return words

        # 2a) 逐段候选窗：自身区间 ±0.8s（验证"原位即对"）+ 搜索半径内
        #     无人认领单元组（间隙 ≤ MERGE_GAP 合并）±0.5s。逐段紧窗，
        #     不合并大簇（v2 教训：大窗内匹配漂移）。
        #     额外把两类"看似健康"的段也纳入探测：零间隙链成员（≥3 段
        #     首尾相接）与词级插值签名段（旧管线兜底插值的产物）。
        probe_set = {i for i, ok in enumerate(healthy) if not ok}
        run = [0]
        for i in range(1, len(segments)):
            if segments[i].start - segments[i - 1].end < 0.02:
                run.append(i)
            else:
                if len(run) >= 3:
                    probe_set.update(run)
                run = [i]
        if len(run) >= 3:
            probe_set.update(run)

        def _interp_signature(seg):
            ws = seg.words or []
            if len(ws) < 3:
                return False
            for x, y in zip(ws, ws[1:]):
                if y.start - x.end > 0.005:
                    return False
            rates = [max(1, len(w.word)) / max(0.04, w.end - w.start)
                     for w in ws]
            return max(rates) / max(1e-6, min(rates)) < 1.35

        for i in range(len(segments)):
            if _interp_signature(segments[i]):
                probe_set.add(i)

        groups: List[List[float]] = []
        for j in unclaimed:
            s, e = units[j]
            if groups and s - groups[-1][1] <= cfg.merge_gap:
                groups[-1][1] = max(groups[-1][1], e)
            else:
                groups.append([s, e])

        own_pad, group_pad, anchor_gap_max = 0.8, 0.5, 3.0
        cand_by_seg: Dict[int, List[Tuple[float, float]]] = {}
        win_keys: Dict[Tuple[float, float], None] = {}

        def _add_win(si, lo, hi):
            if hi - lo < 0.3:
                return
            key = (round(lo * 2) / 2.0, round(hi * 2) / 2.0)
            win_keys.setdefault(key, None)
            cand_by_seg[si].append(key)

        probe_sorted = sorted(probe_set)
        for si in probe_sorted:
            seg = segments[si]
            center = (seg.start + seg.end) / 2.0
            chars = sum(max(1, len(w.word)) for w in (seg.words or []))
            cand_by_seg[si] = []
            _add_win(si, max(0.0, seg.start - own_pad),
                     min(audio_dur, seg.end + own_pad))
            # 无人认领单元组：不限个数（BGM 小岛多，截断会漏掉真位置）
            min_w = chars / (rate_hi + 8.0)
            near = sorted(
                (abs((gs + ge) / 2.0 - center), gs, ge)
                for gs, ge in groups
                if abs((gs + ge) / 2.0 - center) <= search_s)
            for _d, gs, ge in near:
                if ge - gs >= min_w:
                    # 组宽至少装得下整段文本（按 rate_hi+8 的最快语速）
                    _add_win(si, max(0.0, gs - group_pad),
                             min(audio_dur, ge + group_pad))
            # 邻近探测段的自身窗：真位置可能被其它不健康段的词占着
            # （不形成无人认领组），但一定落在某个探测段的自身窗内。
            # 窗口集合与上面重合，不增加 ASR 开销。
            for sj in probe_sorted:
                if sj == si:
                    continue
                o = segments[sj]
                if abs((o.start + o.end) / 2.0 - center) <= search_s:
                    _add_win(si, max(0.0, o.start - own_pad),
                             min(audio_dur, o.end + own_pad))
            # 相邻探测段间的桥接窗：真位置可能落在两段自身窗的间隙里
            # （RMS 阈值漏检的轻声区，无任何单元/组），成对桥接覆盖，
            # 不是整簇大窗（v2 教训），落位仍需通过内容验证。
            for sj in (si - 1, si + 1):
                if sj in probe_set and 0 <= sj < len(segments):
                    o = segments[sj]
                    _add_win(si,
                             max(0.0, min(seg.start, o.start) - own_pad),
                             min(audio_dur, max(seg.end, o.end) + own_pad))

        # 2b) 全局去重后的紧窗批量 ASR（qwen 支持 (wav, sr) 列表）。
        #     注意探针时间戳是窗口相对的，必须加窗口起点偏移。
        import numpy as np

        asr = get_asr_model()
        win_list = list(win_keys.keys())
        probe_by_win: Dict[Tuple[float, float], List[Dict[str, Any]]] = {}

        def _transcribe_windows(keys):
            for key in keys:
                lo, hi = key
                seg_wav = np.asarray(wav[int(lo * sr):int(hi * sr)],
                                     dtype=np.float32)
                try:
                    r = asr.model.transcribe(
                        (seg_wav, sr), language=None, return_time_stamps=True)
                    words = _parse_asr_words(
                        r[0] if isinstance(r, list) else r)
                    probe_by_win[key] = [
                        {"word": w["word"],
                         "start": w["start"] + lo, "end": w["end"] + lo}
                        for w in words
                    ]
                except Exception as e:
                    logger.warning(
                        f"Sync repair: window [{lo:.1f},{hi:.1f}] ASR failed: {e}")

        for k in range(0, len(win_list), 8):
            chunk = win_list[k:k + 8]
            batch = [(np.asarray(wav[int(lo * sr):int(hi * sr)],
                                 dtype=np.float32), sr)
                     for lo, hi in chunk]
            try:
                results = asr.model.transcribe(
                    batch, language=None, return_time_stamps=True)
                if not isinstance(results, list) or len(results) != len(chunk):
                    raise ValueError("unexpected batch result shape")
                for key, item in zip(chunk, results):
                    lo = key[0]
                    words = _parse_asr_words(item)
                    probe_by_win[key] = [
                        {"word": w["word"],
                         "start": w["start"] + lo, "end": w["end"] + lo}
                        for w in words
                    ]
            except Exception as e:
                logger.warning(f"Sync repair: batch ASR failed ({e}), "
                               f"falling back to per-window")
                _transcribe_windows(chunk)

        # 2c) 逐段内容验证落位：difflib 词块匹配，达标者按探针词时间重锚定
        reanchored: Dict[int, float] = {}  # si -> cov（内容验证过的落位）
        moved = kept = 0
        for si in sorted(probe_set):
            seg = segments[si]
            ws = seg.words or []
            if not ws:
                continue
            total_chars = sum(max(1, len(w.word)) for w in ws) or 1
            seg_norm = [_norm(w.word) for w in ws]
            center = (seg.start + seg.end) / 2.0
            n_min = 1 if len(ws) <= 3 else 2

            best = None  # ((cov, -dist), cov, pairs, probe_words, win_key)
            best_cov_any = 0.0
            for key in cand_by_seg.get(si, []):
                pws = probe_by_win.get(key) or []
                if not pws:
                    continue
                probe_norm = [_norm(p["word"]) for p in pws]
                matcher = difflib.SequenceMatcher(
                    None, seg_norm, probe_norm, autojunk=False)
                pairs = [
                    (blk.a + k2, blk.b + k2)
                    for blk in matcher.get_matching_blocks() if blk.size > 0
                    for k2 in range(blk.size)
                ]
                if len(pairs) < n_min:
                    continue
                matched_chars = sum(len(ws[a].word) for a, _ in pairs)
                cov = matched_chars / total_chars
                best_cov_any = max(best_cov_any, cov)
                if cov < 0.5:
                    continue
                span_lo = pws[pairs[0][1]]["start"]
                span_hi = pws[pairs[-1][1]]["end"]
                gaps_ok = all(
                    pws[b2]["start"] - pws[b1]["end"] <= anchor_gap_max
                    for (_a1, b1), (_a2, b2) in zip(pairs, pairs[1:]))
                if not gaps_ok:
                    continue  # 匹配词散布过远：疑似跨语音拼贴
                rate = matched_chars / max(0.3, span_hi - span_lo)
                if rate < rate_lo * 0.5 or rate > rate_hi + 8.0:
                    continue  # 跨度速率不合理
                dist = abs((span_lo + span_hi) / 2.0 - center)
                score = (cov, -dist)
                if best is None or score > best[0]:
                    best = (score, cov, pairs, pws, key)
            if best is None:
                kept += 1  # 各候选窗音频与缓存文本都对不上：保留现状
                logger.debug(
                    f"Sync repair: seg {seg.id} unmatched (kept): "
                    f"best_cov={best_cov_any:.2f} over "
                    f"{len(cand_by_seg.get(si, []))} cands")
                continue
            _score, cov, pairs, pws, key = best
            win_lo, win_hi = key

            times: List[Optional[Tuple[float, float]]] = [None] * len(ws)
            for a, b in pairs:
                times[a] = (pws[b]["start"], pws[b]["end"])
            anchor_idx = [a for a, t in enumerate(times) if t is not None]
            # 未匹配词：锚点间按字符比例小步插值；首尾向窗内延展（≤1.2s）
            for lft, rgt in zip(anchor_idx, anchor_idx[1:]):
                chs = [max(1, len(ws[k2].word)) for k2 in range(lft + 1, rgt)]
                if not chs:
                    continue
                gap = max(0.02, times[rgt][0] - times[lft][1])
                cur = times[lft][1] + gap * 0.05
                for k2, ch in zip(range(lft + 1, rgt), chs):
                    slot = gap * 0.9 * ch / sum(chs)
                    times[k2] = (cur, cur + max(0.04, slot * 0.95))
                    cur += slot
            first_a, last_a = anchor_idx[0], anchor_idx[-1]
            if first_a > 0:
                chs = [max(1, len(ws[k2].word)) for k2 in range(first_a)]
                avail = min(1.2, times[first_a][0] - win_lo)
                if avail > 0.05:
                    cur = times[first_a][0] - avail * 0.9
                    for k2, ch in zip(range(first_a), chs):
                        slot = avail * 0.9 * ch / sum(chs)
                        times[k2] = (cur, cur + max(0.04, slot * 0.95))
                        cur += slot
            if last_a < len(ws) - 1:
                chs = [max(1, len(ws[k2].word))
                       for k2 in range(last_a + 1, len(ws))]
                avail = min(1.2, win_hi - times[last_a][1])
                if avail > 0.05:
                    cur = times[last_a][1] + avail * 0.05
                    for k2, ch in zip(range(last_a + 1, len(ws)), chs):
                        slot = avail * 0.9 * ch / sum(chs)
                        times[k2] = (cur, cur + max(0.04, slot * 0.95))
                        cur += slot
            prev_end = 0.0
            for a, w in enumerate(ws):
                t = times[a] or (prev_end, prev_end + 0.05)
                w.start = max(prev_end, t[0])
                w.end = max(prev_end + 0.02, t[1])
                prev_end = w.end
            reanchored[si] = cov
            moved += 1
            logger.debug(
                f"Sync repair: seg {seg.id} re-anchored (cov={cov:.2f})")

        n_unclaimed = len(unclaimed)

        # ---- 3) 段边界从词重建 ----
        for seg in segments:
            ws = seg.words or []
            if ws:
                seg.start = min(w.start for w in ws)
                seg.end = max(w.end for w in ws)

        # ---- 4) 起点静音吸附（全段遍历，只前移）：修正残留的提前偏差 ----
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

        # ---- 5) 单调性兜底（安全网）：只钳位不回退（v2 教训：revert 会
        #     连锁撤销内容验证过的落位）。倒挂时只挪低信任方的段标签：
        #     健康冻结(2.0) > 内容验证(cov) > 未匹配保留(0)。
        def _trust(i):
            if healthy[i]:
                return 2.0
            return reanchored.get(i, 0.0)

        for _round in range(6):
            violations = 0
            for i in range(1, len(segments)):
                a, b = segments[i - 1], segments[i]
                if b.start >= a.start - 1e-6:
                    continue
                violations += 1
                if _trust(i - 1) < _trust(i):
                    # a 未验证：标签挪到 b 前方的小间隙（词时间本就存疑）
                    a.start = max(0.0, b.start - 0.35)
                else:
                    b.start = a.end
                    if b.end < b.start + 0.05:
                        b.end = b.start + 0.35
                logger.debug(
                    f"Sync repair: seg {a.id}/{b.id} monotonic clamp "
                    f"({a.start:.2f} / {b.start:.2f})")
            if violations == 0:
                break

        # ---- 6) 全局兜底：相邻段重叠 >0.05s 时把前段 end 钳到后段 start ----
        for a, b in zip(segments, segments[1:]):
            if a.end - b.start > 0.05:
                a.end = b.start
                if a.words:
                    last_w = a.words[-1]
                    last_w.end = max(last_w.start + 0.01, min(last_w.end, b.start))

        logger.info(
            f"Sync repair: {len(segments)} segs ({sum(healthy)} healthy-frozen), "
            f"{len(probe_set)} probed in {len(win_list)} windows, "
            f"{moved} re-anchored, {kept} unmatched-kept, "
            f"{snapped} snapped, unclaimed_units={n_unclaimed}"
        )
        return snapshot

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
