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
from app.utils import logger, extract_audio_segment
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
                    audio_path=audio_path,
                    language=language,
                    generate_timestamps=True,
                    use_vad=True
                )
            else:
                # Use standard transcription for shorter files
                transcription_result = asr_service.transcribe_file(
                    audio_path=audio_path,
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

            # Apply forced alignment if available and requested
            # Note: Skip forced alignment for VAD-processed audio as timestamps are already accurate
            if use_alignment and not should_use_vad and alignment_service.check_aligner_ready():
                logger.info("Applying forced alignment...")
                self._apply_alignment_to_segments(
                    segments,
                    audio_path,
                    full_text,
                    language
                )

            processing_time = time.time() - start_time

            result = TranscriptionResult(
                file_id=file_id,
                language=language,
                segments=segments,
                full_text=full_text,
                duration=media_file.duration or 0.0,
                processing_time=processing_time
            )

            # Add metadata about VAD usage
            if should_use_vad:
                result.metadata = {
                    "vad_enabled": True,
                    "num_segments": transcription_result.get("num_segments", 0)
                }

            # Save to cache
            logger.info(f"Saving to cache: {filename}_{file_size}")
            cache_service.save_transcription(filename, file_size, result, audio_path)
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

    def _apply_alignment_to_segments(
        self,
        segments: List[SubtitleSegment],
        audio_path: str,
        full_text: str,
        language: str
    ):
        """
        Apply forced alignment to improve word timestamps

        Args:
            segments: Subtitle segments to update
            audio_path: Path to audio file
            full_text: Full transcript text
            language: Language code
        """
        try:
            # For each segment, refine timestamps
            for segment in segments:
                # Extract audio segment
                segment_audio_path = f"{audio_path}.seg{segment.id}.wav"

                # Note: In production, you might want to extract actual audio segments
                # For now, we'll use the full audio with text segment
                aligned_words = alignment_service.align_text_to_audio(
                    audio_path,
                    segment.text,
                    language
                )

                if aligned_words:
                    # Update segment words with aligned timestamps
                    segment.words = [
                        SubtitleWord(
                            word=w["word"],
                            start=w["start"],
                            end=w["end"],
                            confidence=w.get("score")
                        )
                        for w in aligned_words
                    ]

                    # Update segment boundaries
                    if aligned_words:
                        segment.start = aligned_words[0]["start"]
                        segment.end = aligned_words[-1]["end"]

        except Exception as e:
            logger.warning(f"Alignment failed for segment {segment.id}: {e}")

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
