import { configureStore } from '@reduxjs/toolkit';
import mediaReducer from './mediaSlice';
import subtitleReducer from './subtitleSlice';
import playerReducer from './playerSlice';
import practiceReducer from './practiceSlice';
import uiReducer from './uiSlice';

export const store = configureStore({
  reducer: {
    media: mediaReducer,
    subtitle: subtitleReducer,
    player: playerReducer,
    practice: practiceReducer,
    ui: uiReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['media/uploadFile/fulfilled'],
        // Ignore these paths in the state
        ignoredPaths: ['media.currentFile', 'practice.userAudioBlob'],
      },
    }),
});

// Persist selected microphone deviceId and micNoiseConfig across reloads
let lastPersistedMicId =
  (() => {
    try {
      return localStorage.getItem('selectedMicDeviceId') || null;
    } catch {
      return null;
    }
  })();

let lastPersistedMicNoiseConfig =
  (() => {
    try {
      return JSON.stringify(store.getState().ui.micNoiseConfig);
    } catch {
      return null;
    }
  })();

store.subscribe(() => {
  const state = store.getState().ui;

  // Persist mic device ID
  const micId = state.selectedMicDeviceId || null;
  if (micId !== lastPersistedMicId) {
    try {
      if (micId) localStorage.setItem('selectedMicDeviceId', micId);
      else localStorage.removeItem('selectedMicDeviceId');
    } catch {
      // ignore (e.g. storage disabled)
    }
    lastPersistedMicId = micId;
  }

  // Persist mic noise config
  const micNoiseConfigStr = JSON.stringify(state.micNoiseConfig);
  if (micNoiseConfigStr !== lastPersistedMicNoiseConfig) {
    try {
      localStorage.setItem('micNoiseConfig', micNoiseConfigStr);
    } catch {
      // ignore (e.g. storage disabled)
    }
    lastPersistedMicNoiseConfig = micNoiseConfigStr;
  }
});

export default store;
