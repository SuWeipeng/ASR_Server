"""
Transcription and subtitle generation API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from typing import Optional
from pathlib import Path
import asyncio

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
        logger.info(f"Force refresh: {request.force_refresh}, Language: {request.language.value}, Use VAD: {request.use_vad}")

        # Verify file exists
        media_file = media_service.get_file(request.file_id)
        if not media_file:
            raise HTTPException(status_code=404, detail="File not found")

        # Generate subtitles (VAD + full ASR inference can run for minutes on
        # long videos; offload so the event loop stays free to stream media)
        result = await asyncio.to_thread(
            subtitle_service.generate_subtitles,
            file_id=request.file_id,
            language=request.language.value,
            use_alignment=True,
            use_vad=request.use_vad,
            force_refresh=request.force_refresh,
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate subtitles"
            )

        logger.info(f"Subtitle generation completed: {len(result.segments)} segments generated")

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

        # Debug: log the segments schema
        logger.info(f"[DEBUG] Creating segments schema with {len(segments_schema)} segments")
        if segments_schema:
            logger.info(f"[DEBUG] First segment sample: id={segments_schema[0].id}, text={segments_schema[0].text[:50]}...")

        response_data = TranscriptionGenerateResponse(
            success=True,
            file_id=result.file_id,
            language=result.language,
            segments=segments_schema,
            full_text=result.full_text,
            duration=result.duration,
            processing_time=result.processing_time,
            message="Subtitles generated successfully",
            metadata=result.metadata
        )

        # Debug: log the final response data structure
        logger.info(f"[DEBUG] Final response: success={response_data.success}, segments_count={len(response_data.segments)}")

        return response_data

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
        message="Subtitles retrieved",
        metadata=result.metadata
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


# 进行中的缓存重修复（防同一文件并发重入）
_active_repairs: set = set()


@router.post("/repair/{file_id}", response_model=TranscriptionGenerateResponse)
async def repair_subtitle_timing(file_id: str):
    """
    对已有缓存轻量重跑字幕同步修复（不重跑 demucs/ASR，GPU 约分钟级）

    供设置页修改同步修复参数后即时生效；缓存时间戳被就地更新，
    srt/vtt 一并重新生成。总开关关闭时幂等无害（不改任何文件）。
    """
    try:
        media_file = media_service.get_file(file_id)
        if not media_file:
            raise HTTPException(status_code=404, detail="File not found")

        filename = Path(media_file.original_filename).stem
        file_size = media_file.file_size

        if not cache_service.is_cached(filename, file_size):
            raise HTTPException(
                status_code=404,
                detail="No cache found for this file. Generate subtitles first."
            )

        if file_id in _active_repairs:
            raise HTTPException(status_code=409, detail="Repair already in progress")
        _active_repairs.add(file_id)

        try:
            # 修复含批量 ASR 重探测，长视频可能跑数分钟，offload 保持事件循环空闲
            result = await asyncio.to_thread(
                subtitle_service.repair_cached_timing,
                file_id, filename, file_size,
            )
        finally:
            _active_repairs.discard(file_id)

        if not result:
            raise HTTPException(status_code=500, detail="Failed to repair cached subtitles")

        logger.info(f"Subtitle timing repaired: {len(result.segments)} segments")

        # 回写内存缓存（否则本会话内 /export /search 仍返回旧时间戳）
        _transcription_cache[file_id] = result

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
            message="Subtitle timing repaired from cache",
            metadata=result.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subtitle repair failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vad/status")
async def get_vad_status():
    """
    Get VAD (Voice Activity Detection) system status

    Returns information about VAD configuration and model status
    """
    try:
        from app.core.vad_config import get_vad_config

        vad_manager = get_vad_model()
        vad_cfg = get_vad_config().get_config()  # 动态配置（设置页可改），非静态 settings

        return {
            "vad_enabled": settings.VAD_ENABLED,
            "vad_model_loaded": vad_manager.is_model_loaded(),
            "threshold_duration": settings.VAD_THRESHOLD_DURATION,
            "min_silence_duration_ms": vad_cfg.min_silence_duration_ms,
            "max_speech_duration_s": vad_cfg.max_speech_duration_s,
            "sample_rate": vad_cfg.sample_rate,
            "speech_pad_ms": vad_cfg.speech_pad_ms,
            "max_merge_gap_s": vad_cfg.max_merge_gap_s,
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
            message="Subtitles loaded from cache",
            metadata=result.metadata
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
