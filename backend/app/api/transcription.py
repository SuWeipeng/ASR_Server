"""
Transcription and subtitle generation API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from typing import Optional
from pathlib import Path

from app.services.subtitle_service import subtitle_service
from app.services.media_service import media_service
from app.services.cache_service import cache_service
from app.core import get_vad_model
from app.config import settings
from app.models.schemas import (
    TranscriptionGenerateRequest,
    TranscriptionGenerateResponse,
    SubtitleSearchRequest,
    SubtitleSearchResponse,
    ErrorResponse,
)
from app.utils import logger

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

# In-memory storage for transcription results (deprecated - use cache_service)
_transcription_cache = {}


@router.post("/generate", response_model=TranscriptionGenerateResponse)
async def generate_subtitles(
    request: TranscriptionGenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate subtitles from media file

    This will:
    1. Extract audio from video if needed
    2. Transcribe using Qwen3-ASR
    3. Generate word-level timestamps (if aligner available)
    4. Return subtitle segments
    """
    try:
        logger.info(f"Generating subtitles for file: {request.file_id}")

        # Verify file exists
        media_file = media_service.get_file(request.file_id)
        if not media_file:
            raise HTTPException(status_code=404, detail="File not found")

        # Generate subtitles
        result = subtitle_service.generate_subtitles(
            file_id=request.file_id,
            language=request.language.value,
            use_alignment=True,
            use_vad=request.use_vad,
            force_refresh=request.force_refresh
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate subtitles"
            )

        # Cache result
        _transcription_cache[request.file_id] = result

        # Convert to response format
        from app.models.schemas import SubtitleSegment as SubtitleSegmentSchema

        segments_schema = [
            SubtitleSegmentSchema(
                id=seg.id,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=[
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence
                    }
                    for w in seg.words
                ] if seg.words else None,
                translation=seg.translation
            )
            for seg in result.segments
        ]

        return TranscriptionGenerateResponse(
            success=True,
            file_id=result.file_id,
            language=result.language,
            segments=segments_schema,
            full_text=result.full_text,
            duration=result.duration,
            processing_time=result.processing_time,
            message="Subtitles generated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subtitle generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subtitles/{file_id}", response_model=TranscriptionGenerateResponse)
async def get_subtitles(file_id: str):
    """
    Get cached subtitles for a file
    """
    result = _transcription_cache.get(file_id)

    if not result:
        raise HTTPException(status_code=404, detail="Subtitles not found. Please generate first.")

    # Convert to response format
    from app.models.schemas import SubtitleSegment as SubtitleSegmentSchema

    segments_schema = [
        SubtitleSegmentSchema(
            id=seg.id,
            start=seg.start,
            end=seg.end,
            text=seg.text,
            words=[
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "confidence": w.confidence
                }
                for w in seg.words
            ] if seg.words else None,
            translation=seg.translation
        )
        for seg in result.segments
    ]

    return TranscriptionGenerateResponse(
        success=True,
        file_id=result.file_id,
        language=result.language,
        segments=segments_schema,
        full_text=result.full_text,
        duration=result.duration,
        processing_time=result.processing_time,
        message="Subtitles retrieved"
    )


@router.post("/search/{file_id}", response_model=SubtitleSearchResponse)
async def search_subtitles(file_id: str, request: SubtitleSearchRequest):
    """
    Search within subtitles
    """
    result = _transcription_cache.get(file_id)

    if not result:
        raise HTTPException(status_code=404, detail="Subtitles not found")

    # Search
    from app.models.schemas import SubtitleSegment as SubtitleSegmentSchema

    matched_segments = subtitle_service.search_subtitles(
        result.segments,
        request.query,
        case_sensitive=False
    )

    segments_schema = [
        SubtitleSegmentSchema(
            id=seg.id,
            start=seg.start,
            end=seg.end,
            text=seg.text,
            words=None,
            translation=seg.translation
        )
        for seg in matched_segments
    ]

    return SubtitleSearchResponse(
        success=True,
        query=request.query,
        results=segments_schema,
        total_count=len(matched_segments)
    )


