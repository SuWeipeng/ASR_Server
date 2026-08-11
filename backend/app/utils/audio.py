"""
Audio processing utilities
"""
import os
import tempfile
import numpy as np
import soundfile as sf
from typing import Tuple, Optional
from app.utils.logger import logger


def load_audio(file_path: str) -> Optional[Tuple[np.ndarray, int]]:
    """
    Load audio file using soundfile.

    Falls back to ffmpeg-based conversion when soundfile cannot decode the
    file directly. This is required for browser MediaRecorder output, which
    is typically WebM/Opus or Ogg/Opus regardless of the client-declared
    MIME type (the frontend may label it as ``audio/wav`` even though the
    container is not RIFF/WAVE).

    Args:
        file_path: Path to audio file

    Returns:
        Tuple of (audio_data, sample_rate) or None if failed
    """
    try:
        audio, sr = sf.read(file_path)
        logger.debug(f"Loaded audio: {file_path}, shape={audio.shape}, sr={sr}")
        return audio, sr
    except Exception as e:
        logger.warning(
            f"soundfile could not decode {file_path} ({e}); "
            f"attempting ffmpeg fallback"
        )

    converted_path = None
    try:
        from app.utils.ffmpeg import check_ffmpeg_available, convert_audio_format

        if not check_ffmpeg_available():
            logger.error(
                f"Failed to load audio {file_path}: soundfile failed and "
                f"ffmpeg is not available"
            )
            return None

        fd, converted_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        convert_audio_format(file_path, converted_path, "wav", 16000)

        audio, sr = sf.read(converted_path)
        logger.info(
            f"Loaded audio via ffmpeg fallback: {file_path} -> "
            f"{converted_path}, shape={audio.shape}, sr={sr}"
        )
        return audio, sr
    except Exception as e:
        logger.error(f"Failed to load audio {file_path}: {e}")
        return None
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except OSError:
                pass


def resample_audio(
    audio: np.ndarray,
    original_sr: int,
    target_sr: int
) -> np.ndarray:
    """
    Resample audio to target sample rate

    Args:
        audio: Audio data numpy array
        original_sr: Original sample rate
        target_sr: Target sample rate

    Returns:
        Resampled audio array
    """
    if original_sr == target_sr:
        return audio

    try:
        import resampy
        audio_resampled = resampy.resample(audio, original_sr, target_sr)
        logger.debug(f"Resampled audio: {original_sr}Hz -> {target_sr}Hz")
        return audio_resampled
    except ImportError:
        # Fallback to simple interpolation
        logger.warning("resampy not available, using simple interpolation")
        from scipy import signal
        number_of_samples = round(len(audio) * float(target_sr) / original_sr)
        audio_resampled = signal.resample(audio, number_of_samples)
        return audio_resampled


def convert_to_mono(audio: np.ndarray) -> np.ndarray:
    """
    Convert stereo audio to mono by averaging channels

    Args:
        audio: Audio data (may be stereo)

    Returns:
        Mono audio data
    """
    if len(audio.shape) == 1:
        return audio

    # Average channels
    mono_audio = np.mean(audio, axis=1)
    logger.debug("Converted to mono")
    return mono_audio


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """
    Normalize audio to [-1, 1] range

    Args:
        audio: Audio data

    Returns:
        Normalized audio
    """
    max_value = np.max(np.abs(audio))
    if max_value > 0:
        audio = audio / max_value
    return audio


def calculate_audio_duration(audio: np.ndarray, sample_rate: int) -> float:
    """
    Calculate audio duration in seconds

    Args:
        audio: Audio data
        sample_rate: Sample rate

    Returns:
        Duration in seconds
    """
    return len(audio) / sample_rate


def save_audio(
    file_path: str,
    audio: np.ndarray,
    sample_rate: int
) -> bool:
    """
    Save audio to file

    Args:
        file_path: Output file path
        audio: Audio data
        sample_rate: Sample rate

    Returns:
        True if successful
    """
    try:
        sf.write(file_path, audio, sample_rate)
        logger.debug(f"Saved audio: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save audio {file_path}: {e}")
        return False


def prepare_audio_for_asr(
    audio: np.ndarray,
    original_sr: int,
    target_sr: int = 16000
) -> np.ndarray:
    """
    Prepare audio for ASR model:
    1. Convert to mono if stereo
    2. Resample to target sample rate
    3. Normalize

    Args:
        audio: Audio data
        original_sr: Original sample rate
        target_sr: Target sample rate (default: 16000)

    Returns:
        Prepared audio array
    """
    # Convert to mono
    audio = convert_to_mono(audio)

    # Resample if needed
    if original_sr != target_sr:
        audio = resample_audio(audio, original_sr, target_sr)

    # Normalize
    audio = normalize_audio(audio)

    return audio


def audio_to_float32(audio: np.ndarray) -> np.ndarray:
    """
    Convert audio to float32 format

    Args:
        audio: Audio array

    Returns:
        Float32 audio array
    """
    return audio.astype(np.float32)


def get_audio_energy(audio: np.ndarray) -> float:
    """
    Calculate RMS energy of audio signal

    Args:
        audio: Audio data

    Returns:
        RMS energy value
    """
    return np.sqrt(np.mean(audio ** 2))


