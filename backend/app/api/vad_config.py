"""
VAD 配置 API 路由
"""
from fastapi import APIRouter, HTTPException
from app.core.vad_config import vad_config_manager
from app.models.schemas import VADConfigResponse, VADConfigUpdateRequest, MessageResponse
from app.utils import logger

router = APIRouter(prefix="/api/vad", tags=["vad"])


@router.get("/config", response_model=VADConfigResponse)
async def get_vad_config():
    """获取当前 VAD 配置"""
    try:
        config = vad_config_manager.get_config()
        return VADConfigResponse(
            min_silence_duration_ms=config.min_silence_duration_ms,
            max_speech_duration_s=config.max_speech_duration_s,
            sample_rate=config.sample_rate
        )
    except Exception as e:
        logger.error(f"Failed to get VAD config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=VADConfigResponse)
async def update_vad_config(request: VADConfigUpdateRequest):
    """更新 VAD 配置（只更新提供的字段）"""
    try:
        # 提取非 None 的字段
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # 更新配置（只更新存在的字段）
        config = vad_config_manager.update_config(**update_data)

        return VADConfigResponse(
            min_silence_duration_ms=config.min_silence_duration_ms,
            max_speech_duration_s=config.max_speech_duration_s,
            sample_rate=config.sample_rate
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update VAD config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset", response_model=VADConfigResponse)
async def reset_vad_config():
    """重置 VAD 配置为默认值"""
    try:
        config = vad_config_manager.reset_to_defaults()
        return VADConfigResponse(
            min_silence_duration_ms=config.min_silence_duration_ms,
            max_speech_duration_s=config.max_speech_duration_s,
            sample_rate=config.sample_rate
        )
    except Exception as e:
        logger.error(f"Failed to reset VAD config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
