import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  setCurrentTime,
  setPlaying,
  setDuration,
  setLoopRange,
  setSingleSentenceMode,
} from '../store/playerSlice';
import { setCurrentSubtitleIndex } from '../store/subtitleSlice';

/**
 * Custom hook for player synchronization with subtitles
 * @param {React.MutableRefObject<HTMLMediaElement>} mediaRef - Ref to the video or audio element
 * @returns {Object} Sync functions
 */
export const usePlayerSync = (mediaRef) => {
  const dispatch = useDispatch();
  const subtitles = useSelector((state) => state.subtitle.filteredSubtitles);
  const loopMode = useSelector((state) => state.player.loopMode);
  const loopStart = useSelector((state) => state.player.loopStart);
  const loopEnd = useSelector((state) => state.player.loopEnd);
  const isSeeking = useSelector((state) => state.player.isSeeking);
  const singleSentenceMode = useSelector((state) => state.player.singleSentenceMode);
  const singleSentenceEnd = useSelector((state) => state.player.singleSentenceEnd);
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

    // While the user is dragging the progress bar, VideoPlayer is the source
    // of truth for currentTime / currentSubtitleIndex. Skip the timeupdate
    // dispatch chain to avoid redundant updates and visual jitter.
    if (isSeeking) return;

    const currentTime = mediaElement.currentTime;
    currentTimeRef.current = currentTime;
    dispatch(setCurrentTime(currentTime));
    updateCurrentSubtitle(currentTime);

    // Handle single sentence mode - auto-pause when sentence ends
    if (singleSentenceMode && singleSentenceEnd !== null) {
      if (currentTime >= singleSentenceEnd) {
        dispatch(setPlaying(false));
        dispatch(setSingleSentenceMode({ mode: false, endTime: null }));
        return;
      }
    }

    // Handle loop mode
    if (loopMode && loopStart !== null && loopEnd !== null) {
      if (currentTime >= loopEnd) {
        mediaElement.currentTime = loopStart;
      }
    }
  }, [mediaRef, dispatch, updateCurrentSubtitle, loopMode, loopStart, loopEnd, isSeeking, singleSentenceMode, singleSentenceEnd]);

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
   * Sync playback rate to media element when changed via Redux
   * (e.g. keyboard shortcuts 1/2/3/4).
   */
  useEffect(() => {
    const mediaElement = mediaRef.current;
    if (mediaElement && mediaElement.playbackRate !== playbackRate) {
      mediaElement.playbackRate = playbackRate;
    }
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
