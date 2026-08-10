"""
System status and health check API routes
"""
import time
import torch
from fastapi import APIRouter
from app.services.asr_service import asr_service
from app.services.alignment_service import alignment_service
from app.utils import check_ffmpeg_available, ensure_directories, logger
from app.models.schemas import SystemStatus, HealthCheckResponse
from app.config import settings

router = APIRouter(prefix="/api/system", tags=["system"])

# Track server start time
_start_time = time.time()


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get system status including GPU, model, and service availability
    """
    try:
        # Check GPU
        gpu_available = torch.cuda.is_available()
        gpu_device_name = None
        gpu_memory_used = None
        gpu_memory_total = None

        if gpu_available:
            gpu_device_name = torch.cuda.get_device_name(0)
            gpu_memory_used = torch.cuda.memory_allocated(0) / (1024**3)  # GB
            gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB

        # Check model status
        model_loaded = asr_service.check_model_ready()
        model_info = asr_service.get_model_info()

        # Check FFmpeg
        ffmpeg_available = check_ffmpeg_available()

        # Calculate uptime
        uptime = time.time() - _start_time

        return SystemStatus(
            status="ready" if model_loaded else "initializing",
            gpu_available=gpu_available,
            gpu_device_name=gpu_device_name,
            gpu_memory_used=gpu_memory_used,
            gpu_memory_total=gpu_memory_total,
            model_loaded=model_loaded,
            model_size=model_info.get("model_size"),
            model_device=model_info.get("device"),
            ffmpeg_available=ffmpeg_available,
            uptime=uptime,
            version="1.0.0"
        )

    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return SystemStatus(
            status="error",
            gpu_available=False,
            model_loaded=False,
            ffmpeg_available=False,
            uptime=time.time() - _start_time,
            version="1.0.0"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Basic health check endpoint
    """
    components = {
        "api": True,
        "model": asr_service.check_model_ready(),
        "aligner": alignment_service.check_aligner_ready(),
        "ffmpeg": check_ffmpeg_available(),
    }

    all_healthy = all(components.values())

    return HealthCheckResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        components=components
    )


@router.post("/initialize")
async def initialize_system():
    """
    Initialize system (load models, create directories, etc.)
    """
    try:
        logger.info("Initializing system...")

        # Create directories
        ensure_directories()

        # Check FFmpeg
        check_ffmpeg_on_startup()

        # Preload ASR model (lazy loading will happen on first request otherwise)
        logger.info("Models will be loaded on first use (lazy loading)")

        return {
            "success": True,
            "message": "System initialized successfully",
            "model_path": settings.ASR_MODEL_PATH,
            "device": settings.DEVICE
        }

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return {
            "success": False,
            "message": f"Initialization failed: {str(e)}"
        }


@router.get("/config")
async def get_system_config():
    """
    Get current system configuration
    """
    return {
        "model_size": settings.ASR_MODEL_SIZE,
        "device": settings.DEVICE,
        "dtype": settings.DTYPE,
        "max_batch_size": settings.MAX_INFERENCE_BATCH_SIZE,
        "max_new_tokens": settings.MAX_NEW_TOKENS,
        "host": settings.HOST,
        "port": settings.PORT,
        "max_upload_size": settings.MAX_UPLOAD_SIZE
    }
