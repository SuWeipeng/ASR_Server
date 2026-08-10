import api from './api';

export const dictionaryService = {
  /**
   * Look up word definition
   * @param {string} word - Word to look up
   * @returns {Promise} Dictionary entry
   */
  lookupWord: async (word) => {
    return await api.get(`/dictionary/lookup/${word}`);
  },

  /**
   * Check if dictionary service is available
   * @returns {Promise} Availability status
   */
  checkAvailable: async () => {
    return await api.get('/dictionary/available');
  },
};
