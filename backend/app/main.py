"""
FastAPI Application - Main Entry Point

ASR Server for English Speaking Practice
Based on Qwen3-ASR
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import asyncio
import uvicorn

from app.config import settings
from app.api import api_router
from app.utils import (
    logger,
    ensure_directories,
    check_ffmpeg_on_startup,
)
from app.services.asr_service import asr_service


# Track startup time
_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting ASR Server...")
    logger.info("=" * 60)

    # Print configuration
    settings.print_config()

    # Initialize directories
    ensure_directories()

    # Check FFmpeg availability
    check_ffmpeg_on_startup()

    # Preload ASR model in background
    logger.info("Preloading Qwen3-ASR Model...")

    from app.services.asr_service import asr_service

    try:
        # Run synchronous model loading in background thread
        await asyncio.to_thread(asr_service.model_manager.load_model)
        logger.info("✅ Qwen3-ASR Model loaded successfully during startup!")
    except Exception as e:
        logger.error(f"❌ Failed to preload ASR model: {e}")

    logger.info("✅ ASR Server started successfully!")
    logger.info(f"📖 API documentation: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down ASR Server...")
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="ASR Server",
    description="English Speaking Practice Server powered by Qwen3-ASR",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.time()

    # Log request
    logger.info(f"{request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Log response
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    logger.debug(f"Response: {response.status_code} ({process_time:.3f}s)")

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "details": str(exc) if settings.LOG_LEVEL == "DEBUG" else None
        }
    )


# Include API routes
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    uptime = time.time() - _startup_time

    return {
        "message": "ASR Server - English Speaking Practice",
        "version": "1.0.0",
        "uptime": f"{uptime:.2f}s",
        "status": "running",
        "docs": "/docs",
        "health": "/api/system/health"
    }


# Health check endpoint
@app.get("/health")
async def health():
    """Quick health check"""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": time.time() - _startup_time
    }


if __name__ == "__main__":
    # Run development server
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,  # Auto-reload on code changes
        log_level=settings.LOG_LEVEL.lower()
    )
