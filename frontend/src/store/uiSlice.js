import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { systemService } from '../services/systemService';

export const getSystemStatus = createAsyncThunk(
  'ui/getSystemStatus',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.getStatus();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getVADConfig = createAsyncThunk(
  'ui/getVADConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.getVADConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const updateVADConfig = createAsyncThunk(
  'ui/updateVADConfig',
  async (config, { rejectWithValue }) => {
    try {
      const response = await systemService.updateVADConfig(config);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getNoiseConfig = createAsyncThunk(
  'ui/getNoiseConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.getNoiseConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const updateNoiseConfig = createAsyncThunk(
  'ui/updateNoiseConfig',
  async (config, { rejectWithValue }) => {
    try {
      const response = await systemService.updateNoiseConfig(config);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getDemucsConfig = createAsyncThunk(
  'ui/getDemucsConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.getDemucsConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const updateDemucsConfig = createAsyncThunk(
  'ui/updateDemucsConfig',
  async (config, { rejectWithValue }) => {
    try {
      const response = await systemService.updateDemucsConfig(config);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const resetVADConfig = createAsyncThunk(
  'ui/resetVADConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.resetVADConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const resetNoiseConfig = createAsyncThunk(
  'ui/resetNoiseConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.resetNoiseConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const resetDemucsConfig = createAsyncThunk(
  'ui/resetDemucsConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.resetDemucsConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getSyncRepairConfig = createAsyncThunk(
  'ui/getSyncRepairConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.getSyncRepairConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const updateSyncRepairConfig = createAsyncThunk(
  'ui/updateSyncRepairConfig',
  async (config, { rejectWithValue }) => {
    try {
      const response = await systemService.updateSyncRepairConfig(config);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const resetSyncRepairConfig = createAsyncThunk(
  'ui/resetSyncRepairConfig',
  async (_, { rejectWithValue }) => {
    try {
      const response = await systemService.resetSyncRepairConfig();
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

function getInitialMicDeviceId() {
  try {
    return localStorage.getItem('selectedMicDeviceId') || null;
  } catch {
    return null;
  }
}

function getInitialMicNoiseConfig() {
  try {
    const stored = localStorage.getItem('micNoiseConfig');
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    // Use default if storage fails
  }
  // Default configuration
  return {
    enabled: false,
    lowcut: 200,
    highcut: 3500,
    order: 4,
    filter_type: 'bandpass',
    normalize_after_filter: true,
  };
}

const initialState = {
  isLoading: false,
  loadingMessage: '',
  error: null,
  theme: 'dark',          // 'dark' or 'light'
  mode: 'shadowing',      // 'free', 'intensive', 'shadowing'
  showSettings: false,
  showWordTooltip: false,
  selectedWord: null,
  selectedMicDeviceId: getInitialMicDeviceId(),
  micNoiseConfig: getInitialMicNoiseConfig(),
  systemStatus: null,
  vadConfig: null,
  vadConfigLoading: false,
  vadConfigError: null,
  noiseConfig: null,
  noiseConfigLoading: false,
  noiseConfigError: null,
  demucsConfig: null,
  demucsConfigLoading: false,
  demucsConfigError: null,
  syncRepairConfig: null,
  syncRepairConfigLoading: false,
  syncRepairConfigError: null,
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setLoading: (state, action) => {
      state.isLoading = action.payload;
    },
    setLoadingMessage: (state, action) => {
      state.loadingMessage = action.payload;
    },
    setError: (state, action) => {
      state.error = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    toggleTheme: (state) => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark';
    },
    setMode: (state, action) => {
      state.mode = action.payload;
    },
    toggleSettings: (state) => {
      state.showSettings = !state.showSettings;
    },
    showWordTooltip: (state, action) => {
      state.showWordTooltip = true;
      state.selectedWord = action.payload;
    },
    hideWordTooltip: (state) => {
      state.showWordTooltip = false;
      state.selectedWord = null;
    },
    setMicDeviceId: (state, action) => {
      state.selectedMicDeviceId = action.payload || null;
    },
    setMicNoiseConfig: (state, action) => {
      state.micNoiseConfig = { ...state.micNoiseConfig, ...action.payload };
    },
  },
  extraReducers: (builder) => {
    builder
      // Get system status
      .addCase(getSystemStatus.fulfilled, (state, action) => {
        state.systemStatus = action.payload;
      })
      // Get VAD config
      .addCase(getVADConfig.pending, (state) => {
        state.vadConfigLoading = true;
        state.vadConfigError = null;
      })
      .addCase(getVADConfig.fulfilled, (state, action) => {
        state.vadConfigLoading = false;
        state.vadConfig = action.payload;
      })
      .addCase(getVADConfig.rejected, (state, action) => {
        state.vadConfigLoading = false;
        state.vadConfigError = action.payload;
      })
      // Update VAD config
      .addCase(updateVADConfig.pending, (state) => {
        state.vadConfigLoading = true;
        state.vadConfigError = null;
      })
      .addCase(updateVADConfig.fulfilled, (state, action) => {
        state.vadConfigLoading = false;
        state.vadConfig = action.payload;
      })
      .addCase(updateVADConfig.rejected, (state, action) => {
        state.vadConfigLoading = false;
        state.vadConfigError = action.payload;
      })
      // Get noise config
      .addCase(getNoiseConfig.pending, (state) => {
        state.noiseConfigLoading = true;
        state.noiseConfigError = null;
      })
      .addCase(getNoiseConfig.fulfilled, (state, action) => {
        state.noiseConfigLoading = false;
        state.noiseConfig = action.payload;
      })
      .addCase(getNoiseConfig.rejected, (state, action) => {
        state.noiseConfigLoading = false;
        state.noiseConfigError = action.payload;
      })
      // Update noise config
      .addCase(updateNoiseConfig.pending, (state) => {
        state.noiseConfigLoading = true;
        state.noiseConfigError = null;
      })
      .addCase(updateNoiseConfig.fulfilled, (state, action) => {
        state.noiseConfigLoading = false;
        state.noiseConfig = action.payload;
      })
      .addCase(updateNoiseConfig.rejected, (state, action) => {
        state.noiseConfigLoading = false;
        state.noiseConfigError = action.payload;
      })
      // Get demucs config
      .addCase(getDemucsConfig.pending, (state) => {
        state.demucsConfigLoading = true;
        state.demucsConfigError = null;
      })
      .addCase(getDemucsConfig.fulfilled, (state, action) => {
        state.demucsConfigLoading = false;
        state.demucsConfig = action.payload;
      })
      .addCase(getDemucsConfig.rejected, (state, action) => {
        state.demucsConfigLoading = false;
        state.demucsConfigError = action.payload;
      })
      // Update demucs config
      .addCase(updateDemucsConfig.pending, (state) => {
        state.demucsConfigLoading = true;
        state.demucsConfigError = null;
      })
      .addCase(updateDemucsConfig.fulfilled, (state, action) => {
        state.demucsConfigLoading = false;
        state.demucsConfig = action.payload;
      })
      .addCase(updateDemucsConfig.rejected, (state, action) => {
        state.demucsConfigLoading = false;
        state.demucsConfigError = action.payload;
      })
      // Reset configs（响应即重置后的完整配置，直接刷新状态，
      // 设置页表单经现有 useEffect 自动回填）
      .addCase(resetVADConfig.fulfilled, (state, action) => {
        state.vadConfig = action.payload;
      })
      .addCase(resetNoiseConfig.fulfilled, (state, action) => {
        state.noiseConfig = action.payload;
      })
      .addCase(resetDemucsConfig.fulfilled, (state, action) => {
        state.demucsConfig = action.payload;
      })
      // Get sync repair config
      .addCase(getSyncRepairConfig.pending, (state) => {
        state.syncRepairConfigLoading = true;
        state.syncRepairConfigError = null;
      })
      .addCase(getSyncRepairConfig.fulfilled, (state, action) => {
        state.syncRepairConfigLoading = false;
        state.syncRepairConfig = action.payload;
      })
      .addCase(getSyncRepairConfig.rejected, (state, action) => {
        state.syncRepairConfigLoading = false;
        state.syncRepairConfigError = action.payload;
      })
      // Update sync repair config
      .addCase(updateSyncRepairConfig.pending, (state) => {
        state.syncRepairConfigLoading = true;
        state.syncRepairConfigError = null;
      })
      .addCase(updateSyncRepairConfig.fulfilled, (state, action) => {
        state.syncRepairConfigLoading = false;
        state.syncRepairConfig = action.payload;
      })
      .addCase(updateSyncRepairConfig.rejected, (state, action) => {
        state.syncRepairConfigLoading = false;
        state.syncRepairConfigError = action.payload;
      })
      // Reset sync repair config
      .addCase(resetSyncRepairConfig.fulfilled, (state, action) => {
        state.syncRepairConfig = action.payload;
      });
  },
});

export const {
  setLoading,
  setLoadingMessage,
  setError,
  clearError,
  toggleTheme,
  setMode,
  toggleSettings,
  showWordTooltip,
  hideWordTooltip,
  setMicDeviceId,
  setMicNoiseConfig,
} = uiSlice.actions;

export const getNoiseConfigAction = getNoiseConfig;
export const updateNoiseConfigAction = updateNoiseConfig;

/**
 * 播放器是否应使用人声音轨：
 * 播放偏好开启 + 当前视频的字幕由 demucs 生成（有人声文件）+ 有当前文件
 */
export const selectPlaybackUseVocals = (state) =>
  !!(
    state.ui.demucsConfig?.playback_use_vocals &&
    state.subtitle.transcriptionMetadata?.used_demucs &&
    state.media.fileId
  );

export default uiSlice.reducer;
