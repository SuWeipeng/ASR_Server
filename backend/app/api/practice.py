"""
Practice and evaluation API routes
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.services.evaluation_service import evaluation_service
from app.models.schemas import (
    PracticeEvaluateRequest,
    PracticeEvaluateResponse,
    MessageResponse,
)
from app.utils import logger

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.post("/evaluate", response_model=PracticeEvaluateResponse)
async def evaluate_practice(
    audio: UploadFile = File(..., description="User audio recording (WAV format)"),
    target_text: str = Form(..., description="Target text to compare against"),
    language: str = Form("auto", description="Language code")
):
    """
    Evaluate user's speech against target text

    Returns:
    - score: Similarity score (0-100)
    - accuracy_level: Description (优秀/良好/及格/需改进)
    - user_transcript: What the user said
    - diff_words: Word-by-word comparison
    """
    try:
        logger.info(f"Evaluating practice, target: {target_text[:50]}...")

        # Evaluate
        result = evaluation_service.evaluate_recording(
            audio_file=audio,
            target_text=target_text,
            language=language
        )

        # Convert to response format
        from app.models.schemas import DiffWordResult

        diff_words_response = [
            DiffWordResult(
                word=dw.word,
                status=dw.status,
                original_index=dw.original_index,
                user_index=dw.user_index
            )
            for dw in result.diff_words
        ]

        return PracticeEvaluateResponse(
            success=True,
            score=result.score,
            accuracy_level=result.accuracy_level,
            user_transcript=result.user_transcript,
            target_text=result.target_text,
            diff_words=diff_words_response,
            metrics={
                "correct_count": result.correct_count,
                "total_count": result.total_count,
                "missing_count": result.missing_count,
                "extra_count": result.extra_count,
                "accuracy": result.accuracy
            },
            processing_time=result.processing_time,
            message="Evaluation completed"
        )

    except ValueError as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-score")
async def quick_score(
    user_text: str = Form(..., description="User's spoken text"),
    target_text: str = Form(..., description="Target text")
):
    """
    Quick text-to-text comparison (no audio processing)

    Useful for:
    - Testing without audio
    - Comparing ASR results
    - Manual scoring
    """
    try:
        score = evaluation_service.quick_score(user_text, target_text)

        return {
            "success": True,
            "score": score,
            "message": "Quick score calculated"
        }

    except Exception as e:
        logger.error(f"Quick score failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=MessageResponse)
async def practice_health_check():
    """
    Check if practice/evaluation service is healthy
    """
    from app.services.asr_service import asr_service

    is_ready = asr_service.check_model_ready()

    return MessageResponse(
        success=is_ready,
        message="Ready" if is_ready else "Model not loaded"
    )
