import React, { useRef, useEffect, useState, forwardRef, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Play, Pause, Volume2, VolumeX, ExternalLink, Upload } from 'lucide-react';
import { setPlaying, setVolume, setMuted, togglePlay, setSeeking, setCurrentTime, setIntentTime, setSingleSentenceMode } from '../../store/playerSlice';
import { setCurrentSubtitleIndex, clearSeekRequest } from '../../store/subtitleSlice';
import { formatTime, getPlaybackProgress } from '../../utils/timeFormat';
import { usePlayerSync } from '../../hooks/usePlayerSync';
import { usePlayerWindow } from '../../hooks/usePlayerWindow';
import { mediaService } from '../../services/mediaService';

export const VideoPlayer = forwardRef((props, ref) => {
  const dispatch = useDispatch();
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const progressBarRef = useRef(null);
  const isDraggingRef = useRef(false);

  const fileId = useSelector((state) => state.media.fileId);
  const playbackUseVocals = useSelector((state) => state.ui.demucsConfig?.playback_use_vocals);
  const transcriptionMetadata = useSelector((state) => state.subtitle.transcriptionMetadata);
  const isPlaying = useSelector((state) => state.player.isPlaying);
  const currentTime = useSelector((state) => state.player.currentTime);
  const duration = useSelector((state) => state.player.duration);
  const volume = useSelector((state) => state.player.volume);
  const isMuted = useSelector((state) => state.player.isMuted);
  const isSeeking = useSelector((state) => state.player.isSeeking);
  const singleSentenceMode = useSelector((state) => state.player.singleSentenceMode);
  const singleSentenceEnd = useSelector((state) => state.player.singleSentenceEnd);
  const playbackRate = useSelector((state) => state.player.playbackRate);
  const subtitles = useSelector((state) => state.subtitle.filteredSubtitles);
  const currentSubtitleIndex = useSelector((state) => state.subtitle.currentSubtitleIndex);
  const seekRequest = useSelector((state) => state.subtitle.seekRequest);

  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // 人声音轨：播放偏好开启且当前视频由 demucs 生成字幕时，叠加 audio 元素播放人声
  const audioRef = useRef(null);
  // vocals 文件可能已被清理（404）时回退原声
  const [vocalsAvailable, setVocalsAvailable] = useState(true);
  const useVocals = !!(playbackUseVocals && transcriptionMetadata?.used_demucs && vocalsAvailable);

  // 切换文件时重置回退状态
  useEffect(() => {
    setVocalsAvailable(true);
  }, [fileId]);

  // 换文件时销毁上一个 video。
  //
  // 为什么必须显式停：<video> 带 key={fileId}，换文件时 React 会把旧元素
  // 从 DOM 上摘掉，但【摘掉不等于停止播放】——脱离文档的 media 元素仍会
  // 继续解码并输出音频，于是旧片段变成"看不见但一直响"的幽灵播放器，
  // 还会占着解码器拖慢新视频加载。
  //
  // 用 callback ref 而不是 useEffect 清理来干这件事：
  // useEffect 的清理在 StrictMode 下会在【同一个还挂着的元素】上执行一遍
  // （开发模式故意双调用 effect 来暴露这类问题），把还在用的 video 的 src
  // 抹掉 → 黑屏且永远不播。callback ref 只在元素真正被替换/卸载时才拿到旧元素。
  const handleVideoRef = useCallback((el) => {
    const prev = videoRef.current;
    if (prev && prev !== el) {
      // 旧元素被换掉：彻底停掉并释放解码器
      prev.pause();
      prev.removeAttribute('src');
      prev.load();
    }
    // 转发给父组件
    videoRef.current = el;
    if (typeof ref === 'function') {
      ref(el);
    } else if (ref) {
      ref.current = el;
    }
  }, [ref]);

  // <audio> 是条件渲染的（useVocals），开/关人声或换文件都会让它挂载/卸载，
  // 同样要把旧的停掉，避免留下"看不见但一直响"的幽灵音轨。
  const handleAudioRef = useCallback((el) => {
    const prev = audioRef.current;
    if (prev && prev !== el) {
      prev.pause();
      prev.removeAttribute('src');
      prev.load();
    }
    audioRef.current = el;
  }, []);

  // Model status check for drag upload
  const systemStatus = useSelector((state) => state.ui.systemStatus);
  const isModelReady = systemStatus?.model_loaded;

  // Player window management
  const { isDetached, openPlayerWindow } = usePlayerWindow();

  // Refs that mirror Redux state so drag handlers can read latest values
  // without re-creating the listeners on every dispatch.
  const subtitlesRef = useRef(subtitles);
  const currentSubtitleIndexRef = useRef(currentSubtitleIndex);
  const durationRef = useRef(duration);
  const isPlayingRef = useRef(isPlaying);
  useEffect(() => { subtitlesRef.current = subtitles; }, [subtitles]);
  useEffect(() => { currentSubtitleIndexRef.current = currentSubtitleIndex; }, [currentSubtitleIndex]);
  useEffect(() => { durationRef.current = duration; }, [duration]);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);

  usePlayerSync(videoRef, audioRef);

  // 分离窗口"放回主窗口"时本组件重新挂载：捕获 Redux 中的播放进度
  // （由独立窗口经 STATE_UPDATE 回传），视频元数据加载后 seek 过去，避免跳回开头。
  // 仅挂载时捕获一次——上传新文件不会重挂载本组件，不会误跳。
  const reduxCurrentTime = useSelector((state) => state.player.currentTime);
  const initialSeekRef = useRef(reduxCurrentTime > 0.5 ? reduxCurrentTime : null);
  const initialSeekPendingRef = useRef(false);
  useEffect(() => {
    const video = videoRef.current;
    const target = initialSeekRef.current;
    if (!video || target === null) return;
    initialSeekRef.current = null;
    // seek 期间拦截自动起播，避免先从 0 播放一小段再跳转
    initialSeekPendingRef.current = true;

    const finishSeek = () => {
      initialSeekPendingRef.current = false;
      if (isPlayingRef.current) {
        video.play().catch(console.error);
        const audio = audioRef.current;
        if (audio) {
          audio.currentTime = video.currentTime;
          if (!video.seeking) {
            audio.play().catch(() => {});
          }
        }
      }
    };
    const seekToTarget = () => {
      video.currentTime = target;
      if (video.seeking) {
        video.addEventListener('seeked', finishSeek, { once: true });
      } else {
        finishSeek();
      }
    };
    if (video.readyState >= 1) {
      seekToTarget();
    } else {
      video.addEventListener('loadedmetadata', seekToTarget, { once: true });
    }
  }, []);

  // Compute a seek time from a pointer/touch position relative to the bar.
  const computeTimeFromEvent = useCallback((clientX) => {
    const bar = progressBarRef.current;
    if (!bar) return 0;
    const rect = bar.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, x / rect.width));
    const dur = durationRef.current;
    if (!dur || dur <= 0) return 0;
    return percentage * dur;
  }, []);

  // Find the subtitle index that contains the given time.
  const findSubtitleIndex = useCallback((time) => {
    const subs = subtitlesRef.current;
    if (!subs || subs.length === 0) return -1;
    return subs.findIndex((s) => time >= s.start && time < s.end);
  }, []);

  // Handle seek-to-subtitle requests from SubtitlePanel via Redux.
  // Jump to subtitle, play it, and auto-pause when it ends (single sentence mode).
  useEffect(() => {
    if (seekRequest.index < 0) return;
    const subtitle = subtitles[seekRequest.index];
    if (subtitle && videoRef.current) {
      // Jump to the subtitle start
      videoRef.current.currentTime = subtitle.start;
      dispatch(setIntentTime(subtitle.start));

      // Enable single sentence mode with the subtitle's end time
      dispatch(setSingleSentenceMode({
        mode: true,
        endTime: subtitle.end
      }));

      // Start playing
      dispatch(setPlaying(true));

      dispatch(clearSeekRequest());
    }
  }, [seekRequest.token, subtitles, dispatch]);

  // Update progress bar
  useEffect(() => {
    setProgress(getPlaybackProgress(currentTime, duration));
  }, [currentTime, duration]);

  // Handle play/pause
  const togglePlayback = () => {
    // When user manually clicks play button, exit single sentence mode
    if (singleSentenceMode && !isPlaying) {
      dispatch(setSingleSentenceMode({ mode: false, endTime: null }));
    }
    dispatch(togglePlay());
  };

  // Progress bar drag: pointer/touch start begins a drag, window-level
  // move/end keep tracking even when the cursor leaves the bar.
  const handleSeekStart = (e) => {
    const dur = durationRef.current;
    if (!dur || dur <= 0) return;

    isDraggingRef.current = true;
    dispatch(setSeeking(true));

    const point = e.touches ? e.touches[0] : e;
    const newTime = computeTimeFromEvent(point.clientX);

    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }

    dispatch(setIntentTime(newTime));

    const idx = findSubtitleIndex(newTime);
    if (idx !== -1 && idx !== currentSubtitleIndexRef.current) {
      dispatch(setCurrentSubtitleIndex(idx));
    }
  };

  const handleSeekMove = useCallback((e) => {
    if (!isDraggingRef.current) return;
    const point = e.touches ? e.touches[0] : e;
    const newTime = computeTimeFromEvent(point.clientX);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
    dispatch(setIntentTime(newTime));
    const idx = findSubtitleIndex(newTime);
    if (idx !== -1 && idx !== currentSubtitleIndexRef.current) {
      dispatch(setCurrentSubtitleIndex(idx));
    }
  }, [computeTimeFromEvent, findSubtitleIndex, dispatch]);

  const handleSeekEnd = useCallback(() => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    dispatch(setSeeking(false));
  }, [dispatch]);

  // Register global pointer/touch listeners while the component is mounted.
  useEffect(() => {
    window.addEventListener('mousemove', handleSeekMove);
    window.addEventListener('mouseup', handleSeekEnd);
    window.addEventListener('touchmove', handleSeekMove, { passive: true });
    window.addEventListener('touchend', handleSeekEnd);
    window.addEventListener('touchcancel', handleSeekEnd);
    return () => {
      window.removeEventListener('mousemove', handleSeekMove);
      window.removeEventListener('mouseup', handleSeekEnd);
      window.removeEventListener('touchmove', handleSeekMove);
      window.removeEventListener('touchend', handleSeekEnd);
      window.removeEventListener('touchcancel', handleSeekEnd);
    };
  }, [handleSeekMove, handleSeekEnd]);

  // Safety net: if component unmounts mid-drag, clear the flag.
  useEffect(() => {
    return () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
      }
    };
  }, []);

  // Handle volume change
  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    dispatch(setVolume(newVolume));
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  // Handle mute toggle
  const toggleMute = () => {
    dispatch(setMuted(!isMuted));
    if (videoRef.current) {
      videoRef.current.muted = !isMuted || useVocals;
    }
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
    }
  };

  // Validate media file type
  const validateMediaFile = (file) => {
    const validTypes = ['video/', 'audio/'];
    const isValidType = validTypes.some(type => file.type.startsWith(type));
    const validExtensions = ['.mp4', '.webm', '.ogg', '.mp3', '.wav', '.m4a', '.aac', '.mkv', '.avi', '.mov', '.flv'];
    const hasValidExtension = validExtensions.some(ext =>
      file.name.toLowerCase().endsWith(ext)
    );
    return isValidType || hasValidExtension;
  };

  // Handle drag over
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isModelReady) {
      setIsDragging(true);
    }
  }, [isModelReady]);

  // Handle drag leave
  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Ensure we're really leaving the drop zone
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom) {
      setIsDragging(false);
    }
  }, []);

  // Handle file drop
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    // Check if model is ready
    if (!isModelReady) {
      return;
    }

    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    // Validate file type
    if (!validateMediaFile(file)) {
      return;
    }

    // Trigger file upload event (same as Header button)
    window.dispatchEvent(new CustomEvent('fileUpload', { detail: file }));
  }, [isModelReady]);

  // Sync play state with video (and vocals audio)
  // Only depends on isPlaying - let video element be the source of truth during playback
  useEffect(() => {
    const video = videoRef.current;
    const audio = audioRef.current;
    // 初始 seek（分离窗口放回时的进度恢复）完成前不自动起播
    const pendingInitialSeek = initialSeekPendingRef.current;
    if (video) {
      if (isPlaying && !pendingInitialSeek) {
        video.play().catch(console.error);
      } else if (!isPlaying) {
        video.pause();
      }
    }
    if (audio && video) {
      // 先对齐时间轴；video 仍在 seek 时不先出声，等 seeked 后再一起播放
      // （否则 audio 抢跑后被 seeked 对齐拽回句首，造成开头单词重复的回声）
      audio.currentTime = video.currentTime;
      if (isPlaying && !pendingInitialSeek && !video.seeking) {
        audio.play().catch(console.error);
      } else if (!isPlaying) {
        audio.pause();
      }
    }
  }, [isPlaying, useVocals, fileId]);

  // Sync volume/mute/playbackRate with video and vocals audio
  // 人声模式下 video 静音、audio 承担声音输出。fileId 入 deps：
  // 切换文件时 video 元素被重建（muted 默认 false），必须重新静音，否则双声叠加
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = volume;
      videoRef.current.muted = isMuted || useVocals;
    }
    if (audioRef.current) {
      audioRef.current.volume = volume;
      audioRef.current.muted = isMuted;
      audioRef.current.playbackRate = playbackRate;
    }
  }, [volume, isMuted, playbackRate, useVocals, fileId]);

  // 人声模式：video 的 seek 期间暂停 audio，seeked 后对齐时间轴再一起起播，
  // 避免 audio 抢跑后被拽回句首（单句播放开头 "In In fact" 式重复词回声）。
  // 覆盖：字幕点击跳转 / 进度条拖拽 / 单句循环回跳。
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !useVocals) return;

    const handleSeeking = () => {
      const audio = audioRef.current;
      if (audio && isPlayingRef.current) {
        audio.pause();
      }
    };
    const handleSeeked = () => {
      const audio = audioRef.current;
      if (!audio) return;
      audio.currentTime = video.currentTime;
      if (isPlayingRef.current) {
        audio.play().catch(() => {});
      }
    };
    // audio 缓冲就绪即起播兜底：弹窗打开时 wav 从中间位置缓冲可能滞后于视频，
    // 等它有数据了立即跟上，而不是依赖某一次 play() 调用恰好落在可用时机上
    const handleAudioCanPlay = () => {
      const audio = audioRef.current;
      if (audio && isPlayingRef.current && audio.paused && !video.seeking) {
        audio.play().catch(() => {});
      }
    };
    video.addEventListener('seeking', handleSeeking);
    video.addEventListener('seeked', handleSeeked);
    const audioEl = audioRef.current;
    if (audioEl) {
      audioEl.addEventListener('canplay', handleAudioCanPlay);
      audioEl.addEventListener('loadeddata', handleAudioCanPlay);
    }
    return () => {
      video.removeEventListener('seeking', handleSeeking);
      video.removeEventListener('seeked', handleSeeked);
      if (audioEl) {
        audioEl.removeEventListener('canplay', handleAudioCanPlay);
        audioEl.removeEventListener('loadeddata', handleAudioCanPlay);
      }
    };
  }, [useVocals, fileId]);

  if (!fileId) {
    return (
      <div
        className={`flex flex-col items-center justify-center h-64 bg-bg-secondary border-2 rounded-lg transition-all ${
          isDragging && isModelReady
            ? 'border-primary bg-primary/10 scale-[1.02]'
            : isModelReady
            ? 'border-dashed border-bg-card hover:border-primary/50 cursor-pointer'
            : 'border-bg-card opacity-50 cursor-not-allowed'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        title={!isModelReady ? '模型加载中，请稍后...' : '拖拽音视频文件到此处'}
      >
        <Upload
          size={48}
          className={`mb-3 ${isModelReady ? 'text-primary' : 'text-text-secondary'}`}
        />
        <p className={`text-lg ${isModelReady ? 'text-text-primary' : 'text-text-secondary'}`}>
          {!isModelReady ? '模型加载中...' : '请先上传音视频文件'}
        </p>
        {isModelReady && (
          <p className="text-sm text-text-secondary mt-2">
            拖拽文件到此处或点击上方"打开文件"按钮
          </p>
        )}
      </div>
    );
  }

  const mediaUrl = mediaService.getMediaUrl(fileId);

  return (
    <div ref={containerRef} className="bg-bg-secondary rounded-lg overflow-hidden">
      {/* Header with open window button */}
      <div className="h-8 bg-bg-tertiary flex items-center justify-end px-3">
        <button
          onClick={openPlayerWindow}
          className="flex items-center space-x-2 px-3 py-1.5 text-xs bg-bg-card hover:bg-bg-primary text-text-primary rounded-md transition-colors"
          title="打开独立窗口"
        >
          <ExternalLink size={14} />
          <span>打开独立窗口</span>
        </button>
      </div>

      {/* Video element */}
      <div className="relative aspect-video bg-black group">
        {/* key 必须与下面的 <audio> 区分开：video 和 audio 是兄弟节点，
            用同一个 key 会让 React 的协调逻辑错乱，旧 video 不会被删除。 */}
        <video
          key={`video-${fileId}`}
          ref={handleVideoRef}
          src={mediaUrl}
          preload="auto"
          className="w-full h-full"
          onClick={togglePlayback}
          onError={(e) => {
            console.error('[VideoPlayer] Video error:', e);
          }}
        />

        {/* 人声音轨（video 静音，audio 跟随 video 时钟播放） */}
        {useVocals && (
          <audio
            key={`audio-${fileId}`}
            ref={handleAudioRef}
            src={mediaService.getVocalsUrl(fileId)}
            preload="auto"
            className="hidden"
            onError={(e) => {
              console.warn('[VideoPlayer] Vocals audio unavailable, falling back to original audio:', e);
              setVocalsAvailable(false);
            }}
          />
        )}

        {/* Center play overlay - only when not playing */}
        {!isPlaying && (
          <button
            onClick={togglePlayback}
            className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors"
            aria-label="播放"
          >
            <div className="w-20 h-20 rounded-full bg-white/90 hover:bg-white flex items-center justify-center shadow-2xl transition-all group-hover:scale-110">
              <Play size={40} className="text-bg-primary ml-1" fill="currentColor" />
            </div>
          </button>
        )}
      </div>

      {/* Controls */}
      <div className="p-4 space-y-3">
        {/* Progress bar */}
        <div
          ref={progressBarRef}
          className="relative h-2 bg-bg-card rounded-full cursor-pointer group select-none touch-none"
          onMouseDown={handleSeekStart}
          onTouchStart={handleSeekStart}
        >
          <div
            className={`absolute h-full bg-primary rounded-full ${isSeeking ? '' : 'transition-all'}`}
            style={{ width: `${progress}%` }}
          />
          <div
            className={`absolute h-full w-4 bg-primary rounded-full ${isSeeking ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}
            style={{ left: `${progress}%`, transform: 'translateX(-50%)' }}
          />
        </div>

        {/* Control buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {/* Play/Pause */}
            <button
              onClick={togglePlayback}
              className="p-2 rounded-lg hover:bg-bg-card transition-colors"
              aria-label={isPlaying ? '暂停' : '播放'}
            >
              {isPlaying ? (
                <Pause size={24} className="text-text-primary" />
              ) : (
                <Play size={24} className="text-text-primary" />
              )}
            </button>

            {/* Time display */}
            <div className="text-sm font-mono text-text-secondary">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>
          </div>

          {/* Volume control */}
          <div className="flex items-center space-x-2">
            <button
              onClick={toggleMute}
              className="p-2 rounded-lg hover:bg-bg-card transition-colors"
              aria-label={isMuted ? '取消静音' : '静音'}
            >
              {isMuted ? (
                <VolumeX size={20} className="text-text-primary" />
              ) : (
                <Volume2 size={20} className="text-text-primary" />
              )}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-24"
              aria-label="音量"
            />
            {/* Playback rate indicator */}
            <span
              className={`ml-2 px-2 py-1 text-xs font-mono rounded ${
                playbackRate !== 1.0
                  ? 'bg-primary/20 text-primary'
                  : 'bg-bg-card text-text-secondary'
              }`}
              aria-label="当前播放倍速"
              title="倍速（1/2/3/4 切换）"
            >
              {playbackRate.toFixed(2).replace(/\.?0+$/, '')}x
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});
