#!/usr/bin/env python3
"""
 基本用法：
  # 对比两个完整音频
  python compare_audio_waveform.py audio1.wav audio2.wav

  # 保存图片
  python compare_audio_waveform.py audio1.wav audio2.wav -o comparison.png

  SRT 时间戳功能：
  # 先列出 SRT 中的所有段落
  python compare_audio_waveform.py audio.wav --srt subtitles.srt --list-segments

  # 对比第 5 个段落对应的音频（将该段字幕作为窗口标题）
  python compare_audio_waveform.py audio1.wav audio2.wav --srt subtitles.srt --segment 5

  # 对比多个段落 (如第 1,3,5 段)
  python compare_audio_waveform.py audio1.wav audio2.wav --srt subtitles.srt --segments 1,3,5

  手动指定时间范围：
  python compare_audio_waveform.py audio1.wav audio2.wav --start 10.5 --end 15.0

  输出说明：
  - 弹窗窗口标题（代替 Figure 1）: 显示当前 segment 的字幕文本
  - 上图：两个音频的振幅波形对比（画两条线）
  - 下图：两个音频的音高轮廓对比（画两条线）
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import librosa

# 设置中文字体支持，防止字幕中文显示为方块
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号


def parse_srt_timestamp(timestamp_str: str) -> float:
    """Parse SRT timestamp to seconds"""
    parts = timestamp_str.split(',')
    time_part = parts[0]
    ms = int(parts[1]) if len(parts) > 1 else 0

    h, m, s = map(int, time_part.split(':'))
    return h * 3600 + m * 60 + s + ms / 1000


def parse_srt_file(srt_path: str) -> list:
    """Parse SRT subtitle file"""
    segments = []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d+)\s*\n\s*(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)\n(?=\d+\s*\n|\Z)'

    for match in re.finditer(pattern, content):
        index = int(match.group(1))
        start = parse_srt_timestamp(match.group(2))
        end = parse_srt_timestamp(match.group(3))
        text = match.group(4).strip()

        segments.append({
            'index': index,
            'start': start,
            'end': end,
            'text': text,
            'duration': end - start
        })

    return segments


def list_srt_segments(segments: list):
    """List all SRT segments for user selection"""
    print("\nAvailable SRT segments:")
    print("-" * 80)
    for seg in segments:
        print(f"#{seg['index']:3d} | {seg['start']:7.3f}s - {seg['end']:7.3f}s | {seg['duration']:5.2f}s | {seg['text'][:50]}")
    print("-" * 80)


def load_audio_segment(audio_path: str, start_time: float = 0, duration: float = None):
    """Load audio segment using librosa"""
    try:
        y, sr = librosa.load(audio_path, sr=None, offset=start_time, duration=duration)
        return y, sr
    except Exception as e:
        print(f"Error loading {audio_path}: {e}")
        sys.exit(1)


def generate_amplitude_waveform(audio: np.ndarray, num_points: int = 500) -> np.ndarray:
    """Generate amplitude waveform data (normalized 0 to 1)"""
    frame_length = len(audio) // num_points

    if frame_length > 0:
        frames = audio[:frame_length * num_points].reshape(-1, frame_length)
        amplitudes = np.sqrt(np.mean(frames ** 2, axis=1))
        if np.max(amplitudes) > 0:
            amplitudes = amplitudes / np.max(amplitudes)
        return amplitudes
    else:
        return np.zeros(num_points)


def generate_pitch_contour(audio: np.ndarray, sr: int, num_points: int = 500) -> np.ndarray:
    """Generate pitch contour using librosa's pyin pitch detection"""
    try:
        pitches, voiced_mask, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz('C2'),  # ~65 Hz
            fmax=librosa.note_to_hz('C7'),   # ~2093 Hz
            sr=sr,
            frame_length=2048,
            hop_length=512
        )

        if len(pitches) > num_points:
            indices = np.linspace(0, len(pitches) - 1, num_points).astype(int)
            pitches = pitches[indices]
        elif len(pitches) < num_points:
            pitches = np.interp(
                np.linspace(0, len(pitches) - 1, num_points),
                np.arange(len(pitches)),
                pitches
            )

        return pitches

    except Exception as e:
        print(f"Pitch detection failed: {e}")
        return np.full(num_points, np.nan)


