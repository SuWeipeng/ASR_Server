import React, { useRef, useEffect, useState, forwardRef, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';
import { setPlaying, setVolume, setMuted, togglePlay, setSeeking, setCurrentTime, setIntentTime } from '../../store/playerSlice';
import { setCurrentSubtitleIndex, clearSeekRequest } from '../../store/subtitleSlice';
import { formatTime, getPlaybackProgress } from '../../utils/timeFormat';
import { usePlayerSync } from '../../hooks/usePlayerSync';
import { mediaService } from '../../services/mediaService';

export const VideoPlayer = forwardRef((props, ref) => {
  const dispatch = useDispatch();
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const progressBarRef = useRef(null);
  const isDraggingRef = useRef(false);

  // Forward the video element directly to the parent ref
  const setVideoRef = useCallback((el) => {
    videoRef.current = el;
    if (typeof ref === 'function') {
      ref(el);
    } else if (ref) {
      ref.current = el;
    }
  }, [ref]);

  const fileId = useSelector((state) => state.media.fileId);
  const isPlaying = useSelector((state) => state.player.isPlaying);
  const currentTime = useSelector((state) => state.player.currentTime);
  const duration = useSelector((state) => state.player.duration);
  const volume = useSelector((state) => state.player.volume);
  const isMuted = useSelector((state) => state.player.isMuted);
  const playbackRate = useSelector((state) => state.player.playbackRate);
  const isSeeking = useSelector((state) => state.player.isSeeking);
  const subtitles = useSelector((state) => state.subtitle.filteredSubtitles);
  const currentSubtitleIndex = useSelector((state) => state.subtitle.currentSubtitleIndex);
  const seekRequest = useSelector((state) => state.subtitle.seekRequest);

  const [progress, setProgress] = useState(0);

  // Refs that mirror Redux state so drag handlers can read latest values
  // without re-creating the listeners on every dispatch.
  const subtitlesRef = useRef(subtitles);
  const currentSubtitleIndexRef = useRef(currentSubtitleIndex);
  const durationRef = useRef(duration);
  useEffect(() => { subtitlesRef.current = subtitles; }, [subtitles]);
  useEffect(() => { currentSubtitleIndexRef.current = currentSubtitleIndex; }, [currentSubtitleIndex]);
  useEffect(() => { durationRef.current = duration; }, [duration]);

  usePlayerSync(videoRef);

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
  // Update intentTime but don't auto-play - let user click play button.
  useEffect(() => {
    if (seekRequest.index < 0) return;
    const subtitle = subtitles[seekRequest.index];
    if (subtitle && videoRef.current) {
      videoRef.current.currentTime = subtitle.start;
      dispatch(setIntentTime(subtitle.start));
      dispatch(clearSeekRequest());
    }
  }, [seekRequest.token, subtitles, dispatch]);

  // Update progress bar
  useEffect(() => {
    setProgress(getPlaybackProgress(currentTime, duration));
  }, [currentTime, duration]);

  // Handle play/pause
  const togglePlayback = () => {
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
  };

  // Handle mute toggle
  const toggleMute = () => {
    dispatch(setMuted(!isMuted));
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
    }
  };

  // Sync play state with video
  // Only depends on isPlaying - let video element be the source of truth during playback
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(console.error);
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  // Sync volume with video
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = volume;
      videoRef.current.muted = isMuted;
    }
  }, [volume, isMuted]);

  if (!fileId) {
    return (
      <div className="flex items-center justify-center h-64 bg-bg-secondary border border-bg-card rounded-lg">
        <p className="text-text-secondary">请先上传音视频文件</p>
      </div>
    );
  }

  const mediaUrl = mediaService.getMediaUrl(fileId);

  return (
    <div ref={containerRef} className="bg-bg-secondary rounded-lg overflow-hidden">
      {/* Video element */}
      <div className="relative aspect-video bg-black group">
        <video
          key={fileId}
          ref={setVideoRef}
          src={mediaUrl}
          preload="auto"
          className="w-full h-full"
          onClick={togglePlayback}
        />

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
          </div>

          {/* Playback speed */}
          <div className="text-sm text-text-secondary">
            {playbackRate}x
          </div>
        </div>
      </div>
    </div>
  );
});
