"""
demucs 人声分离工具

- 可用性检测：demucs 与服务器运行在同一 Python 环境，用 importlib.util.find_spec
  检测（毫秒级，避免 import demucs 连带 torch 的数秒开销拖垮 /api/system/status 轮询）
- 人声分离：通过 subprocess 调用 `python -m demucs.separate`（sys.executable 保证环境一致），
  只分离 vocals 轨（--two-stems vocals），输出 16kHz 单声道 WAV 供下游 VAD/ASR 直接使用
"""
import os
import sys
import shutil
import subprocess
import importlib.util
from pathlib import Path
from typing import Optional

from app.utils.logger import logger
from app.utils.ffmpeg import extract_audio, get_ffmpeg_env
from app.config import settings


# 进程内缓存检测结果（demucs 安装状态在运行期间不会变化）
_demucs_available_cache: Optional[bool] = None


def check_demucs_available() -> bool:
    """
    检测 demucs 是否已安装（当前 Python 环境中可导入）

    Returns:
        True if demucs package is available
    """
    global _demucs_available_cache
    if _demucs_available_cache is None:
        _demucs_available_cache = importlib.util.find_spec("demucs") is not None
        if _demucs_available_cache:
            logger.info("demucs package detected")
        else:
            logger.info("demucs package not found (vocal separation disabled)")
    return _demucs_available_cache


def check_demucs_on_startup():
    """启动时检测 demucs 可用性并记录日志"""
    if not check_demucs_available():
        logger.warning("demucs not found! Vocal separation feature will be disabled.")
        logger.warning("Install with: pip install demucs")
        return False

    # 检查本地模型仓库路径（配置了仓库路径但目录不存在时提前预警）
    from app.core.demucs_config import get_demucs_config
    repo_path = get_demucs_config().get_config().repo_path
    if repo_path and not os.path.isdir(repo_path):
        logger.warning(
            f"demucs repo path does not exist: {repo_path}. "
            "Separation will fail or try to download models from HuggingFace."
        )
    logger.info("✅ demucs is available")
    return True


def separate_vocals_to_16k_mono(
    file_id: str,
    input_path: str,
    output_path: str,
    model_name: str = "htdemucs",
    repo_path: str = "",
    duration: Optional[float] = None
) -> bool:
    """
    用 demucs 分离人声并转换为 16kHz 单声道 WAV

    Args:
        file_id: 媒体文件 ID（用于临时工作目录命名）
        input_path: 输入媒体文件路径（视频或音频，demucs 内部用 ffmpeg 解码）
        output_path: 输出 WAV 文件路径（16kHz 单声道 16bit PCM）
        model_name: demucs 模型名称（如 htdemucs）
        repo_path: 本地模型仓库路径；为空或不存在则不传 --repo（demucs 联网下载）
        duration: 媒体时长（秒），用于计算子进程超时

    Returns:
        True 成功；False 失败（调用方应回退用原始音频）
    """
    work_dir = Path(settings.TEMP_DIR) / "demucs" / file_id
    try:
        # 清理上次可能残留的临时输出
        shutil.rmtree(work_dir, ignore_errors=True)
        work_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "demucs.separate",
            "--two-stems", "vocals",
            "--other-method", "none",  # 不写 no_vocals.wav，磁盘 IO 减半
            "-n", model_name,
        ]
        if repo_path and os.path.isdir(repo_path):
            cmd += ["--repo", repo_path]
        cmd += ["-o", str(work_dir), str(input_path)]

        # demucs 解码输入用的是裸命令名 ffmpeg/ffprobe，必须注入 ffmpeg 所在目录到 PATH
        env = get_ffmpeg_env()

        # GPU 上分离速度约为实时的 40-70 倍；600s 下限覆盖模型加载/CUDA 初始化，
        # 时长 x20 的系数覆盖慢机或 CPU 回退场景
        timeout = max(600, int((duration or 0) * 20))
        logger.info(f"Running demucs vocal separation (timeout={timeout}s): {' '.join(cmd)}")

        try:
            # 显式 utf-8：demucs 往 stdout 打 unicode 进度条，
            # Windows 下 text=True 默认 GBK 解码会抛 UnicodeDecodeError
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"demucs separation timed out after {timeout}s")
            return False
        except FileNotFoundError as e:
            logger.warning(f"Failed to launch demucs subprocess: {e}")
            return False

        if result.returncode != 0:
            stderr_tail = (result.stderr or "")[-500:]
            logger.warning(f"demucs exited with code {result.returncode}: {stderr_tail}")
            return False

        # 定位输出文件：{work_dir}/{model_name}/{输入文件名去扩展名}/vocals.wav
        track_stem = Path(input_path).stem
        vocals_raw = work_dir / model_name / track_stem / "vocals.wav"
        if not vocals_raw.exists():
            found = list(work_dir.rglob("vocals.wav"))
            if not found:
                logger.warning("demucs produced no vocals.wav output")
                return False
            vocals_raw = found[0]

        # 转换为 16kHz 单声道，下游 VAD/ASR 无需任何改动
        extract_audio(str(vocals_raw), output_path,
                      sample_rate=settings.AUDIO_SAMPLE_RATE,
                      channels=settings.AUDIO_CHANNELS)
        logger.info(f"Vocal separation complete: {output_path}")
        return True

    except Exception as e:
        logger.warning(f"demucs separation failed: {e}")
        return False
    finally:
        # cleanup_temp_files 只遍历 temp 顶层文件，不递归子目录，
        # 因此 demucs 的中间输出目录必须即用即删
        shutil.rmtree(work_dir, ignore_errors=True)
