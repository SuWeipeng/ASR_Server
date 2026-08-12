import { useEffect, useCallback, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  togglePlay,
  setPlaybackRate,
  toggleLoop,
} from '../store/playerSlice';
import { setCurrentSubtitleIndex } from '../store/subtitleSlice';
import { setRecording } from '../store/practiceSlice';
import { SHORTCUTS, isShortcutMatch } from '../utils/shortcuts';

/**
 * Custom hook for keyboard shortcuts
 * @param {React.RefObject<HTMLMediaElement>} mediaRef - Ref to the video/audio element
 * @param {Function} onSeekToSubtitle - Function to seek to subtitle
 */
export const useKeyboardShortcuts = (mediaRef, onSeekToSubtitle) => {
  const dispatch = useDispatch();
  const subtitles = useSelector((state) => state.subtitle.subtitles);
  const currentSubtitleIndex = useSelector(
    (state) => state.subtitle.currentSubtitleIndex
  );
  const isRecording = useSelector((state) => state.practice.isRecording);
  const recordingStartRef = useRef(null);

  /**
   * Handle keyboard shortcuts
   */
  const handleKeyDown = useCallback(
    (event) => {
      // Ignore if in input/textarea
      if (
        event.target.tagName === 'INPUT' ||
        event.target.tagName === 'TEXTAREA' ||
        event.target.isContentEditable
      ) {
        return;
      }

      // Play/Pause
      if (event.key === SHORTCUTS.PLAY_PAUSE) {
        event.preventDefault();
        if (isRecording) {
          dispatch(setRecording(false));
        } else {
          dispatch(togglePlay());
        }
      }

      // Previous sentence
      if (isShortcutMatch(event, SHORTCUTS.PREVIOUS_SENTENCE)) {
        event.preventDefault();
        if (currentSubtitleIndex > 0) {
          onSeekToSubtitle(currentSubtitleIndex - 1);
        }
      }

      // Next sentence
      if (isShortcutMatch(event, SHORTCUTS.NEXT_SENTENCE)) {
        event.preventDefault();
        if (currentSubtitleIndex < subtitles.length - 1) {
          onSeekToSubtitle(currentSubtitleIndex + 1);
        }
      }

      // Replay current sentence
      if (isShortcutMatch(event, SHORTCUTS.REPLAY_CURRENT)) {
        event.preventDefault();
        if (currentSubtitleIndex >= 0) {
          onSeekToSubtitle(currentSubtitleIndex);
        }
      }

      // Toggle loop
      if (isShortcutMatch(event, SHORTCUTS.TOGGLE_LOOP)) {
        event.preventDefault();
        dispatch(toggleLoop());
      }

      // Recording (hold to record)
      if (isShortcutMatch(event, SHORTCUTS.START_RECORDING)) {
        if (!event.repeat && !isRecording) {
          event.preventDefault();
          dispatch(setRecording(true));
          recordingStartRef.current = Date.now();
        }
      }

      // Playback speed
      if (isShortcutMatch(event, SHORTCUTS.SPEED_0_5X)) {
        event.preventDefault();
        dispatch(setPlaybackRate(0.5));
      }
      if (isShortcutMatch(event, SHORTCUTS.SPEED_0_75X)) {
        event.preventDefault();
        dispatch(setPlaybackRate(0.75));
      }
      if (isShortcutMatch(event, SHORTCUTS.SPEED_1_0X)) {
        event.preventDefault();
        dispatch(setPlaybackRate(1.0));
      }
      if (isShortcutMatch(event, SHORTCUTS.SPEED_1_25X)) {
        event.preventDefault();
        dispatch(setPlaybackRate(1.25));
      }

      // Search
      if (event.key === SHORTCUTS.SEARCH && event.ctrlKey) {
        event.preventDefault();
        const searchInput = document.querySelector('[data-search-input]');
        if (searchInput) {
          searchInput.focus();
        }
      }

      // Close modal
      if (event.key === SHORTCUTS.CLOSE_MODAL) {
        event.preventDefault();
      }

      // Show help (no-op: help is shown via hover tooltip in Header)
    },
    [
      mediaRef,
      currentSubtitleIndex,
      subtitles.length,
      isRecording,
      dispatch,
      onSeekToSubtitle,
    ]
  );

  /**
   * Handle keyboard key up (for recording release)
   */
  const handleKeyUp = useCallback(
    (event) => {
      if (isShortcutMatch(event, SHORTCUTS.START_RECORDING) && isRecording) {
        // Always reset isRecording on keyup to avoid the state getting
        // stuck if the key is released before the 500ms threshold.
        dispatch(setRecording(false));
      }
    },
    [isRecording, dispatch]
  );

  /**
   * Setup event listeners
   */
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleKeyDown, handleKeyUp]);
};