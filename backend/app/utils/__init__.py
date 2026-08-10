"""
Utility modules package
"""
from app.utils.logger import logger, setup_logger
from app.utils.file_manager import (
    ensure_directories,
    generate_file_id,
    get_upload_path,
    get_temp_path,
    cleanup_file,
    cleanup_temp_files,
    cleanup_all_temp_files,
    validate_file_size,
    is_valid_extension
)
from app.utils.ffmpeg import (
    check_ffmpeg_available,
    extract_audio,
    get_audio_duration,
    get_media_info,
    convert_audio_format,
    extract_audio_segment,
    check_ffmpeg_on_startup,
    FFmpegError
)
from app.utils.audio import (
    load_audio,
    save_audio,
    prepare_audio_for_asr,
    calculate_audio_duration,
    get_audio_energy
)
from app.utils.text_diff import (
    normalize_text,
    calculate_similarity,
    compare_texts,
    highlight_diff_text,
    get_accuracy_level,
    calculate_word_accuracy
)

__all__ = [
    "logger",
    "setup_logger",
    "ensure_directories",
    "generate_file_id",
    "get_upload_path",
    "get_temp_path",
    "cleanup_file",
    "cleanup_temp_files",
    "cleanup_all_temp_files",
    "validate_file_size",
    "is_valid_extension",
    "check_ffmpeg_available",
    "extract_audio",
    "get_audio_duration",
    "get_media_info",
    "convert_audio_format",
    "extract_audio_segment",
    "check_ffmpeg_on_startup",
    "FFmpegError",
    "load_audio",
    "save_audio",
    "prepare_audio_for_asr",
    "calculate_audio_duration",
    "get_audio_energy",
    "normalize_text",
    "calculate_similarity",
    "compare_texts",
    "highlight_diff_text",
    "get_accuracy_level",
    "calculate_word_accuracy",
]