def plot_comparison(audio1_path: str, audio2_path: str,
                    label1: str = "Audio 1", label2: str = "Audio 2",
                    num_points: int = 500,
                    start_time: float = None,
                    end_time: float = None,
                    output_path: str = None,
                    title: str = None):
    """
    Generate stacked comparison plots for two audio files (2 subplots)
    - Top plot: Amplitude comparison (2 lines)
    - Bottom plot: Pitch comparison (2 lines)
    """
    duration = None if start_time is None or end_time is None else (end_time - start_time)

    print(f"Loading {audio1_path}...")
    y1, sr1 = load_audio_segment(audio1_path, start_time, duration)
    actual_duration1 = len(y1) / sr1
    time_offset1 = start_time if start_time else 0
    print(f"  Segment: {time_offset1:.2f}s - {time_offset1 + actual_duration1:.2f}s ({actual_duration1:.2f}s total)")
    print(f"  Sample rate: {sr1}Hz")

    print(f"Loading {audio2_path}...")
    y2, sr2 = load_audio_segment(audio2_path, start_time, duration)
    actual_duration2 = len(y2) / sr2
    time_offset2 = start_time if start_time else 0
    print(f"  Segment: {time_offset2:.2f}s - {time_offset2 + actual_duration2:.2f}s ({actual_duration2:.2f}s total)")
    print(f"  Sample rate: {sr2}Hz")

    print("Generating amplitude waveforms...")
    amp1 = generate_amplitude_waveform(y1, num_points)
    amp2 = generate_amplitude_waveform(y2, num_points)

    print("Generating pitch contours...")
    pitch1 = generate_pitch_contour(y1, sr1, num_points)
    pitch2 = generate_pitch_contour(y2, sr2, num_points)

    # Create time axis
    time1 = np.linspace(time_offset1, time_offset1 + actual_duration1, num_points)
    time2 = np.linspace(time_offset2, time_offset2 + actual_duration2, num_points)

    # 创建 2x1 布局图（上下两个图，共享 X 轴）
    fig, (ax_amp, ax_pitch) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 确定标题（优先使用传入的字幕文本，没有则使用默认格式）
    fig_title = title if title else f'Audio Comparison: {label1} vs {label2}'

    # 重点：更改弹窗对话框的标题（代替默认的 "Figure 1"）
    if hasattr(fig.canvas, 'manager') and fig.canvas.manager is not None:
        try:
            fig.canvas.manager.set_window_title(fig_title)
        except Exception:
            pass

    # 设置图表顶部的主标题
    fig.suptitle(fig_title, fontsize=14, fontweight='bold')

    # 定义对比颜色
    color1 = '#2E86AB'  # Audio 1 使用蓝色
    color2 = '#C73E1D'  # Audio 2 使用红/橙色

    # 1. 上图：振幅波形对比（画两条线）
    ax_amp.plot(time1, amp1, color=color1, linewidth=1.5, alpha=0.8, label=label1)
    ax_amp.plot(time2, amp2, color=color2, linewidth=1.5, alpha=0.8, label=label2)
    ax_amp.set_title('Amplitude Waveform Comparison', fontsize=11, fontweight='bold')
    ax_amp.set_ylabel('Amplitude (normalized)')
    ax_amp.set_ylim(0, 1.1)
    ax_amp.grid(True, alpha=0.3)
    ax_amp.legend(loc='upper right')

    # 2. 下图：音高轮廓对比（画两条线）
    valid_pitch1 = pitch1[~np.isnan(pitch1)]
    valid_pitch2 = pitch2[~np.isnan(pitch2)]

    ax_pitch.plot(time1, pitch1, color=color1, linewidth=1.5, alpha=0.8, label=f'{label1} Pitch')
    ax_pitch.plot(time2, pitch2, color=color2, linewidth=1.5, alpha=0.8, label=f'{label2} Pitch')
    ax_pitch.set_title('Pitch Contour Comparison', fontsize=11, fontweight='bold')
    ax_pitch.set_xlabel('Time (s)')
    ax_pitch.set_ylabel('Pitch (Hz)')

    # 根据数据动态设置音高 Y 轴上限
    all_valid = np.concatenate([valid_pitch1, valid_pitch2]) if (len(valid_pitch1) or len(valid_pitch2)) else np.array([])
    if len(all_valid) > 0:
        max_p = np.nanmax(all_valid)
        ax_pitch.set_ylim(0, max(500, max_p * 1.15))
    else:
        ax_pitch.set_ylim(0, 800)

    ax_pitch.grid(True, alpha=0.3)
    ax_pitch.legend(loc='upper right')

    # 显示音高范围文本框
    info_texts = []
    if len(valid_pitch1) > 0:
        info_texts.append(f'{label1} pitch: {np.nanmin(pitch1):.1f}-{np.nanmax(pitch1):.1f} Hz')
    if len(valid_pitch2) > 0:
        info_texts.append(f'{label2} pitch: {np.nanmin(pitch2):.1f}-{np.nanmax(pitch2):.1f} Hz')

    if info_texts:
        ax_pitch.text(0.02, 0.95, '\n'.join(info_texts),
                      transform=ax_pitch.transAxes, verticalalignment='top',
                      bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\nPlot saved to: {output_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Compare two audio files with waveform and pitch visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Compare full audio files
  python compare_audio_waveform.py audio1.wav audio2.wav

  # Compare with custom labels
  python compare_audio_waveform.py audio1.wav audio2.wav --label1 "Original" --label2 "Denoised"

  # Compare specific time range
  python compare_audio_waveform.py audio1.wav audio2.wav --start 10.5 --end 15.0

  # List SRT segments first
  python compare_audio_waveform.py audio.wav --srt subtitles.srt --list-segments

  # Compare segment #5 from SRT
  python compare_audio_waveform.py audio1.wav audio2.wav --srt subtitles.srt --segment 5

  # Compare multiple segments
  python compare_audio_waveform.py audio1.wav audio2.wav --srt subtitles.srt --segments 1,3,5
        '''
    )
    parser.add_argument('audio1', help='Path to first audio file')
    parser.add_argument('audio2', nargs='?', help='Path to second audio file (optional with --list-segments)')
    parser.add_argument('--label1', default='Audio 1', help='Label for first audio (default: "Audio 1")')
    parser.add_argument('--label2', default='Audio 2', help='Label for second audio (default: "Audio 2")')
    parser.add_argument('--points', type=int, default=500, help='Number of data points (default: 500)')
    parser.add_argument('--start', type=float, help='Start time in seconds')
    parser.add_argument('--end', type=float, help='End time in seconds')
    parser.add_argument('--output', '-o', help='Output path for saving the plot')
    parser.add_argument('--srt', help='Path to SRT subtitle file for segment selection')
    parser.add_argument('--list-segments', action='store_true', help='List all SRT segments and exit')
    parser.add_argument('--segment', type=int, help='SRT segment number to visualize (1-based)')
    parser.add_argument('--segments', help='Comma-separated SRT segment numbers to visualize (e.g., "1,3,5")')

    args = parser.parse_args()

    # Handle SRT listing mode
    if args.list_segments:
        if not args.srt:
            print("Error: --srt is required for --list-segments")
            sys.exit(1)
        if not Path(args.srt).exists():
            print(f"Error: SRT file not found: {args.srt}")
            sys.exit(1)
        segments = parse_srt_file(args.srt)
        list_srt_segments(segments)
        sys.exit(0)

    # Check required arguments
    if not args.audio2:
        print("Error: audio2 is required (unless using --list-segments)")
        parser.print_help()
        sys.exit(1)

    # Validate input files
    if not Path(args.audio1).exists():
        print(f"Error: File not found: {args.audio1}")
        sys.exit(1)
    if not Path(args.audio2).exists():
        print(f"Error: File not found: {args.audio2}")
        sys.exit(1)

    # Determine time range & segment title
    start_time = args.start
    end_time = args.end
    segment_title = None

    # Handle SRT segment selection
    if args.srt:
        if not Path(args.srt).exists():
            print(f"Error: SRT file not found: {args.srt}")
            sys.exit(1)

        segments = parse_srt_file(args.srt)

        # Single segment
        if args.segment:
            seg = next((s for s in segments if s['index'] == args.segment), None)
            if not seg:
                print(f"Error: Segment #{args.segment} not found in SRT")
                sys.exit(1)
            start_time = seg['start']
            end_time = seg['end']
            # 将 SRT 编号与字幕内容设为窗口/图表标题
            segment_title = f"#{seg['index']}: {seg['text']}"
            print(f"\nSelected segment #{seg['index']}: {seg['text'][:60]}")
            print(f"Time range: {start_time:.3f}s - {end_time:.3f}s")

        # Multiple segments
        elif args.segments:
            segment_indices = [int(x.strip()) for x in args.segments.split(',')]
            selected_segments = [s for s in segments if s['index'] in segment_indices]

            if not selected_segments:
                print(f"Error: No matching segments found")
                sys.exit(1)

            start_time = min(s['start'] for s in selected_segments)
            end_time = max(s['end'] for s in selected_segments)

            segment_ids_str = ", ".join(f"#{s['index']}" for s in selected_segments)
            combined_text = " / ".join(s['text'] for s in selected_segments)
            segment_title = f"Segments [{segment_ids_str}]: {combined_text}"

            print(f"\nSelected segments: {segment_ids_str}")
            for s in selected_segments:
                print(f"  #{s['index']}: {s['text'][:50]}")
            print(f"Combined time range: {start_time:.3f}s - {end_time:.3f}s")

    # Validate time range
    if start_time is not None and end_time is not None:
        if start_time >= end_time:
            print("Error: start time must be less than end time")
            sys.exit(1)

    plot_comparison(
        args.audio1,
        args.audio2,
        label1=args.label1,
        label2=args.label2,
        num_points=args.points,
        start_time=start_time,
        end_time=end_time,
        output_path=args.output,
        title=segment_title
    )


if __name__ == '__main__':
    main()