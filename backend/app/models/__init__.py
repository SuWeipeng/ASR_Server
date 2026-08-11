"""
Models package
"""
from app.models.schemas import (
    # Enums
    Language,
    MediaType,

    # Request schemas
    MediaUploadRequest,
    TranscriptionGenerateRequest,
    PracticeEvaluateRequest,
    SubtitleSearchRequest,
    SettingsUpdateRequest,
    DictionaryLookupRequest,

    # Response schemas
    MediaUploadResponse,
    SubtitleWord,
    SubtitleSegment,
    TranscriptionGenerateResponse,
    DiffWordResult,
    PracticeEvaluateResponse,
    SubtitleSearchResponse,
    SubtitleExportResponse,
    SystemStatus,
    HealthCheckResponse,
    DictionaryEntry as DictionaryEntrySchema,
    DictionaryResponse,
    ErrorResponse,
    MessageResponse,
)

from app.models.domain import (
    ProcessingStatus,
    MediaFile,
    SubtitleSegment as SubtitleSegmentDomain,
    SubtitleWord as SubtitleWordDomain,
    TranscriptionResult,
    DiffWordResult as DiffWordResultDomain,
    EvaluationResult,
    DictionaryEntry as DictionaryEntryDomain,
    SystemInfo,
)

__all__ = [
    # Enums
    "Language",
    "MediaType",
    "ProcessingStatus",

    # Request schemas
    "MediaUploadRequest",
    "TranscriptionGenerateRequest",
    "PracticeEvaluateRequest",
    "SubtitleSearchRequest",
    "SettingsUpdateRequest",
    "DictionaryLookupRequest",

    # Response schemas
    "MediaUploadResponse",
    "SubtitleWord",
    "SubtitleSegment",
    "TranscriptionGenerateResponse",
    "DiffWordResult",
    "PracticeEvaluateResponse",
    "SubtitleSearchResponse",
    "SubtitleExportResponse",
    "SystemStatus",
    "HealthCheckResponse",
    "DictionaryEntrySchema",
    "DictionaryResponse",
    "ErrorResponse",
    "MessageResponse",

    # Domain models
    "MediaFile",
    "TranscriptionResult",
    "EvaluationResult",
    "DictionaryEntryDomain",
    "SystemInfo",
]
