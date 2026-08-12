import React, { useState, useEffect, useRef, useCallback } from 'react';
import { VideoPlayerWindow } from './components/player/VideoPlayerWindow';

// Message types - must match main window
const MSG_TYPES = {
  SYNC_STATE: 'SYNC_STATE',
  WINDOW_READY: 'WINDOW_READY',
  WINDOW_CLOSED: 'WINDOW_CLOSED',
  STATE_UPDATE: 'STATE_UPDATE',
  SEEK_TO_SUBTITLE: 'SEEK_TO_SUBTITLE',
  RECORDING_START: 'RECORDING_START',
  RECORDING_STOP: 'RECORDING_STOP',
};

function PlayerWindowApp() {
  const [isReady, setIsReady] = useState(false);
  const channelRef = useRef(null);
  const [initialState, setInitialState] = useState(null);
  const [seekRequest, setSeekRequest] = useState(null);

  useEffect(() => {
    // Initialize BroadcastChannel
    channelRef.current = new BroadcastChannel('asr-player-sync');

    // Send ready message to main window
    channelRef.current.postMessage({ type: MSG_TYPES.WINDOW_READY });

    // Listen for messages from main window
    channelRef.current.onmessage = (event) => {
      const { type, payload } = event.data;

      switch (type) {
        case MSG_TYPES.SYNC_STATE:
          // 收到状态数据
          setInitialState(payload);
          setIsReady(true);
          break;

        case MSG_TYPES.SEEK_TO_SUBTITLE:
          // 字幕点击跳转
          if (payload.start !== undefined && payload.end !== undefined) {
            setSeekRequest({ start: payload.start, end: payload.end });
          }
          break;

        case MSG_TYPES.CLOSE:
          window.close();
          break;

        default:
          break;
      }
    };

    // Notify main window when closing
    const handleBeforeUnload = () => {
      if (channelRef.current) {
        channelRef.current.postMessage({ type: MSG_TYPES.WINDOW_CLOSED });
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);

  // Handle state update back to main window
  const handleStateUpdate = useCallback((state) => {
    if (channelRef.current) {
      // 如果是录音消息，直接转发
      if (state.type === MSG_TYPES.RECORDING_START ||
          state.type === MSG_TYPES.RECORDING_STOP) {
        channelRef.current.postMessage({
          type: state.type,
        });
      } else {
        // 普通状态更新
        channelRef.current.postMessage({
          type: MSG_TYPES.STATE_UPDATE,
          payload: { player: state },
        });
      }
    }
  }, []);

  // Handle close (return to main window)
  const handleClose = useCallback(() => {
    if (channelRef.current) {
      channelRef.current.postMessage({ type: MSG_TYPES.WINDOW_CLOSED });
    }
    window.close();
  }, []);

  if (!isReady || !initialState) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg-secondary">
        <div className="text-text-secondary">正在加载播放器...</div>
      </div>
    );
  }

  return (
    <VideoPlayerWindow
      initialState={initialState}
      seekRequest={seekRequest}
      onSeekHandled={() => setSeekRequest(null)}
      onStateUpdate={handleStateUpdate}
      onClose={handleClose}
    />
  );
}

export { PlayerWindowApp };

