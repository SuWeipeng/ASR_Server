import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { transcriptionService } from '../services/transcriptionService';

export const generateSubtitles = createAsyncThunk(
  'subtitle/generateSubtitles',
  async ({ fileId, language = 'auto', forceRefresh = false }, { rejectWithValue }) => {
    try {
      const response = await transcriptionService.generateSubtitles(fileId, language, forceRefresh);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getSubtitles = createAsyncThunk(
  'subtitle/getSubtitles',
  async (fileId, { rejectWithValue }) => {
    try {
      const response = await transcriptionService.getSubtitles(fileId);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const searchSubtitles = createAsyncThunk(
  'subtitle/searchSubtitles',
  async ({ fileId, query }, { rejectWithValue }) => {
    try {
      const response = await transcriptionService.searchSubtitles(fileId, query);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const loadCachedSubtitles = createAsyncThunk(
  'subtitle/loadCachedSubtitles',
  async (fileId, { rejectWithValue }) => {
    try {
      const response = await transcriptionService.loadCachedSubtitles(fileId);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

const initialState = {
  subtitles: [],
  filteredSubtitles: [],
  currentSubtitleIndex: -1,
  searchQuery: '',
  showTranslation: false,
  isLoading: false,
  error: null,
  fromCache: false,  // 标记字幕是否来自缓存
  // Increment to request a seek to the subtitle at seekToIndex
  seekRequest: { index: -1, token: 0 },
};

const subtitleSlice = createSlice({
  name: 'subtitle',
  initialState,
  reducers: {
    setCurrentSubtitleIndex: (state, action) => {
      state.currentSubtitleIndex = action.payload;
    },
    requestSeekToSubtitle: (state, action) => {
      state.seekRequest = {
        index: action.payload,
        token: state.seekRequest.token + 1,
      };
    },
    setSearchQuery: (state, action) => {
      state.searchQuery = action.payload;
      // Filter subtitles based on search query
      if (action.payload.trim() === '') {
        state.filteredSubtitles = state.subtitles;
      } else {
        const query = action.payload.toLowerCase();
        state.filteredSubtitles = state.subtitles.filter(sub =>
          sub.text.toLowerCase().includes(query)
        );
      }
    },
    toggleTranslation: (state) => {
      state.showTranslation = !state.showTranslation;
    },
    clearSubtitles: (state) => {
      state.subtitles = [];
      state.filteredSubtitles = [];
      state.currentSubtitleIndex = -1;
      state.searchQuery = '';
      state.fromCache = false;
      state.error = null;
    },
    clearError: (state) => {
      state.error = null;
    },
    clearSeekRequest: (state) => {
      state.seekRequest = { index: -1, token: 0 };
    },
  },
  extraReducers: (builder) => {
    builder
      // Generate subtitles
      .addCase(generateSubtitles.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(generateSubtitles.fulfilled, (state, action) => {
        state.isLoading = false;
        state.subtitles = action.payload.segments;
        state.filteredSubtitles = action.payload.segments;
        state.currentSubtitleIndex = -1;
        state.error = null;
      })
      .addCase(generateSubtitles.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload || 'Failed to generate subtitles';
      })
      // Get subtitles
      .addCase(getSubtitles.fulfilled, (state, action) => {
        state.subtitles = action.payload.segments;
        state.filteredSubtitles = action.payload.segments;
      })
      // Search subtitles
      .addCase(searchSubtitles.fulfilled, (state, action) => {
        state.filteredSubtitles = action.payload.results;
      })
      // Load cached subtitles
      .addCase(loadCachedSubtitles.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(loadCachedSubtitles.fulfilled, (state, action) => {
        state.isLoading = false;
        state.subtitles = action.payload.segments;
        state.filteredSubtitles = action.payload.segments;
        state.currentSubtitleIndex = -1;
        state.fromCache = true;  // 标记来自缓存
        state.error = null;
      })
      .addCase(loadCachedSubtitles.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload || 'Failed to load cached subtitles';
      });
  },
});

export const {
  setCurrentSubtitleIndex,
  requestSeekToSubtitle,
  setSearchQuery,
  toggleTranslation,
  clearSubtitles,
  clearError,
  clearSeekRequest,
} = subtitleSlice.actions;

export default subtitleSlice.reducer;
