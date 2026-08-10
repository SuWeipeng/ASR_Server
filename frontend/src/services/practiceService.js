import api from './api';

export const practiceService = {
  /**
   * Evaluate user pronunciation
   * @param {Blob} audioBlob - User audio recording as blob
   * @param {string} targetText - Target text to compare against
   * @returns {Promise} Evaluation response
   */
  evaluateSpeech: async (audioBlob, targetText) => {
    const formData = new FormData();
    const mimeType = audioBlob.type || 'audio/webm';
    const ext = mimeType.includes('ogg')
      ? 'ogg'
      : mimeType.includes('mp4')
        ? 'mp4'
        : mimeType.includes('wav')
          ? 'wav'
          : 'webm';
    formData.append('audio', audioBlob, `recording.${ext}`);
    formData.append('target_text', targetText);

    return await api.post('/practice/evaluate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 1 minute
    });
  },

  /**
   * Quick text-to-text comparison (no audio)
   * @param {string} userText - User's text
   * @param {string} targetText - Target text
   * @returns {Promise} Score response
   */
  quickScore: async (userText, targetText) => {
    const formData = new FormData();
    formData.append('user_text', userText);
    formData.append('target_text', targetText);

    return await api.post('/practice/quick-score', formData);
  },

  /**
   * Check practice service health
   * @returns {Promise} Health status
   */
  checkHealth: async () => {
    return await api.get('/practice/health');
  },
};
