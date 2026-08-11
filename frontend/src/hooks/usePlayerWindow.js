import { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { detachPlayer, attachPlayer, setPlaying, setVolume, setMuted } from '../store/playerSlice';

const PLAYER_WINDOW_URL = '/?mode=player';
const CHANNEL_NAME = 'asr-player-sync';
const WINDOW_WIDTH = 800;
const WINDOW_HEIGHT = 600;

// Message types for cross-window communication
export const MSG_TYPES = {
  // From main window to player window
  SYNC_STATE: 'SYNC_STATE',
  SEEK: 'SEEK',
  PLAY_PAUSE: 'PLAY_PAUSE',
  VOLUME: 'VOLUME',
  MUTE: 'MUTE',
  RATE: 'RATE',
  CLOSE: 'CLOSE',

  // From player window to main window
  WINDOW_READY: 'WINDOW_READY',
  WINDOW_CLOSED: 'WINDOW_CLOSED',
  STATE_UPDATE: 'STATE_UPDATE',
};

export const usePlayerWindow = () => {
  const dispatch = useDispatch();
  const isDetached = useSelector((state) => state.player.isDetached);
  const playerState = useSelector((state) => state.player);
  const subtitleState = useSelector((state) => state.subtitle);
  const fileId = useSelector((state) => state.media.fileId);

  const windowRef = useRef(null);
  const channelRef = useRef(null);
  const checkIntervalRef = useRef(null);

  // Use refs to store latest state values for message handlers
  const playerStateRef = useRef(playerState);
  const subtitleStateRef = useRef(subtitleState);
  const fileIdRef = useRef(fileId);
  const dispatchRef = useRef(dispatch);

  // Update refs when state changes
  useEffect(() => {
    playerStateRef.current = playerState;
    subtitleStateRef.current = subtitleState;
    fileIdRef.current = fileId;
    dispatchRef.current = dispatch;
  }, [playerState, subtitleState, fileId, dispatch]);

  // Initialize BroadcastChannel - only once on mount
  useEffect(() => {
    if (typeof BroadcastChannel !== 'undefined') {
      channelRef.current = new BroadcastChannel(CHANNEL_NAME);

      channelRef.current.onmessage = (event) => {
        const { type, payload } = event.data;
        const currentDispatch = dispatchRef.current;
        const currentPlayerState = playerStateRef.current;

        switch (type) {
          case MSG_TYPES.WINDOW_READY:
            // Window is ready, send initial state
            if (channelRef.current) {
              channelRef.current.postMessage({
                type: MSG_TYPES.SYNC_STATE,
                payload: {
                  player: playerStateRef.current,
                  subtitle: subtitleStateRef.current,
                  fileId: fileIdRef.current,
                },
              });
            }
            break;

          case MSG_TYPES.WINDOW_CLOSED:
            // Player window was closed, re-attach
            currentDispatch(attachPlayer());
            break;

          case MSG_TYPES.STATE_UPDATE:
            // Player window updated its state, sync back to main store
            if (payload.player) {
              if (payload.player.isPlaying !== currentPlayerState.isPlaying) {
                currentDispatch(setPlaying(payload.player.isPlaying));
              }
              if (payload.player.volume !== currentPlayerState.volume) {
                currentDispatch(setVolume(payload.player.volume));
              }
              if (payload.player.isMuted !== currentPlayerState.isMuted) {
                currentDispatch(setMuted(payload.player.isMuted));
              }
            }
            break;
        }
      };
    }

    return () => {
      if (channelRef.current) {
        channelRef.current.close();
        channelRef.current = null;
      }
    };
  }, []); // Empty deps - only run once on mount

  // Send state updates to player window when state changes
  useEffect(() => {
    if (isDetached && channelRef.current && windowRef.current && !windowRef.current.closed) {
      channelRef.current.postMessage({
        type: MSG_TYPES.SYNC_STATE,
        payload: {
          player: playerState,
          subtitle: subtitleState,
          fileId,
        },
      });
    }
  }, [playerState, subtitleState, fileId, isDetached]);

  // Clean up when detaching state changes to false
  useEffect(() => {
    if (!isDetached && windowRef.current) {
      // Close window if it exists
      if (!windowRef.current.closed) {
        windowRef.current.close();
      }
      windowRef.current = null;
    }
  }, [isDetached]);

  // Check if window was closed externally
  useEffect(() => {
    if (isDetached && windowRef.current) {
      checkIntervalRef.current = setInterval(() => {
        if (windowRef.current && windowRef.current.closed) {
          dispatch(attachPlayer());
        }
      }, 500);
    }

    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
        checkIntervalRef.current = null;
      }
    };
  }, [isDetached, dispatch]);

  // Open player window
  const openPlayerWindow = useCallback(() => {
    if (windowRef.current && !windowRef.current.closed) {
      // Window is already open, focus it
      windowRef.current.focus();
      return;
    }

    // Calculate centered position
    const left = Math.max(0, (window.screen.width - WINDOW_WIDTH) / 2);
    const top = Math.max(0, (window.screen.height - WINDOW_HEIGHT) / 2);

    // Open new window
    const newWindow = window.open(
      PLAYER_WINDOW_URL,
      'ASRPlayerWindow',
      `width=${WINDOW_WIDTH},height=${WINDOW_HEIGHT},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );

    if (newWindow) {
      windowRef.current = newWindow;
      dispatch(detachPlayer());
    } else {
      console.error('Failed to open player window. Please allow popups for this site.');
      // Could show a user-facing error message here
    }
  }, [dispatch]);

  // Close player window
  const closePlayerWindow = useCallback(() => {
    if (windowRef.current && !windowRef.current.closed) {
      windowRef.current.close();
    }
    windowRef.current = null;
    dispatch(attachPlayer());
  }, [dispatch]);

  // Send a message to the player window
  const sendMessage = useCallback((type, payload) => {
    if (channelRef.current && isDetached && windowRef.current && !windowRef.current.closed) {
      channelRef.current.postMessage({ type, payload });
    }
  }, [isDetached]);

  return {
    isDetached,
    openPlayerWindow,
    closePlayerWindow,
    sendMessage,
    channel: channelRef.current,
  };
};
