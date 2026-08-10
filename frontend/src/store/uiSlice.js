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
  async (config, { rejectWithValue, dispatch, getState }) => {
    try {
      const response = await systemService.updateVADConfig(config);

      // 更新成功后，如果有当前文件，强制刷新字幕（跳过缓存）
      const fileId = getState().media.fileId;
      if (fileId) {
        // 动态导入 subtitleSlice 避免循环依赖
        const { generateSubtitles } = await import('../store/subtitleSlice');
        await dispatch(generateSubtitles({ fileId, forceRefresh: true }));
      }

      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

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
  systemStatus: null,
  vadConfig: null,
  vadConfigLoading: false,
  vadConfigError: null,
};

function getInitialMicDeviceId() {
  try {
    return localStorage.getItem('selectedMicDeviceId') || null;
  } catch {
    return null;
  }
}

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
} = uiSlice.actions;

export default uiSlice.reducer;
