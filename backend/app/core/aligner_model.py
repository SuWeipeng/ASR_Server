"""
Forced Aligner model manager - Handles word-level timestamp alignment
"""
import torch
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import settings
from app.utils.logger import logger


def normalize_align_language(language: Optional[str]) -> str:
    """
    规整 aligner 的语言参数

    Qwen3ForcedAligner 的 encode_timestamp 对 language 直接调 .lower()，
    None 会崩溃；"auto"/空串落入库的通用分词分支（中英混排均可用）。
    """
    if language is None or language == "" or language == "auto":
        return "auto"
    return language


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

            results = aligner.align(
                audio_path,
                text,
                language=normalize_align_language(language)
            )

            words = self._parse_align_results(results)

            logger.info(f"Alignment complete: {len(words)} words")
            return words

        except Exception as e:
            logger.error(f"Alignment failed: {e}")
            return None

    def align_waveform(
        self,
        waveform: Any,
        text: str,
        language: str = "auto"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Align text to an in-memory waveform, avoiding temporary files

        Args:
            waveform: (np.ndarray, sample_rate) tuple
            text: Transcript text to align
            language: Language code

        Returns:
            List of word dictionaries with timestamps, or None if failed
        """
        try:
            aligner = self.aligner
            if aligner is None:
                logger.warning("Aligner not available")
                return None

            results = aligner.align(
                waveform,
                text,
                language=normalize_align_language(language)
            )

            return self._parse_align_results(results)

        except Exception as e:
            logger.error(f"Waveform alignment failed: {e}")
            return None

    @staticmethod
    def _parse_align_results(results: Any) -> List[Dict[str, Any]]:
        """
        Parse aligner output into word dictionaries

        aligner.align() returns List[ForcedAlignResult]; each result is
        iterable over items with .text / .start_time / .end_time
        """
        words: List[Dict[str, Any]] = []
        if not results:
            return words
        for item in results[0]:
            words.append({
                "word": item.text,
                "start": float(item.start_time),
                "end": float(item.end_time),
                "score": 1.0,
            })
        return words

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
