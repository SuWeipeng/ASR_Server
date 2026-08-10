"""
ASR model manager - Handles Qwen3-ASR model loading and inference
"""
import torch
from typing import Optional, Dict, Any, List
from pathlib import Path
from app.config import settings
from app.utils.logger import logger


class ASRModelManager:
    """
    Singleton ASR model manager with lazy loading
    """

    _instance = None
    _model = None
    _aligner_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize model manager (models are loaded lazily)"""
        if self._model is None:
            logger.info("ASR Model Manager initialized (models will be loaded on first use)")

    def load_model(self):
        """Load Qwen3-ASR model (lazy loading)"""
        if self._model is not None:
            return self._model

        try:
            logger.info("=" * 60)
            logger.info("Loading Qwen3-ASR Model...")
            logger.info(f"Model Size: {settings.ASR_MODEL_SIZE}")
            logger.info(f"Model Path: {settings.ASR_MODEL_PATH}")
            logger.info(f"Device: {settings.DEVICE}")
            logger.info(f"Dtype: {settings.DTYPE}")

            # Check if model path exists
            if not Path(settings.ASR_MODEL_PATH).exists():
                raise FileNotFoundError(
                    f"Model path not found: {settings.ASR_MODEL_PATH}\n"
                    f"Please ensure the model files are in the models directory."
                )

            # Import qwen_asr library
            from qwen_asr import Qwen3ASRModel, Qwen3ForcedAligner

            # Check if forced aligner path exists
            if not Path(settings.FORCED_ALIGNER_PATH).exists():
                logger.warning(
                    f"Forced aligner path not found: {settings.FORCED_ALIGNER_PATH}\n"
                    f"Timestamp alignment will not be available."
                )
                forced_aligner = None
                forced_aligner_kwargs = None
            else:
                forced_aligner = settings.FORCED_ALIGNER_PATH
                forced_aligner_kwargs = dict(
                    dtype=settings.get_torch_dtype(),
                    device_map=settings.DEVICE,
                    attn_implementation="sdpa",
                )

            # Load model
            self._model = Qwen3ASRModel.from_pretrained(
                settings.ASR_MODEL_PATH,
                dtype=settings.get_torch_dtype(),
                device_map=settings.DEVICE,
                forced_aligner=forced_aligner,
                forced_aligner_kwargs=forced_aligner_kwargs,
                max_inference_batch_size=settings.MAX_INFERENCE_BATCH_SIZE,
                max_new_tokens=settings.MAX_NEW_TOKENS,
            )

            logger.info("✅ Qwen3-ASR Model loaded successfully!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Failed to load ASR model: {e}")
            raise

        return self._model

    @property
    def model(self):
        """Get model instance (lazy loads if necessary)"""
        return self.load_model()

    def transcribe(
        self,
        audio_path: str,
        language: str = "auto",
        generate_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio file

        Args:
            audio_path: Path to audio file (16kHz WAV recommended)
            language: Language code (default: "English")
            generate_timestamps: Whether to generate timestamps (not used, kept for compatibility)

        Returns:
            Dictionary containing:
            - text: Transcribed text
            - timestamps: List of (start, end, word) tuples if available
        """
        try:
            logger.info(f"Transcribing: {audio_path}")

            model = self.model

            # Convert "auto" to None for Qwen3-ASR (it uses None for auto-detection)
            model_language = None if language == "auto" else language

            # Transcribe (Qwen3ASRModel automatically generates timestamps)
            # Note: The qwen-asr library's transcribe() method may not support generate_timestamps parameter
            result = model.transcribe(
                audio_path,
                language=model_language
            )

            logger.info(f"Transcription complete: {len(result.get('text', ''))} characters")

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def transcribe_with_alignment(
        self,
        audio_path: str,
        language: str = "English"
    ) -> List[Dict[str, Any]]:
        """
        Transcribe audio with word-level timestamps

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of word dictionaries with timestamps:
            [
                {"word": "hello", "start": 0.0, "end": 0.5},
                {"word": "world", "start": 0.5, "end": 1.0},
                ...
            ]
        """
        try:
            result = self.transcribe(audio_path, language, generate_timestamps=True)

            # Extract words with timestamps
            words = []
            if "timestamps" in result:
                for start, end, word in result["timestamps"]:
                    words.append({
                        "word": word,
                        "start": start,
                        "end": end
                    })

            return words

        except Exception as e:
            logger.error(f"Transcription with alignment failed: {e}")
            return []

    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None

    def unload_model(self):
        """Unload model from memory"""
        if self._model is not None:
            del self._model
            self._model = None
            torch.cuda.empty_cache()
            logger.info("Model unloaded from memory")


# Global model manager instance
model_manager = ASRModelManager()


def get_asr_model() -> ASRModelManager:
    """
    Get global ASR model manager instance

    Returns:
        ASRModelManager instance
    """
    return model_manager
