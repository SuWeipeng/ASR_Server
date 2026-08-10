import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  setCurrentTime,
  setPlaying,
  setDuration,
  setLoopRange,
} from '../store/playerSlice';
import { setCurrentSubtitleIndex } from '../store/subtitleSlice';

/**
 * Custom hook for player synchronization with subtitles
 * @param {React.MutableRefObject<HTMLMediaElement>} mediaRef - Ref to the video or audio element
 * @returns {Object} Sync functions
 */
export const usePlayerSync = (mediaRef) => {
  const dispatch = useDispatch();
  const subtitles = useSelector((state) => state.subtitle.subtitles);
  const loopMode = useSelector((state) => state.player.loopMode);
  const playbackRate = useSelector((state) => state.player.playbackRate);
  const currentTimeRef = useRef(0);

  /**
   * Find current subtitle based on time
   */
  const updateCurrentSubtitle = useCallback(
    (time) => {
      if (!subtitles || subtitles.length === 0) return;

      const currentIndex = subtitles.findIndex(
        (sub) => time >= sub.start && time < sub.end
      );

      if (currentIndex !== -1) {
        dispatch(setCurrentSubtitleIndex(currentIndex));

        // Set loop range if loop mode is enabled
        if (loopMode && subtitles[currentIndex]) {
          const sub = subtitles[currentIndex];
          dispatch(
            setLoopRange({
              start: sub.start,
              end: sub.end,
            })
          );
        }
      }
    },
    [subtitles, dispatch, loopMode]
  );

  /**
   * Handle time update event
   */
  const handleTimeUpdate = useCallback(() => {
    const mediaElement = mediaRef.current;
    if (!mediaElement) return;

    const currentTime = mediaElement.currentTime;
    currentTimeRef.current = currentTime;
    dispatch(setCurrentTime(currentTime));
    updateCurrentSubtitle(currentTime);

    // Handle loop mode
    if (loopMode) {
      const loopStart = parseFloat(mediaElement.dataset.loopStart || 0);
      const loopEnd = parseFloat(mediaElement.dataset.loopEnd || 0);

      if (loopEnd > 0 && currentTime >= loopEnd) {
        mediaElement.currentTime = loopStart;
      }
    }
  }, [mediaRef, dispatch, updateCurrentSubtitle, loopMode]);

  /**
   * Handle loaded metadata event
   */
  const handleLoadedMetadata = useCallback(() => {
    const mediaElement = mediaRef.current;
    if (!mediaElement) return;

    const duration = mediaElement.duration;
    dispatch(setDuration(duration));
  }, [mediaRef, dispatch]);

  /**
   * Handle ended event
   */
  const handleEnded = useCallback(() => {
    dispatch(setPlaying(false));
  }, [dispatch]);

  /**
   * Setup event listeners
   */
  useEffect(() => {
    const mediaElement = mediaRef.current;
    if (!mediaElement) return;

    mediaElement.addEventListener('timeupdate', handleTimeUpdate);
    mediaElement.addEventListener('loadedmetadata', handleLoadedMetadata);
    mediaElement.addEventListener('ended', handleEnded);

    return () => {
      mediaElement.removeEventListener('timeupdate', handleTimeUpdate);
      mediaElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
      mediaElement.removeEventListener('ended', handleEnded);
    };
  }, [mediaRef, handleTimeUpdate, handleLoadedMetadata, handleEnded]);

  /**
   * Apply playback rate changes
   */
  useEffect(() => {
    const mediaElement = mediaRef.current;
    if (!mediaElement) return;

    mediaElement.playbackRate = playbackRate;
  }, [mediaRef, playbackRate]);

  return {
    updateCurrentSubtitle,
  };
};

/**
 * Hook for seeking to specific subtitle
 * @param {HTMLMediaElement} mediaElement - Video or audio element
 * @returns {Function} Seek to subtitle function
 */
export const useSubtitleSeek = (mediaElement) => {
  const dispatch = useDispatch();

  const seekToSubtitle = useCallback(
    (subtitleIndex) => {
      if (!mediaElement) return;

      const subtitles = useSelector((state) => state.subtitle.subtitles);
      const subtitle = subtitles[subtitleIndex];

      if (subtitle) {
        mediaElement.currentTime = subtitle.start;
        dispatch(setCurrentSubtitleIndex(subtitleIndex));
      }
    },
    [mediaElement, dispatch]
  );

  return { seekToSubtitle };
};
