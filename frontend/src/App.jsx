import React, { useEffect, useRef, useCallback, useMemo } from 'react';
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
import { selectPlaybackUseVocals } from './store/uiSlice';
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
  USE_VOCALS: 'USE_VOCALS',
  SUBTITLES: 'SUBTITLES',
  FILE_CHANGED: 'FILE_CHANGED',
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
  const playbackUseVocals = useSelector(selectPlaybackUseVocals);

  // 播放器分离时，"播放时使用人声音轨"变化实时同步到独立窗口。
  // 注意：负责推送 SYNC_STATE 的 usePlayerWindow 挂在 VideoPlayer 里，
  // 分离后 VideoPlayer 已卸载（其 channel 也关闭了），所以由这里补发。
  useEffect(() => {
    if (isDetached && window.playerWindowChannel) {
      window.playerWindowChannel.postMessage({
        type: MSG_TYPES.USE_VOCALS,
        payload: { useVocals: playbackUseVocals },
      });
    }
  }, [playbackUseVocals, isDetached]);

  // 分离期间主窗口切换/加载新文件后，同步到独立窗口。
  //
  // 为什么必须由这里发：负责推送 SYNC_STATE 的 usePlayerWindow 挂在 VideoPlayer 里，
  // 分离后 VideoPlayer 已卸载（其 channel 也关闭了），fileId 根本传不过去，
  // 弹窗会一直放着旧视频（"放回主窗口"才刷新就是因为主窗口重新渲染了播放器）。
  //
  // 关键：fileId 与 subtitles 必须一起发。Redux 里 state.media.fileId 在
  // uploadFile.fulfilled 时就变了，而字幕要等缓存检查/ASR 完成才到位，
  // 分开发会出现"字幕已换、视频还是旧的"的错位。
  const subtitles = useSelector((state) => state.subtitle.subtitles);
  const transcriptionMetadata = useSelector((state) => state.subtitle.transcriptionMetadata);
  const playerIsPlaying = useSelector((state) => state.player.isPlaying);
  // 用序列化后的内容做指纹，避免依赖数组引用（Redux 里 subtitles 是整体替换，
  // 引用会变，但同一份内容重复渲染时也可能换引用）
  const subtitlesKey = useMemo(
    () => (subtitles.length ? JSON.stringify(subtitles) : ''),
    [subtitles]
  );
  const lastSentFileRef = useRef(null);

  // 分离状态变化时重置同步游标：
  // 刚分离时弹窗通过 WINDOW_READY → SYNC_STATE 握手拿到完整快照，
  // 不需要再发 FILE_CHANGED（否则会重复重置播放位置）。
  useEffect(() => {
    if (!isDetached) {
      lastSentFileRef.current = null;
    }
  }, [isDetached]);

  useEffect(() => {
    if (!isDetached || !window.playerWindowChannel) return;

    // fileId 变了（新文件已上传）→ 通知弹窗切换视频
    if (fileId && fileId !== lastSentFileRef.current) {
      lastSentFileRef.current = fileId;
      window.playerWindowChannel.postMessage({
        type: MSG_TYPES.FILE_CHANGED,
        payload: {
          fileId,
          subtitles,
          transcriptionMetadata,
          // 带上当前播放状态：弹窗切到新文件后要接着播，
          // 不能因为 initialState.player 是打开弹窗时的旧快照就变成暂停。
          isPlaying: playerIsPlaying,
        },
      });
    }
  }, [fileId, subtitles, transcriptionMetadata, playerIsPlaying, isDetached]);

  // 同一文件内字幕被重新生成（缓存加载/ASR 完成/修复），单独下发字幕内容
  useEffect(() => {
    if (!isDetached || !window.playerWindowChannel) return;
    if (!fileId || fileId !== lastSentFileRef.current) return; // 文件变更那次已带上了

    window.playerWindowChannel.postMessage({
      type: MSG_TYPES.SUBTITLES,
      payload: {
        subtitles,
        transcriptionMetadata,
      },
    });
  }, [subtitlesKey, transcriptionMetadata, fileId, isDetached]);

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
                useVocals: selectPlaybackUseVocals(state),
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
