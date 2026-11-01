"""
Media upload and processing API routes
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
import asyncio
import os
import re
from app.services.media_service import media_service
from app.models.schemas import (
    MediaUploadResponse,
    MessageResponse,
    ErrorResponse
)
from app.utils import logger, cleanup_file, get_temp_path, extract_audio_clip

# Import waveform service with error handling
try:
    from app.services.waveform_service import waveform_service
    logger.info("Waveform service loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import waveform service: {e}")
    waveform_service = None

router = APIRouter(prefix="/api/media", tags=["media"])

_RANGE_HEADER_RE = re.compile(r"bytes=(\d*)-(\d*)$")


def media_file_response(
    file_path: str,
    media_type: str,
    request: Request,
    filename: Optional[str] = None,
    headers: Optional[dict] = None,
):
    """
    Serve a media file with real Range request support (RFC 7233).

    Browsers' video/audio elements issue Range requests for seeking. Without
    206 support (FileResponse always returns 200 with the full file), seeking
    to the middle of a large media file forces the browser to download it
    sequentially from byte 0 - causing long buffering gaps (e.g. silent video
    after jumping to a mid position).
    """
    base_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
        "Access-Control-Allow-Origin": "*",  # Explicit CORS for media elements
        **(headers or {}),
    }
    file_size = os.path.getsize(file_path)

    range_header = request.headers.get("range")
    match = _RANGE_HEADER_RE.match(range_header.strip()) if range_header else None
    if match:
        start_str, end_str = match.groups()
        if not start_str and end_str:
            # suffix range "bytes=-N": last N bytes
            start = max(0, file_size - int(end_str))
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        if start <= end:
            content_length = end - start + 1

            def iter_range():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk = f.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                iter_range(),
                status_code=206,
                media_type=media_type,
                headers={
                    **base_headers,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(content_length),
                },
            )

    return FileResponse(file_path, media_type=media_type, filename=filename, headers=base_headers)


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
async def get_media_file(file_id: str, request: Request):
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

    # Return file for streaming with real Range support (206 partial content)
    return media_file_response(
        file_path,
        media_type="video/mp4" if media_file.file_type == "video" else "audio/mpeg",
        request=request,
        filename=media_file.original_filename,
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
async def get_extracted_audio(file_id: str, request: Request):
    """
    Get extracted audio file by file ID
    """
    # ffmpeg extraction of a long video can take seconds; run it in a worker
    # thread so the event loop stays free to stream media files
    audio_path = await asyncio.to_thread(
        media_service.extract_audio_from_media, file_id
    )

    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")

    return media_file_response(
        audio_path,
        media_type="audio/wav",
        request=request,
        filename=f"{file_id}.wav",
    )


@router.get("/vocals/{file_id}")
async def get_vocals_audio(file_id: str, request: Request):
    """
    Get demucs-separated vocals audio (16kHz mono WAV)

    Returns 404 if the file has no separated vocals (e.g. demucs was
    disabled when subtitles were generated, or temp files were cleaned).
    """
    vocals_path = get_temp_path(f"{file_id}_vocals", ".wav")

    if not os.path.exists(vocals_path):
        raise HTTPException(status_code=404, detail="Vocals not found")

    return media_file_response(
        vocals_path,
        media_type="audio/wav",
        request=request,
        filename=f"{file_id}_vocals.wav",
    )


@router.get("/sentence/{file_id}")
async def get_sentence_audio(
    file_id: str,
    background_tasks: BackgroundTasks,
    start: float = Query(..., ge=0, description="Sentence start time in seconds"),
    end: float = Query(..., ge=0, description="Sentence end time in seconds"),
    use_vocals: bool = Query(False, description="Cut from demucs-separated vocals if available"),
    name: str = Query("", description="Sentence text, used as the download filename"),
):
    """
    Download one subtitle sentence as an MP3 clip.

    With use_vocals=true, cuts from the demucs-separated vocals (falls back to
    the original audio when no vocals file exists).
    """
    media_file = media_service.get_file(file_id)
    if not media_file:
        raise HTTPException(status_code=404, detail="File not found")

    # 音源：人声模式优先，无人声文件自动回退原声
    source_path = None
    if use_vocals:
        vocals_path = get_temp_path(f"{file_id}_vocals", ".wav")
        if os.path.exists(vocals_path):
            source_path = vocals_path
    if not source_path:
        if media_file.file_type == "video":
            source_path = await asyncio.to_thread(
                media_service.extract_audio_from_media, file_id
            )
        else:
            source_path = media_file.file_path

    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Audio not found")

    duration = max(0.1, end - start)

    # 下载文件名：句文本清洗后使用（去除文件系统非法字符），退化为时间命名
    safe_name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (name or "").strip())[:40].strip(" ._")
    if not safe_name:
        safe_name = f"sentence_{int(start)}s"

    clip_path = get_temp_path(f"{file_id}_sentence_{int(start * 10)}", ".mp3")
    try:
        await asyncio.to_thread(
            extract_audio_clip, source_path, clip_path, start, duration
        )
    except Exception as e:
        logger.error(f"Failed to extract sentence clip: {e}")
        cleanup_file(clip_path)
        raise HTTPException(status_code=500, detail="Failed to extract sentence audio")

    # 响应发送完毕后清理临时剪辑文件
    background_tasks.add_task(cleanup_file, clip_path)

    return FileResponse(
        clip_path,
        media_type="audio/mpeg",
        filename=f"{safe_name}.mp3",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/waveform/{file_id}")
async def get_waveform_data(
    file_id: str,
    start_time: float = Query(0, ge=0, description="Start time in seconds"),
    end_time: Optional[float] = Query(None, ge=0, description="End time in seconds"),
    num_points: int = Query(500, ge=10, le=2000, description="Number of data points"),
    use_vocals: bool = Query(False, description="Use demucs-separated vocals if available")
):
    """
    Get waveform visualization data for a media file

    Returns amplitude and pitch data for visualization.
    Use start_time and end_time to get waveform for a specific segment.
    With use_vocals=true, prefers the demucs-separated vocals as the source
    (falls back to original audio when no vocals exist).
    """
    if waveform_service is None:
        raise HTTPException(status_code=503, detail="Waveform service not available")

    # librosa.load + pyin pitch tracking are CPU-heavy (seconds per call for a
    # sentence). Running them inline blocks the event loop, which stalls all
    # other requests - including the video element's range requests, causing
    # playback freezes. Offload to a worker thread instead.
    result = await asyncio.to_thread(
        waveform_service.get_waveform_data,
        file_id=file_id,
        start_time=start_time,
        end_time=end_time,
        num_points=num_points,
        use_vocals=use_vocals,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Failed to generate waveform data")

    return {
        "success": True,
        "file_id": file_id,
        "waveform": result
    }
