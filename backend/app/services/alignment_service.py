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

            # Perform alignment
            # Convert "auto" to None for Qwen3-ASR (it uses None for auto-detection)
            model_language = None if language == "auto" else language

            words = aligner.align(
                audio_path,
                text,
                language=model_language
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
