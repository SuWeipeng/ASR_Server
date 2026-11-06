import api from './api';

export const transcriptionService = {
  /**
   * Generate subtitles from media file
   * @param {string} fileId - File ID
   * @param {string} language - Language code (default: 'English')
   * @param {boolean} forceRefresh - Force regeneration, skip cache (default: false)
   * @returns {Promise} Subtitle generation response
   */
  generateSubtitles: async (fileId, language = 'auto', forceRefresh = false) => {
    return await api.post('/transcription/generate', {
      file_id: fileId,
      language: language,
      generate_timestamps: true,
      force_refresh: forceRefresh,
    }, {
      // demucs 分离 + VAD + ASR 在长视频上很容易超过全局 5 分钟超时
      timeout: 30 * 60 * 1000,
    });
  },

  /**
   * 对已有缓存轻量重跑字幕同步修复（不重跑 demucs/ASR，分钟级）
   * @param {string} fileId - File ID
   * @returns {Promise} 修复后的完整字幕响应（与 generate 同构）
   */
  repairSubtitles: async (fileId) => {
    return await api.post(`/transcription/repair/${fileId}`, {}, {
      // 修复含批量 ASR 重探测，长视频可能跑数分钟
      timeout: 30 * 60 * 1000,
    });
  },

  /**
   * Get cached subtitles
   * @param {string} fileId - File ID
   * @returns {Promise} Subtitles response
   */
  getSubtitles: async (fileId) => {
    return await api.get(`/transcription/subtitles/${fileId}`);
  },

  /**
   * Search within subtitles
   * @param {string} fileId - File ID
   * @param {string} query - Search query
   * @returns {Promise} Search results
   */
  searchSubtitles: async (fileId, query) => {
    return await api.post(`/transcription/search/${fileId}`, {
      query: query,
      search_translations: false,
    });
  },

  /**
   * Export subtitles
   * @param {string} fileId - File ID
   * @param {string} format - Format ('srt' or 'vtt')
   * @returns {Promise} Export response
   */
  exportSubtitles: async (fileId, format = 'srt') => {
    return await api.get(`/transcription/export/${fileId}?format=${format}`, {
      responseType: 'blob',
    });
  },

  /**
   * Check if file has cached subtitles
   * @param {string} fileId - File ID
   * @returns {Promise} Cache status response
   */
  checkCacheStatus: async (fileId) => {
    return await api.get(`/transcription/cache/check/${fileId}`);
  },

  /**
   * Load cached subtitles
   * @param {string} fileId - File ID
   * @returns {Promise} Cached subtitles response
   */
  loadCachedSubtitles: async (fileId) => {
    return await api.get(`/transcription/cache/load/${fileId}`);
  },
};
