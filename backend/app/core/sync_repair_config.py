"""
字幕同步修复动态配置管理器

SYNC_REPAIR_* 环境变量（app/config.py Settings）仅作首次种子；
backend/sync_repair_config.json 落盘后以 JSON 为准（设置页运行时可调）。
与 vad/noise/demucs 配置管理器同构，差异：
  - from_dict 逐字段容错（残缺/旧版 JSON 不整体回退默认）
  - update_config 副本校验式（跨字段不变量 rate_lo<rate_hi 等，部分 PUT 时
    pydantic 看不到合并后状态，只有这里能校验）
  - 原子写（tmp + os.replace，防 uvicorn reload 杀进程写坏 JSON）
"""
import dataclasses
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.logger import logger

# 配置文件路径（backend/sync_repair_config.json）
SYNC_REPAIR_CONFIG_FILE = Path(__file__).parent.parent.parent / "sync_repair_config.json"


@dataclass
class SyncRepairConfig:
    """字幕同步修复配置（机制与参数说明见 README_sync_repair.md）"""
    enabled: bool = True        # 总开关（false = 保留 ASR 原始时间戳，回滚保险）
    max_word_dur: float = 1.5   # 单词时长超过此值视为不健康（秒）
    speech_ratio: float = 0.35  # 段区间语音帧占比低于此值视为不健康
    snap_window: float = 0.7    # 起点静音吸附最大前移（秒）
    rate_lo: float = 4.0        # 语速下限（chars/s），低于视为拖沓/铺静音
    rate_hi: float = 34.0       # 语速上限（chars/s），高于视为挤扁/错位
    search_s: float = 12.0      # 候选窗搜索半径（秒）
    merge_gap: float = 1.2      # 无人认领单元合并成候选组的最大桥接间隔（秒）
    min_island_w: float = 0.12  # 参与候选的最小单元宽（秒，短感叹词岛 ~0.15s）
    bandpass: bool = False      # 修复通道内可选带通（探针 A/B 无增益，默认关）
    bandpass_lo: float = 80.0   # 带通低频（Hz）
    bandpass_hi: float = 5500.0  # 带通高频（Hz）

    @classmethod
    def from_settings(cls) -> "SyncRepairConfig":
        """从静态 settings 创建配置（env 可覆盖；重置即回到这些值）"""
        return cls(
            enabled=settings.SUBTITLE_SYNC_REPAIR,
            max_word_dur=settings.SYNC_REPAIR_MAX_WORD_DUR,
            speech_ratio=settings.SYNC_REPAIR_SPEECH_RATIO,
            snap_window=settings.SYNC_REPAIR_SNAP_WINDOW,
            rate_lo=settings.SYNC_REPAIR_RATE_LO,
            rate_hi=settings.SYNC_REPAIR_RATE_HI,
            search_s=settings.SYNC_REPAIR_SEARCH_S,
            merge_gap=settings.SYNC_REPAIR_MERGE_GAP,
            min_island_w=settings.SYNC_REPAIR_MIN_ISLAND_W,
            bandpass=settings.SYNC_REPAIR_BANDPASS,
            bandpass_lo=settings.SYNC_REPAIR_BANDPASS_LO,
            bandpass_hi=settings.SYNC_REPAIR_BANDPASS_HI,
        )

    @classmethod
    def get_defaults(cls) -> "SyncRepairConfig":
        return cls.from_settings()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SyncRepairConfig":
        """逐字段容错：以 settings 默认为基底，只覆盖存在且合法的键"""
        base = cls.get_defaults().to_dict()
        fields = {f.name for f in dataclasses.fields(cls)}
        for key, value in data.items():
            if key in fields and value is not None:
                base[key] = value
        return cls(**base)


class SyncRepairConfigManager:
    """字幕同步修复配置管理器（单例）"""
    _instance: Optional["SyncRepairConfigManager"] = None
    _config: SyncRepairConfig

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = cls._load_from_file() or SyncRepairConfig.from_settings()
        return cls._instance

    def get_config(self) -> SyncRepairConfig:
        return self._config

    def update_config(self, **kwargs) -> SyncRepairConfig:
        """更新配置（副本校验式）：不变量通过后才落内存并持久化"""
        updates = {k: v for k, v in kwargs.items() if hasattr(self._config, k)}
        candidate = dataclasses.replace(self._config, **updates)
        if candidate.rate_lo >= candidate.rate_hi:
            raise ValueError("rate_lo must be less than rate_hi")
        if candidate.bandpass_lo >= candidate.bandpass_hi:
            raise ValueError("bandpass_lo must be less than bandpass_hi")
        self._config = candidate
        for key, value in updates.items():
            logger.info(f"Sync repair config updated: {key} = {value}")
        self._save_to_file()
        return self._config

    def reset_to_defaults(self) -> SyncRepairConfig:
        """重置为 settings 默认（env 可覆盖，而非硬编码）"""
        self._config = SyncRepairConfig.get_defaults()
        self._save_to_file()
        logger.info("Sync repair config reset to settings defaults")
        return self._config

    @staticmethod
    def _load_from_file() -> Optional[SyncRepairConfig]:
        if not os.path.exists(SYNC_REPAIR_CONFIG_FILE):
            logger.info(
                f"Sync repair config file not found: {SYNC_REPAIR_CONFIG_FILE}, "
                f"using settings defaults")
            return None
        try:
            with open(SYNC_REPAIR_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = SyncRepairConfig.from_dict(data)
            logger.info(f"Sync repair config loaded from file: {SYNC_REPAIR_CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(
                f"Failed to load sync repair config from file: {e}, "
                f"using settings defaults")
            return None

    def _save_to_file(self) -> None:
        """原子写：先写 tmp 再 os.replace，防进程中途被杀写坏 JSON"""
        try:
            tmp = SYNC_REPAIR_CONFIG_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            os.replace(tmp, SYNC_REPAIR_CONFIG_FILE)
            logger.info(f"Sync repair config saved to file: {SYNC_REPAIR_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save sync repair config to file: {e}")


# 全局实例
sync_repair_config_manager = SyncRepairConfigManager()


def get_sync_repair_config() -> SyncRepairConfigManager:
    """获取全局字幕同步修复配置管理器实例"""
    return sync_repair_config_manager
