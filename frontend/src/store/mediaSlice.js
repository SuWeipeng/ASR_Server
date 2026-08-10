import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { mediaService } from '../services/mediaService';

export const uploadFile = createAsyncThunk(
  'media/uploadFile',
  async (file, { rejectWithValue }) => {
    try {
      console.log('[uploadFile thunk] mediaService:', mediaService);
      console.log('[uploadFile thunk] mediaService.uploadFile:', mediaService.uploadFile);
      console.log('[uploadFile thunk] Type of uploadFile:', typeof mediaService.uploadFile);

      const response = await mediaService.uploadFile(file);
      return response;
    } catch (error) {
      console.error('[uploadFile thunk] Error:', error);
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

export const getFileInfo = createAsyncThunk(
  'media/getFileInfo',
  async (fileId, { rejectWithValue }) => {
    try {
      const response = await mediaService.getFileInfo(fileId);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data || error.message);
    }
  }
);

const initialState = {
  currentFile: null,
  fileId: null,
  filename: '',
  fileType: null,
  duration: 0,
  fileSize: 0,
  isProcessing: false,
  error: null,
};

const mediaSlice = createSlice({
  name: 'media',
  initialState,
  reducers: {
    clearMedia: (state) => {
      state.currentFile = null;
      state.fileId = null;
      state.filename = '';
      state.fileType = null;
      state.duration = 0;
      state.fileSize = 0;
      state.error = null;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Upload file
      .addCase(uploadFile.pending, (state) => {
        state.isProcessing = true;
        state.error = null;
      })
      .addCase(uploadFile.fulfilled, (state, action) => {
        state.isProcessing = false;
        state.fileId = action.payload.file_id;
        state.filename = action.payload.filename;
        state.fileType = action.payload.file_type;
        state.duration = action.payload.duration || 0;
        state.fileSize = action.payload.file_size;
        state.error = null;
      })
      .addCase(uploadFile.rejected, (state, action) => {
        state.isProcessing = false;
        state.error = action.payload || 'Failed to upload file';
      })
      // Get file info
      .addCase(getFileInfo.fulfilled, (state, action) => {
        state.fileId = action.payload.file_id;
        state.filename = action.payload.filename;
        state.fileType = action.payload.file_type;
        state.duration = action.payload.duration || 0;
        state.fileSize = action.payload.file_size;
      });
  },
});

export const { clearMedia, clearError } = mediaSlice.actions;
export default mediaSlice.reducer;
