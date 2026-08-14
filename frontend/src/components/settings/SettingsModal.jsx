import React, { useEffect, useState, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { X, RotateCcw, Mic } from 'lucide-react';
import { getVADConfig, updateVADConfig, getNoiseConfig, updateNoiseConfig, toggleSettings, setMicDeviceId, setMicNoiseConfig } from '../../store/uiSlice';
import { store } from '../../store';
import { generateSubtitles } from '../../store/subtitleSlice';

export const SettingsModal = () => {
  const dispatch = useDispatch();
  const showSettings = useSelector((state) => state.ui.showSettings);
  const vadConfig = useSelector((state) => state.ui.vadConfig);
  const vadConfigLoading = useSelector((state) => state.ui.vadConfigLoading);
  const vadConfigError = useSelector((state) => state.ui.vadConfigError);
  const noiseConfig = useSelector((state) => state.ui.noiseConfig);
  const noiseConfigLoading = useSelector((state) => state.ui.noiseConfigLoading);
  const noiseConfigError = useSelector((state) => state.ui.noiseConfigError);
  const fileId = useSelector((state) => state.media.fileId);
  const isProcessing = useSelector((state) => state.media.isProcessing);
  const selectedMicDeviceId = useSelector((state) => state.ui.selectedMicDeviceId);
  const micNoiseConfig = useSelector((state) => state.ui.micNoiseConfig);

  const [audioInputs, setAudioInputs] = useState([]);
  const [micPermissionState, setMicPermissionState] = useState('unknown'); // 'unknown' | 'granted' | 'denied'
  const [micPermissionError, setMicPermissionError] = useState(null);

  // 麦克风降噪表单状态
  const [micNoiseFormData, setMicNoiseFormData] = useState({
    enabled: false,
    lowcut: 200,
    highcut: 3500,
    order: 4,
    filter_type: 'bandpass',
    normalize_after_filter: true,
  });

  // 麦克风降噪是否有未保存的更改
  const [micNoiseHasChanges, setMicNoiseHasChanges] = useState(false);

  // 本地表单状态 - VAD 参数
  const [formData, setFormData] = useState({
    min_silence_duration_ms: 500,
    max_speech_duration_s: 30,
    sample_rate: 16000,
  });

  // 降噪参数表单状态
  const [noiseFormData, setNoiseFormData] = useState({
    enabled: true,
    lowcut: 200,
    highcut: 3500,
    order: 4,
    filter_type: 'bandpass',
    normalize_after_filter: true,
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

  // 当降噪配置加载时更新表单
  useEffect(() => {
    if (noiseConfig) {
      setNoiseFormData({
        enabled: noiseConfig.enabled ?? true,
        lowcut: noiseConfig.lowcut || 200,
        highcut: noiseConfig.highcut || 3500,
        order: noiseConfig.order || 4,
        filter_type: noiseConfig.filter_type || 'bandpass',
        normalize_after_filter: noiseConfig.normalize_after_filter ?? true,
      });
    }
  }, [noiseConfig]);

  // 当麦克风降噪配置加载时更新表单
  useEffect(() => {
    if (micNoiseConfig) {
      setMicNoiseFormData({
        enabled: micNoiseConfig.enabled ?? false,
        lowcut: micNoiseConfig.lowcut || 200,
        highcut: micNoiseConfig.highcut || 3500,
        order: micNoiseConfig.order || 4,
        filter_type: micNoiseConfig.filter_type || 'bandpass',
        normalize_after_filter: micNoiseConfig.normalize_after_filter ?? true,
      });
      setMicNoiseHasChanges(false); // 重置变更状态
    }
  }, [micNoiseConfig]);

  // 打开设置时加载配置
  useEffect(() => {
    if (showSettings && !vadConfig) {
      dispatch(getVADConfig());
    }
    if (showSettings && !noiseConfig) {
      dispatch(getNoiseConfig());
    }
  }, [showSettings, vadConfig, noiseConfig, dispatch]);

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

  const handleNoiseInputChange = (field, value) => {
    setNoiseFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleMicNoiseInputChange = (field, value) => {
    setMicNoiseFormData((prev) => ({ ...prev, [field]: value }));
    setMicNoiseHasChanges(true);
  };

  const handleSave = async () => {
    // VAD 配置更新
    const vadUpdates = {};
    Object.keys(formData).forEach((key) => {
      if (vadConfig && formData[key] !== vadConfig[key]) {
        vadUpdates[key] = formData[key];
      }
    });

    // 降噪配置更新
    const noiseUpdates = {};
    Object.keys(noiseFormData).forEach((key) => {
      if (noiseConfig && noiseFormData[key] !== noiseConfig[key]) {
        noiseUpdates[key] = noiseFormData[key];
      }
    });

    if (Object.keys(vadUpdates).length === 0 && Object.keys(noiseUpdates).length === 0) {
      dispatch(toggleSettings());
      return;
    }

    try {
      // 并发更新 VAD 和降噪配置
      const promises = [];
      if (Object.keys(vadUpdates).length > 0) {
        promises.push(dispatch(updateVADConfig(vadUpdates)).unwrap());
      }
      if (Object.keys(noiseUpdates).length > 0) {
        promises.push(dispatch(updateNoiseConfig(noiseUpdates)).unwrap());
      }

      await Promise.all(promises);

      // 配置保存成功，立即关闭设置模态框
      // 不等待字幕刷新完成，提升用户体验
      dispatch(toggleSettings());

      // 配置更新成功后，如果有当前文件，强制刷新字幕（跳过缓存）
      // 在后台异步执行，不阻塞 UI
      if (fileId) {
        dispatch(generateSubtitles({ fileId, forceRefresh: true }))
          .unwrap()
          .catch((error) => {
            // 字幕刷新失败不影响配置保存的结果
            console.error('Failed to refresh subtitles after config update:', error);
          });
      }
    } catch (error) {
      // 配置保存失败，保持模态框打开让用户看到错误
      console.error('Failed to save config:', error);
    }
  };

  const handleMicNoiseSave = () => {
    // 麦克风降噪配置更新 (直接保存到 Redux，会自动持久化到 localStorage)
    const micNoiseUpdates = {};
    Object.keys(micNoiseFormData).forEach((key) => {
      if (micNoiseConfig && micNoiseFormData[key] !== micNoiseConfig[key]) {
        micNoiseUpdates[key] = micNoiseFormData[key];
      }
    });
    dispatch(setMicNoiseConfig(micNoiseUpdates));
    setMicNoiseHasChanges(false);
  };

  const handleReset = async () => {
    // 重置为默认值
    setFormData({
      min_silence_duration_ms: 500,
      max_speech_duration_s: 30,
      sample_rate: 16000,
    });
    setNoiseFormData({
      enabled: true,
      lowcut: 200,
      highcut: 3500,
      order: 4,
      filter_type: 'bandpass',
      normalize_after_filter: true,
    });
    setMicNoiseFormData({
      enabled: false,
      lowcut: 200,
      highcut: 3500,
      order: 4,
      filter_type: 'bandpass',
      normalize_after_filter: true,
    });
    setMicNoiseHasChanges(false); // 重置变更状态
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
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* ==================== 麦克风设置 ==================== */}
          <div className="space-y-6">
            <div>
              <h3 className="text-base font-semibold text-text-primary mb-4 flex items-center gap-2">
                <Mic size={18} />
                麦克风设置
              </h3>
              <p className="text-xs text-text-tertiary -mt-3 mb-4">
                配置录音设备和用户录音降噪参数
              </p>
            </div>

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

            {/* 麦克风降噪设置 */}
            <div className="space-y-2 pt-2 border-t border-bg-card/50">
              <div className="flex items-center justify-between">
                <label className="text-sm text-text-secondary flex items-center gap-2">
                  <Mic size={14} />
                  麦克风降噪
                </label>
                <button
                  type="button"
                  onClick={() => handleMicNoiseInputChange('enabled', !micNoiseFormData.enabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    micNoiseFormData.enabled ? 'bg-primary' : 'bg-bg-card'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      micNoiseFormData.enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              {micNoiseFormData.enabled && (
                <>
                  {/* 滤波器类型 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">滤波器类型</label>
                    <select
                      value={micNoiseFormData.filter_type}
                      onChange={(e) => handleMicNoiseInputChange('filter_type', e.target.value)}
                      className="input px-3 py-1 text-sm w-32"
                    >
                      <option value="bandpass">带通</option>
                      <option value="highpass">高通</option>
                      <option value="lowpass">低通</option>
                    </select>
                  </div>

                  {/* 低频截止 */}
                  {micNoiseFormData.filter_type !== 'lowpass' && (
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        低频截止: {micNoiseFormData.lowcut} Hz
                        <span className="text-xs text-text-tertiary ml-2">
                          (切除风扇、空调等低频噪音)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="50"
                        max="500"
                        step="10"
                        value={micNoiseFormData.lowcut}
                        onChange={(e) => handleMicNoiseInputChange('lowcut', parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  )}

                  {/* 高频截止 */}
                  {micNoiseFormData.filter_type !== 'highpass' && (
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        高频截止: {micNoiseFormData.highcut} Hz
                        <span className="text-xs text-text-tertiary ml-2">
                          (切除电流声、电子杂音等高频噪音)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="2000"
                        max="8000"
                        step="100"
                        value={micNoiseFormData.highcut}
                        onChange={(e) => handleMicNoiseInputChange('highcut', parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  )}

                  {/* 滤波器阶数 */}
                  <div className="space-y-2">
                    <label className="text-sm text-text-secondary">
                      滤波器阶数: {micNoiseFormData.order}
                      <span className="text-xs text-text-tertiary ml-2">
                        (值越大滤波越陡峭，4-6为常用值)
                      </span>
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="8"
                      step="1"
                      value={micNoiseFormData.order}
                      onChange={(e) => handleMicNoiseInputChange('order', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  {/* 滤波后归一化 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">滤波后归一化</label>
                    <button
                      type="button"
                      onClick={() => handleMicNoiseInputChange('normalize_after_filter', !micNoiseFormData.normalize_after_filter)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        micNoiseFormData.normalize_after_filter ? 'bg-primary' : 'bg-bg-card'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          micNoiseFormData.normalize_after_filter ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* 提示信息 */}
                  <div className="p-3 bg-bg-card rounded-lg text-xs text-text-tertiary">
                    <div className="font-medium mb-1">💡 麦克风降噪说明</div>
                    <div>• 用于播放用户录音时实时降噪</div>
                    <div>• 与"音视频降噪"独立配置，互不影响</div>
                    <div>• 人声频率范围约 300-3400Hz</div>
                  </div>

                  {/* 单独保存按钮 */}
                  <button
                    onClick={handleMicNoiseSave}
                    disabled={!micNoiseHasChanges}
                    className={`w-full px-4 py-2 text-sm rounded-lg transition-colors ${
                      micNoiseHasChanges
                        ? 'bg-primary text-white hover:bg-primary-hover'
                        : 'bg-bg-tertiary text-text-tertiary cursor-not-allowed'
                    }`}
                  >
                    {micNoiseHasChanges ? '保存麦克风降噪设置' : '已保存'}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* 分隔线 */}
          <div className="border-t-2 border-bg-card" />

          {/* ==================== 音视频设置 ==================== */}
          <div className="space-y-6">
            <div>
              <h3 className="text-base font-semibold text-text-primary mb-4 flex items-center gap-2">
                🎬 音视频设置
              </h3>
              <p className="text-xs text-text-tertiary -mt-3 mb-4">
                配置视频字幕生成和音视频降噪参数
              </p>
            </div>

            {/* 音视频降噪参数 */}
            <div className="space-y-2">
              <div className="text-sm font-semibold text-text-primary">音视频降噪参数</div>

              {noiseConfigLoading && (
                <div className="flex items-center justify-center py-8">
                  <div className="spinner w-6 h-6 border-2 border-primary border-t-transparent" />
                </div>
              )}

              {noiseConfigError && (
                <div className="p-4 bg-error/10 border border-error/30 rounded-lg text-error text-sm">
                  {noiseConfigError}
                </div>
              )}

              {!noiseConfigLoading && noiseConfig && (
                <>
                  {/* 启用降噪 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">启用降噪</label>
                    <button
                      type="button"
                      onClick={() => handleNoiseInputChange('enabled', !noiseFormData.enabled)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        noiseFormData.enabled ? 'bg-primary' : 'bg-bg-card'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          noiseFormData.enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* 滤波器类型 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">滤波器类型</label>
                    <select
                      value={noiseFormData.filter_type}
                      onChange={(e) => handleNoiseInputChange('filter_type', e.target.value)}
                      className="input px-3 py-1 text-sm w-32"
                    >
                      <option value="bandpass">带通</option>
                      <option value="highpass">高通</option>
                      <option value="lowpass">低通</option>
                    </select>
                  </div>

                  {/* 低频截止 */}
                  {noiseFormData.filter_type !== 'lowpass' && (
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        低频截止: {noiseFormData.lowcut} Hz
                        <span className="text-xs text-text-tertiary ml-2">
                          (切除风扇、空调等低频噪音)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="50"
                        max="500"
                        step="10"
                        value={noiseFormData.lowcut}
                        onChange={(e) => handleNoiseInputChange('lowcut', parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  )}

                  {/* 高频截止 */}
                  {noiseFormData.filter_type !== 'highpass' && (
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        高频截止: {noiseFormData.highcut} Hz
                        <span className="text-xs text-text-tertiary ml-2">
                          (切除电流声、电子杂音等高频噪音)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="2000"
                        max="8000"
                        step="100"
                        value={noiseFormData.highcut}
                        onChange={(e) => handleNoiseInputChange('highcut', parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  )}

                  {/* 滤波器阶数 */}
                  <div className="space-y-2">
                    <label className="text-sm text-text-secondary">
                      滤波器阶数: {noiseFormData.order}
                      <span className="text-xs text-text-tertiary ml-2">
                        (值越大滤波越陡峭，4-6为常用值)
                      </span>
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="8"
                      step="1"
                      value={noiseFormData.order}
                      onChange={(e) => handleNoiseInputChange('order', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  {/* 滤波后归一化 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">滤波后归一化</label>
                    <button
                      type="button"
                      onClick={() => handleNoiseInputChange('normalize_after_filter', !noiseFormData.normalize_after_filter)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        noiseFormData.normalize_after_filter ? 'bg-primary' : 'bg-bg-card'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          noiseFormData.normalize_after_filter ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* 提示信息 */}
                  <div className="p-4 bg-bg-card rounded-lg text-xs text-text-tertiary">
                    <div className="font-medium mb-2">默认值:</div>
                    <div>• 启用: 是</div>
                    <div>• 滤波器类型: 带通</div>
                    <div>• 低频截止: 200 Hz</div>
                    <div>• 高频截止: 3500 Hz</div>
                    <div>• 滤波器阶数: 4</div>
                    <div>• 滤波后归一化: 是</div>
                    <div className="mt-2 text-primary">💡 人声频率范围约 300-3400Hz</div>
                  </div>
                </>
              )}
            </div>

            {/* VAD 参数 */}
            <div className="space-y-2 pt-2 border-t border-bg-card/50">
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

            {/* 音视频设置保存按钮 */}
            <button
              onClick={handleSave}
              disabled={(vadConfigLoading || noiseConfigLoading) || isProcessing}
              className={`w-full px-4 py-2 text-sm rounded-lg transition-colors ${
                (vadConfigLoading || noiseConfigLoading || isProcessing)
                  ? 'bg-bg-tertiary text-text-tertiary cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary-hover'
              }`}
            >
              {(vadConfigLoading || noiseConfigLoading || isProcessing) ? '保存中...' : '保存并刷新字幕'}
            </button>
          </div>
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

          <button
            onClick={() => dispatch(toggleSettings())}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
};
