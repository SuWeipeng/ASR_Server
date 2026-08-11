#!/usr/bin/env python3
"""
denoise_audio.py

  使用方法

  # 基本用法
  python denoise_audio.py input.mp3
  python denoise_audio.py input.mp4

  # 指定输出文件名
  python denoise_audio.py input.mp4 --output result.mp3

  # 命令行参数调整
  python denoise_audio.py input.mp3 --lowcut 100 --highcut 4000 --order 6

  # 使用高通滤波器
  python denoise_audio.py input.mp3 --filter-type highpass

  # 禁用降噪（仅提取音频）
  python denoise_audio.py input.mp4 --disable

  可调参数

  顶部文件可修改：
  ENABLED = True                          # 是否启用降噪
  FILTER_TYPE = "bandpass"               # bandpass/highpass/lowpass
  LOWCUT = 200                           # 低频截止 (Hz)
  HIGHCUT = 3500                         # 高频截止 (Hz)
  ORDER = 4                              # 滤波器阶数
  NORMALIZE_AFTER_FILTER = True          # 是否归一化
  OUTPUT_FILE = "audio_denoised.mp3"     # 输出文件名

  命令行参数

  ┌────────────────┬──────────────┬──────────────┐
  │      参数      │    默认值    │     说明     │
  ├────────────────┼──────────────┼──────────────┤
  │ --lowcut       │ 200          │ 低频截止频率 │
  ├────────────────┼──────────────┼──────────────┤
  │ --highcut      │ 3500         │ 高频截止频率 │
  ├────────────────┼──────────────┼──────────────┤
  │ --order        │ 4            │ 滤波器阶数   │
  ├────────────────┼──────────────┼──────────────┤
  │ --filter-type  │ bandpass     │ 滤波器类型   │
  ├────────────────┼──────────────┼──────────────┤
  │ --no-normalize │ -            │ 不归一化音频 │
  ├────────────────┼──────────────┼──────────────┤
  │ --disable      │ -            │ 禁用降噪     │
  └────────────────┴──────────────┴──────────────┘

  方便你快速测试不同参数效果！
"""

import os
import sys
import argparse
import tempfile
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal

# ============================================================
# 可调参数 - 修改这些参数来调整降噪效果
# ============================================================

# 是否启用降噪
ENABLED = True

# 滤波器类型: "bandpass"(带通), "highpass"(高通), "lowpass"(低通)
FILTER_TYPE = "bandpass"

# 低频截止 (Hz) - 切除风扇、空调等低频噪音
# 调大: 保留更多低频(如男声), 但可能保留噪音
# 调小: 切除更多低频噪音, 但声音可能变薄
LOWCUT = 200

# 高频截止 (Hz) - 切除电流声、电子杂音等高频噪音
# 调大: 保留更多高频(如齿音、女声), 但可能保留噪音
# 调小: 切除更多高频噪音
HIGHCUT = 3500

# 滤波器阶数 - 控制滤波器的"陡峭程度"
# 调大: 滤波更精确, 但计算量增加, 可能引入振铃
# 调小: 滤波更平缓, 但可能在截止频率附近有残留
# 建议: 4-6 是常用值
ORDER = 4

# 滤波后是否归一化 - 防止音量变小
NORMALIZE_AFTER_FILTER = True

# 输出文件名
OUTPUT_FILE = "audio_denoised.mp3"

# ============================================================
# 降噪算法实现
# ============================================================


def apply_bandpass_filter(data, lowcut, highcut, fs, order=4):
    """带通滤波器"""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    y = signal.lfilter(b, a, data)
    return y


def apply_highpass_filter(data, cutoff, fs, order=4):
    """高通滤波器"""
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='high')
    y = signal.lfilter(b, a, data)
    return y


def apply_lowpass_filter(data, cutoff, fs, order=4):
    """低通滤波器"""
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='low')
    y = signal.lfilter(b, a, data)
    return y


def normalize_audio(data):
    """归一化音频到 [-1, 1] 范围"""
    max_value = np.max(np.abs(data))
    if max_value > 0:
        data = data / max_value
    return data


def apply_noise_reduction(data, sample_rate):
    """应用降噪"""
    if not ENABLED:
        print("降噪已禁用，直接返回原始音频")
        return data

    print(f"正在应用降噪...")
    print(f"  滤波器类型: {FILTER_TYPE}")
    print(f"  低频截止: {LOWCUT} Hz")
    print(f"  高频截止: {HIGHCUT} Hz")
    print(f"  滤波器阶数: {ORDER}")

    # 应用相应滤波器
    if FILTER_TYPE == "bandpass":
        filtered = apply_bandpass_filter(data, LOWCUT, HIGHCUT, sample_rate, ORDER)
    elif FILTER_TYPE == "highpass":
        filtered = apply_highpass_filter(data, LOWCUT, sample_rate, ORDER)
    elif FILTER_TYPE == "lowpass":
        filtered = apply_lowpass_filter(data, HIGHCUT, sample_rate, ORDER)
    else:
        print(f"未知滤波器类型: {FILTER_TYPE}，使用带通滤波")
        filtered = apply_bandpass_filter(data, LOWCUT, HIGHCUT, sample_rate, ORDER)

    # 归一化
    if NORMALIZE_AFTER_FILTER:
        filtered = normalize_audio(filtered)
        print("  已归一化音频")

    return filtered


