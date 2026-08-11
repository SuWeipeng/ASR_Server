import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { practiceService } from '../services/practiceService';

export const evaluateSpeech = createAsyncThunk(
  'practice/evaluateSpeech',
  async ({ audioBlob, targetText }, { rejectWithValue }) => {
    try {
      const response = await practiceService.evaluateSpeech(audioBlob, targetText);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

const initialState = {
  isRecording: false,
  isProcessing: false,
  currentSentence: null,
  lastScore: null,
  diffResult: null,
  userAudioBlob: null,
  audioUrl: null,
  audioDuration: 0,  // Duration for progress tracking
  error: null,
};

const practiceSlice = createSlice({
  name: 'practice',
  initialState,
  reducers: {
    setRecording: (state, action) => {
      state.isRecording = action.payload;
    },
    setCurrentSentence: (state, action) => {
      state.currentSentence = action.payload;
    },
    setUserAudio: (state, action) => {
      state.userAudioBlob = action.payload.blob;
      state.audioUrl = action.payload.url;
    },
    clearUserAudio: (state) => {
      state.userAudioBlob = null;
      if (state.audioUrl) {
        URL.revokeObjectURL(state.audioUrl);
        state.audioUrl = null;
      }
    },
    clearPractice: (state) => {
      state.lastScore = null;
      state.diffResult = null;
      state.error = null;
      state.isProcessing = false;  // Also clear processing state
    },
    clearError: (state) => {
      state.error = null;
    },
    setAudioDuration: (state, action) => {
      state.audioDuration = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Evaluate speech
      .addCase(evaluateSpeech.pending, (state) => {
        state.isProcessing = true;
        state.error = null;
      })
      .addCase(evaluateSpeech.fulfilled, (state, action) => {
        state.isProcessing = false;
        state.lastScore = {
          score: action.payload.score,
          accuracy_level: action.payload.accuracy_level,
          user_transcript: action.payload.user_transcript,
        };
        state.diffResult = action.payload.diff_words.map(dw => ({
          word: dw.word,
          status: dw.status,
          original_index: dw.original_index,
          user_index: dw.user_index,
          start: dw.start,  // Word start timestamp for sync
          end: dw.end       // Word end timestamp for sync
        }));
        state.error = null;
      })
      .addCase(evaluateSpeech.rejected, (state, action) => {
        state.isProcessing = false;
        state.error = action.payload || 'Failed to evaluate speech';
      });
  },
});

export const {
  setRecording,
  setCurrentSentence,
  setUserAudio,
  clearUserAudio,
  clearPractice,
  clearError,
  setAudioDuration,
} = practiceSlice.actions;

export default practiceSlice.reducer;
