import api from './api';

export const systemService = {
  /**
   * Get system status
   * @returns {Promise} System status information
   */
  getStatus: async () => {
    return await api.get('/system/status');
  },

  /**
   * Health check
   * @returns {Promise} Health status
   */
  healthCheck: async () => {
    return await api.get('/system/health');
  },

  /**
   * Initialize system
   * @returns {Promise} Initialization response
   */
  initialize: async () => {
    return await api.post('/system/initialize');
  },

  /**
   * Get system configuration
   * @returns {Promise} Configuration
   */
  getConfig: async () => {
    return await api.get('/system/config');
  },

  /**
   * Get VAD configuration
   * @returns {Promise} VAD configuration
   */
  getVADConfig: async () => {
    return await api.get('/vad/config');
  },

  /**
   * Update VAD configuration
   * @param {Object} config - VAD configuration updates
   * @returns {Promise} Updated VAD configuration
   */
  updateVADConfig: async (config) => {
    return await api.put('/vad/config', config);
  },

  /**
   * Reset VAD configuration to defaults
   * @returns {Promise} Reset VAD configuration
   */
  resetVADConfig: async () => {
    return await api.post('/vad/config/reset');
  },

  /**
   * Get noise reduction configuration
   * @returns {Promise} Noise reduction configuration
   */
  getNoiseConfig: async () => {
    return await api.get('/noise/config');
  },

  /**
   * Update noise reduction configuration
   * @param {Object} config - Noise reduction configuration updates
   * @returns {Promise} Updated noise reduction configuration
   */
  updateNoiseConfig: async (config) => {
    return await api.put('/noise/config', config);
  },

  /**
   * Reset noise reduction configuration to defaults
   * @returns {Promise} Reset noise reduction configuration
   */
  resetNoiseConfig: async () => {
    return await api.post('/noise/config/reset');
  },
};
