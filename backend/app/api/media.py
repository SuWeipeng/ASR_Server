"""
Media upload and processing API routes
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
import os
from app.services.media_service import media_service
from app.models.schemas import (
    MediaUploadResponse,
    MessageResponse,
    ErrorResponse
)
from app.utils import logger, cleanup_file

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media_file(file: UploadFile = File(...)):
    """
    Upload media file (video or audio)

    Supports:
    - Video: mp4, avi, mov, mkv, webm, flv
    - Audio: mp3, wav, m4a, aac, flac, ogg, wma
    """
    try:
        logger.info(f"Upload request: {file.filename}")

        # Upload and process file
        media_file = await media_service.upload_file(file)

        return MediaUploadResponse(
            success=True,
            file_id=media_file.file_id,
            filename=media_file.original_filename,
            file_type=media_file.file_type,
            duration=media_file.duration,
            file_size=media_file.file_size,
            message="File uploaded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{file_id}")
async def get_media_file(file_id: str):
    """
    Get media file by ID (for streaming/download)
    Supports Range requests for video seeking
    """
    media_file = media_service.get_file(file_id)

    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = media_file.file_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Return file for streaming with Range support
    return FileResponse(
        file_path,
        media_type="video/mp4" if media_file.file_type == "video" else "audio/mpeg",
        filename=media_file.original_filename,
        headers={
            "Accept-Ranges": "bytes",  # Explicitly enable Range requests
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        }
    )


@router.get("/info/{file_id}", response_model=MediaUploadResponse)
async def get_file_info(file_id: str):
    """
    Get file information by ID
    """
    media_file = media_service.get_file(file_id)

    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")

    return MediaUploadResponse(
        success=True,
        file_id=media_file.file_id,
        filename=media_file.original_filename,
        file_type=media_file.file_type,
        duration=media_file.duration,
        file_size=media_file.file_size,
        message="File info retrieved"
    )


@router.delete("/file/{file_id}", response_model=MessageResponse)
async def delete_file(file_id: str):
    """
    Delete media file
    """
    success = media_service.delete_file(file_id)

    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return MessageResponse(
        success=True,
        message=f"File {file_id} deleted successfully"
    )


@router.get("/audio/{file_id}")
async def get_extracted_audio(file_id: str):
    """
    Get extracted audio file by file ID
    """
    audio_path = media_service.extract_audio_from_media(file_id)

    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"{file_id}.wav"
    )
