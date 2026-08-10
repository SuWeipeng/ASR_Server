"""
Media file processing service
"""
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict
from fastapi import UploadFile, HTTPException
from datetime import datetime
from app.config import settings
from app.utils import (
    logger,
    generate_file_id,
    get_upload_path,
    get_temp_path,
    cleanup_file,
    is_valid_extension,
    validate_file_size,
    extract_audio,
    get_audio_duration,
)
from app.models.domain import MediaFile
from app.models.schemas import MediaType
from app.services.cache_service import cache_service


# 文件元数据存储路径
MEDIA_METADATA_FILE = Path(__file__).parent.parent.parent / "media_metadata.json"


class MediaService:
    """Service for handling media file uploads and processing"""

    def __init__(self):
        self._files: Dict[str, MediaFile] = {}  # In-memory file storage
        # 启动时从文件加载元数据
        self._load_metadata()

    async def upload_file(self, file: UploadFile) -> MediaFile:
        """
        Upload and process media file

        Args:
            file: Uploaded file

        Returns:
            MediaFile entity

        Raises:
            HTTPException: If upload fails
        """
        original_filename = file.filename
        file_extension = Path(original_filename).suffix
        filename_stem = Path(original_filename).stem

        logger.info(f"Uploading file: {original_filename}")

        # Validate file extension
        if not is_valid_extension(original_filename, settings.ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )

        # Read file content first to get size and check cache
        content = await file.read()
        file_size = len(content)

        # Check if cache exists for this file
        if cache_service.is_cached(filename_stem, file_size):
            logger.info(f"Cache hit for {filename_stem}_{file_size}, checking for existing file_id")
            metadata = cache_service.get_cache_metadata(filename_stem, file_size)
            if metadata and metadata.get("file_ids"):
                existing_file_id = metadata["file_ids"][0]
                existing_file = self.get_file(existing_file_id)
                if existing_file:
                    logger.info(f"Returning existing file_id: {existing_file_id}")
                    # Link the new context to existing cache
                    cache_service.link_file_id(filename_stem, file_size, existing_file_id)
                    return existing_file
            logger.info(f"Cache exists but no valid file_id, creating new entry")

        # Reset file pointer for potential reuse
        await file.seek(0)

        file_id = generate_file_id()

        # Save uploaded file
        upload_path = get_upload_path(file_id, file_extension)
        try:
            with open(upload_path, "wb") as f:
                f.write(content)

            logger.info(f"File saved: {upload_path}")

            # Validate file size
            if not validate_file_size(upload_path, settings.MAX_UPLOAD_SIZE):
                cleanup_file(upload_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes"
                )

            # Determine media type
            if file_extension in settings.ALLOWED_VIDEO_EXTENSIONS:
                media_type = MediaType.VIDEO
            else:
                media_type = MediaType.AUDIO

            # Get duration
            duration = get_audio_duration(upload_path)

            # Create media file entity
            media_file = MediaFile(
                file_id=file_id,
                original_filename=original_filename,
                file_path=upload_path,
                file_type=media_type.value,
                file_size=file_size,
                duration=duration
            )

            # Store in memory
            self._files[file_id] = media_file

            # 保存元数据到文件
            self._save_metadata()

            logger.info(f"File uploaded successfully: {file_id}")
            return media_file

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            cleanup_file(upload_path)
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    def extract_audio_from_media(self, file_id: str) -> Optional[str]:
        """
        Extract audio from media file

        Args:
            file_id: File ID

        Returns:
            Path to extracted audio file, or None if failed
        """
        if file_id not in self._files:
            logger.error(f"File not found: {file_id}")
            return None

        media_file = self._files[file_id]
        audio_output_path = get_temp_path(file_id, ".wav")

        # If already extracted and exists, return cached
        if os.path.exists(audio_output_path):
            logger.debug(f"Using cached audio: {audio_output_path}")
            return audio_output_path

        # Extract audio
        try:
            logger.info(f"Extracting audio from {media_file.file_path}")
            success = extract_audio(
                media_file.file_path,
                audio_output_path,
                sample_rate=settings.AUDIO_SAMPLE_RATE,
                channels=settings.AUDIO_CHANNELS
            )

            if success:
                logger.info(f"Audio extracted: {audio_output_path}")
                return audio_output_path
            else:
                logger.error("Failed to extract audio")
                return None

        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return None

    def get_file(self, file_id: str) -> Optional[MediaFile]:
        """
        Get media file by ID

        Args:
            file_id: File ID

        Returns:
            MediaFile entity or None
        """
        return self._files.get(file_id)

    def get_file_path(self, file_id: str) -> Optional[str]:
        """
        Get file path by ID

        Args:
            file_id: File ID

        Returns:
            File path or None
        """
        media_file = self._files.get(file_id)
        return media_file.file_path if media_file else None

    def delete_file(self, file_id: str) -> bool:
        """
        Delete file and cleanup

        Args:
            file_id: File ID

        Returns:
            True if deleted
        """
        if file_id not in self._files:
            return False

        media_file = self._files[file_id]

        # Delete original file
        cleanup_file(media_file.file_path)

        # Delete extracted audio
        audio_path = get_temp_path(file_id, ".wav")
        cleanup_file(audio_path)

        # Remove from memory
        del self._files[file_id]

        # 保存元数据到文件
        self._save_metadata()

        logger.info(f"File deleted: {file_id}")
        return True

    def cleanup_old_files(self, max_age_hours: float = 24.0):
        """
        Clean up old files

        Args:
            max_age_hours: Maximum age in hours
        """
        current_time = time.time()

        files_to_delete = []
        for file_id, media_file in self._files.items():
            file_age_hours = (current_time - media_file.upload_time.timestamp()) / 3600
            if file_age_hours > max_age_hours:
                files_to_delete.append(file_id)

        for file_id in files_to_delete:
            self.delete_file(file_id)

        logger.info(f"Cleaned up {len(files_to_delete)} old files")

    def _load_metadata(self) -> None:
        """从文件加载文件元数据"""
        if not os.path.exists(MEDIA_METADATA_FILE):
            logger.info(f"Media metadata file not found: {MEDIA_METADATA_FILE}")
            return

        try:
            with open(MEDIA_METADATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 重建 MediaFile 对象
            for file_id, file_data in data.items():
                # 检查文件是否仍然存在
                file_path = file_data.get('file_path')
                if file_path and os.path.exists(file_path):
                    self._files[file_id] = MediaFile(
                        file_id=file_id,
                        original_filename=file_data['original_filename'],
                        file_path=file_data['file_path'],
                        file_type=file_data['file_type'],
                        file_size=file_data['file_size'],
                        duration=file_data.get('duration'),
                        upload_time=datetime.fromisoformat(file_data['upload_time'])
                    )
                else:
                    logger.warning(f"File {file_id} no longer exists, skipping")

            logger.info(f"Loaded {len(self._files)} file metadata entries")

        except Exception as e:
            logger.warning(f"Failed to load media metadata: {e}")

    def _save_metadata(self) -> None:
        """保存文件元数据到文件"""
        try:
            # 转换为可序列化的格式
            data = {}
            for file_id, media_file in self._files.items():
                data[file_id] = {
                    'file_id': media_file.file_id,
                    'original_filename': media_file.original_filename,
                    'file_path': media_file.file_path,
                    'file_type': media_file.file_type,
                    'file_size': media_file.file_size,
                    'duration': media_file.duration,
                    'upload_time': media_file.upload_time.isoformat()
                }

            with open(MEDIA_METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save media metadata: {e}")


# Global media service instance
media_service = MediaService()
