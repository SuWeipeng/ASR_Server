import React, { useEffect, useRef, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Header } from './components/layout/Header';
import { VideoPlayer } from './components/player/VideoPlayer';
import { SubtitlePanel } from './components/subtitle/SubtitlePanel';
import { PracticeCard } from './components/practice/PracticeCard';
import { ErrorMessage } from './components/common/ErrorMessage';
import { SettingsModal } from './components/settings/SettingsModal';
import { uploadFile } from './store/mediaSlice';
import { generateSubtitles, loadCachedSubtitles, setCurrentSubtitleIndex } from './store/subtitleSlice';
import { setRecording } from './store/practiceSlice';
import { getSystemStatus } from './store/uiSlice';
import { setError as setUIError } from './store/uiSlice';
import { attachPlayer, setPlaying, setVolume, setMuted, setCurrentTime } from './store/playerSlice';
import { store } from './store';
import { transcriptionService } from './services/transcriptionService';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

const MSG_TYPES = {
  SYNC_STATE: 'SYNC_STATE',
  WINDOW_READY: 'WINDOW_READY',
  WINDOW_CLOSED: 'WINDOW_CLOSED',
  STATE_UPDATE: 'STATE_UPDATE',
  SEEK_TO_SUBTITLE: 'SEEK_TO_SUBTITLE',
  PLAY_PAUSE: 'PLAY_PAUSE',
  RECORDING_START: 'RECORDING_START',
  RECORDING_STOP: 'RECORDING_STOP',
};

// Export for use in other components
window.playerMsgTypes = MSG_TYPES;

