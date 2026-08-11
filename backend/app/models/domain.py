"""
Domain models for business logic
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    """File processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MediaFile:
    """Media file entity"""
    file_id: str
    original_filename: str
    file_path: str
    file_type: str  # 'video' or 'audio'
    file_size: int
    duration: Optional[float] = None
    upload_time: datetime = field(default_factory=datetime.now)
    processing_status: ProcessingStatus = ProcessingStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "duration": self.duration,
            "upload_time": self.upload_time.isoformat(),
            "processing_status": self.processing_status.value
        }


@dataclass
class SubtitleSegment:
    """Subtitle segment entity"""
    id: int
    start: float
    end: float
    text: str
    words: Optional[List['SubtitleWord']] = None
    translation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [w.to_dict() for w in self.words] if self.words else None,
            "translation": self.translation
        }


@dataclass
class SubtitleWord:
    """Word-level subtitle with timestamp"""
    word: str
    start: float
    end: float
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence
        }


@dataclass
class TranscriptionResult:
    """Complete transcription result"""
    file_id: str
    language: str
    segments: List[SubtitleSegment]
    full_text: str
    duration: float
    processing_time: float
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_id": self.file_id,
            "language": self.language,
            "segments": [s.to_dict() for s in self.segments],
            "full_text": self.full_text,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class DiffWordResult:
    """Word comparison result"""
    word: str
    status: str  # 'correct', 'missing', 'extra'
    original_index: Optional[int] = None
    user_index: Optional[int] = None
    start: Optional[float] = None  # Word start timestamp in seconds
    end: Optional[float] = None    # Word end timestamp in seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "word": self.word,
            "status": self.status,
            "original_index": self.original_index,
            "user_index": self.user_index,
            "start": self.start,
            "end": self.end
        }


@dataclass
class EvaluationResult:
    """Speech evaluation result"""
    score: int
    accuracy_level: str
    user_transcript: str
    target_text: str
    diff_words: List[DiffWordResult]
    correct_count: int
    total_count: int
    missing_count: int
    extra_count: int
    accuracy: float
    waveform: Optional[Dict[str, Any]] = None
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "score": self.score,
            "accuracy_level": self.accuracy_level,
            "user_transcript": self.user_transcript,
            "target_text": self.target_text,
            "diff_words": [dw.to_dict() for dw in self.diff_words],
            "metrics": {
                "correct_count": self.correct_count,
                "total_count": self.total_count,
                "missing_count": self.missing_count,
                "extra_count": self.extra_count,
                "accuracy": self.accuracy
            },
            "waveform": self.waveform,
            "processing_time": self.processing_time
        }


@dataclass
class DictionaryEntry:
    """Dictionary word entry"""
    word: str
    phonetic: Optional[str] = None
    part_of_speech: Optional[str] = None
    definition: Optional[str] = None
    example: Optional[str] = None
    synonyms: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "word": self.word,
            "phonetic": self.phonetic,
            "part_of_speech": self.part_of_speech,
            "definition": self.definition,
            "example": self.example,
            "synonyms": self.synonyms
        }


@dataclass
class SystemInfo:
    """System information"""
    status: str
    gpu_available: bool
    gpu_device_name: Optional[str] = None
    gpu_memory_used: Optional[float] = None
    gpu_memory_total: Optional[float] = None
    model_loaded: bool = False
    model_size: Optional[str] = None
    model_device: Optional[str] = None
    ffmpeg_available: bool = False
    uptime: float = 0.0
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "status": self.status,
            "gpu_available": self.gpu_available,
            "gpu_device_name": self.gpu_device_name,
            "gpu_memory_used": self.gpu_memory_used,
            "gpu_memory_total": self.gpu_memory_total,
            "model_loaded": self.model_loaded,
            "model_size": self.model_size,
            "model_device": self.model_device,
            "ffmpeg_available": self.ffmpeg_available,
            "uptime": self.uptime,
            "version": self.version
        }