def detect_silence(
    audio: np.ndarray,
    threshold: float = 0.01,
    min_silence_duration: float = 0.5,
    sample_rate: int = 16000
) -> list:
    """
    Detect silent segments in audio

    Args:
        audio: Audio data
        threshold: Energy threshold for silence detection
        min_silence_duration: Minimum silence duration in seconds
        sample_rate: Sample rate

    Returns:
        List of (start, end) silent segments
    """
    min_samples = int(min_silence_duration * sample_rate)
    silence_segments = []
    is_silent = False
    start_idx = 0

    for i in range(0, len(audio), sample_rate // 10):  # Check every 0.1s
        segment = audio[i:i + sample_rate // 10]
        energy = get_audio_energy(segment)

        if energy < threshold:
            if not is_silent:
                is_silent = True
                start_idx = i
        else:
            if is_silent:
                duration = (i - start_idx) / sample_rate
                if duration >= min_silence_duration:
                    silence_segments.append((
                        start_idx / sample_rate,
                        i / sample_rate
                    ))
                is_silent = False

    return silence_segments


def apply_bandpass_filter(
    data: np.ndarray,
    lowcut: int,
    highcut: int,
    fs: int,
    order: int = 4
) -> np.ndarray:
    """
    Apply Butterworth bandpass filter to audio data

    This removes frequencies outside the human speech range (300-3400 Hz),
    effectively eliminating low-frequency noise (fans, hum) and high-frequency
    noise (hiss, electronic interference).

    Args:
        data: Audio waveform array
        lowcut: Low frequency cutoff in Hz (frequencies below this are removed)
        highcut: High frequency cutoff in Hz (frequencies above this are removed)
        fs: Sample rate in Hz
        order: Filter order (higher = steeper cutoff, but more computation)

    Returns:
        Filtered audio array
    """
    from scipy import signal

    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq

    # Design Butterworth bandpass filter
    b, a = signal.butter(order, [low, high], btype='band')

    # Apply filter using lfilter (forward filter)
    y = signal.lfilter(b, a, data)

    return y


def apply_highpass_filter(
    data: np.ndarray,
    cutoff: int,
    fs: int,
    order: int = 4
) -> np.ndarray:
    """
    Apply Butterworth highpass filter to remove low-frequency noise

    Args:
        data: Audio waveform array
        cutoff: Cutoff frequency in Hz (frequencies below this are removed)
        fs: Sample rate in Hz
        order: Filter order

    Returns:
        Filtered audio array
    """
    from scipy import signal

    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq

    b, a = signal.butter(order, normal_cutoff, btype='high')
    y = signal.lfilter(b, a, data)

    return y


def apply_lowpass_filter(
    data: np.ndarray,
    cutoff: int,
    fs: int,
    order: int = 4
) -> np.ndarray:
    """
    Apply Butterworth lowpass filter to remove high-frequency noise

    Args:
        data: Audio waveform array
        cutoff: Cutoff frequency in Hz (frequencies above this are removed)
        fs: Sample rate in Hz
        order: Filter order

    Returns:
        Filtered audio array
    """
    from scipy import signal

    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq

    b, a = signal.butter(order, normal_cutoff, btype='low')
    y = signal.lfilter(b, a, data)

    return y


def apply_noise_reduction(
    data: np.ndarray,
    fs: int,
    enabled: bool = True,
    lowcut: int = 200,
    highcut: int = 3500,
    order: int = 4,
    filter_type: str = "bandpass",
    normalize_after_filter: bool = True
) -> np.ndarray:
    """
    Apply noise reduction using traditional signal processing (Butterworth filter)

    This is effective for mild background noise like fans, hum, and white noise.
    It operates entirely offline with minimal computational overhead.

    Args:
        data: Audio waveform array
        fs: Sample rate in Hz
        enabled: Whether to apply noise reduction
        lowcut: Low frequency cutoff in Hz
        highcut: High frequency cutoff in Hz
        order: Filter order (1-8, higher = steeper but more computation)
        filter_type: Type of filter - "bandpass", "highpass", or "lowpass"
        normalize_after_filter: Whether to normalize audio after filtering

    Returns:
        Processed audio array (original if disabled or error occurs)
    """
    if not enabled:
        return data

    try:
        logger.info(
            f"Applying noise reduction: type={filter_type}, "
            f"lowcut={lowcut}Hz, highcut={highcut}Hz, order={order}"
        )

        # Apply appropriate filter
        if filter_type == "bandpass":
            filtered = apply_bandpass_filter(data, lowcut, highcut, fs, order)
        elif filter_type == "highpass":
            filtered = apply_highpass_filter(data, lowcut, fs, order)
        elif filter_type == "lowpass":
            filtered = apply_lowpass_filter(data, highcut, fs, order)
        else:
            logger.warning(f"Unknown filter type: {filter_type}, using bandpass")
            filtered = apply_bandpass_filter(data, lowcut, highcut, fs, order)

        # Normalize after filtering if requested
        if normalize_after_filter:
            filtered = normalize_audio(filtered)
            logger.debug("Normalized audio after noise reduction")

        logger.info("Noise reduction applied successfully")
        return filtered

    except Exception as e:
        logger.error(f"Noise reduction failed: {e}, returning original audio")
        return data
