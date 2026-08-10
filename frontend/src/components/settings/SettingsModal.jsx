import React, { useEffect, useState, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { X, RotateCcw, Mic } from 'lucide-react';
import { getVADConfig, updateVADConfig, toggleSettings, setMicDeviceId } from '../../store/uiSlice';
import { store } from '../../store';

export const SettingsModal = () => {
  const dispatch = useDispatch();
  const showSettings = useSelector((state) => state.ui.showSettings);
  const vadConfig = useSelector((state) => state.ui.vadConfig);
  const vadConfigLoading = useSelector((state) => state.ui.vadConfigLoading);
  const vadConfigError = useSelector((state) => state.ui.vadConfigError);
  const fileId = useSelector((state) => state.media.fileId);
  const isProcessing = useSelector((state) => state.media.isProcessing);
  const selectedMicDeviceId = useSelector((state) => state.ui.selectedMicDeviceId);

  const [audioInputs, setAudioInputs] = useState([]);
  const [micPermissionState, setMicPermissionState] = useState('unknown'); // 'unknown' | 'granted' | 'denied'
  const [micPermissionError, setMicPermissionError] = useState(null);

  // 本地表单状态 - 只保留 example 中使用的 3 个参数
  const [formData, setFormData] = useState({
    min_silence_duration_ms: 500,
    max_speech_duration_s: 30,
    sample_rate: 16000,
  });

  // 当配置加载时更新表单
  useEffect(() => {
    if (vadConfig) {
      setFormData({
        min_silence_duration_ms: vadConfig.min_silence_duration_ms || 500,
        max_speech_duration_s: vadConfig.max_speech_duration_s || 30,
        sample_rate: vadConfig.sample_rate || 16000,
      });
    }
  }, [vadConfig]);

  // 打开设置时加载配置
  useEffect(() => {
    if (showSettings && !vadConfig) {
      dispatch(getVADConfig());
    }
  }, [showSettings, vadConfig, dispatch]);

  // 枚举录音设备 + 监听热插拔
  const loadAudioInputs = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs = devices.filter((d) => d.kind === 'audioinput');
      setAudioInputs(inputs);

      const hasLabels = inputs.some((d) => d.label);
      if (hasLabels) setMicPermissionState('granted');

      // 如果之前持久化的设备已不存在，回退到系统默认
      const persistedId = store.getState().ui.selectedMicDeviceId;
      if (persistedId && !inputs.some((d) => d.deviceId === persistedId)) {
        dispatch(setMicDeviceId(null));
      }
    } catch (e) {
      console.error('Failed to enumerate devices:', e);
    }
  }, [dispatch]);

  useEffect(() => {
    if (!showSettings) return;
    loadAudioInputs();
    navigator.mediaDevices?.addEventListener?.('devicechange', loadAudioInputs);
    return () => {
      navigator.mediaDevices?.removeEventListener?.('devicechange', loadAudioInputs);
    };
  }, [showSettings, loadAudioInputs]);

  // 请求一次麦克风权限以获取设备真实名称
  const requestMicPermission = useCallback(async () => {
    setMicPermissionError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicPermissionState('granted');
      await loadAudioInputs();
    } catch (e) {
      setMicPermissionState('denied');
      setMicPermissionError(e?.message || '无法获取麦克风权限');
    }
  }, [loadAudioInputs]);

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    // 只发送修改过的字段
    const updates = {};
    Object.keys(formData).forEach((key) => {
      if (vadConfig && formData[key] !== vadConfig[key]) {
        updates[key] = formData[key];
      }
    });

    if (Object.keys(updates).length === 0) {
      dispatch(toggleSettings());
      return;
    }

    try {
      const result = await dispatch(updateVADConfig(updates)).unwrap();

      // 保存成功后关闭设置模态框
      if (result) {
        dispatch(toggleSettings());
      }
    } catch (error) {
      // 保存失败，保持模态框打开让用户看到错误
      console.error('Failed to save VAD config:', error);
    }
  };

  const handleReset = async () => {
    // 重置为 example 中的默认值
    setFormData({
      min_silence_duration_ms: 500,
      max_speech_duration_s: 30,
      sample_rate: 16000,
    });
  };

  if (!showSettings) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-bg-secondary rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-card">
          <h2 className="text-xl font-semibold text-text-primary">设置</h2>
          <button
            onClick={() => dispatch(toggleSettings())}
            className="p-1 rounded hover:bg-bg-card transition-colors"
          >
            <X size={20} className="text-text-secondary" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 录音设备 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm text-text-secondary flex items-center gap-2">
                <Mic size={14} />
                录音设备
              </label>
              {micPermissionState !== 'granted' && (
                <button
                  type="button"
                  onClick={requestMicPermission}
                  className="text-xs text-primary hover:underline"
                >
                  {micPermissionState === 'denied' ? '重试授权' : '允许访问麦克风'}
                </button>
              )}
            </div>
            <select
              value={selectedMicDeviceId || ''}
              onChange={(e) => dispatch(setMicDeviceId(e.target.value || null))}
              className="input w-full"
            >
              <option value="">系统默认</option>
              {audioInputs.map((device, i) => (
                <option key={device.deviceId || `input-${i}`} value={device.deviceId}>
                  {device.label || `麦克风 ${i + 1}`}
                </option>
              ))}
            </select>
            {micPermissionState !== 'granted' && audioInputs.length > 0 && (
              <div className="text-xs text-text-tertiary">
                设备名称仅在授予麦克风权限后可见
              </div>
            )}
            {audioInputs.length === 0 && (
              <div className="text-xs text-text-tertiary">
                未检测到录音设备
              </div>
            )}
            {micPermissionError && (
              <div className="text-xs text-error">{micPermissionError}</div>
            )}
          </div>

          {/* 分隔 */}
          <div className="border-t border-bg-card" />

          <div className="text-sm font-semibold text-text-primary">VAD 参数</div>

          {vadConfigLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="spinner w-6 h-6 border-2 border-primary border-t-transparent" />
            </div>
          )}

          {vadConfigError && (
            <div className="p-4 bg-error/10 border border-error/30 rounded-lg text-error text-sm">
              {vadConfigError}
            </div>
          )}

          {!vadConfigLoading && vadConfig && (
            <>
              {/* 最小静音时长 */}
              <div className="space-y-2">
                <label className="text-sm text-text-secondary">
                  最小静音时长: {formData.min_silence_duration_ms} ms
                  <span className="text-xs text-text-tertiary ml-2">
                    (超过此时长才允许分割)
                  </span>
                </label>
                <input
                  type="range"
                  min="100"
                  max="2000"
                  step="50"
                  value={formData.min_silence_duration_ms}
                  onChange={(e) => handleInputChange('min_silence_duration_ms', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* 最大语音时长 */}
              <div className="space-y-2">
                <label className="text-sm text-text-secondary">
                  单段最大语音时长: {formData.max_speech_duration_s} 秒
                  <span className="text-xs text-text-tertiary ml-2">
                    (单段语音的最大时长)
                  </span>
                </label>
                <input
                  type="range"
                  min="5"
                  max="120"
                  step="5"
                  value={formData.max_speech_duration_s}
                  onChange={(e) => handleInputChange('max_speech_duration_s', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* 采样率 */}
              <div className="flex items-center justify-between">
                <label className="text-sm text-text-secondary">采样率</label>
                <select
                  value={formData.sample_rate}
                  onChange={(e) => handleInputChange('sample_rate', parseInt(e.target.value))}
                  className="input px-3 py-1 text-sm w-32"
                >
                  <option value="8000">8000 Hz</option>
                  <option value="16000">16000 Hz</option>
                  <option value="48000">48000 Hz</option>
                </select>
              </div>

              {/* 默认值说明 */}
              <div className="p-4 bg-bg-card rounded-lg text-xs text-text-tertiary">
                <div className="font-medium mb-2">默认值:</div>
                <div>• min_silence_duration_ms: 500</div>
                <div>• max_speech_duration_s: 30</div>
                <div>• sampling_rate: 16000</div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-bg-card">
          <button
            onClick={handleReset}
            className="flex items-center space-x-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            <RotateCcw size={16} />
            <span>重置默认</span>
          </button>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => dispatch(toggleSettings())}
              className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={vadConfigLoading || isProcessing}
              className="btn-primary px-4 py-2 text-sm"
            >
              {vadConfigLoading || isProcessing ? '保存中...' : '保存并刷新字幕'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
