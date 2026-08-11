"""
降噪动态配置管理器
支持运行时更新降噪参数，支持持久化存储
使用传统信号处理方法（Butterworth 滤波器）进行降噪
"""
import json
import os
from typing import Optional, Literal
from dataclasses import dataclass, asdict
from pathlib import Path
from app.utils.logger import logger


# 降噪配置文件路径
NOISE_CONFIG_FILE = Path(__file__).parent.parent.parent / "noise_config.json"


@dataclass
class NoiseReductionConfig:
    """降噪配置数据类"""
    enabled: bool = True  # 是否启用降噪
    lowcut: int = 200  # 低频截止 (Hz)，切除低频噪音
    highcut: int = 3500  # 高频截止 (Hz)，切除高频噪音
    order: int = 4  # 滤波器阶数，越高越陡峭
    filter_type: Literal["bandpass", "highpass", "lowpass"] = "bandpass"  # 滤波器类型
    normalize_after_filter: bool = True  # 滤波后是否重新归一化音频

    @classmethod
    def get_defaults(cls) -> 'NoiseReductionConfig':
        """获取默认配置"""
        return cls(
            enabled=True,
            lowcut=200,
            highcut=3500,
            order=4,
            filter_type="bandpass",
            normalize_after_filter=True,
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'NoiseReductionConfig':
        """从字典创建配置"""
        return cls(**data)


class NoiseReductionConfigManager:
    """降噪配置管理器（单例）"""
    _instance: Optional['NoiseReductionConfigManager'] = None
    _config: NoiseReductionConfig

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 先尝试从文件加载，失败则使用默认值
            cls._instance._config = cls._load_from_file() or NoiseReductionConfig.get_defaults()
        return cls._instance

    def get_config(self) -> NoiseReductionConfig:
        """获取当前配置"""
        return self._config

    def update_config(self, **kwargs) -> NoiseReductionConfig:
        """更新配置并返回新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Noise reduction config updated: {key} = {value}")
        # 保存到文件
        self._save_to_file()
        return self._config

    def reset_to_defaults(self) -> NoiseReductionConfig:
        """重置为默认配置"""
        self._config = NoiseReductionConfig.get_defaults()
        self._save_to_file()
        logger.info("Noise reduction config reset to defaults")
        return self._config

    @staticmethod
    def _load_from_file() -> Optional[NoiseReductionConfig]:
        """从文件加载配置"""
        if not os.path.exists(NOISE_CONFIG_FILE):
            logger.info(f"Noise config file not found: {NOISE_CONFIG_FILE}, using defaults")
            return None

        try:
            with open(NOISE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            config = NoiseReductionConfig.from_dict(data)
            logger.info(f"Noise reduction config loaded from file: {NOISE_CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load noise reduction config from file: {e}, using defaults")
            return None

    def _save_to_file(self) -> None:
        """保存配置到文件"""
        try:
            with open(NOISE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Noise reduction config saved to file: {NOISE_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save noise reduction config to file: {e}")


# 全局实例
noise_config_manager = NoiseReductionConfigManager()


def get_noise_config() -> NoiseReductionConfigManager:
    """获取全局降噪配置管理器实例"""
    return noise_config_manager
