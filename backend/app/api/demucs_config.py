"""
demucs 人声分离配置 API 路由
"""
from fastapi import APIRouter, HTTPException
from app.core.demucs_config import demucs_config_manager
from app.models.schemas import (
    DemucsConfigResponse,
    DemucsConfigUpdateRequest
)
from app.utils import logger, check_demucs_available

router = APIRouter(prefix="/api/demucs", tags=["demucs"])


def _build_response(config) -> DemucsConfigResponse:
    return DemucsConfigResponse(
        enabled=config.enabled,
        model_name=config.model_name,
        repo_path=config.repo_path,
        playback_use_vocals=config.playback_use_vocals,
        demucs_available=check_demucs_available()
    )


@router.get("/config", response_model=DemucsConfigResponse)
async def get_demucs_config():
    """获取当前 demucs 配置（含可用性检测）"""
    try:
        return _build_response(demucs_config_manager.get_config())
    except Exception as e:
        logger.error(f"Failed to get demucs config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=DemucsConfigResponse)
async def update_demucs_config(request: DemucsConfigUpdateRequest):
    """更新 demucs 配置（只更新提供的字段）"""
    try:
        # 提取非 None 的字段
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # 更新配置（只更新存在的字段）
        config = demucs_config_manager.update_config(**update_data)

        return _build_response(config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update demucs config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset", response_model=DemucsConfigResponse)
async def reset_demucs_config():
    """重置 demucs 配置为默认值"""
    try:
        config = demucs_config_manager.reset_to_defaults()
        return _build_response(config)
    except Exception as e:
        logger.error(f"Failed to reset demucs config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
