"""
Waveform generation service for audio visualization
"""
import os
import numpy as np
from typing import Dict, List, Optional, Tuple
from app.utils import logger
from app.services.media_service import media_service
import librosa


class WaveformService:
    """Service for generating waveform visualization data"""

    def __init__(self):
        self._cache = {}

    def get_waveform_data(
        self,
        file_id: str,
        start_time: float = 0,
        end_time: Optional[float] = None,
        num_points: int = 500
    ) -> Optional[Dict]:
        """
        Generate waveform data for visualization

        Args:
            file_id: Media file ID
            start_time: Start time in seconds
            end_time: End time in seconds (None for full duration)
            num_points: Number of data points to generate

        Returns:
            Dictionary with amplitude and optionally pitch data
        """
        try:
            # Check cache
            cache_key = f"{file_id}_{start_time}_{end_time}_{num_points}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Get media file info
            media_file = media_service.get_file(file_id)
            if not media_file:
                logger.error(f"Media file not found: {file_id}")
                return None

            # Get audio file path
            if media_file.file_type == 'video':
                audio_path = media_service.extract_audio_from_media(file_id)
            else:
                audio_path = media_file.file_path

            if not audio_path or not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return None

            # Load audio with librosa
            y, sr = librosa.load(audio_path, sr=None, offset=start_time, duration=end_time - start_time if end_time else None)

            # Generate amplitude waveform
            amplitude_data = self._generate_amplitude_waveform(y, num_points)

            # Generate pitch contour (basic version)
            pitch_data = self._generate_pitch_contour(y, sr, num_points)

            result = {
                'amplitude': amplitude_data,
                'pitch': pitch_data,
                'sample_rate': sr,
                'duration': len(y) / sr,
                'num_points': num_points
            }

            # Cache the result (limit cache size)
            if len(self._cache) > 50:
                self._cache.clear()
            self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Failed to generate waveform data: {e}")
            return None

    def _generate_amplitude_waveform(self, audio: np.ndarray, num_points: int) -> List[float]:
        """
        Generate amplitude waveform data

        Args:
            audio: Audio data array
            num_points: Number of data points

        Returns:
            List of amplitude values (normalized -1 to 1)
        """
        # Calculate frame length
        frame_length = len(audio) // num_points

        # Reshape into frames and calculate RMS for each frame
        if frame_length > 0:
            frames = audio[:frame_length * num_points].reshape(-1, frame_length)
            # Calculate RMS (root mean square) for amplitude
            amplitudes = np.sqrt(np.mean(frames ** 2, axis=1))
            # Normalize to -1 to 1 range
            if np.max(amplitudes) > 0:
                amplitudes = amplitudes / np.max(amplitudes)
            return amplitudes.tolist()
        else:
            return [0.0] * num_points

    def _generate_pitch_contour(self, audio: np.ndarray, sr: int, num_points: int) -> List[Optional[float]]:
        """
        Generate pitch contour using librosa's pitch detection

        Args:
            audio: Audio data array
            sr: Sample rate
            num_points: Number of data points

        Returns:
            List of pitch values in Hz (None for unvoiced frames)
        """
        try:
            # Extract pitch using librosa's pyin
            pitches, voiced_mask, _ = librosa.pyin(
                audio,
                fmin=librosa.note_to_hz('C2'),  # ~65 Hz
                fmax=librosa.note_to_hz('C7'),   # ~2093 Hz
                sr=sr,
                frame_length=2048,
                hop_length=512
            )

            # Resample to desired number of points
            if len(pitches) > num_points:
                # Downsample
                indices = np.linspace(0, len(pitches) - 1, num_points).astype(int)
                pitches = pitches[indices]
            elif len(pitches) < num_points:
                # Upsample
                pitches = np.interp(
                    np.linspace(0, len(pitches) - 1, num_points),
                    np.arange(len(pitches)),
                    pitches
                )

            # Replace NaN with None
            return [float(p) if not np.isnan(p) else None for p in pitches]

        except Exception as e:
            logger.warning(f"Pitch detection failed: {e}")
            return [None] * num_points

    def clear_cache(self):
        """Clear the waveform cache"""
        self._cache.clear()


# Global waveform service instance
waveform_service = WaveformService()
