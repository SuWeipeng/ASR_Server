"""
降噪配置 API 路由
"""
from fastapi import APIRouter, HTTPException
from app.core.noise_config import noise_config_manager
from app.models.schemas import (
    NoiseReductionConfigResponse,
    NoiseReductionConfigUpdateRequest,
    MessageResponse
)
from app.utils import logger

router = APIRouter(prefix="/api/noise", tags=["noise"])


@router.get("/config", response_model=NoiseReductionConfigResponse)
async def get_noise_config():
    """获取当前降噪配置"""
    try:
        config = noise_config_manager.get_config()
        return NoiseReductionConfigResponse(
            enabled=config.enabled,
            lowcut=config.lowcut,
            highcut=config.highcut,
            order=config.order,
            filter_type=config.filter_type,
            normalize_after_filter=config.normalize_after_filter
        )
    except Exception as e:
        logger.error(f"Failed to get noise reduction config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=NoiseReductionConfigResponse)
async def update_noise_config(request: NoiseReductionConfigUpdateRequest):
    """更新降噪配置（只更新提供的字段）"""
    try:
        # 提取非 None 的字段
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # 更新配置（只更新存在的字段）
        config = noise_config_manager.update_config(**update_data)

        return NoiseReductionConfigResponse(
            enabled=config.enabled,
            lowcut=config.lowcut,
            highcut=config.highcut,
            order=config.order,
            filter_type=config.filter_type,
            normalize_after_filter=config.normalize_after_filter
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update noise reduction config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset", response_model=NoiseReductionConfigResponse)
async def reset_noise_config():
    """重置降噪配置为默认值"""
    try:
        config = noise_config_manager.reset_to_defaults()
        return NoiseReductionConfigResponse(
            enabled=config.enabled,
            lowcut=config.lowcut,
            highcut=config.highcut,
            order=config.order,
            filter_type=config.filter_type,
            normalize_after_filter=config.normalize_after_filter
        )
    except Exception as e:
        logger.error(f"Failed to reset noise reduction config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
