import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Upload, Settings, HelpCircle, Moon, Sun } from 'lucide-react';
import { toggleTheme, toggleSettings, toggleShortcutsHelp } from '../../store/uiSlice';

export const Header = () => {
  const dispatch = useDispatch();
  const theme = useSelector((state) => state.ui.theme);
  const systemStatus = useSelector((state) => state.ui.systemStatus);
  const fileId = useSelector((state) => state.media.fileId);
  const isProcessing = useSelector((state) => state.media.isProcessing);

  // Check if model is ready for file upload
  const isModelReady = systemStatus?.model_loaded;

  const handleFileUpload = () => {
    // Prevent upload if model is not ready
    if (!isModelReady) return;

    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'video/*,audio/*';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (file) {
        // Dispatch upload action
        window.dispatchEvent(new CustomEvent('fileUpload', { detail: file }));
      }
    };
    input.click();
  };

  return (
    <header className="flex items-center justify-between px-6 py-3 bg-bg-secondary border-b border-bg-card">
      {/* Left: Logo and file upload */}
      <div className="flex items-center space-x-4">
        <h1 className="text-xl font-bold text-text-primary">
          ASR Practice
        </h1>
        <button
          onClick={handleFileUpload}
          disabled={!isModelReady}
          className={`flex items-center space-x-2 px-4 py-2 text-sm rounded-lg transition-colors ${
            isModelReady
              ? 'bg-primary text-white hover:bg-primary-hover'
              : 'bg-bg-card text-text-secondary opacity-50 cursor-not-allowed'
          }`}
        >
          <Upload size={18} />
          <span>{!isModelReady ? '模型加载中...' : '打开文件'}</span>
        </button>
      </div>

      {/* Center: System status */}
      <div className="flex items-center space-x-4 text-sm">
        {systemStatus && (fileId || isProcessing) && (
          <div className="flex items-center space-x-4">
            <div
              className={`flex items-center space-x-2 ${
                systemStatus.model_loaded ? 'text-success' : 'text-warning'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-current animate-pulse' : 'bg-current'}`} />
              <span>
                {isProcessing ? '处理中' :
                 (systemStatus.model_loaded ? 'GPU就绪' : '模型加载中')}
              </span>
            </div>
            {systemStatus.model_size && (
              <span className="text-text-secondary">
                {systemStatus.model_size}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-2">
        <button
          onClick={() => dispatch(toggleTheme())}
          className="p-2 rounded-lg hover:bg-bg-card transition-colors"
          title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
        >
          {theme === 'dark' ? (
            <Sun size={20} className="text-text-primary" />
          ) : (
            <Moon size={20} className="text-text-primary" />
          )}
        </button>
        <button
          onClick={() => dispatch(toggleShortcutsHelp())}
          className="p-2 rounded-lg hover:bg-bg-card transition-colors"
          title="快捷键帮助"
        >
          <HelpCircle size={20} className="text-text-primary" />
        </button>
        <button
          onClick={() => dispatch(toggleSettings())}
          className="p-2 rounded-lg hover:bg-bg-card transition-colors"
          title="设置"
        >
          <Settings size={20} className="text-text-primary" />
        </button>
      </div>
    </header>
  );
};
