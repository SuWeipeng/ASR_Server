"""
API routes package
"""
from fastapi import APIRouter
from app.api import media, transcription, practice, dictionary, system, vad_config

# Create main API router
api_router = APIRouter()

# Register all route modules
api_router.include_router(media.router)
api_router.include_router(transcription.router)
api_router.include_router(practice.router)
api_router.include_router(dictionary.router)
api_router.include_router(system.router)
api_router.include_router(vad_config.router)

__all__ = ["api_router"]
