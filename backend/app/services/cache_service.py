"""
Cache service for ASR transcription results
"""
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import re

from app.models.cache import CacheMetadata, CacheFileInfo
from app.models.domain import TranscriptionResult, SubtitleSegment
from app.config import settings
from app.utils import logger


class CacheService:
    """Service for managing ASR transcription cache"""

    # Required cache files
    CACHE_FILES = ["audio.mp3", "transcription.json", "subtitle.srt", "subtitle.vtt"]
    METADATA_FILE = "metadata.json"

    def __init__(self):
        """Initialize cache service and ensure cache directory exists"""
        self.cache_dir = Path(settings.BASE_DIR) / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        logger.info(f"Cache directory: {self.cache_dir}")

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by replacing invalid characters with underscore

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for directory names
        """
        # Replace invalid characters with underscore
        # Invalid on Windows: / \ : * ? " < > |
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
        # Also handle leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        # Limit length to avoid path length issues
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized

    def _get_cache_dir(self, filename: str, file_size: int) -> Path:
        """
        Get cache directory path for a file

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes

        Returns:
            Path to cache directory
        """
        sanitized_name = self._sanitize_filename(filename)
        cache_dir_name = f"{sanitized_name}_{file_size}"
        return self.cache_dir / cache_dir_name

    def is_cached(self, filename: str, file_size: int) -> bool:
        """
        Check if a complete cache exists for the file

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes

        Returns:
            True if complete cache exists
        """
        cache_dir = self._get_cache_dir(filename, file_size)
        if not cache_dir.exists():
            return False

        cache_info = CacheFileInfo.check(cache_dir)
        return cache_info.is_complete

    def is_cache_complete(self, cache_dir: Path) -> bool:
        """
        Verify all required cache files exist

        Args:
            cache_dir: Cache directory path

        Returns:
            True if all required files exist
        """
        cache_info = CacheFileInfo.check(cache_dir)
        return cache_info.is_complete

    def load_transcription(self, filename: str, file_size: int) -> Optional[TranscriptionResult]:
        """
        Load transcription result from cache

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes

        Returns:
            TranscriptionResult or None if cache doesn't exist/invalid
        """
        cache_dir = self._get_cache_dir(filename, file_size)
        transcription_file = cache_dir / "transcription.json"

        if not transcription_file.exists():
            logger.warning(f"Transcription cache not found: {transcription_file}")
            return None

        try:
            with open(transcription_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct TranscriptionResult
            segments = []
            for seg_data in data.get("segments", []):
                words = None
                if seg_data.get("words"):
                    from app.models.domain import SubtitleWord
                    words = [
                        SubtitleWord(**w) for w in seg_data["words"]
                    ]
                segments.append(SubtitleSegment(
                    id=seg_data["id"],
                    start=seg_data["start"],
                    end=seg_data["end"],
                    text=seg_data["text"],
                    words=words,
                    translation=seg_data.get("translation")
                ))

            result = TranscriptionResult(
                file_id=data["file_id"],
                language=data["language"],
                segments=segments,
                full_text=data["full_text"],
                duration=data["duration"],
                processing_time=data["processing_time"],
                created_at=datetime.fromisoformat(data["created_at"]),
                metadata=data.get("metadata", {})
            )

            # Update access metadata
            self._update_access_metadata(filename, file_size)

            logger.info(f"Loaded transcription from cache: {filename}_{file_size}")
            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load transcription cache: {e}")
            return None

    def save_transcription(self, filename: str, file_size: int,
                           result: TranscriptionResult, audio_path: str) -> bool:
        """
        Save transcription result to cache

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes
            result: TranscriptionResult to save
            audio_path: Path to audio file to copy

        Returns:
            True if saved successfully
        """
        cache_dir = self._get_cache_dir(filename, file_size)
        cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save transcription JSON
            transcription_file = cache_dir / "transcription.json"
            transcription_data = {
                "file_id": result.file_id,
                "language": result.language,
                "segments": [
                    {
                        "id": seg.id,
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text,
                        "words": [
                            {
                                "word": w.word,
                                "start": w.start,
                                "end": w.end,
                                "confidence": w.confidence
                            }
                            for w in seg.words
                        ] if seg.words else None,
                        "translation": seg.translation
                    }
                    for seg in result.segments
                ],
                "full_text": result.full_text,
                "duration": result.duration,
                "processing_time": result.processing_time,
                "created_at": result.created_at.isoformat(),
                "metadata": result.metadata or {}
            }

            with open(transcription_file, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)

            # Copy audio file
            audio_cache = cache_dir / "audio.mp3"
            if audio_path and Path(audio_path).exists():
                shutil.copy2(audio_path, audio_cache)
                logger.info(f"Copied audio to cache: {audio_cache}")
            else:
                logger.warning(f"Audio file not found: {audio_path}")

            # Save metadata
            self._save_metadata(filename, file_size, result)

            logger.info(f"Saved transcription to cache: {filename}_{file_size}")
            return True

        except Exception as e:
            logger.error(f"Failed to save transcription cache: {e}")
            return False

    def generate_subtitle_files(self, filename: str, file_size: int,
                                segments: List[SubtitleSegment]) -> bool:
        """
        Generate and save SRT/VTT subtitle files

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes
            segments: List of subtitle segments

        Returns:
            True if generated successfully
        """
        cache_dir = self._get_cache_dir(filename, file_size)

        try:
            # Generate SRT
            srt_content = self._generate_srt(segments)
            srt_file = cache_dir / "subtitle.srt"
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write(srt_content)

            # Generate VTT
            vtt_content = self._generate_vtt(segments)
            vtt_file = cache_dir / "subtitle.vtt"
            with open(vtt_file, 'w', encoding='utf-8') as f:
                f.write(vtt_content)

            logger.info(f"Generated subtitle files: {filename}_{file_size}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate subtitle files: {e}")
            return False

    def _generate_srt(self, segments: List[SubtitleSegment]) -> str:
        """Generate SRT format content"""
        srt_lines = []

        for i, segment in enumerate(segments, 1):
            start_time = self._format_srt_time(segment.start)
            end_time = self._format_srt_time(segment.end)

            srt_lines.append(str(i))
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(segment.text)
            srt_lines.append("")  # Empty line between segments

        return "\n".join(srt_lines)

    def _generate_vtt(self, segments: List[SubtitleSegment]) -> str:
        """Generate WebVTT format content"""
        vtt_lines = ["WEBVTT", ""]

        for segment in segments:
            start_time = self._format_vtt_time(segment.start)
            end_time = self._format_vtt_time(segment.end)

            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(segment.text)
            vtt_lines.append("")

        return "\n".join(vtt_lines)

    def _format_srt_time(self, seconds: float) -> str:
        """Format time to SRT timestamp format (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_time(self, seconds: float) -> str:
        """Format time to WebVTT timestamp format (00:00:00.000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def link_file_id(self, filename: str, file_size: int, file_id: str) -> None:
        """
        Link a file_id to the cache entry

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes
            file_id: File ID to link
        """
        cache_dir = self._get_cache_dir(filename, file_size)
        metadata_file = cache_dir / self.METADATA_FILE

        if not metadata_file.exists():
            return

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if file_id not in data.get("file_ids", []):
                data["file_ids"].append(file_id)
                data["last_accessed"] = datetime.now().isoformat()
                data["access_count"] = data.get("access_count", 0) + 1

                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to link file_id: {e}")

    def unlink_file_id(self, file_id: str) -> None:
        """
        Remove a file_id from all cache entries

        Args:
            file_id: File ID to unlink
        """
        for metadata_file in self.cache_dir.glob("*/" + self.METADATA_FILE):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if file_id in data.get("file_ids", []):
                    data["file_ids"].remove(file_id)
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Unlinked file_id {file_id} from {metadata_file.parent}")

            except Exception as e:
                logger.error(f"Failed to unlink file_id from {metadata_file}: {e}")

    def get_cache_metadata(self, filename: str, file_size: int) -> Optional[Dict[str, Any]]:
        """
        Get cache metadata

        Args:
            filename: Original filename (without extension)
            file_size: File size in bytes

        Returns:
            Metadata dict or None if not found
        """
        cache_dir = self._get_cache_dir(filename, file_size)
        metadata_file = cache_dir / self.METADATA_FILE

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return None

    def _save_metadata(self, filename: str, file_size: int,
                       result: TranscriptionResult) -> None:
        """Save cache metadata"""
        cache_dir = self._get_cache_dir(filename, file_size)
        metadata_file = cache_dir / self.METADATA_FILE

        metadata = {
            "original_filename": filename,
            "file_size": file_size,
            "cached_at": datetime.now().isoformat(),
            "duration": result.duration,
            "processing_time": result.processing_time,
            "num_segments": len(result.segments),
            "detected_language": result.language,
            "file_ids": [],
            "last_accessed": datetime.now().isoformat(),
            "access_count": 0
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _update_access_metadata(self, filename: str, file_size: int) -> None:
        """Update access time and count in metadata"""
        cache_dir = self._get_cache_dir(filename, file_size)
        metadata_file = cache_dir / self.METADATA_FILE

        if not metadata_file.exists():
            return

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data["last_accessed"] = datetime.now().isoformat()
            data["access_count"] = data.get("access_count", 0) + 1

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to update access metadata: {e}")

    def cleanup_orphaned_cache(self, max_age_days: int = 30) -> int:
        """
        Clean up orphaned cache entries (no linked file_ids or too old)

        Args:
            max_age_days: Maximum age in days before cleanup

        Returns:
            Number of cache entries cleaned up
        """
        from datetime import timedelta

        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        for cache_dir in self.cache_dir.iterdir():
            if not cache_dir.is_dir():
                continue

            metadata_file = cache_dir / self.METADATA_FILE

            if not metadata_file.exists():
                # No metadata, consider orphaned
                shutil.rmtree(cache_dir, ignore_errors=True)
                cleaned_count += 1
                continue

            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if orphaned (no linked file_ids) or too old
                file_ids = data.get("file_ids", [])
                cached_at = datetime.fromisoformat(data.get("cached_at", ""))

                if not file_ids or cached_at < cutoff_date:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    cleaned_count += 1
                    logger.info(f"Cleaned up cache: {cache_dir.name}")

            except Exception as e:
                logger.error(f"Failed to process cache dir {cache_dir}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cache cleanup completed: {cleaned_count} entries removed")

        return cleaned_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        total_entries = 0
        total_size = 0
        complete_entries = 0

        for cache_dir in self.cache_dir.iterdir():
            if not cache_dir.is_dir():
                continue

            total_entries += 1

            # Calculate directory size
            try:
                dir_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
                total_size += dir_size

                cache_info = CacheFileInfo.check(cache_dir)
                if cache_info.is_complete:
                    complete_entries += 1
            except Exception:
                pass

        return {
            "total_entries": total_entries,
            "complete_entries": complete_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir)
        }


# Global cache service instance
cache_service = CacheService()
