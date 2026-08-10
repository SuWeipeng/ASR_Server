"""
Forced Aligner model manager - Handles word-level timestamp alignment
"""
import torch
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import settings
from app.utils.logger import logger


class AlignerModelManager:
    """
    Singleton forced aligner model manager
    """

    _instance = None
    _aligner_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize aligner manager"""
        if self._aligner_model is None:
            logger.info("Aligner Model Manager initialized")

    def load_aligner(self):
        """Load forced aligner model"""
        if self._aligner_model is not None:
            return self._aligner_model

        try:
            logger.info("Loading Forced Aligner Model...")
            logger.info(f"Aligner Path: {settings.FORCED_ALIGNER_PATH}")

            # Check if aligner path exists
            if not Path(settings.FORCED_ALIGNER_PATH).exists():
                raise FileNotFoundError(
                    f"Forced aligner path not found: {settings.FORCED_ALIGNER_PATH}"
                )

            # Import aligner
            from qwen_asr import Qwen3ForcedAligner

            # Load aligner
            self._aligner_model = Qwen3ForcedAligner.from_pretrained(
                settings.FORCED_ALIGNER_PATH,
                dtype=settings.get_torch_dtype(),
                device_map=settings.DEVICE,
            )

            logger.info("✅ Forced Aligner loaded successfully!")

        except Exception as e:
            logger.error(f"Failed to load aligner: {e}")
            self._aligner_model = None

        return self._aligner_model

    @property
    def aligner(self):
        """Get aligner instance (lazy loads if necessary)"""
        return self.load_aligner()

    def align(
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
            List of word dictionaries with timestamps, or None if failed
        """
        try:
            aligner = self.aligner
            if aligner is None:
                logger.warning("Aligner not available, using timestamps from ASR instead")
                return None

            logger.info(f"Aligning text to audio: {audio_path}")

            # Convert "auto" to None for Qwen3-ASR (it uses None for auto-detection)
            model_language = None if language == "auto" else language

            # Perform alignment
            result = aligner.align(
                audio_path,
                text,
                language=model_language
            )

            # Format result
            words = []
            if result and "segments" in result:
                for segment in result["segments"]:
                    for word_info in segment.get("words", []):
                        words.append({
                            "word": word_info.get("word", ""),
                            "start": word_info.get("start", 0.0),
                            "end": word_info.get("end", 0.0),
                            "score": word_info.get("score", 1.0)
                        })

            logger.info(f"Alignment complete: {len(words)} words")
            return words

        except Exception as e:
            logger.error(f"Alignment failed: {e}")
            return None

    def is_aligner_loaded(self) -> bool:
        """Check if aligner is loaded"""
        return self._aligner_model is not None

    def unload_aligner(self):
        """Unload aligner from memory"""
        if self._aligner_model is not None:
            del self._aligner_model
            self._aligner_model = None
            torch.cuda.empty_cache()
            logger.info("Aligner unloaded from memory")


# Global aligner manager instance
aligner_manager = AlignerModelManager()


def get_aligner() -> Optional[AlignerModelManager]:
    """
    Get global aligner manager instance

    Returns:
        AlignerModelManager instance or None if not available
    """
    return aligner_manager
