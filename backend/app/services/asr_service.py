"""
ASR (Automatic Speech Recognition) service
"""
import os
import tempfile
import time
from typing import Dict, List, Any, Optional
from app.core import get_asr_model
from app.services.vad_service import vad_splitter, AudioSegment
from app.config import settings
from app.utils import logger


class ASRService:
    """Service for ASR transcription"""

    def __init__(self):
        self._model_manager = None

    @property
    def model_manager(self):
        """Get ASR model manager (lazy initialization)"""
        if self._model_manager is None:
            self._model_manager = get_asr_model()
        return self._model_manager

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,  # 默认 None，自动检测语言
        generate_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio file

        Args:
            audio_path: Path to audio file (16kHz WAV)
            language: Language code
            generate_timestamps: Whether to generate timestamps

        Returns:
            Transcription result dictionary
        """
        start_time = time.time()

        logger.info(f"Starting transcription: {audio_path}")

        try:
            # Get model and transcribe
            # Note: Qwen3ASRModel.transcribe() uses 'return_time_stamps' parameter
            # and returns a list of results, we take the first one
            model = self.model_manager.model

            # Convert "auto" to None for Qwen3-ASR (it uses None for auto-detection)
            model_language = None if language == "auto" else language

            results = model.transcribe(
                audio_path,
                language=model_language,
                return_time_stamps=generate_timestamps
            )

            # Extract first result and convert to dict format
            if results and len(results) > 0:
                result = results[0]
                # Convert to dict format for compatibility
                result_dict = {
                    "text": result.text,
                    "language": result.language if hasattr(result, 'language') else language
                }
                # Add timestamps if available
                if hasattr(result, 'time_stamps') and result.time_stamps:
                    result_dict["timestamps"] = [
                        (ts.start_time, ts.end_time, ts.text)
                        for ts in result.time_stamps
                    ]
                result = result_dict
            else:
                # Fallback to empty result
                result = {"text": "", "language": language}

            processing_time = time.time() - start_time

            logger.info(f"Transcription completed in {processing_time:.2f}s")

            # Add processing time to result
            result["processing_time"] = processing_time

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def transcribe_with_word_timestamps(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Transcribe with word-level timestamps

        Args:
            audio_path: Path to audio file
            language: Language code

        Returns:
            List of word dictionaries with timestamps
        """
        try:
            result = self.transcribe_file(audio_path, language, generate_timestamps=True)

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
            logger.error(f"Word-level transcription failed: {e}")
            return []

    def transcribe_long_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
        generate_timestamps: bool = True,
        use_vad: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe long audio file using VAD-based splitting

        This method splits long audio files into smaller segments to avoid
        GPU memory issues and processes each segment separately.

        Args:
            audio_path: Path to audio file (16kHz WAV)
            language: Language code
            generate_timestamps: Whether to generate timestamps
            use_vad: Whether to use VAD for intelligent splitting

        Returns:
            Transcription result dictionary with combined segments
        """
        start_time = time.time()
        temp_files = []

        try:
            logger.info(f"Starting long audio transcription: {audio_path}")

            # Determine if we should use VAD splitting
            should_use_vad = use_vad and settings.VAD_ENABLED

            if should_use_vad:
                logger.info("Using VAD-based audio splitting")
                # Split audio using VAD
                segments = vad_splitter.split_audio(audio_path)
            else:
                logger.info("VAD disabled, using standard transcription")
                # Use standard transcription for shorter files
                return self.transcribe_file(audio_path, language, generate_timestamps)

            if not segments:
                logger.warning("No audio segments detected")
                return {
                    "text": "",
                    "language": language,
                    "timestamps": [],
                    "processing_time": time.time() - start_time
                }

            logger.info(f"Processing {len(segments)} audio segments")

            # Transcribe each segment
            all_results = []
            for i, segment in enumerate(segments):
                logger.info(f"Transcribing segment {i + 1}/{len(segments)} "
                          f"(duration: {segment.duration:.2f}s)")

                # Save segment to temporary file
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=f"_seg{i}.wav",
                    delete=False
                )
                temp_path = temp_file.name
                temp_files.append(temp_path)
                temp_file.close()

                # Save audio segment
                vad_splitter.save_segment(segment, temp_path)

                try:
                    # Transcribe the segment
                    result = self.transcribe_file(
                        temp_path,
                        language=language,
                        generate_timestamps=generate_timestamps
                    )

                    # Adjust timestamps to account for segment offset
                    if result:
                        adjusted_result = self._adjust_timestamps(
                            result,
                            segment.start_time
                        )
                        all_results.append(adjusted_result)

                except Exception as e:
                    logger.warning(f"Failed to transcribe segment {i + 1}: {e}")
                    # Continue with other segments

            # Merge all segment results
            merged_result = self._merge_results(all_results)

            # Store VAD segments info for subtitle generation
            # This allows subtitle_service to use VAD segments instead of fixed 10s splitting
            if segments:
                merged_result["vad_segments"] = [
                    {
                        "start": seg.start_time,
                        "end": seg.end_time,
                        "duration": seg.duration
                    }
                    for seg in segments
                ]

            processing_time = time.time() - start_time

            logger.info(f"Long audio transcription completed in {processing_time:.2f}s")

            # Add processing time to result
            merged_result["processing_time"] = processing_time
            merged_result["num_segments"] = len(segments)

            return merged_result

        except Exception as e:
            logger.error(f"Long audio transcription failed: {e}")
            raise

        finally:
            # Clean up temporary files
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        logger.debug(f"Cleaned up temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

    def _adjust_timestamps(self, result: Dict[str, Any], offset: float) -> Dict[str, Any]:
        """
        Adjust timestamps in transcription result by adding offset

        Args:
            result: Transcription result
            offset: Time offset in seconds to add

        Returns:
            Adjusted transcription result
        """
        adjusted = result.copy()

        # Adjust word-level timestamps
        if "timestamps" in adjusted and adjusted["timestamps"]:
            adjusted_timestamps = []
            for start, end, word in adjusted["timestamps"]:
                adjusted_timestamps.append((start + offset, end + offset, word))
            adjusted["timestamps"] = adjusted_timestamps

        return adjusted

    def _merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple transcription results into one

        Args:
            results: List of transcription results

        Returns:
            Merged transcription result
        """
        if not results:
            return {
                "text": "",
                "timestamps": [],
                "language": "auto"
            }

        # Combine all text
        combined_text = " ".join(
            result.get("text", "") for result in results
        )

        # Combine all timestamps
        combined_timestamps = []
        for i, result in enumerate(results):
            if "timestamps" in result and result["timestamps"]:
                logger.info(f"[MERGE] Segment {i} has {len(result['timestamps'])} timestamps")
                combined_timestamps.extend(result["timestamps"])

        logger.info(f"[MERGE] Total combined timestamps: {len(combined_timestamps)}")

        # Use language from first result (or auto if not detected)
        language = results[0].get("language", "auto")

        return {
            "text": combined_text,
            "timestamps": combined_timestamps,
            "language": language
        }

    def check_model_ready(self) -> bool:
        """
        Check if ASR model is loaded and ready

        Returns:
            True if model is ready
        """
        try:
            return self.model_manager.is_model_loaded()
        except Exception as e:
            logger.error(f"Failed to check model status: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information

        Returns:
            Model information dictionary
        """
        from app.config import settings

        return {
            "model_size": settings.ASR_MODEL_SIZE,
            "model_path": settings.ASR_MODEL_PATH,
            "device": settings.DEVICE,
            "dtype": settings.DTYPE,
            "loaded": self.check_model_ready()
        }


# Global ASR service instance
asr_service = ASRService()
