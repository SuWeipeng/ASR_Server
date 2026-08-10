import api from './api';

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
   * @param {string} fileId - File ID
   * @returns {string} Media URL
   */
  getMediaUrl: (fileId) => {
    return `/api/media/file/${fileId}`;
  },

  /**
   * Get extracted audio file URL
   * @param {string} fileId - File ID
   * @returns {string} Audio URL
   */
  getAudioUrl: (fileId) => {
    return `/api/media/audio/${fileId}`;
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
