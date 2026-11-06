"""
字幕同步修复配置 API 路由
"""
from fastapi import APIRouter, HTTPException

from app.core.sync_repair_config import sync_repair_config_manager
from app.models.schemas import (
    SyncRepairConfigResponse,
    SyncRepairConfigUpdateRequest,
)
from app.utils import logger

router = APIRouter(prefix="/api/sync-repair", tags=["sync-repair"])


def _build_response(config) -> SyncRepairConfigResponse:
    return SyncRepairConfigResponse(
        enabled=config.enabled,
        max_word_dur=config.max_word_dur,
        speech_ratio=config.speech_ratio,
        snap_window=config.snap_window,
        rate_lo=config.rate_lo,
        rate_hi=config.rate_hi,
        search_s=config.search_s,
        merge_gap=config.merge_gap,
        min_island_w=config.min_island_w,
        bandpass=config.bandpass,
        bandpass_lo=config.bandpass_lo,
        bandpass_hi=config.bandpass_hi,
    )


@router.get("/config", response_model=SyncRepairConfigResponse)
async def get_sync_repair_config():
    """获取当前字幕同步修复配置"""
    try:
        return _build_response(sync_repair_config_manager.get_config())
    except Exception as e:
        logger.error(f"Failed to get sync repair config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=SyncRepairConfigResponse)
async def update_sync_repair_config(request: SyncRepairConfigUpdateRequest):
    """更新字幕同步修复配置（只更新提供的字段）"""
    try:
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        config = sync_repair_config_manager.update_config(**update_data)
        return _build_response(config)
    except HTTPException:
        raise
    except ValueError as e:
        # 跨字段不变量（rate_lo<rate_hi 等）违反
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update sync repair config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/reset", response_model=SyncRepairConfigResponse)
async def reset_sync_repair_config():
    """重置字幕同步修复配置为默认值（settings/env 可覆盖值）"""
    try:
        config = sync_repair_config_manager.reset_to_defaults()
        return _build_response(config)
    except Exception as e:
        logger.error(f"Failed to reset sync repair config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
