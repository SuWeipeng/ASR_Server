"""
demucs 人声分离动态配置管理器
支持运行时更新配置参数，支持持久化存储
配置项包括：字幕生成时是否启用人声分离、模型名称、本地模型仓库路径、播放时是否使用人声音轨
"""
import json
import os
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from app.utils.logger import logger


# demucs 配置文件路径
DEMUCS_CONFIG_FILE = Path(__file__).parent.parent.parent / "demucs_config.json"

# 本地模型仓库默认路径（含 htdemucs 模型权重；留空则 demucs 联网从 HuggingFace 下载）
DEFAULT_DEMUCS_REPO_PATH = r"D:\adefossez\HTDemucs"


@dataclass
class DemucsConfig:
    """demucs 配置数据类"""
    enabled: bool = False  # 生成字幕时是否启用人声分离
    model_name: str = "htdemucs"  # 模型名称
    repo_path: str = DEFAULT_DEMUCS_REPO_PATH  # 本地模型仓库路径，留空则联网下载
    playback_use_vocals: bool = False  # 播放时是否使用人声音轨（不影响字幕生成）

    @classmethod
    def get_defaults(cls) -> 'DemucsConfig':
        """获取默认配置"""
        return cls(
            enabled=False,
            model_name="htdemucs",
            repo_path=DEFAULT_DEMUCS_REPO_PATH,
            playback_use_vocals=False,
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'DemucsConfig':
        """从字典创建配置"""
        return cls(**data)


class DemucsConfigManager:
    """demucs 配置管理器（单例）"""
    _instance: Optional['DemucsConfigManager'] = None
    _config: DemucsConfig

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 先尝试从文件加载，失败则使用默认值
            cls._instance._config = cls._load_from_file() or DemucsConfig.get_defaults()
        return cls._instance

    def get_config(self) -> DemucsConfig:
        """获取当前配置"""
        return self._config

    def update_config(self, **kwargs) -> DemucsConfig:
        """更新配置并返回新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Demucs config updated: {key} = {value}")
        # 保存到文件
        self._save_to_file()
        return self._config

    def reset_to_defaults(self) -> DemucsConfig:
        """重置为默认配置"""
        self._config = DemucsConfig.get_defaults()
        self._save_to_file()
        logger.info("Demucs config reset to defaults")
        return self._config

    @staticmethod
    def _load_from_file() -> Optional[DemucsConfig]:
        """从文件加载配置"""
        if not os.path.exists(DEMUCS_CONFIG_FILE):
            logger.info(f"Demucs config file not found: {DEMUCS_CONFIG_FILE}, using defaults")
            return None

        try:
            with open(DEMUCS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            config = DemucsConfig.from_dict(data)
            logger.info(f"Demucs config loaded from file: {DEMUCS_CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load demucs config from file: {e}, using defaults")
            return None

    def _save_to_file(self) -> None:
        """保存配置到文件"""
        try:
            with open(DEMUCS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Demucs config saved to file: {DEMUCS_CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save demucs config to file: {e}")


# 全局实例
demucs_config_manager = DemucsConfigManager()


def get_demucs_config() -> DemucsConfigManager:
    """获取全局 demucs 配置管理器实例"""
    return demucs_config_manager
