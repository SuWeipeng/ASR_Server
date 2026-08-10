"""
VAD (Voice Activity Detection) audio splitting service
Intelligently splits long audio files into segments for processing
"""
import os
import tempfile
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
import soundfile as sf
import torch

from app.core.vad_model import get_vad_model
from app.core.vad_config import get_vad_config
from app.config import settings
from app.utils.logger import logger


@dataclass
class AudioSegment:
    """Represents a segment of audio with timing information"""
    audio: np.ndarray
    start_time: float
    end_time: float
    sample_rate: int

    @property
    def duration(self) -> float:
        """Get segment duration in seconds"""
        return self.end_time - self.start_time


class VADAudioSplitter:
    """
    Audio splitter using Voice Activity Detection
    Intelligently identifies speech segments and splits audio accordingly
    """

    def __init__(self):
        """Initialize VAD audio splitter"""
        self.vad_manager = get_vad_model()

    def split_audio(self, audio_path: str) -> List[AudioSegment]:
        """
        Split audio file into segments using VAD

        Args:
            audio_path: Path to audio file (WAV format)

        Returns:
            List of AudioSegment objects
        """
        logger.info(f"Splitting audio: {audio_path}")

        try:
            # Load audio file
            wav, sr = sf.read(audio_path)

            # Convert to mono if stereo
            if len(wav.shape) > 1:
                wav = wav.mean(axis=1)

            # 获取动态配置
            vad_config = get_vad_config().get_config()

            # Resample if needed
            if sr != vad_config.sample_rate:
                import resampy
                wav = resampy.resample(wav, orig_sr=sr, target_sr=vad_config.sample_rate)
                sr = vad_config.sample_rate

            # Try VAD-based splitting first (与 example_qwen3_asr_with_vad.py 一致)
            vad_model = self.vad_manager.model
            vad_utils = self.vad_manager.utils
            logger.info(f"[VAD DEBUG] Model loaded: {vad_model is not None}, Utils loaded: {vad_utils is not None}")

            if vad_model is not None:
                try:
                    logger.info(f"[VAD DEBUG] Attempting VAD-based splitting...")
                    logger.info(f"[VAD DEBUG] Audio duration: {len(wav)/sr:.2f}s, Sample rate: {sr}Hz")
                    logger.info(f"[VAD DEBUG] Config: min_silence={vad_config.min_silence_duration_ms}ms, max_speech={vad_config.max_speech_duration_s}s")

                    segments = self._split_with_vad(wav, sr)
                    if segments:
                        logger.info(f"[VAD SUCCESS] VAD split audio into {len(segments)} segments")
                        for i, seg in enumerate(segments):
                            logger.info(f"[VAD SEGMENT {i+1}] {seg.start_time:.2f}s - {seg.end_time:.2f}s (duration: {seg.duration:.2f}s)")
                        return segments
                    else:
                        logger.warning(f"[VAD WARNING] VAD returned no segments")
                except Exception as e:
                    logger.warning(f"[VAD ERROR] VAD processing failed: {e}, falling back to simple split")
                    import traceback
                    logger.warning(f"[VAD ERROR] Traceback: {traceback.format_exc()}")
            else:
                logger.warning(f"[VAD SKIP] VAD model is None, falling back to simple split")

            # Fallback to simple time-based splitting
            logger.info(f"[VAD FALLBACK] Using simple time-based splitting with {vad_config.max_speech_duration_s}s segments")
            segments = self._simple_split(wav, sr)
            logger.info(f"[SIMPLE SPLIT] Generated {len(segments)} segments")

            return segments

        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            raise

    def _split_with_vad(self, wav: np.ndarray, sr: int) -> List[AudioSegment]:
        """
        Use Silero VAD model to detect speech segments

        Args:
            wav: Audio waveform array
            sr: Sample rate

        Returns:
            List of AudioSegment objects
        """
        vad_model = self.vad_manager.model
        vad_utils = self.vad_manager.utils

        if vad_model is None or vad_utils is None:
            raise RuntimeError("VAD model not loaded")

        # 获取动态配置
        vad_config = get_vad_config().get_config()

        # Convert to tensor for VAD
        wav_tensor = torch.from_numpy(wav).float()

        # Get VAD timestamps - 完全按照 example_qwen3_asr_with_vad.py 的方式
        # 参数顺序：音频、模型、然后是其他参数
        get_speech_timestamps = vad_utils[0]
        logger.info(f"[VAD SPLIT] Calling get_speech_timestamps with params: "
                   f"sampling_rate={sr}, min_silence={vad_config.min_silence_duration_ms}ms, "
                   f"max_speech={vad_config.max_speech_duration_s}s")

        speech_timestamps = get_speech_timestamps(
            wav_tensor,
            vad_model,
            sampling_rate=sr,
            min_silence_duration_ms=vad_config.min_silence_duration_ms,
            max_speech_duration_s=vad_config.max_speech_duration_s
        )

        logger.info(f"[VAD SPLIT] Detected {len(speech_timestamps) if speech_timestamps else 0} speech segments")

        if not speech_timestamps:
            logger.warning("[VAD SPLIT] No speech detected in audio")
            return []

        # Convert VAD timestamps to audio segments (与 example_qwen3_asr_with_vad.py 一致)
        segments = []
        for i, timestamp in enumerate(speech_timestamps):
            # example 中直接使用 ts['start'] 和 ts['end']，不需要 .item()
            start_sample = timestamp['start']
            end_sample = timestamp['end']

            # 如果是 tensor，转换为 int
            if hasattr(start_sample, 'item'):
                start_sample = start_sample.item()
            if hasattr(end_sample, 'item'):
                end_sample = end_sample.item()

            start_time = start_sample / sr
            end_time = end_sample / sr

            # Apply maximum speech duration limit (与 example 一致)
            if end_time - start_time > get_vad_config().get_config().max_speech_duration_s:
                logger.info(f"Segment {i} exceeds max duration, splitting further")
                # Split long segments
                sub_segments = self._split_long_segment(wav, sr, start_time, end_time)
                segments.extend(sub_segments)
            else:
                # Extract audio segment (与 example 一致)
                segment_audio = wav[start_sample:end_sample]

                segments.append(AudioSegment(
                    audio=segment_audio,
                    start_time=start_time,
                    end_time=end_time,
                    sample_rate=sr
                ))

        return segments

    def _split_long_segment(
        self,
        wav: np.ndarray,
        sr: int,
        start_time: float,
        end_time: float
    ) -> List[AudioSegment]:
        """
        Split a long segment into smaller chunks

        Args:
            wav: Full audio waveform
            sr: Sample rate
            start_time: Segment start time
            end_time: Segment end time

        Returns:
            List of smaller AudioSegment objects
        """
        segments = []
        max_duration = get_vad_config().get_config().max_speech_duration_s

        current_start = start_time
        while current_start < end_time:
            current_end = min(current_start + max_duration, end_time)

            start_sample = int(current_start * sr)
            end_sample = int(current_end * sr)
            segment_audio = wav[start_sample:end_sample]

            segments.append(AudioSegment(
                audio=segment_audio,
                start_time=current_start,
                end_time=current_end,
                sample_rate=sr
            ))

            current_start = current_end

        return segments

    def _simple_split(self, wav: np.ndarray, sr: int) -> List[AudioSegment]:
        """
        Simple time-based audio splitting (fallback when VAD is unavailable)

        Args:
            wav: Audio waveform array
            sr: Sample rate

        Returns:
            List of AudioSegment objects
        """
        segments = []
        segment_duration = get_vad_config().get_config().max_speech_duration_s

        total_duration = len(wav) / sr
        num_segments = int(np.ceil(total_duration / segment_duration))

        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = min(start_time + segment_duration, total_duration)

            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)
            segment_audio = wav[start_sample:end_sample]

            segments.append(AudioSegment(
                audio=segment_audio,
                start_time=start_time,
                end_time=end_time,
                sample_rate=sr
            ))

        return segments

    def save_segment(self, segment: AudioSegment, output_path: str) -> None:
        """
        Save audio segment to WAV file

        Args:
            segment: AudioSegment to save
            output_path: Output file path
        """
        sf.write(output_path, segment.audio, segment.sample_rate)
        logger.debug(f"Saved segment to {output_path}")


# Global VAD service instance
vad_splitter = VADAudioSplitter()