@router.get("/export/{file_id}")
async def export_subtitles(
    file_id: str,
    format: str = "srt"
):
    """
    Export subtitles to file

    Formats: srt, vtt
    """
    result = _transcription_cache.get(file_id)

    if not result:
        raise HTTPException(status_code=404, detail="Subtitles not found")

    # Generate export
    if format.lower() == "srt":
        content = subtitle_service.export_srt(result.segments)
        media_type = "text/plain"
        filename = f"subtitles_{file_id}.srt"
    elif format.lower() == "vtt":
        content = subtitle_service.export_vtt(result.segments)
        media_type = "text/vtt"
        filename = f"subtitles_{file_id}.vtt"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/vad/status")
async def get_vad_status():
    """
    Get VAD (Voice Activity Detection) system status

    Returns information about VAD configuration and model status
    """
    try:
        vad_manager = get_vad_model()

        return {
            "vad_enabled": settings.VAD_ENABLED,
            "vad_model_loaded": vad_manager.is_model_loaded(),
            "threshold_duration": settings.VAD_THRESHOLD_DURATION,
            "min_silence_duration_ms": settings.VAD_MIN_SILENCE_DURATION_MS,
            "max_speech_duration_s": settings.VAD_MAX_SPEECH_DURATION_S,
            "sample_rate": settings.VAD_SAMPLE_RATE,
            "max_segments": settings.VAD_MAX_SEGMENTS,
            "model_available": vad_manager.is_enabled()
        }

    except Exception as e:
        logger.error(f"Failed to get VAD status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache endpoints

@router.get("/cache/check/{file_id}")
async def check_cache_status(file_id: str):
    """
    Check if a file has cached subtitles

    Returns cache status and metadata if available
    """
    try:
        media_file = media_service.get_file(file_id)
        if not media_file:
            raise HTTPException(status_code=404, detail="File not found")

        filename = Path(media_file.original_filename).stem
        file_size = media_file.file_size

        has_cache = cache_service.is_cached(filename, file_size)
        metadata = cache_service.get_cache_metadata(filename, file_size) if has_cache else None

        return {
            "has_cache": has_cache,
            "metadata": metadata
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/load/{file_id}")
async def load_cached_subtitles(file_id: str):
    """
    Load cached subtitles for a file

    Returns cached transcription result if available
    """
    try:
        media_file = media_service.get_file(file_id)
        if not media_file:
            raise HTTPException(status_code=404, detail="File not found")

        filename = Path(media_file.original_filename).stem
        file_size = media_file.file_size

        if not cache_service.is_cached(filename, file_size):
            raise HTTPException(status_code=404, detail="No cache found for this file")

        result = cache_service.load_transcription(filename, file_size)
        if not result:
            raise HTTPException(status_code=404, detail="Failed to load cached subtitles")

        # Link this file_id to the cache
        cache_service.link_file_id(filename, file_size, file_id)

        # Convert to response format
        from app.models.schemas import SubtitleSegment as SubtitleSegmentSchema

        segments_schema = [
            SubtitleSegmentSchema(
                id=seg.id,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=[
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence
                    }
                    for w in seg.words
                ] if seg.words else None,
                translation=seg.translation
            )
            for seg in result.segments
        ]

        return TranscriptionGenerateResponse(
            success=True,
            file_id=file_id,
            language=result.language,
            segments=segments_schema,
            full_text=result.full_text,
            duration=result.duration,
            processing_time=result.processing_time,
            message="Subtitles loaded from cache"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load cached subtitles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics

    Returns information about cache usage
    """
    try:
        stats = cache_service.get_cache_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup")
async def cleanup_cache(max_age_days: int = 30):
    """
    Clean up orphaned or expired cache entries

    Args:
        max_age_days: Maximum age in days before cleanup

    Returns number of entries cleaned
    """
    try:
        cleaned_count = cache_service.cleanup_orphaned_cache(max_age_days)
        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "message": f"Cleaned up {cleaned_count} cache entries"
        }

    except Exception as e:
        logger.error(f"Failed to cleanup cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
