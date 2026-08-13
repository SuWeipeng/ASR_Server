import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Play, Pause, Volume2, VolumeX, ArrowLeft } from 'lucide-react';
import { formatTime, getPlaybackProgress } from '../../utils/timeFormat';
import { MSG_TYPES } from '../../hooks/usePlayerWindow';
import { mediaService } from '../../services/mediaService';
import { SHORTCUTS, isShortcutMatch } from '../../utils/shortcuts';

export function VideoPlayerWindow({ initialState, seekRequest, onSeekHandled, onStateUpdate, onClose }) {
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const progressBarRef = useRef(null);
  const isDraggingRef = useRef(false);

  // Local state
  const [isPlaying, setIsPlaying] = useState(initialState?.player?.isPlaying || false);
  const [currentTime, setCurrentTime] = useState(initialState?.player?.currentTime || 0);
  const [duration, setDuration] = useState(initialState?.player?.duration || 0);
  const [volume, setVolume] = useState(initialState?.player?.volume || 1.0);
  const [isMuted, setIsMuted] = useState(initialState?.player?.isMuted || false);
  const [isSeeking, setIsSeeking] = useState(false);
  const [progress, setProgress] = useState(0);
  const [fileId, setFileId] = useState(initialState?.fileId || null);
  const [singleSentenceMode, setSingleSentenceMode] = useState(false);
  const [singleSentenceEnd, setSingleSentenceEnd] = useState(null);
  const [subtitles, setSubtitles] = useState(initialState?.subtitle?.subtitles || []);
  const [currentSubtitleIndex, setCurrentSubtitleIndex] = useState(initialState?.subtitle?.currentSubtitleIndex || 0);
  const [isRecordingLocal, setIsRecordingLocal] = useState(false);
  const [isVideoReady, setIsVideoReady] = useState(false);

  // Refs for drag handlers
  const durationRef = useRef(duration);
  const singleSentenceModeRef = useRef(singleSentenceMode);
  const singleSentenceEndRef = useRef(singleSentenceEnd);

  useEffect(() => { durationRef.current = duration; }, [duration]);
  useEffect(() => { singleSentenceModeRef.current = singleSentenceMode; }, [singleSentenceMode]);
  useEffect(() => { singleSentenceEndRef.current = singleSentenceEnd; }, [singleSentenceEnd]);

  // Sync state from main window
  useEffect(() => {
    if (initialState) {
      const newFileId = initialState.fileId ?? fileId;
      setFileId(newFileId);

      // 只在 fileId 变化或第一次初始化时同步状态
      if (newFileId && newFileId !== fileId) {
        setCurrentTime(initialState.player?.currentTime ?? 0);
        setVolume(initialState.player?.volume ?? 1.0);
        setIsMuted(initialState.player?.isMuted ?? false);
        // 不要自动开始播放，让用户手动控制
        setIsPlaying(false);
        setDuration(initialState.player?.duration ?? 0);
      }
    }
  }, [initialState, fileId]);

  // Handle seek request from main window (subtitle click)
  useEffect(() => {
    if (seekRequest && seekRequest.start !== null && videoRef.current && typeof seekRequest.start === 'number' && isFinite(seekRequest.start)) {
      videoRef.current.currentTime = seekRequest.start;
      setCurrentTime(seekRequest.start);

      // 启用单句播放模式
      setSingleSentenceMode(true);
      setSingleSentenceEnd(seekRequest.end);

      // 开始播放
      setIsPlaying(true);

      onSeekHandled?.();
    }
  }, [seekRequest, onSeekHandled]);

  // Notify main window of state changes
  const notifyStateChange = useCallback(() => {
    if (onStateUpdate) {
      onStateUpdate({
        isPlaying,
        currentTime,
        duration,
        volume,
        isMuted,
      });
    }
  }, [isPlaying, currentTime, duration, volume, isMuted, onStateUpdate]);

  // Update progress bar
  useEffect(() => {
    setProgress(getPlaybackProgress(currentTime, duration));
  }, [currentTime, duration]);

  // Sync play state with video
  useEffect(() => {
    if (videoRef.current && isVideoReady) {
      if (isPlaying) {
        videoRef.current.play().catch(console.error);
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying, isVideoReady]);

  // Sync volume with video
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = volume;
      videoRef.current.muted = isMuted;
    }
  }, [volume, isMuted]);

  // Handle video events
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const newCurrentTime = video.currentTime;
      setCurrentTime(newCurrentTime);

      // 单句播放模式 - 到达结尾时自动暂停
      if (singleSentenceModeRef.current && singleSentenceEndRef.current !== null && newCurrentTime >= singleSentenceEndRef.current) {
        setIsPlaying(false);
        setSingleSentenceMode(false);
        setSingleSentenceEnd(null);
      }
    };

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      setIsVideoReady(true);
    };

    const handleCanPlay = () => {
      setIsVideoReady(true);
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setSingleSentenceMode(false);
      setSingleSentenceEnd(null);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('ended', handleEnded);
    };
  }, []);

  // Notify state changes on important updates
  useEffect(() => {
    notifyStateChange();
  }, [isPlaying, volume, isMuted, currentTime, notifyStateChange]);

  // Handle play/pause
  const togglePlayback = useCallback(() => {
    setIsPlaying(prevPlaying => !prevPlaying);
  }, []);

  // Compute seek time from pointer position
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

  const handleSeekStart = (e) => {
    const dur = durationRef.current;
    if (!dur || dur <= 0) return;

    isDraggingRef.current = true;
    setIsSeeking(true);

    const point = e.touches ? e.touches[0] : e;
    const newTime = computeTimeFromEvent(point.clientX);

    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
  };

  const handleSeekMove = useCallback((e) => {
    if (!isDraggingRef.current) return;
    const point = e.touches ? e.touches[0] : e;
    const newTime = computeTimeFromEvent(point.clientX);
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
  }, [computeTimeFromEvent]);

  const handleSeekEnd = useCallback(() => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    setIsSeeking(false);
  }, []);

  // Register global pointer/touch listeners
  useEffect(() => {
    window.addEventListener('mousemove', handleSeekMove);
    window.addEventListener('mouseup', handleSeekEnd);
    window.addEventListener('touchmove', handleSeekMove, { passive: true });
    window.addEventListener('touchend', handleSeekEnd);
    return () => {
      window.removeEventListener('mousemove', handleSeekMove);
      window.removeEventListener('mouseup', handleSeekEnd);
      window.removeEventListener('touchmove', handleSeekMove);
      window.removeEventListener('touchend', handleSeekEnd);
    };
  }, [handleSeekMove, handleSeekEnd]);

  // Handle volume change
  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
  };

  // Handle mute toggle
  const toggleMute = () => {
    const newState = !isMuted;
    setIsMuted(newState);
    if (videoRef.current) {
      videoRef.current.muted = newState;
    }
  };

  // Handle subtitle jump (for keyboard shortcuts)
  const handleSubtitleJump = useCallback((index) => {
    const target = subtitles[index];
    if (target && videoRef.current) {
      videoRef.current.currentTime = target.start;
      setCurrentTime(target.start);
      setCurrentSubtitleIndex(index);

      // 启用单句播放模式
      setSingleSentenceMode(true);
      setSingleSentenceEnd(target.end);

      // 开始播放
      setIsPlaying(true);

      // 通知主窗口更新当前字幕索引
      if (onStateUpdate) {
        onStateUpdate({
          isPlaying: true,
          currentTime: target.start,
          duration,
          volume,
          isMuted,
        });
      }
    }
  }, [subtitles, duration, volume, isMuted, onStateUpdate]);

  // Keyboard shortcuts handler
  const handleKeyDown = useCallback((event) => {
    // 忽略输入框中的按键
    if (
      event.target.tagName === 'INPUT' ||
      event.target.tagName === 'TEXTAREA' ||
      event.target.isContentEditable
    ) {
      return;
    }

    // A - 上一句
    if (isShortcutMatch(event, SHORTCUTS.PREVIOUS_SENTENCE)) {
      event.preventDefault();
      if (currentSubtitleIndex > 0) {
        handleSubtitleJump(currentSubtitleIndex - 1);
      }
    }

    // D - 下一句
    if (isShortcutMatch(event, SHORTCUTS.NEXT_SENTENCE)) {
      event.preventDefault();
      if (currentSubtitleIndex < subtitles.length - 1) {
        handleSubtitleJump(currentSubtitleIndex + 1);
      }
    }

    // R - 重播当前句
    if (isShortcutMatch(event, SHORTCUTS.REPLAY_CURRENT)) {
      event.preventDefault();
      if (currentSubtitleIndex >= 0) {
        handleSubtitleJump(currentSubtitleIndex);
      }
    }

    // Space - 播放/暂停
    if (event.code === 'Space' || event.key === ' ') {
      event.preventDefault();
      togglePlayback();
    }

    // L - 按住录音
    if (isShortcutMatch(event, SHORTCUTS.START_RECORDING)) {
      if (!event.repeat && !isRecordingLocal) {
        event.preventDefault();
        setIsRecordingLocal(true);
        if (onStateUpdate) {
          onStateUpdate({ type: MSG_TYPES.RECORDING_START });
        }
      }
    }
  }, [currentSubtitleIndex, subtitles.length, handleSubtitleJump, togglePlayback, isRecordingLocal, onStateUpdate]);

  // Keyboard keyup handler (for recording release)
  const handleKeyUp = useCallback((event) => {
    if (isShortcutMatch(event, SHORTCUTS.START_RECORDING) && isRecordingLocal) {
      setIsRecordingLocal(false);
      if (onStateUpdate) {
        onStateUpdate({ type: MSG_TYPES.RECORDING_STOP });
      }
    }
  }, [isRecordingLocal, onStateUpdate]);

  // Register keyboard shortcuts
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleKeyDown, handleKeyUp]);

  if (!fileId) {
    return (
      <div className="flex items-center justify-center h-full bg-bg-secondary">
        <p className="text-text-secondary">等待视频加载...</p>
      </div>
    );
  }

  const mediaUrl = mediaService.getMediaUrl(fileId);

  return (
    <div ref={containerRef} className="h-full flex flex-col bg-bg-secondary">
      {/* Header with "Return to main window" button */}
      <div className="h-10 bg-bg-tertiary flex items-center justify-between px-4 flex-shrink-0">
        <h1 className="text-sm font-medium text-text-primary">视频播放器</h1>
        <button
          onClick={onClose}
          className="flex items-center space-x-2 px-3 py-1.5 text-sm bg-bg-card hover:bg-bg-primary text-text-primary rounded-md transition-colors"
        >
          <ArrowLeft size={16} />
          <span>放回主窗口</span>
        </button>
      </div>

      {/* Video element */}
      <div className="flex-1 relative bg-black">
        <video
          ref={videoRef}
          src={mediaUrl}
          preload="auto"
          className="w-full h-full object-contain"
          onClick={togglePlayback}
          onError={(e) => {
            console.error('[VideoPlayerWindow] Video error:', e);
          }}
        />

        {/* Center play overlay - only when not playing */}
        {!isPlaying && (
          <button
            onClick={togglePlayback}
            className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors"
            aria-label="播放"
          >
            <div className="w-20 h-20 rounded-full bg-white/90 hover:bg-white flex items-center justify-center shadow-2xl transition-all hover:scale-110">
              <Play size={40} className="text-bg-primary ml-1" fill="currentColor" />
            </div>
          </button>
        )}
      </div>

      {/* Controls */}
      <div className="p-4 space-y-3 bg-bg-secondary flex-shrink-0">
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
          </div>
        </div>
      </div>
    </div>
  );
}