def extract_audio_with_ffmpeg(input_file, output_wav):
    """使用 FFmpeg 提取音频并转换为 WAV"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_file,
            '-vn',  # 不要视频
            '-acodec', 'pcm_s16le',  # PCM 16-bit
            '-ar', '16000',  # 16kHz 采样率
            '-ac', '1',  # 单声道
            '-y',  # 覆盖输出文件
            output_wav
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 错误: {e.stderr.decode()}")
        return False


def convert_to_mp3(input_wav, output_mp3):
    """使用 FFmpeg 转换为 MP3"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_wav,
            '-b:a', '192k',  # 比特率
            '-y',  # 覆盖输出文件
            output_mp3
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 错误: {e.stderr.decode()}")
        return False


def main():
    # 提前声明 global，防止在下面的 argparse 读取默认值时触发 SyntaxError
    global ENABLED, FILTER_TYPE, LOWCUT, HIGHCUT, ORDER, NORMALIZE_AFTER_FILTER

    parser = argparse.ArgumentParser(
        description='音频降噪工具 - 使用传统信号处理方法去除背景噪音',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python denoise_audio.py input.mp3
  python denoise_audio.py input.mp4
  python denoise_audio.py input.mp4 --output result.mp3

参数说明:
  lowcut:    低频截止频率，切除低频噪音（风扇、空调）
  highcut:   高频截止频率，切除高频噪音（电流声、电子杂音）
  order:     滤波器阶数，越大越陡峭，常用值 4-6
  filter_type: 滤波器类型 (bandpass/highpass/lowpass)
        '''
    )
    parser.add_argument('input', help='输入文件 (MP3/MP4)')
    parser.add_argument('--output', default=OUTPUT_FILE, help='输出文件名 (默认: denoised.mp3)')
    parser.add_argument('--lowcut', type=int, default=LOWCUT, help=f'低频截止频率 (默认: {LOWCUT} Hz)')
    parser.add_argument('--highcut', type=int, default=HIGHCUT, help=f'高频截止频率 (默认: {HIGHCUT} Hz)')
    parser.add_argument('--order', type=int, default=ORDER, help=f'滤波器阶数 (默认: {ORDER})')
    parser.add_argument('--filter-type', default=FILTER_TYPE,
                        choices=['bandpass', 'highpass', 'lowpass'],
                        help=f'滤波器类型 (默认: {FILTER_TYPE})')
    parser.add_argument('--no-normalize', action='store_true', help='不归一化音频')
    parser.add_argument('--disable', action='store_true', help='禁用降噪')

    args = parser.parse_args()

    # 更新参数
    ENABLED = not args.disable
    FILTER_TYPE = args.filter_type
    LOWCUT = args.lowcut
    HIGHCUT = args.highcut
    ORDER = args.order
    NORMALIZE_AFTER_FILTER = not args.no_normalize

    # 检查输入文件
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        return 1

    input_file = args.input
    output_file = args.output

    print("=" * 60)
    print("音频降噪工具")
    print("=" * 60)
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"降噪配置:")
    print(f"  启用: {ENABLED}")
    print(f"  滤波器类型: {FILTER_TYPE}")
    print(f"  低频截止: {LOWCUT} Hz")
    print(f"  高频截止: {HIGHCUT} Hz")
    print(f"  滤波器阶数: {ORDER}")
    print(f"  归一化: {NORMALIZE_AFTER_FILTER}")
    print("=" * 60)

    # 创建临时文件
    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()

    try:
        # 提取音频 (如果是 MP4 或其他格式)
        print(f"\n[1/3] 提取音频...")
        if input_file.lower().endswith('.mp4') or input_file.lower().endswith('.avi') or input_file.lower().endswith('.mkv'):
            success = extract_audio_with_ffmpeg(input_file, temp_wav_path)
            if not success:
                print("提取音频失败")
                return 1
            print(f"  音频已提取到临时文件")
        else:
            # 直接使用 soundfile 读取
            temp_wav_path = input_file

        # 读取音频
        print(f"\n[2/3] 读取音频文件...")
        try:
            audio, sr = sf.read(temp_wav_path)
            print(f"  采样率: {sr} Hz")
            print(f"  声道数: {1 if len(audio.shape) == 1 else audio.shape[1]}")
            print(f"  时长: {len(audio) / sr:.2f} 秒")

            # 转为单声道
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
                print(f"  已转为单声道")
        except Exception as e:
            print(f"读取音频失败: {e}")
            return 1

        # 应用降噪
        print(f"\n[3/3] 应用降噪...")
        denoised_audio = apply_noise_reduction(audio, sr)

        # 保存降噪后的音频
        print(f"\n保存降噪后的音频...")
        temp_denoised_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_denoised_wav_path = temp_denoised_wav.name
        temp_denoised_wav.close()

        sf.write(temp_denoised_wav_path, denoised_audio, sr)
        print(f"  已保存 WAV 格式")

        # 转换为 MP3
        print(f"  转换为 MP3...")
        if convert_to_mp3(temp_denoised_wav_path, output_file):
            print(f"\n✓ 降噪完成! 输出文件: {output_file}")

            # 显示文件大小
            input_size = os.path.getsize(input_file) / 1024 / 1024
            output_size = os.path.getsize(output_file) / 1024 / 1024
            print(f"\n文件大小:")
            print(f"  输入: {input_size:.2f} MB")
            print(f"  输出: {output_size:.2f} MB")
        else:
            print("转换为 MP3 失败")
            return 1

        # 清理临时文件
        try:
            if temp_wav_path != input_file:
                os.unlink(temp_wav_path)
            os.unlink(temp_denoised_wav_path)
        except:
            pass

        return 0

    except KeyboardInterrupt:
        print("\n\n用户中断")
        return 1
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())