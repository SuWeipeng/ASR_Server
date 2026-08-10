"""
VAD 动态配置管理器
支持运行时更新 VAD 参数，支持持久化存储
与 example_qwen3_asr_with_vad.py 保持一致
"""
import json
import os
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from app.config import settings
from app.utils.logger import logger


# VAD 配置文件路径
VAD_CONFIG_FILE = Path(__file__).parent.parent.parent / "vad_config.json"


@dataclass
class VADConfig:
    """VAD 配置数据类 - 与 example_qwen3_asr_with_vad.py 一致"""
    min_silence_duration_ms: int = 500  # 毫秒，最小静音时长
    max_speech_duration_s: float = 30.0  # 秒，单段最大语音时长
    sample_rate: int = 16000  # 采样率

    @classmethod
    def from_settings(cls) -> 'VADConfig':
        """从静态 settings 创建初始配置"""
        return cls(
            min_silence_duration_ms=settings.VAD_MIN_SILENCE_DURATION_MS,
            max_speech_duration_s=settings.VAD_MAX_SPEECH_DURATION_S,
            sample_rate=settings.VAD_SAMPLE_RATE,
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'VADConfig':
        """从字典创建配置"""
        return cls(**data)


class VADConfigManager:
    """VAD 配置管理器（单例）"""
    _instance: Optional['VADConfigManager'] = None
    _config: VADConfig

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 先尝试从文件加载，失败则使用默认值
            cls._instance._config = cls._load_from_file() or VADConfig.from_settings()
        return cls._instance

    def get_config(self) -> VADConfig:
        """获取当前配置"""
        return self._config

    def update_config(self, **kwargs) -> VADConfig:
        """更新配置并返回新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"VAD config updated: {key} = {value}")
        # 保存到文件
        self._save_to_file()
        return self._config

    def reset_to_defaults(self) -> VADConfig:
        """重置为 example 默认配置"""
        self._config = VADConfig(
            min_silence_duration_ms=500,
            max_speech_duration_s=30.0,
            sample_rate=16000,
        )
        self._save_to_file()
        logger.info("VAD config reset to example defaults")
        return self._config

    @staticmethod
    def _load_from_file() -> Optional[VADConfig]:
        """从文件加载配置"""
        if not os.path.exists(VAD_CONFIG_FILE):
            logger.info(f"VAD config file not found: {VAD_CONFIG_FILE}, using defaults")
            return None

        try:
            with open(VAD_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            config = VADConfig.from_dict(data)
            logger.info(f"VAD config loaded from file: {VAD_CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load VAD config from file: {e}, using defaults")
            return None

    def _save_to_file(self) -> None:
        """保存配置到文件"""
        try:
            with open(VAD_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"VAD config saved to file: {VAD_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save VAD config to file: {e}")


# 全局实例
vad_config_manager = VADConfigManager()


def get_vad_config() -> VADConfigManager:
    """获取全局 VAD 配置管理器实例"""
    return vad_config_manager
