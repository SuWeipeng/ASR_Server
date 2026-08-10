import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  isPlaying: false,
  currentTime: 0,
  intentTime: 0,          // User's intended playback position (from seeking/subtitle click)
  singleSentenceMode: false,  // When true, auto-pause after current sentence ends
  singleSentenceEnd: null,    // The end time of the single sentence being played
  duration: 0,
  loopMode: false,        // Single sentence loop
  loopStart: null,
  loopEnd: null,
  volume: 1.0,
  isMuted: false,
  isSeeking: false,       // True while user is dragging the progress bar
  playbackRate: 1.0,      // Playback speed multiplier (0.5 / 0.75 / 1.0 / 1.25)
};

const playerSlice = createSlice({
  name: 'player',
  initialState,
  reducers: {
    setPlaying: (state, action) => {
      state.isPlaying = action.payload;
    },
    setCurrentTime: (state, action) => {
      state.currentTime = action.payload;
    },
    setDuration: (state, action) => {
      state.duration = action.payload;
    },
    setLoopMode: (state, action) => {
      state.loopMode = action.payload;
    },
    setLoopRange: (state, action) => {
      state.loopStart = action.payload.start;
      state.loopEnd = action.payload.end;
    },
    clearLoopRange: (state) => {
      state.loopStart = null;
      state.loopEnd = null;
    },
    setVolume: (state, action) => {
      state.volume = action.payload;
    },
    setMuted: (state, action) => {
      state.isMuted = action.payload;
    },
    togglePlay: (state) => {
      state.isPlaying = !state.isPlaying;
    },
    toggleLoop: (state) => {
      state.loopMode = !state.loopMode;
    },
    toggleMute: (state) => {
      state.isMuted = !state.isMuted;
    },
    setSeeking: (state, action) => {
      state.isSeeking = action.payload;
    },
    setIntentTime: (state, action) => {
      state.intentTime = action.payload;
      state.currentTime = action.payload; // Keep currentTime in sync for compatibility
    },
    setSingleSentenceMode: (state, action) => {
      state.singleSentenceMode = action.payload.mode;
      state.singleSentenceEnd = action.payload.endTime || null;
    },
    setPlaybackRate: (state, action) => {
      const rate = action.payload;
      if ([0.5, 0.75, 1.0, 1.25].includes(rate)) {
        state.playbackRate = rate;
      }
    },
  },
});

export const {
  setPlaying,
  setCurrentTime,
  setIntentTime,
  setSingleSentenceMode,
  setDuration,
  setLoopMode,
  setLoopRange,
  clearLoopRange,
  setVolume,
  setMuted,
  togglePlay,
  toggleLoop,
  toggleMute,
  setSeeking,
  setPlaybackRate,
} = playerSlice.actions;

export default playerSlice.reducer;
