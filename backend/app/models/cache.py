"""
Cache models for ASR transcription caching
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CacheMetadata:
    """Cache metadata for a transcribed file"""
    original_filename: str
    file_size: int
    cached_at: datetime
    duration: float
    processing_time: float
    num_segments: int
    detected_language: Optional[str] = None
    file_ids: List[str] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "cached_at": self.cached_at.isoformat(),
            "duration": self.duration,
            "processing_time": self.processing_time,
            "num_segments": self.num_segments,
            "detected_language": self.detected_language,
            "file_ids": self.file_ids,
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheMetadata':
        """Create from dictionary"""
        return cls(
            original_filename=data["original_filename"],
            file_size=data["file_size"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            duration=data["duration"],
            processing_time=data["processing_time"],
            num_segments=data["num_segments"],
            detected_language=data.get("detected_language"),
            file_ids=data.get("file_ids", []),
            last_accessed=datetime.fromisoformat(data.get("last_accessed", data["cached_at"])),
            access_count=data.get("access_count", 0)
        )


@dataclass
class CacheFileInfo:
    """Information about cached files"""
    cache_dir: Path
    has_audio: bool
    has_transcription: bool
    has_srt: bool
    has_vtt: bool
    is_complete: bool

    @classmethod
    def check(cls, cache_dir: Path) -> 'CacheFileInfo':
        """Check cache directory completeness"""
        audio_exists = (cache_dir / "audio.mp3").exists()
        transcription_exists = (cache_dir / "transcription.json").exists()
        srt_exists = (cache_dir / "subtitle.srt").exists()
        vtt_exists = (cache_dir / "subtitle.vtt").exists()

        return cls(
            cache_dir=cache_dir,
            has_audio=audio_exists,
            has_transcription=transcription_exists,
            has_srt=srt_exists,
            has_vtt=vtt_exists,
            is_complete=all([audio_exists, transcription_exists, srt_exists, vtt_exists])
        )
