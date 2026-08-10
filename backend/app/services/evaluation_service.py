"""
Speech evaluation and scoring service
"""
import time
import io
import tempfile
import os
from typing import Dict, Any
from fastapi import UploadFile
from app.services.asr_service import asr_service
from app.utils import (
    logger,
    compare_texts,
    get_accuracy_level,
    calculate_word_accuracy,
    save_audio,
    load_audio,
    prepare_audio_for_asr,
)
from app.models.domain import EvaluationResult


class EvaluationService:
    """Service for evaluating user speech pronunciation"""

    def evaluate_recording(
        self,
        audio_file: UploadFile,
        target_text: str,
        language: str = "auto"
    ) -> EvaluationResult:
        """
        Evaluate user recording against target text

        Args:
            audio_file: User's audio recording
            target_text: Target text to compare against
            language: Language code

        Returns:
            EvaluationResult with score and diff analysis
        """
        start_time = time.time()

        logger.info(f"Evaluating recording against: {target_text[:50]}...")

        try:
            # Save uploaded audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio.write(audio_file.file.read())
                temp_audio_path = temp_audio.name

            try:
                # Load and prepare audio
                loaded = load_audio(temp_audio_path)
                if loaded is None:
                    raise ValueError("Failed to load audio")
                audio_data, sr = loaded

                # Prepare for ASR (16kHz, mono, normalized)
                prepared_audio = prepare_audio_for_asr(audio_data, sr)

                # Save prepared audio
                prepared_path = temp_audio_path.replace(".wav", ".prepared.wav")
                save_audio(prepared_path, prepared_audio, 16000)

                # Transcribe user audio
                user_transcription = asr_service.transcribe_file(
                    prepared_path,
                    language=language,
                    generate_timestamps=False
                )

                if not user_transcription:
                    raise ValueError("Failed to transcribe user audio")

                user_text = user_transcription.get("text", "")

                # Compare texts
                comparison_result = compare_texts(target_text, user_text)

                # Calculate metrics
                word_metrics = calculate_word_accuracy(target_text, user_text)

                # Get accuracy level
                accuracy_level = get_accuracy_level(comparison_result["score"])

                # Build evaluation result
                evaluation = EvaluationResult(
                    score=comparison_result["score"],
                    accuracy_level=accuracy_level,
                    user_transcript=user_text,
                    target_text=target_text,
                    diff_words=[
                        type("DiffWord", (), {
                            "word": dw["word"],
                            "status": dw["status"],
                            "original_index": dw.get("original_index"),
                            "user_index": dw.get("user_index"),
                            "to_dict": lambda: dw
                        })()
                        for dw in comparison_result["diff_words"]
                    ],
                    correct_count=comparison_result["correct_count"],
                    total_count=comparison_result["total_count"],
                    missing_count=comparison_result["missing_count"],
                    extra_count=comparison_result["extra_count"],
                    accuracy=word_metrics["accuracy"],
                    processing_time=time.time() - start_time
                )

                logger.info(f"Evaluation completed: score={evaluation.score}")
                return evaluation

            finally:
                # Cleanup temp files
                for path in [temp_audio_path, temp_audio_path.replace(".wav", ".prepared.wav")]:
                    if os.path.exists(path):
                        os.remove(path)

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise ValueError(f"Evaluation failed: {str(e)}")

    def evaluate_audio_bytes(
        self,
        audio_bytes: bytes,
        target_text: str,
        language: str = "auto"
    ) -> EvaluationResult:
        """
        Evaluate user audio from bytes

        Args:
            audio_bytes: Audio data as bytes
            target_text: Target text to compare against
            language: Language code

        Returns:
            EvaluationResult with score and diff analysis
        """
        # Create UploadFile-like object from bytes
        from io import BytesIO

        class BytesUploadFile:
            def __init__(self, data: bytes):
                self.file = BytesIO(data)
                self.filename = "recording.wav"
                self.content_type = "audio/wav"

        upload_file = BytesUploadFile(audio_bytes)

        # Delegate to main evaluation method
        return self.evaluate_recording(upload_file, target_text, language)

    def quick_score(self, user_text: str, target_text: str) -> int:
        """
        Calculate quick similarity score (no audio processing)

        Args:
            user_text: User's spoken text
            target_text: Target text

        Returns:
            Score (0-100)
        """
        result = compare_texts(target_text, user_text)
        return result["score"]


# Global evaluation service instance
evaluation_service = EvaluationService()
