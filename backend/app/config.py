"""
Configuration module for ASR Server
"""
from pathlib import Path
import os
import torch


class Settings:
    """Application configuration class"""

    # Project root directory
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # Model configuration - select via environment variable
    ASR_MODEL_SIZE = os.getenv("ASR_MODEL_SIZE", "1.7B")  # Options: "0.6B" or "1.7B"

    # Dynamic model path selection based on configuration
    if ASR_MODEL_SIZE == "0.6B":
        ASR_MODEL_PATH = str(BASE_DIR / "models" / "Qwen3-ASR-0.6B")
    else:
        ASR_MODEL_PATH = str(BASE_DIR / "models" / "Qwen3-ASR-1.7B")

    FORCED_ALIGNER_PATH = str(BASE_DIR / "models" / "Qwen3-ForcedAligner-0.6B")

    # Device configuration
    USE_CPU = os.getenv("USE_CPU", "false").lower() == "true"
    DEVICE = "cpu" if USE_CPU else ("cuda:0" if torch.cuda.is_available() else "cpu")

    # Model inference parameters
    DTYPE = os.getenv("DTYPE", "bfloat16")  # Options: "bfloat16", "float16", "float32"
    MAX_INFERENCE_BATCH_SIZE = int(os.getenv("MAX_INFERENCE_BATCH_SIZE", "32"))
    MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "256"))

    # Server configuration
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))

    # File upload configuration
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(500 * 1024 * 1024)))  # 500MB
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
    ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
    ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS

    # Directory configuration
    UPLOAD_DIR = str(BASE_DIR / "uploads")
    TEMP_DIR = str(BASE_DIR / "temp")

    # Audio processing configuration
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_CHANNELS = 1

    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Frontend URL for CORS
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # VAD Configuration
    VAD_ENABLED = os.getenv("VAD_ENABLED", "true").lower() == "true"
    VAD_THRESHOLD_DURATION = float(os.getenv("VAD_THRESHOLD_DURATION", "60"))  # seconds
    VAD_MIN_SILENCE_DURATION_MS = int(os.getenv("VAD_MIN_SILENCE_DURATION_MS", "500"))
    VAD_MAX_SPEECH_DURATION_S = float(os.getenv("VAD_MAX_SPEECH_DURATION_S", "30"))
    VAD_SAMPLE_RATE = int(os.getenv("VAD_SAMPLE_RATE", "16000"))
    VAD_MAX_SEGMENTS = int(os.getenv("VAD_MAX_SEGMENTS", "100"))

    @classmethod
    def get_torch_dtype(cls):
        """Get PyTorch dtype from string"""
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        return dtype_map.get(cls.DTYPE, torch.bfloat16)

    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("=" * 60)
        print("ASR Server Configuration")
        print("=" * 60)
        print(f"Model Size: {cls.ASR_MODEL_SIZE}")
        print(f"ASR Model Path: {cls.ASR_MODEL_PATH}")
        print(f"Forced Aligner Path: {cls.FORCED_ALIGNER_PATH}")
        print(f"Device: {cls.DEVICE}")
        print(f"Dtype: {cls.DTYPE}")
        print(f"Max Batch Size: {cls.MAX_INFERENCE_BATCH_SIZE}")
        print(f"Max New Tokens: {cls.MAX_NEW_TOKENS}")
        print(f"Host: {cls.HOST}")
        print(f"Port: {cls.PORT}")
        print(f"Upload Dir: {cls.UPLOAD_DIR}")
        print(f"Temp Dir: {cls.TEMP_DIR}")
        print(f"VAD Enabled: {cls.VAD_ENABLED}")
        print(f"VAD Threshold Duration: {cls.VAD_THRESHOLD_DURATION}s")
        print("=" * 60)


# Global settings instance
settings = Settings()

if __name__ == "__main__":
    settings.print_config()
