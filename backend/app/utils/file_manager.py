"""
File and directory management utilities
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from app.config import settings
from app.utils.logger import logger


def ensure_directories():
    """Ensure required directories exist"""
    directories = [settings.UPLOAD_DIR, settings.TEMP_DIR]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    logger.info(f"Directories ensured: {directories}")


def generate_file_id() -> str:
    """Generate unique file ID"""
    return str(uuid.uuid4())


def get_upload_path(file_id: str, extension: str = "") -> str:
    """
    Get upload file path for a file ID

    Args:
        file_id: Unique file identifier
        extension: File extension (e.g., ".mp4")

    Returns:
        Full path to upload file
    """
    filename = f"{file_id}{extension}"
    return str(Path(settings.UPLOAD_DIR) / filename)


def get_temp_path(file_id: str, extension: str = "") -> str:
    """
    Get temp file path for a file ID

    Args:
        file_id: Unique file identifier
        extension: File extension (e.g., ".wav")

    Returns:
        Full path to temp file
    """
    filename = f"{file_id}{extension}"
    return str(Path(settings.TEMP_DIR) / filename)


def cleanup_file(file_path: str):
    """
    Safely remove a file if it exists

    Args:
        file_path: Path to file to remove
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to remove file {file_path}: {e}")


def cleanup_temp_files(older_than_hours: Optional[float] = None):
    """
    Clean up temporary files

    Args:
        older_than_hours: Only delete files older than this many hours.
                         If None, delete all temp files.
    """
    import time
    temp_dir = Path(settings.TEMP_DIR)

    if not temp_dir.exists():
        return

    current_time = time.time()

    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            if older_than_hours is None:
                # Delete all files
                cleanup_file(str(file_path))
            else:
                # Delete only old files
                file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
                if file_age_hours > older_than_hours:
                    cleanup_file(str(file_path))

    logger.info(f"Cleaned up temp files (older_than_hours={older_than_hours})")


def cleanup_all_temp_files():
    """Clean up all temporary files"""
    cleanup_temp_files(older_than_hours=None)


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes

    Args:
        file_path: Path to file

    Returns:
        File size in bytes
    """
    return os.path.getsize(file_path)


def validate_file_size(file_path: str, max_size: int) -> bool:
    """
    Validate file size is within limit

    Args:
        file_path: Path to file
        max_size: Maximum allowed size in bytes

    Returns:
        True if file size is valid
    """
    size = get_file_size(file_path)
    if size > max_size:
        logger.warning(f"File too large: {size} bytes (max: {max_size} bytes)")
        return False
    return True


def is_valid_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Check if file extension is allowed

    Args:
        filename: Name of file
        allowed_extensions: Set of allowed extensions (e.g., {".mp4", ".wav"})

    Returns:
        True if extension is allowed
    """
    return Path(filename).suffix.lower() in allowed_extensions