function App() {
  const dispatch = useDispatch();
  const videoRef = useRef(null);
  const isDetached = useSelector((state) => state.player.isDetached);

  const handleSeekToSubtitle = useCallback((index) => {
    const state = store.getState();
    const subtitles = state.subtitle.subtitles;
    const target = subtitles[index];
    if (target) {
      // 更新字幕索引
      dispatch(setCurrentSubtitleIndex(index));

      // 如果播放器已弹出，通过 BroadcastChannel 通知播放窗口跳转
      if (isDetached && window.playerWindowChannel) {
        window.playerWindowChannel.postMessage({
          type: MSG_TYPES.SEEK_TO_SUBTITLE,
          payload: { start: target.start, end: target.end },
        });
      } else if (videoRef.current) {
        // 否则直接操作主窗口的视频元素
        videoRef.current.currentTime = target.start;
        // 启动播放
        dispatch(setPlaying(true));
      }
    }
  }, [dispatch, isDetached]);

  useKeyboardShortcuts(videoRef, handleSeekToSubtitle);

  // Selectors
  const fileId = useSelector((state) => state.media.fileId);
  const isProcessing = useSelector((state) => state.media.isProcessing);
  const uiError = useSelector((state) => state.ui.error);
  const theme = useSelector((state) => state.ui.theme);

  // Initialize system with polling for model loading
  useEffect(() => {
    dispatch(getSystemStatus());

    // Poll every 2 seconds to check model status until ready
    const pollInterval = setInterval(() => {
      dispatch(getSystemStatus());
    }, 2000);

    // Check if model is ready and stop polling
    const checkModelReady = setInterval(() => {
      const state = store.getState();
      if (state.ui.systemStatus?.model_loaded) {
        clearInterval(pollInterval);
        clearInterval(checkModelReady);
      }
    }, 500);

    return () => {
      clearInterval(pollInterval);
      clearInterval(checkModelReady);
    };
  }, [dispatch]);

  // Apply theme
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Handle file upload event
  useEffect(() => {
    const handleFileUpload = async (event) => {
      const file = event.detail;

      if (file) {
        try {
          // 1. 上传文件
          const uploadResponse = await dispatch(uploadFile(file)).unwrap();
          const fileId = uploadResponse.file_id;

          // 2. 检查缓存
          const cacheCheck = await transcriptionService.checkCacheStatus(fileId);

          if (cacheCheck.has_cache) {
            console.log('Loading from cache:', cacheCheck.metadata);
            // 3a. 加载缓存的字幕
            await dispatch(loadCachedSubtitles(fileId));
          } else {
            console.log('No cache, generating subtitles...');
            // 3b. 执行 ASR
            await dispatch(generateSubtitles({ fileId }));
          }
        } catch (error) {
          console.error('Upload error:', error);
          dispatch(setUIError(typeof error === 'string' ? error : '上传失败'));
        }
      }
    };

    window.addEventListener('fileUpload', handleFileUpload);
    return () => window.removeEventListener('fileUpload', handleFileUpload);
  }, [dispatch]);

  // Initialize BroadcastChannel for player window communication
  useEffect(() => {
    if (typeof BroadcastChannel !== 'undefined') {
      const channel = new BroadcastChannel('asr-player-sync');

      // 保存 channel 引用供外部使用
      window.playerWindowChannel = channel;

      channel.onmessage = (event) => {
        const { type, payload } = event.data;

        switch (type) {
          case MSG_TYPES.WINDOW_READY:
            // 发送当前状态给弹窗
            const state = store.getState();
            channel.postMessage({
              type: MSG_TYPES.SYNC_STATE,
              payload: {
                player: state.player,
                subtitle: state.subtitle,
                fileId: state.media.fileId,
              },
            });
            break;

          case MSG_TYPES.WINDOW_CLOSED:
            // 弹窗关闭，恢复播放器显示
            dispatch(attachPlayer());
            break;

          case MSG_TYPES.STATE_UPDATE:
            // 弹窗更新了状态，同步回来
            if (payload.player) {
              const currentPlayer = store.getState().player;
              const currentSubtitleState = store.getState().subtitle;

              if (payload.player.isPlaying !== currentPlayer.isPlaying) {
                dispatch(setPlaying(payload.player.isPlaying));
              }
              if (payload.player.currentTime !== currentPlayer.currentTime) {
                dispatch(setCurrentTime(payload.player.currentTime));

                // 同步字幕索引 - 找到当前时间对应的字幕
                if (currentSubtitleState.subtitles && currentSubtitleState.subtitles.length > 0) {
                  const newIndex = currentSubtitleState.subtitles.findIndex(
                    (sub) => payload.player.currentTime >= sub.start && payload.player.currentTime < sub.end
                  );
                  if (newIndex !== -1 && newIndex !== currentSubtitleState.currentSubtitleIndex) {
                    dispatch(setCurrentSubtitleIndex(newIndex));
                  }
                }
              }
              if (payload.player.volume !== currentPlayer.volume) {
                dispatch(setVolume(payload.player.volume));
              }
              if (payload.player.isMuted !== currentPlayer.isMuted) {
                dispatch(setMuted(payload.player.isMuted));
              }
            }
            break;

          case MSG_TYPES.RECORDING_START:
            dispatch(setRecording(true));
            break;

          case MSG_TYPES.RECORDING_STOP:
            dispatch(setRecording(false));
            break;
        }
      };

      return () => {
        channel.close();
        window.playerWindowChannel = null;
      };
    }
  }, [dispatch]);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <Header />

      {/* Main content */}
      <main className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto overflow-x-hidden min-h-0">
          {/* Error message */}
          {uiError && (
            <ErrorMessage
              error={uiError}
              onDismiss={() => dispatch(setUIError(null))}
            />
          )}

          {/* Video player - 仅在未分离时显示 */}
          {!isDetached && (
            <div className="flex-shrink-0">
              <VideoPlayer ref={videoRef} />
            </div>
          )}

          {/* Practice card */}
          {fileId && <PracticeCard videoRef={videoRef} />}
        </div>

        {/* Subtitle panel */}
        {fileId && (
          <div className="w-96 border-l border-bg-card h-full overflow-hidden flex-shrink-0">
            <SubtitlePanel />
          </div>
        )}
      </main>

      {/* Loading overlay */}
      {isProcessing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-secondary rounded-lg p-6 shadow-xl">
            <div className="flex items-center space-x-3">
              <div className="spinner w-6 h-6 border-2 border-primary border-t-transparent" />
              <span className="text-text-primary">处理中...</span>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      <SettingsModal />
    </div>
  );
}

export default App;
