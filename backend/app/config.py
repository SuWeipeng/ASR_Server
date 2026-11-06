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
    VAD_SPEECH_PAD_MS = int(os.getenv("VAD_SPEECH_PAD_MS", "200"))  # 语音段边界向外填充
    VAD_MAX_MERGE_GAP_S = float(os.getenv("VAD_MAX_MERGE_GAP_S", "0.5"))  # 相邻语音段合并的最大间隔

    # Subtitle segmentation
    SUBTITLE_MAX_SEGMENT_DURATION = float(os.getenv("SUBTITLE_MAX_SEGMENT_DURATION", "10"))  # 秒，超长句二次切分阈值

    # Subtitle sync repair（退化段时间戳修复，补偿 aligner 在长窗口上的漂移）
    # 注意：以下 SYNC_REPAIR_* 值现仅作 sync_repair_config.json 的首次种子
    # （运行时配置走设置页 /api/sync-repair/config，改 env 需删 JSON 并重启才生效）
    SUBTITLE_SYNC_REPAIR = os.getenv("SUBTITLE_SYNC_REPAIR", "true").lower() == "true"
    SYNC_REPAIR_MAX_WORD_DUR = float(os.getenv("SYNC_REPAIR_MAX_WORD_DUR", "1.5"))  # 单词时长超过此值视为退化（秒）
    SYNC_REPAIR_SPEECH_RATIO = float(os.getenv("SYNC_REPAIR_SPEECH_RATIO", "0.35"))  # 段区间语音帧占比低于此值视为退化
    SYNC_REPAIR_SNAP_WINDOW = float(os.getenv("SYNC_REPAIR_SNAP_WINDOW", "0.7"))  # 起点静音吸附的最大前移距离（秒）
    # 2026-11-06 重构：健康锚定 + 局部重探测（替换全局 DP 预算重排）。
    # 语速上下限同时用于健康判定与候选窗可行性——判健康即冻结，保证重跑幂等。
    SYNC_REPAIR_RATE_LO = float(os.getenv("SYNC_REPAIR_RATE_LO", "4"))   # chars/s 低于视为拖沓/铺静音
    SYNC_REPAIR_RATE_HI = float(os.getenv("SYNC_REPAIR_RATE_HI", "34"))  # chars/s 高于视为挤扁/错位
    SYNC_REPAIR_SEARCH_S = float(os.getenv("SYNC_REPAIR_SEARCH_S", "12"))   # 候选窗搜索半径（秒）
    SYNC_REPAIR_MERGE_GAP = float(os.getenv("SYNC_REPAIR_MERGE_GAP", "1.2"))  # 候选窗内相邻单元最大桥接间隔（秒）
    SYNC_REPAIR_MIN_ISLAND_W = float(os.getenv("SYNC_REPAIR_MIN_ISLAND_W", "0.12"))  # 参与候选/回收的最小单元宽（秒，短感叹词岛 ~0.15s 也要能成为候选）
    # demucs 后带通（P2）：对人声做温和语音频段带通再喂 ASR/修复。探针 A/B
    # （probe_sync_truth.py，01_part1 18 窗）显示电话频段(450-3100)会丢词、
    # 语音频段(80-5500)与 raw 持平——默认关闭，仅特殊素材需要时打开。
    SYNC_REPAIR_BANDPASS = os.getenv("SYNC_REPAIR_BANDPASS", "false").lower() == "true"
    SYNC_REPAIR_BANDPASS_LO = float(os.getenv("SYNC_REPAIR_BANDPASS_LO", "80"))   # Hz
    SYNC_REPAIR_BANDPASS_HI = float(os.getenv("SYNC_REPAIR_BANDPASS_HI", "5500"))  # Hz

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
