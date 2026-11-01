import api from './api';

// Direct backend URL for media files to bypass Vite proxy
// Vite proxy has issues with large video files (ERR_INVALID_HTTP_RESPONSE)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const mediaService = {
  /**
   * Upload media file
   * @param {File} file - Media file to upload
   * @returns {Promise} Upload response with file_id
   */
  uploadFile: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    // Don't set Content-Type when sending FormData - browser will set it automatically with boundary
    return await api.post('/media/upload', formData);
  },

  /**
   * Get file information
   * @param {string} fileId - File ID
   * @returns {Promise} File information
   */
  getFileInfo: async (fileId) => {
    return await api.get(`/media/info/${fileId}`);
  },

  /**
   * Get media file URL for streaming
   * Uses direct backend URL to bypass Vite proxy (issues with large files)
   * @param {string} fileId - File ID
   * @returns {string} Media URL
   */
  getMediaUrl: (fileId) => {
    return `${API_BASE_URL}/api/media/file/${fileId}`;
  },

  /**
   * Get extracted audio file URL
   * Uses direct backend URL to bypass Vite proxy
   * @param {string} fileId - File ID
   * @returns {string} Audio URL
   */
  getAudioUrl: (fileId) => {
    return `${API_BASE_URL}/api/media/audio/${fileId}`;
  },

  /**
   * Get demucs-separated vocals audio URL
   * Uses direct backend URL (same reason as getMediaUrl)
   * @param {string} fileId - File ID
   * @returns {string} Vocals audio URL
   */
  getVocalsUrl: (fileId) => {
    return `${API_BASE_URL}/api/media/vocals/${fileId}`;
  },

  /**
   * Get subtitle sentence audio clip download URL (MP3)
   * Uses direct backend URL (same reason as getMediaUrl)
   * @param {string} fileId - File ID
   * @param {number} start - Sentence start time (seconds)
   * @param {number} end - Sentence end time (seconds)
   * @param {boolean} useVocals - Cut from demucs-separated vocals when available
   * @param {string} name - Sentence text, used as the download filename
   * @returns {string} Sentence clip URL
   */
  getSentenceUrl: (fileId, start, end, useVocals, name) => {
    const params = new URLSearchParams({
      start: String(start),
      end: String(end),
      use_vocals: String(!!useVocals),
      name: name || '',
    });
    return `${API_BASE_URL}/api/media/sentence/${fileId}?${params.toString()}`;
  },

  /**
   * Delete file
   * @param {string} fileId - File ID
   * @returns {Promise} Delete response
   */
  deleteFile: async (fileId) => {
    return await api.delete(`/media/file/${fileId}`);
  },
};
