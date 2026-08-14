"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from enum import Enum


class Language(str, Enum):
    """Supported languages"""
    ENGLISH = "English"
    CHINESE = "Chinese"
    AUTO = "auto"


class MediaType(str, Enum):
    """Media file types"""
    VIDEO = "video"
    AUDIO = "audio"


# ===== Request Schemas =====

class MediaUploadRequest(BaseModel):
    """Media file upload request"""
    file_type: Optional[MediaType] = None


class TranscriptionGenerateRequest(BaseModel):
    """Subtitle generation request"""
    file_id: str = Field(..., description="File ID from upload")
    language: Language = Field(default=Language.AUTO, description="Transcription language")
    generate_timestamps: bool = Field(default=True, description="Generate word-level timestamps")
    use_vad: bool = Field(default=True, description="Use VAD for long audio processing")
    force_refresh: bool = Field(default=False, description="Force regeneration, skip cache")


class PracticeEvaluateRequest(BaseModel):
    """Speech practice evaluation request"""
    target_text: str = Field(..., description="Target text to compare against")
    language: Language = Field(default=Language.AUTO)


class SubtitleSearchRequest(BaseModel):
    """Subtitle search request"""
    query: str = Field(..., min_length=1, description="Search query")
    search_translations: bool = Field(default=False, description="Also search in translations")


class SettingsUpdateRequest(BaseModel):
    """Update application settings"""
    asr_model_size: Optional[str] = Field(None, pattern="^(0\\.6B|1\\.7B)$")
    use_cpu: Optional[bool] = None
    dtype: Optional[str] = Field(None, pattern="^(bfloat16|float16|float32)$")


class DictionaryLookupRequest(BaseModel):
    """Dictionary word lookup request"""
    word: str = Field(..., min_length=1, max_length=50)


# ===== Response Schemas =====

class MediaUploadResponse(BaseModel):
    """Media file upload response"""
    success: bool
    file_id: str
    filename: str
    file_type: MediaType
    duration: Optional[float] = Field(None, description="Duration in seconds")
    file_size: int = Field(..., description="File size in bytes")
    message: str


class SubtitleWord(BaseModel):
    """Single word with timestamp"""
    word: str
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class SubtitleSegment(BaseModel):
    """Subtitle segment (sentence/phrase)"""
    model_config = ConfigDict(populate_by_name=True)

    id: int
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str
    words: Optional[List[SubtitleWord]] = Field(None, description="Word-level timestamps")
    translation: Optional[str] = Field(None, description="Translation (if available)")


class TranscriptionGenerateResponse(BaseModel):
    """Subtitle generation response"""
    success: bool
    file_id: str
    language: str
    segments: List[SubtitleSegment]
    full_text: str
    duration: float
    processing_time: float = Field(..., description="Processing time in seconds")
    message: str


class DiffWordResult(BaseModel):
    """Word comparison result"""
    word: str
    status: str = Field(..., description="Status: correct, missing, extra")
    original_index: Optional[int] = None
    user_index: Optional[int] = None
    start: Optional[float] = Field(None, description="Word start time in seconds")
    end: Optional[float] = Field(None, description="Word end time in seconds")


class PracticeEvaluateResponse(BaseModel):
    """Speech practice evaluation response"""
    success: bool
    score: int = Field(..., ge=0, le=100, description="Similarity score (0-100)")
    accuracy_level: str = Field(..., description="Accuracy level description")
    user_transcript: str = Field(..., description="User spoken text")
    target_text: str
    diff_words: List[DiffWordResult]
    metrics: Dict[str, Any] = Field(..., description="Detailed metrics")
    processing_time: float
    message: str


class SubtitleSearchResponse(BaseModel):
    """Subtitle search response"""
    success: bool
    query: str
    results: List[SubtitleSegment]
    total_count: int


class SubtitleExportResponse(BaseModel):
    """Subtitle export response (for metadata, actual file is downloaded)"""
    success: bool
    file_id: str
    format: str
    segment_count: int
    download_url: str


class SystemStatus(BaseModel):
    """System status information"""
    status: str = Field(..., description="System status: ready, busy, error")
    gpu_available: bool
    gpu_device_name: Optional[str] = None
    gpu_memory_used: Optional[float] = None  # GB
    gpu_memory_total: Optional[float] = None  # GB
    model_loaded: bool
    model_size: Optional[str] = None
    model_device: Optional[str] = None
    ffmpeg_available: bool
    uptime: float = Field(..., description="Server uptime in seconds")
    version: str


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    components: Dict[str, bool]


class DictionaryEntry(BaseModel):
    """Dictionary word entry"""
    word: str
    phonetic: Optional[str] = None
    part_of_speech: Optional[str] = None
    definition: Optional[str] = None
    example: Optional[str] = None
    synonyms: Optional[List[str]] = None


class DictionaryResponse(BaseModel):
    """Dictionary lookup response"""
    success: bool
    entry: Optional[DictionaryEntry] = None
    message: str


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Generic message response"""
    success: bool
    message: str


# ===== VAD Configuration Schemas =====

class VADConfigResponse(BaseModel):
    """VAD 配置响应 - 与 example_qwen3_asr_with_vad.py 一致"""
    min_silence_duration_ms: int
    max_speech_duration_s: float
    sample_rate: int


class VADConfigUpdateRequest(BaseModel):
    """VAD 配置更新请求（所有字段可选）"""
    min_silence_duration_ms: Optional[int] = Field(None, ge=100, le=2000)
    max_speech_duration_s: Optional[float] = Field(None, ge=5, le=120)
    sample_rate: Optional[int] = Field(None, ge=8000, le=48000)


# ===== Noise Reduction Configuration Schemas =====

class NoiseReductionConfigResponse(BaseModel):
    """降噪配置响应"""
    enabled: bool
    lowcut: int
    highcut: int
    order: int
    filter_type: str
    normalize_after_filter: bool


class NoiseReductionConfigUpdateRequest(BaseModel):
    """降噪配置更新请求（所有字段可选）"""
    enabled: Optional[bool] = None
    lowcut: Optional[int] = Field(None, ge=50, le=500)
    highcut: Optional[int] = Field(None, ge=2000, le=8000)
    order: Optional[int] = Field(None, ge=1, le=8)
    filter_type: Optional[str] = Field(None, pattern="^(bandpass|highpass|lowpass)$")
    normalize_after_filter: Optional[bool] = None
