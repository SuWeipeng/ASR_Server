"""
FFmpeg wrapper utilities for audio/video processing
"""
import subprocess
import os
import sys
import shutil
import platform
from typing import Optional, Tuple
from app.utils.logger import logger


class FFmpegError(Exception):
    """FFmpeg processing error"""
    pass


def find_ffmpeg_executable() -> Optional[str]:
    """
    Find FFmpeg executable in the system

    Returns:
        Full path to ffmpeg executable, or None if not found
    """
    # Try to find ffmpeg using shutil.which
    ffmpeg_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    ffmpeg_path = shutil.which(ffmpeg_name)

    if ffmpeg_path:
        logger.debug(f"Found FFmpeg in PATH: {ffmpeg_path}")
        return ffmpeg_path

    logger.debug(f"FFmpeg not found in PATH with name '{ffmpeg_name}'")

    # If not found in PATH, try common conda environment paths
    conda_paths = [
        os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "Library", "bin", "ffmpeg.exe"),
        os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "bin", "ffmpeg"),
    ]

    for path in conda_paths:
        logger.debug(f"Checking conda path: {path}")
        if os.path.exists(path):
            logger.debug(f"Found FFmpeg in conda environment: {path}")
            return path

    logger.debug("FFmpeg not found in system")
    return None


def check_ffmpeg_available() -> bool:
    """
    Check if FFmpeg is installed and accessible

    Returns:
        True if FFmpeg is available
    """
    try:
        # First try to find ffmpeg executable
        ffmpeg_path = find_ffmpeg_executable()

        if not ffmpeg_path:
            logger.warning("FFmpeg executable not found in PATH or common locations")
            return False

        # For conda environments on Windows, we need to add Library/bin to PATH
        env = os.environ.copy()
        if "conda" in ffmpeg_path.lower() and platform.system() == "Windows":
            # Add the conda Library/bin directory to PATH for DLL dependencies
            bin_dir = os.path.dirname(ffmpeg_path)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
            logger.debug(f"Added {bin_dir} to PATH for DLL dependencies")

        # Test if it actually works
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env
        )

        if result.returncode == 0:
            logger.info(f"FFmpeg is available: {ffmpeg_path}")
            return True
        else:
            logger.warning(f"FFmpeg found but failed to run")
            logger.warning(f"Return code: {result.returncode}")
            logger.warning(f"Stderr: {result.stderr}")
            logger.warning(f"Stdout: {result.stdout[:200] if result.stdout else 'None'}")
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"FFmpeg check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking FFmpeg: {e}")
        return False


def get_ffmpeg_path() -> str:
    """
    Get FFmpeg executable path

    Returns:
        Path to ffmpeg executable

    Raises:
        FFmpegError: If FFmpeg not found
    """
    ffmpeg_path = find_ffmpeg_executable()
    if not ffmpeg_path:
        raise FFmpegError("FFmpeg not found in system")
    return ffmpeg_path


def get_ffprobe_path() -> str:
    """
    Get FFprobe executable path

    Returns:
        Path to ffprobe executable

    Raises:
        FFmpegError: If FFprobe not found
    """
    # FFprobe is usually in the same directory as FFmpeg
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe").replace("ffmpeg.exe", "ffprobe.exe")

    if not os.path.exists(ffprobe_path):
        # Try using shutil.which as fallback
        ffprobe_name = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
        ffprobe_path = shutil.which(ffprobe_name)

    if not ffprobe_path or not os.path.exists(ffprobe_path):
        raise FFmpegError("FFprobe not found in system")

    return ffprobe_path


def get_ffmpeg_env() -> dict:
    """
    Get environment variables for FFmpeg execution

    Returns:
        Environment variables dict with proper PATH setup
    """
    env = os.environ.copy()

    try:
        ffmpeg_path = find_ffmpeg_executable()
        if ffmpeg_path and "conda" in ffmpeg_path.lower() and platform.system() == "Windows":
            # Add the conda Library/bin directory to PATH for DLL dependencies
            bin_dir = os.path.dirname(ffmpeg_path)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
            logger.debug(f"Using FFmpeg environment with PATH: {bin_dir}")
    except:
        pass  # Use default environment if FFmpeg not found

    return env


