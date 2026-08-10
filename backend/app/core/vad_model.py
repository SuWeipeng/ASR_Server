"""
VAD (Voice Activity Detection) model manager - Handles Silero VAD model loading
"""
import torch
from typing import Optional, Callable
from app.config import settings
from app.utils.logger import logger


class VADModelManager:
    """
    Singleton VAD model manager with lazy loading
    Uses Silero VAD model from torch.hub for voice activity detection
    """

    _instance = None
    _vad_model = None
    _vad_utils = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize VAD model manager (model is loaded lazily)"""
        if self._vad_model is None and settings.VAD_ENABLED:
            logger.info("VAD Model Manager initialized (model will be loaded on first use)")

    def load_vad_model(self):
        """
        Load Silero VAD model from torch.hub (lazy loading)

        Returns:
            Tuple of (model, utils) or (None, None) if loading fails
        """
        if self._vad_model is not None:
            return self._vad_model, self._vad_utils

        if not settings.VAD_ENABLED:
            logger.info("VAD is disabled, skipping model loading")
            return None, None

        try:
            logger.info("=" * 60)
            logger.info("Loading Silero VAD Model...")

            # Load Silero VAD model from torch.hub
            self._vad_model, self._vad_utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                verbose=False
            )

            logger.info("✅ Silero VAD Model loaded successfully!")
            logger.info("=" * 60)

        except Exception as e:
            logger.warning(f"Failed to load VAD model: {e}")
            logger.warning("VAD features will use simple time-based splitting as fallback")
            self._vad_model = None
            self._vad_utils = None

        return self._vad_model, self._vad_utils

    @property
    def model(self):
        """Get VAD model instance (lazy loads if necessary)"""
        if self._vad_model is None:
            self.load_vad_model()
        return self._vad_model

    @property
    def utils(self):
        """Get VAD utils instance (lazy loads if necessary)"""
        if self._vad_utils is None:
            self.load_vad_model()
        return self._vad_utils

    def is_model_loaded(self) -> bool:
        """
        Check if VAD model is loaded

        Returns:
            True if model is loaded successfully
        """
        return self._vad_model is not None

    def is_enabled(self) -> bool:
        """
        Check if VAD is enabled

        Returns:
            True if VAD is enabled and available
        """
        return settings.VAD_ENABLED and self.is_model_loaded()

    def unload_model(self):
        """Unload VAD model from memory"""
        if self._vad_model is not None:
            del self._vad_model
            self._vad_model = None
        if self._vad_utils is not None:
            del self._vad_utils
            self._vad_utils = None

        torch.cuda.empty_cache()
        logger.info("VAD Model unloaded from memory")


# Global VAD model manager instance
vad_model_manager = VADModelManager()


def get_vad_model() -> VADModelManager:
    """
    Get global VAD model manager instance

    Returns:
        VADModelManager instance
    """
    return vad_model_manager
