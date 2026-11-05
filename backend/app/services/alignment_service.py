"""
Forced alignment service for word-level timestamps
"""
import time
from typing import List, Dict, Any, Optional
from app.core import get_aligner
from app.utils import logger


class AlignmentService:
    """Service for forced alignment"""

    def __init__(self):
        self._aligner_manager = None

    @property
    def aligner_manager(self):
        """Get aligner manager (lazy initialization)"""
        if self._aligner_manager is None:
            self._aligner_manager = get_aligner()
        return self._aligner_manager

    def align_text_to_audio(
        self,
        audio_path: str,
        text: str,
        language: str = "auto"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Align text to audio, generating word-level timestamps

        Args:
            audio_path: Path to audio file
            text: Transcript text to align
            language: Language code

        Returns:
            List of word dictionaries with timestamps
        """
        start_time = time.time()

        logger.info(f"Starting alignment: {audio_path}")

        try:
            aligner = self.aligner_manager

            if aligner is None or aligner.aligner is None:
                logger.warning("Aligner not available")
                return None

            # Perform alignment (language normalization handled by the manager)
            words = aligner.align(
                audio_path,
                text,
                language=language
            )

            processing_time = time.time() - start_time

            if words:
                logger.info(f"Alignment completed in {processing_time:.2f}s: {len(words)} words")
            else:
                logger.warning("Alignment returned no results")

            return words

        except Exception as e:
            logger.error(f"Alignment failed: {e}")
            return None

    def refine_alignment(
        self,
        wav,
        sr: int,
        text: str,
        window,
        language: str = "auto"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        在全量音频的指定时间窗口内重对齐文本（紧窗口对齐更稳定）

        Args:
            wav: 全量波形 np.ndarray（mono）
            sr: 采样率
            text: 窗口内语音对应的文本
            window: (win_start, win_end) 秒，相对全量音频
            language: Language code

        Returns:
            词列表 [{"word", "start", "end"}]（全量音频时间坐标），失败返回 None
        """
        import numpy as np

        try:
            aligner = self.aligner_manager
            if aligner is None or aligner.aligner is None:
                logger.warning("Aligner not available for refinement")
                return None

            win_start, win_end = window
            i0 = max(0, int(win_start * sr))
            i1 = min(len(wav), max(i0 + 1, int(win_end * sr)))
            if i1 - i0 < sr * 0.05:  # 窗口短于 50ms，无法对齐
                return None

            seg_wav = np.asarray(wav[i0:i1], dtype=np.float32)

            words = aligner.align_waveform((seg_wav, sr), text, language)
            if not words:
                return None

            offset = i0 / sr
            return [
                {"word": w["word"], "start": w["start"] + offset, "end": w["end"] + offset}
                for w in words
            ]

        except Exception as e:
            logger.warning(f"Refine alignment failed: {e}")
            return None

    def check_aligner_ready(self) -> bool:
        """
        Check if aligner is loaded and ready

        Returns:
            True if aligner is ready
        """
        try:
            aligner = self.aligner_manager
            return aligner is not None and aligner.is_aligner_loaded()
        except Exception as e:
            logger.error(f"Failed to check aligner status: {e}")
            return False

    def get_aligner_info(self) -> Dict[str, Any]:
        """
        Get aligner information

        Returns:
            Aligner information dictionary
        """
        from app.config import settings

        return {
            "aligner_path": settings.FORCED_ALIGNER_PATH,
            "device": settings.DEVICE,
            "loaded": self.check_aligner_ready()
        }


# Global alignment service instance
alignment_service = AlignmentService()