def extract_audio(
    input_path: str,
    output_path: str,
    sample_rate: int = 16000,
    channels: int = 1,
    codec: str = "pcm_s16le"
) -> bool:
    """
    Extract audio from video/audio file and convert to WAV format

    Args:
        input_path: Input file path
        output_path: Output WAV file path
        sample_rate: Output sample rate (default: 16000 for ASR)
        channels: Number of audio channels (1 = mono)
        codec: Audio codec (default: pcm_s16le for 16-bit PCM)

    Returns:
        True if successful

    Raises:
        FFmpegError: If FFmpeg processing fails
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        # Get FFmpeg path
        ffmpeg_path = get_ffmpeg_path()

        # Build FFmpeg command
        command = [
            ffmpeg_path,
            "-i", input_path,          # Input file
            "-vn",                      # No video
            "-acodec", codec,           # Audio codec
            "-ar", str(sample_rate),    # Sample rate
            "-ac", str(channels),       # Number of channels
            "-y",                       # Overwrite output
            output_path
        ]

        logger.info(f"Extracting audio: {input_path} -> {output_path}")

        # Run FFmpeg with proper environment
        env = get_ffmpeg_env()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )

        if result.returncode != 0:
            raise FFmpegError(f"FFmpeg error: {result.stderr}")

        # Verify output file exists
        if not os.path.exists(output_path):
            raise FFmpegError(f"Output file not created: {output_path}")

        logger.info(f"Audio extraction complete: {output_path}")
        return True

    except subprocess.TimeoutExpired:
        raise FFmpegError("FFmpeg timeout")
    except Exception as e:
        raise FFmpegError(f"Failed to extract audio: {e}")


def get_audio_duration(file_path: str) -> Optional[float]:
    """
    Get audio/video file duration in seconds using FFprobe

    Args:
        file_path: Path to audio/video file

    Returns:
        Duration in seconds, or None if failed
    """
    try:
        ffprobe_path = get_ffprobe_path()

        command = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]

        env = get_ffmpeg_env()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )

        if result.returncode == 0:
            duration = float(result.stdout.strip())
            logger.debug(f"Duration of {file_path}: {duration:.2f}s")
            return duration

        return None

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        logger.warning(f"Failed to get duration: {file_path}")
        return None


def get_media_info(file_path: str) -> Optional[dict]:
    """
    Get detailed media information using ffprobe

    Args:
        file_path: Path to media file

    Returns:
        Dictionary with media info, or None if failed
    """
    try:
        ffprobe_path = get_ffprobe_path()

        command = [
            ffprobe_path,
            "-v", "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            "stream=codec_type,width,height,channels,sample_rate",
            "-of", "json",
            file_path
        ]

        env = get_ffmpeg_env()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )

        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            logger.debug(f"Media info for {file_path}: {info}")
            return info

        return None

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        logger.warning(f"Failed to get media info: {file_path}")
        return None


def convert_audio_format(
    input_path: str,
    output_path: str,
    output_format: str = "wav",
    sample_rate: int = 16000
) -> bool:
    """
    Convert audio to different format

    Args:
        input_path: Input audio file
        output_path: Output file path
        output_format: Target format (wav, mp3, etc.)
        sample_rate: Output sample rate

    Returns:
        True if successful
    """
    try:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        ffmpeg_path = get_ffmpeg_path()

        command = [
            ffmpeg_path,
            "-i", input_path,
            "-ar", str(sample_rate),
            "-ac", "1",
            "-y",
            output_path
        ]

        env = get_ffmpeg_env()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )

        if result.returncode != 0:
            raise FFmpegError(f"FFmpeg error: {result.stderr}")

        logger.info(f"Audio conversion complete: {output_path}")
        return True

    except Exception as e:
        raise FFmpegError(f"Failed to convert audio: {e}")


def extract_audio_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float
) -> bool:
    """
    Extract a segment of audio

    Args:
        input_path: Input audio file
        output_path: Output file path
        start_time: Start time in seconds
        end_time: End time in seconds

    Returns:
        True if successful
    """
    try:
        duration = end_time - start_time
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        command = [
            "ffmpeg",
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c", "copy",
            "-y",
            output_path
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise FFmpegError(f"FFmpeg error: {result.stderr}")

        logger.debug(f"Extracted audio segment: {start_time:.2f}s - {end_time:.2f}s")
        return True

    except Exception as e:
        raise FFmpegError(f"Failed to extract audio segment: {e}")


def check_ffmpeg_on_startup():
    """Check FFmpeg availability and log warning if not found"""
    if not check_ffmpeg_available():
        logger.error("FFmpeg not found! Please install FFmpeg to use audio/video processing features.")
        logger.error("Download from: https://ffmpeg.org/download.html")
        return False
    logger.info("✅ FFmpeg is available")
    return True
