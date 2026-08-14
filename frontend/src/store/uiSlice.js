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

export default uiSlice.reducer;
