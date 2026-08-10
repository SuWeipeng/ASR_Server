import React, { useRef, useEffect, useState, forwardRef, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';
import { setPlaying, setVolume, setMuted, togglePlay } from '../../store/playerSlice';
import { setCurrentSubtitleIndex } from '../../store/subtitleSlice';
import { formatTime, getPlaybackProgress } from '../../utils/timeFormat';
import { usePlayerSync } from '../../hooks/usePlayerSync';
import { mediaService } from '../../services/mediaService';

export const VideoPlayer = forwardRef((props, ref) => {
  const dispatch = useDispatch();
  const videoRef = useRef(null);
  const containerRef = useRef(null);

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
  const subtitles = useSelector((state) => state.subtitle.filteredSubtitles);
  const seekRequest = useSelector((state) => state.subtitle.seekRequest);

  const [progress, setProgress] = useState(0);

  usePlayerSync(videoRef);

  // Handle seek-to-subtitle requests from SubtitlePanel via Redux
  useEffect(() => {
    if (seekRequest.index < 0) return;
    const subtitle = subtitles[seekRequest.index];
    if (subtitle && videoRef.current) {
      videoRef.current.currentTime = subtitle.start;
    }
  }, [seekRequest, subtitles]);

  // Update progress bar
  useEffect(() => {
    setProgress(getPlaybackProgress(currentTime, duration));
  }, [currentTime, duration]);

  // Handle play/pause
  const togglePlayback = () => {
    dispatch(togglePlay());
  };

  // Handle seek
  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newTime = percentage * duration;

    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
  };

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
          ref={setVideoRef}
          src={mediaUrl}
          className="w-full h-full"
          onPlay={() => dispatch(setPlaying(true))}
          onPause={() => dispatch(setPlaying(false))}
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
          className="relative h-2 bg-bg-card rounded-full cursor-pointer group"
          onClick={handleSeek}
        >
          <div
            className="absolute h-full bg-primary rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute h-full w-4 bg-primary rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
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
