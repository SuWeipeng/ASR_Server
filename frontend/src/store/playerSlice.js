import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  playbackRate: 1.0,
  loopMode: false,        // Single sentence loop
  loopStart: null,
  loopEnd: null,
  volume: 1.0,
  isMuted: false,
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
    setPlaybackRate: (state, action) => {
      state.playbackRate = action.payload;
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
  },
});

export const {
  setPlaying,
  setCurrentTime,
  setDuration,
  setPlaybackRate,
  setLoopMode,
  setLoopRange,
  clearLoopRange,
  setVolume,
  setMuted,
  togglePlay,
  toggleLoop,
  toggleMute,
} = playerSlice.actions;

export default playerSlice.reducer;
