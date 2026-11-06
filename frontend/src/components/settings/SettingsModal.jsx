import React, { useEffect, useState, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { X, RotateCcw, Mic, ChevronDown, ChevronRight } from 'lucide-react';
import {
  getVADConfig, updateVADConfig, getNoiseConfig, updateNoiseConfig,
  getDemucsConfig, updateDemucsConfig, getSyncRepairConfig, updateSyncRepairConfig,
  resetVADConfig, resetNoiseConfig, resetDemucsConfig, resetSyncRepairConfig,
  toggleSettings, setMicDeviceId, setMicNoiseConfig,
} from '../../store/uiSlice';
import { store } from '../../store';
import { generateSubtitles, repairSubtitles } from '../../store/subtitleSlice';
import { LoadingSpinner } from '../common/LoadingSpinner';

// 设置页选项卡（顺序即展示顺序）
const TABS = [
  { id: 'mic', label: '麦克风' },
  { id: 'noise', label: '降噪' },
  { id: 'demucs', label: '人声分离' },
  { id: 'subtitle', label: '字幕质量' },
];

// 字幕同步修复高级参数（滑条范围须为后端 schema 校验范围的子集）
const SYNC_ADVANCED_FIELDS = [
  {
    key: 'rate_lo', label: '语速下限', unit: '字/秒', dec: 1,
    min: 1, max: 15, step: 0.5, hint: '低于视为拖沓/铺静音',
    tip: '字幕段语速（字/秒）低于该值视为可疑（拖沓/铺静音），会触发重新探测定位。默认 4',
  },
  {
    key: 'rate_hi', label: '语速上限', unit: '字/秒', dec: 0,
    min: 10, max: 60, step: 1, hint: '高于视为挤扁/错位',
    tip: '字幕段语速（字/秒）高于该值视为可疑（挤扁/错位），会触发重新探测定位（重探测接受窗自动放宽到该值 +8）。默认 34',
  },
  {
    key: 'search_s', label: '候选窗搜索半径', unit: '秒', dec: 0,
    min: 1, max: 30, step: 1, hint: '在当前时间附近多大范围找真实位置',
    tip: '对可疑字幕段，在其当前时间戳附近多大范围内搜索这句话的真实位置。错位通常在 4~7 秒内。默认 12',
  },
  {
    key: 'merge_gap', label: '单元桥接间隔', unit: '秒', dec: 1,
    min: 0, max: 5, step: 0.1, hint: '相邻无主语音岛合并为同一候选',
    tip: '相邻的无人认领语音岛间隔小于该值时，合并为一个候选位置。默认 1.2',
  },
  {
    key: 'min_island_w', label: '最小语音岛宽', unit: '秒', dec: 2,
    min: 0.02, max: 1, step: 0.01, hint: '短于此的岛不作候选',
    tip: '短于该时长的语音岛不作为候选位置。"Huh?" 这类短感叹词的岛约 0.15 秒，不宜设得太大。默认 0.12',
  },
  {
    key: 'max_word_dur', label: '单词时长上限', unit: '秒', dec: 1,
    min: 0.3, max: 5, step: 0.1, hint: '超过视为退化时间戳',
    tip: '单个词的时间戳时长超过该值视为退化信号（对齐器钉死/漂移），触发整段重探测。默认 1.5',
  },
  {
    key: 'speech_ratio', label: '语音占比下限', unit: '', dec: 2,
    min: 0, max: 1, step: 0.05, hint: '段内语音帧占比低于则可疑',
    tip: '字幕段时间轴内语音帧占比低于该值视为可疑（可能铺在静音上），触发重探测。默认 0.35',
  },
  {
    key: 'snap_window', label: '静音吸附窗口', unit: '秒', dec: 1,
    min: 0, max: 3, step: 0.1, hint: '起点最多向前吸附多少秒',
    tip: '字幕段起点落在静音里时，最多向前吸附多少秒到最近的语音起点。默认 0.7',
  },
];

const SYNC_BANDPASS_FIELDS = [
  {
    key: 'bandpass_lo', label: '带通下限', unit: 'Hz', dec: 0,
    min: 20, max: 1000, step: 10, hint: '低于被滤除',
    tip: '修复通道内带通滤波的低频截止（Hz）。默认 80',
  },
  {
    key: 'bandpass_hi', label: '带通上限', unit: 'Hz', dec: 0,
    min: 1000, max: 8000, step: 100, hint: '高于被滤除',
    tip: '修复通道内带通滤波的高频截止（Hz）。默认 5500',
  },
];

export const SettingsModal = () => {
  const dispatch = useDispatch();
  const showSettings = useSelector((state) => state.ui.showSettings);
  const vadConfig = useSelector((state) => state.ui.vadConfig);
  const vadConfigLoading = useSelector((state) => state.ui.vadConfigLoading);
  const vadConfigError = useSelector((state) => state.ui.vadConfigError);
  const noiseConfig = useSelector((state) => state.ui.noiseConfig);
  const noiseConfigLoading = useSelector((state) => state.ui.noiseConfigLoading);
  const noiseConfigError = useSelector((state) => state.ui.noiseConfigError);
  const demucsConfig = useSelector((state) => state.ui.demucsConfig);
  const demucsConfigLoading = useSelector((state) => state.ui.demucsConfigLoading);
  const demucsConfigError = useSelector((state) => state.ui.demucsConfigError);
  const syncRepairConfig = useSelector((state) => state.ui.syncRepairConfig);
  const syncRepairConfigLoading = useSelector((state) => state.ui.syncRepairConfigLoading);
  const syncRepairConfigError = useSelector((state) => state.ui.syncRepairConfigError);
  const systemStatus = useSelector((state) => state.ui.systemStatus);
  const transcriptionMetadata = useSelector((state) => state.subtitle.transcriptionMetadata);
  const fileId = useSelector((state) => state.media.fileId);
  const isProcessing = useSelector((state) => state.media.isProcessing);
  const selectedMicDeviceId = useSelector((state) => state.ui.selectedMicDeviceId);
  const micNoiseConfig = useSelector((state) => state.ui.micNoiseConfig);

  // 当前选项卡（记忆上次所在卡）
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const saved = localStorage.getItem('settingsActiveTab');
      return TABS.some((t) => t.id === saved) ? saved : 'mic';
    } catch {
      return 'mic';
    }
  });
  const switchTab = (id) => {
    setActiveTab(id);
    try { localStorage.setItem('settingsActiveTab', id); } catch { /* ignore */ }
  };

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
    speech_pad_ms: 200,
    max_merge_gap_s: 0.5,
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

  // demucs 人声分离表单状态
  const [demucsFormData, setDemucsFormData] = useState({
    enabled: false,
    model_name: 'htdemucs',
    repo_path: '',
    playback_use_vocals: false,
  });

  // 字幕同步修复表单状态（默认值与后端一致）
  const [syncRepairFormData, setSyncRepairFormData] = useState({
    enabled: true,
    max_word_dur: 1.5,
    speech_ratio: 0.35,
    snap_window: 0.7,
    rate_lo: 4,
    rate_hi: 34,
    search_s: 12,
    merge_gap: 1.2,
    min_island_w: 0.12,
    bandpass: false,
    bandpass_lo: 80,
    bandpass_hi: 5500,
  });
  const [showSyncAdvanced, setShowSyncAdvanced] = useState(false);

  // 当配置加载时更新表单
  useEffect(() => {
    if (vadConfig) {
      setFormData({
        min_silence_duration_ms: vadConfig.min_silence_duration_ms || 500,
        max_speech_duration_s: vadConfig.max_speech_duration_s || 30,
        sample_rate: vadConfig.sample_rate || 16000,
        speech_pad_ms: vadConfig.speech_pad_ms ?? 200,
        max_merge_gap_s: vadConfig.max_merge_gap_s ?? 0.5,
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

  // 当 demucs 配置加载时更新表单
  useEffect(() => {
    if (demucsConfig) {
      setDemucsFormData({
        enabled: demucsConfig.enabled ?? false,
        model_name: demucsConfig.model_name || 'htdemucs',
        repo_path: demucsConfig.repo_path ?? '',
        playback_use_vocals: demucsConfig.playback_use_vocals ?? false,
      });
    }
  }, [demucsConfig]);

  // 当同步修复配置加载时更新表单
  useEffect(() => {
    if (syncRepairConfig) {
      setSyncRepairFormData({
        enabled: syncRepairConfig.enabled ?? true,
        max_word_dur: syncRepairConfig.max_word_dur ?? 1.5,
        speech_ratio: syncRepairConfig.speech_ratio ?? 0.35,
        snap_window: syncRepairConfig.snap_window ?? 0.7,
        rate_lo: syncRepairConfig.rate_lo ?? 4,
        rate_hi: syncRepairConfig.rate_hi ?? 34,
        search_s: syncRepairConfig.search_s ?? 12,
        merge_gap: syncRepairConfig.merge_gap ?? 1.2,
        min_island_w: syncRepairConfig.min_island_w ?? 0.12,
        bandpass: syncRepairConfig.bandpass ?? false,
        bandpass_lo: syncRepairConfig.bandpass_lo ?? 80,
        bandpass_hi: syncRepairConfig.bandpass_hi ?? 5500,
      });
    }
  }, [syncRepairConfig]);

  // 打开设置时加载配置
  useEffect(() => {
    if (showSettings && !vadConfig) {
      dispatch(getVADConfig());
    }
    if (showSettings && !noiseConfig) {
      dispatch(getNoiseConfig());
    }
    if (showSettings && !demucsConfig) {
      dispatch(getDemucsConfig());
    }
    if (showSettings && !syncRepairConfig) {
      dispatch(getSyncRepairConfig());
    }
  }, [showSettings, vadConfig, noiseConfig, demucsConfig, syncRepairConfig, dispatch]);

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

  const handleDemucsInputChange = (field, value) => {
    setDemucsFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSyncRepairInputChange = (field, value) => {
    setSyncRepairFormData((prev) => ({ ...prev, [field]: value }));
  };

  // demucs 是否可用（后端检测结果，优先用配置接口返回值）
  const demucsUsable = demucsConfig?.demucs_available ?? systemStatus?.demucs_available ?? false;

  // 播放偏好是纯播放设置，点击立即保存生效（不触发字幕重新生成）
  const handlePlaybackVocalsToggle = () => {
    if (!demucsUsable) return;
    const newValue = !demucsFormData.playback_use_vocals;
    handleDemucsInputChange('playback_use_vocals', newValue);
    dispatch(updateDemucsConfig({ playback_use_vocals: newValue }));
  };

  const handleMicNoiseInputChange = (field, value) => {
    setMicNoiseFormData((prev) => ({ ...prev, [field]: value }));
    setMicNoiseHasChanges(true);
  };

  // 表单与已保存配置的 diff（空对象 = 无变更）
  const diffUpdates = (form, config) => {
    const updates = {};
    if (config) {
      Object.keys(form).forEach((key) => {
        if (form[key] !== config[key]) {
          updates[key] = form[key];
        }
      });
    }
    return updates;
  };

  const handleSave = async () => {
    // VAD 配置更新
    const vadUpdates = diffUpdates(formData, vadConfig);

    // 降噪配置更新
    const noiseUpdates = diffUpdates(noiseFormData, noiseConfig);

    // demucs 配置更新（区分影响字幕生成的字段与纯播放偏好的字段）
    const demucsGenFields = ['enabled', 'model_name', 'repo_path'];
    const demucsUpdates = diffUpdates(demucsFormData, demucsConfig);
    const demucsGenUpdates = {};
    Object.keys(demucsUpdates).forEach((key) => {
      if (demucsGenFields.includes(key)) {
        demucsGenUpdates[key] = demucsUpdates[key];
      }
    });

    // 字幕同步修复配置更新
    const syncRepairUpdates = diffUpdates(syncRepairFormData, syncRepairConfig);

    const hasUpdates =
      Object.keys(vadUpdates).length > 0 ||
      Object.keys(noiseUpdates).length > 0 ||
      Object.keys(demucsUpdates).length > 0 ||
      Object.keys(syncRepairUpdates).length > 0;
    if (!hasUpdates) {
      dispatch(toggleSettings());
      return;
    }

    // 只有影响字幕生成的配置变化才需要全量重新生成；
    // 纯播放偏好（playback_use_vocals）即时生效，无需重新生成；
    // 仅同步修复参数变化走轻量重修复（不重跑 demucs/ASR）
    const shouldRegenerate =
      Object.keys(vadUpdates).length > 0 ||
      Object.keys(noiseUpdates).length > 0 ||
      Object.keys(demucsGenUpdates).length > 0;
    const syncRepairAffects =
      Object.keys(syncRepairUpdates).some((k) => k !== 'enabled') ||
      syncRepairUpdates.enabled === true; // 仅关闭总开关无需重修复

    try {
      // 并发更新各配置
      const promises = [];
      if (Object.keys(vadUpdates).length > 0) {
        promises.push(dispatch(updateVADConfig(vadUpdates)).unwrap());
      }
      if (Object.keys(noiseUpdates).length > 0) {
        promises.push(dispatch(updateNoiseConfig(noiseUpdates)).unwrap());
      }
      if (Object.keys(demucsUpdates).length > 0) {
        promises.push(dispatch(updateDemucsConfig(demucsUpdates)).unwrap());
      }
      if (Object.keys(syncRepairUpdates).length > 0) {
        promises.push(dispatch(updateSyncRepairConfig(syncRepairUpdates)).unwrap());
      }

      await Promise.all(promises);

      // 配置保存成功，立即关闭设置模态框
      // 不等待字幕刷新完成，提升用户体验
      dispatch(toggleSettings());

      // 在后台异步刷新字幕，不阻塞 UI
      if (fileId && shouldRegenerate) {
        // VAD/降噪/demucs 生成类变更：全量重新生成（内部会用新配置跑同步修复）
        dispatch(generateSubtitles({ fileId, forceRefresh: true }))
          .unwrap()
          .catch((error) => {
            console.error('Failed to refresh subtitles after config update:', error);
          });
      } else if (fileId && syncRepairAffects) {
        // 仅修复参数变更：轻量重修复（只重排时间戳，GPU 约分钟级）
        dispatch(repairSubtitles({ fileId }))
          .unwrap()
          .catch((error) => {
            console.error('Failed to repair subtitles after config update:', error);
          });
      }
    } catch (error) {
      // 配置保存失败，保持模态框打开让用户看到错误
      console.error('Failed to save config:', error);
    }
  };

  const handleMicNoiseSave = () => {
    // 麦克风降噪配置更新 (直接保存到 Redux，会自动持久化到 localStorage)
    const micNoiseUpdates = diffUpdates(micNoiseFormData, micNoiseConfig);
    dispatch(setMicNoiseConfig(micNoiseUpdates));
    setMicNoiseHasChanges(false);
  };

  const handleReset = async () => {
    // 麦克风降噪是纯前端本地配置，本地重置
    setMicNoiseFormData({
      enabled: false,
      lowcut: 200,
      highcut: 3500,
      order: 4,
      filter_type: 'bandpass',
      normalize_after_filter: true,
    });
    setMicNoiseHasChanges(false);
    // 后端配置区：调各 reset 端点（响应即默认值，表单经 useEffect 自动回填）
    try {
      await Promise.all([
        dispatch(resetVADConfig()).unwrap(),
        dispatch(resetNoiseConfig()).unwrap(),
        dispatch(resetDemucsConfig()).unwrap(),
        dispatch(resetSyncRepairConfig()).unwrap(),
      ]);
    } catch (e) {
      console.error('Failed to reset config:', e);
    }
  };

  // 各选项卡是否有未保存修改（脏标记）
  const tabDirty = {
    mic: micNoiseHasChanges,
    noise: Object.keys(diffUpdates(noiseFormData, noiseConfig)).length > 0,
    demucs: Object.keys(diffUpdates(demucsFormData, demucsConfig)).length > 0,
    subtitle:
      Object.keys(diffUpdates(formData, vadConfig)).length > 0 ||
      Object.keys(diffUpdates(syncRepairFormData, syncRepairConfig)).length > 0,
  };

  const anyConfigLoading =
    vadConfigLoading || noiseConfigLoading || demucsConfigLoading || syncRepairConfigLoading;

  // 同步修复滑条行（label 与滑条均带悬停说明）
  const renderSyncSlider = (f) => (
    <div className="space-y-2" key={f.key}>
      <label className="text-sm text-text-secondary cursor-help" title={f.tip}>
        {f.label}: {syncRepairFormData[f.key].toFixed(f.dec)}{f.unit ? ` ${f.unit}` : ''}
        <span className="text-xs text-text-tertiary ml-2">({f.hint})</span>
      </label>
      <input
        type="range"
        min={f.min}
        max={f.max}
        step={f.step}
        value={syncRepairFormData[f.key]}
        onChange={(e) => handleSyncRepairInputChange(f.key, parseFloat(e.target.value))}
        className="w-full cursor-help"
        title={f.tip}
      />
    </div>
  );

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

        {/* Tabs */}
        <div className="flex px-2 border-b border-bg-card">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => switchTab(t.id)}
              className={`relative flex-1 px-3 py-2.5 text-sm transition-colors ${
                activeTab === t.id
                  ? 'text-primary border-b-2 border-primary font-medium'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t.label}
              {tabDirty[t.id] && (
                <span
                  className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-primary"
                  title="有未保存的修改"
                />
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* ==================== 麦克风选项卡 ==================== */}
          {activeTab === 'mic' && (
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
                      <div>• 与"降噪"选项卡独立配置，互不影响</div>
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
          )}

          {/* ==================== 降噪选项卡 ==================== */}
          {activeTab === 'noise' && (
            <div className="space-y-2">
              <div className="text-sm font-semibold text-text-primary">音视频降噪参数</div>
              <p className="text-xs text-text-tertiary">
                对音视频做人声降噪后再识别（与麦克风降噪互不影响）
              </p>

              {noiseConfigLoading && (
                <LoadingSpinner size="md" />
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
          )}

          {/* ==================== 人声分离选项卡 ==================== */}
          {activeTab === 'demucs' && (
            <div className="space-y-2">
              <div className="text-sm font-semibold text-text-primary">人声分离 (demucs)</div>

              {demucsConfigLoading && (
                <LoadingSpinner size="md" />
              )}

              {demucsConfigError && (
                <div className="p-4 bg-error/10 border border-error/30 rounded-lg text-error text-sm">
                  {demucsConfigError}
                </div>
              )}

              {!demucsConfigLoading && demucsConfig && (
                <>
                  {/* 生成字幕时启用人声分离 */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">生成字幕时启用人声分离</label>
                    <button
                      type="button"
                      disabled={!demucsUsable}
                      onClick={() => demucsUsable && handleDemucsInputChange('enabled', !demucsFormData.enabled)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        demucsFormData.enabled ? 'bg-primary' : 'bg-bg-card'
                      } ${!demucsUsable ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          demucsFormData.enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {!demucsUsable && (
                    <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg text-warning text-xs">
                      未检测到 demucs：请在服务器 conda 环境中安装（pip install demucs）后重启服务
                    </div>
                  )}

                  {/* 模型名称 */}
                  <div className="space-y-2">
                    <label className="text-sm text-text-secondary">
                      模型名称
                      <span className="text-xs text-text-tertiary ml-2">
                        (默认 htdemucs)
                      </span>
                    </label>
                    <input
                      type="text"
                      value={demucsFormData.model_name}
                      onChange={(e) => handleDemucsInputChange('model_name', e.target.value)}
                      placeholder="htdemucs"
                      className="input w-full px-3 py-1.5 text-sm"
                    />
                  </div>

                  {/* 模型仓库路径 */}
                  <div className="space-y-2">
                    <label className="text-sm text-text-secondary">
                      模型仓库路径
                      <span className="text-xs text-text-tertiary ml-2">
                        (本地模型目录，留空则联网下载)
                      </span>
                    </label>
                    <input
                      type="text"
                      value={demucsFormData.repo_path}
                      onChange={(e) => handleDemucsInputChange('repo_path', e.target.value)}
                      placeholder="D:\adefossez\HTDemucs"
                      className="input w-full px-3 py-1.5 text-sm"
                    />
                  </div>

                  {/* 播放时使用人声音轨（点击立即生效） */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-text-secondary">
                      播放时使用人声音轨
                      <span className="text-xs text-text-tertiary ml-2">
                        (点击立即生效，仅对已用人声分离生成的视频生效)
                      </span>
                    </label>
                    <button
                      type="button"
                      disabled={!demucsUsable}
                      onClick={handlePlaybackVocalsToggle}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        demucsFormData.playback_use_vocals ? 'bg-primary' : 'bg-bg-card'
                      } ${!demucsUsable ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          demucsFormData.playback_use_vocals ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* 当前视频没有人声分离结果时的提示 */}
                  {demucsFormData.playback_use_vocals && fileId && !transcriptionMetadata?.used_demucs && (
                    <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg text-warning text-xs">
                      当前视频还没有人声分离结果：勾选上方"生成字幕时启用人声分离"并点保存，重新生成字幕后此开关才会生效
                    </div>
                  )}

                  {/* 提示信息 */}
                  <div className="p-3 bg-bg-card rounded-lg text-xs text-text-tertiary">
                    <div className="font-medium mb-1">💡 人声分离说明</div>
                    <div>• 启用后生成字幕时先分离出人声，消除背景音乐干扰，识别更准确</div>
                    <div>• 分离需要额外时间（GPU 上约为音频时长的 10%~30%），长视频会明显变慢</div>
                    <div>• 分离失败时自动回退用原声继续生成字幕</div>
                    <div>• 同一视频的分离结果会复用，不会重复计算</div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ==================== 字幕质量选项卡 ==================== */}
          {activeTab === 'subtitle' && (
            <div className="space-y-6">
              {/* VAD 参数 */}
              <div className="space-y-2">
                <div className="text-sm font-semibold text-text-primary">VAD 参数</div>
                <p className="text-xs text-text-tertiary">
                  长音频的语音活动检测与分段参数
                </p>

                {vadConfigLoading && (
                  <LoadingSpinner size="md" />
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

                    {/* 语音边界填充 */}
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        语音边界填充: {formData.speech_pad_ms} ms
                        <span className="text-xs text-text-tertiary ml-2">
                          (语音段首尾向外扩展，给识别模型更多上下文)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="500"
                        step="50"
                        value={formData.speech_pad_ms}
                        onChange={(e) => handleInputChange('speech_pad_ms', parseInt(e.target.value))}
                        className="w-full"
                      />
                    </div>

                    {/* 相邻段合并间隔 */}
                    <div className="space-y-2">
                      <label className="text-sm text-text-secondary">
                        相邻段合并间隔: {formData.max_merge_gap_s} 秒
                        <span className="text-xs text-text-tertiary ml-2">
                          (间隔小于该值的相邻语音段合并后再识别，避免句中切断)
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="3"
                        step="0.1"
                        value={formData.max_merge_gap_s}
                        onChange={(e) => handleInputChange('max_merge_gap_s', parseFloat(e.target.value))}
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
                      <div>• speech_pad_ms: 200</div>
                      <div>• max_merge_gap_s: 0.5</div>
                      <div>• sampling_rate: 16000</div>
                    </div>
                  </>
                )}
              </div>

              {/* 字幕同步修复 */}
              <div className="space-y-2 pt-2 border-t border-bg-card/50">
                <div className="text-sm font-semibold text-text-primary">字幕同步修复</div>

                {syncRepairConfigLoading && (
                  <LoadingSpinner size="md" />
                )}

                {syncRepairConfigError && (
                  <div className="p-4 bg-error/10 border border-error/30 rounded-lg text-error text-sm">
                    {syncRepairConfigError}
                  </div>
                )}

                {!syncRepairConfigLoading && syncRepairConfig && (
                  <>
                    {/* 总开关 */}
                    <div className="flex items-center justify-between">
                      <label
                        className="text-sm text-text-secondary cursor-help"
                        title="自动校对字幕与语音的对齐（错位/挤扁/漂移）：健康的字幕段保持不动，可疑段通过紧窗重转写重新定位。关闭后保留 ASR 原始时间戳"
                      >
                        启用时间戳修复
                        <span className="text-xs text-text-tertiary ml-2">
                          (校对字幕与语音对齐；关闭后保留原始时间戳)
                        </span>
                      </label>
                      <button
                        type="button"
                        onClick={() => handleSyncRepairInputChange('enabled', !syncRepairFormData.enabled)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          syncRepairFormData.enabled ? 'bg-primary' : 'bg-bg-card'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            syncRepairFormData.enabled ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>

                    {/* 高级参数（折叠） */}
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => setShowSyncAdvanced((v) => !v)}
                        className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
                      >
                        {showSyncAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        高级参数（悬停查看各项说明）
                      </button>

                      {showSyncAdvanced && (
                        <div className="space-y-3 pt-2">
                          {SYNC_ADVANCED_FIELDS.map(renderSyncSlider)}

                          {/* 带通开关 */}
                          <div className="flex items-center justify-between pt-1 border-t border-bg-card/50">
                            <label
                              className="text-sm text-text-secondary cursor-help"
                              title="在修复通道内先对人声做带通滤波再检测语音岛。实测一般无增益，仅特殊素材（如配乐残留严重）尝试"
                            >
                              修复通道内带通
                              <span className="text-xs text-text-tertiary ml-2">(特殊素材用，默认关)</span>
                            </label>
                            <button
                              type="button"
                              onClick={() => handleSyncRepairInputChange('bandpass', !syncRepairFormData.bandpass)}
                              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                syncRepairFormData.bandpass ? 'bg-primary' : 'bg-bg-card'
                              }`}
                            >
                              <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                  syncRepairFormData.bandpass ? 'translate-x-6' : 'translate-x-1'
                                }`}
                              />
                            </button>
                          </div>

                          {syncRepairFormData.bandpass && SYNC_BANDPASS_FIELDS.map(renderSyncSlider)}
                        </div>
                      )}
                    </div>

                    {/* 提示信息 */}
                    <div className="p-3 bg-bg-card rounded-lg text-xs text-text-tertiary">
                      <div className="font-medium mb-1">💡 字幕同步修复说明</div>
                      <div>• 修改参数保存后，会自动对当前视频轻量重跑修复（不重新转写，约 1 分钟）</div>
                      <div>• 时间戳本来就对的字幕段（健康段）会被冻结，不会被重排</div>
                      <div>• 出现修复误判时优先调低"候选窗搜索半径"，或临时关闭总开关</div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-bg-card">
          <button
            onClick={handleReset}
            className="flex items-center space-x-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            title="把各配置区恢复为服务器默认值（麦克风降噪仅本地重置）"
          >
            <RotateCcw size={16} />
            <span>重置默认</span>
          </button>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={anyConfigLoading || isProcessing}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                anyConfigLoading || isProcessing
                  ? 'bg-bg-tertiary text-text-tertiary cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary-hover'
              }`}
            >
              {anyConfigLoading || isProcessing ? '保存中...' : '保存'}
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
    </div>
  );
};
