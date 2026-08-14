/**
 * Audio Filter Utilities
 *
 * Implements Butterworth-style filters using WebAudio API's BiquadFilterNode.
 * High-order filters are created by cascading multiple biquad sections.
 *
 * Q values are pre-calculated to match scipy.signal.butter behavior:
 * - 2nd order: 0.707
 * - 4th order: 0.541, 1.306
 * - 6th order: 0.518, 0.707, 1.932
 * - 8th order: 0.509, 0.601, 0.900, 2.563
 */

/**
 * Q values for Butterworth filter sections
 * Based on scipy.signal.butter implementation
 */
const Q_VALUES = {
  2: [0.707],
  4: [0.541, 1.306],
  6: [0.518, 0.707, 1.932],
  8: [0.509, 0.601, 0.900, 2.563]
};

/**
 * Get Q values for a given filter order
 * @param {number} order - Filter order (1-8)
 * @returns {number[]} Array of Q values for each biquad section
 */
export function getQValues(order) {
  // Clamp order to 1-8
  const clampedOrder = Math.max(1, Math.min(8, order));
  return Q_VALUES[clampedOrder] || [0.707];
}

/**
 * Create a single highpass filter section
 * @param {AudioContext} ctx - WebAudio Context
 * @param {number} frequency - Cutoff frequency in Hz
 * @param {number} Q - Q value for this section
 * @returns {BiquadFilterNode} The created filter node
 */
function createHighpassSection(ctx, frequency, Q) {
  const filter = ctx.createBiquadFilter();
  filter.type = 'highpass';
  filter.frequency.value = frequency;
  filter.Q.value = Q;
  return filter;
}

/**
 * Create a single lowpass filter section
 * @param {AudioContext} ctx - WebAudio Context
 * @param {number} frequency - Cutoff frequency in Hz
 * @param {number} Q - Q value for this section
 * @returns {BiquadFilterNode} The created filter node
 */
function createLowpassSection(ctx, frequency, Q) {
  const filter = ctx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.value = frequency;
  filter.Q.value = Q;
  return filter;
}

/**
 * Create a highpass filter chain (Nth order)
 * @param {AudioContext} ctx - WebAudio Context
 * @param {number} frequency - Cutoff frequency in Hz
 * @param {number} order - Filter order (1-8)
 * @returns {BiquadFilterNode[]} Array of filter nodes
 */
export function createHighpassFilterChain(ctx, frequency, order) {
  const qValues = getQValues(order);
  return qValues.map(Q => createHighpassSection(ctx, frequency, Q));
}

/**
 * Create a lowpass filter chain (Nth order)
 * @param {AudioContext} ctx - WebAudio Context
 * @param {number} frequency - Cutoff frequency in Hz
 * @param {number} order - Filter order (1-8)
 * @returns {BiquadFilterNode[]} Array of filter nodes
 */
export function createLowpassFilterChain(ctx, frequency, order) {
  const qValues = getQValues(order);
  return qValues.map(Q => createLowpassSection(ctx, frequency, Q));
}

/**
 * Create a bandpass filter chain (Nth order)
 * Bandpass is implemented as highpass followed by lowpass
 * Each is Nth order, so total sections = 2 * (N/2)
 * @param {AudioContext} ctx - WebAudio Context
 * @param {number} lowcut - Low cutoff frequency in Hz
 * @param {number} highcut - High cutoff frequency in Hz
 * @param {number} order - Filter order per section (1-8)
 * @returns {BiquadFilterNode[]} Array of filter nodes
 */
export function createBandpassFilterChain(ctx, lowcut, highcut, order) {
  const highpassFilters = createHighpassFilterChain(ctx, lowcut, order);
  const lowpassFilters = createLowpassFilterChain(ctx, highcut, order);
  return [...highpassFilters, ...lowpassFilters];
}

/**
 * Create a noise reduction filter chain based on configuration
 * @param {AudioContext} ctx - WebAudio Context
 * @param {Object} config - Noise reduction configuration
 * @param {boolean} config.enabled - Whether noise reduction is enabled
 * @param {number} config.lowcut - Low cutoff frequency in Hz
 * @param {number} config.highcut - High cutoff frequency in Hz
 * @param {number} config.order - Filter order (1-8)
 * @param {string} config.filter_type - 'bandpass', 'highpass', or 'lowpass'
 * @param {boolean} config.normalize_after_filter - Whether to normalize after filtering
 * @returns {Object} Object containing filter nodes array and optional gain node
 */
export function createNoiseFilterChain(ctx, config) {
  if (!config || !config.enabled) {
    return { filters: [], gainNode: null };
  }

  let filters = [];
  const { lowcut, highcut, order, filter_type } = config;

  switch (filter_type) {
    case 'highpass':
      filters = createHighpassFilterChain(ctx, lowcut, order);
      break;
    case 'lowpass':
      filters = createLowpassFilterChain(ctx, highcut, order);
      break;
    case 'bandpass':
    default:
      filters = createBandpassFilterChain(ctx, lowcut, highcut, order);
      break;
  }

  // Add gain node for normalization if enabled
  let gainNode = null;
  if (config.normalize_after_filter) {
    gainNode = ctx.createGain();
    // Start with 1.0 gain, can be adjusted based on analysis
    gainNode.gain.value = 1.0;
  }

  return { filters, gainNode };
}

/**
 * Connect a source through a filter chain to destination
 * @param {AudioNode} source - Source audio node
 * @param {AudioNode} destination - Destination audio node
 * @param {BiquadFilterNode[]} filters - Array of filter nodes
 * @param {GainNode|null} gainNode - Optional gain node
 */
export function connectFilterChain(source, destination, filters, gainNode = null) {
  let currentNode = source;

  // Connect through all filters
  filters.forEach(filter => {
    currentNode.connect(filter);
    currentNode = filter;
  });

  // Connect through gain node if present
  if (gainNode) {
    currentNode.connect(gainNode);
    currentNode = gainNode;
  }

  // Connect to destination
  currentNode.connect(destination);
}

/**
 * Disconnect and clean up a filter chain
 * @param {BiquadFilterNode[]} filters - Array of filter nodes
 * @param {GainNode|null} gainNode - Optional gain node
 */
export function disconnectFilterChain(filters, gainNode = null) {
  filters.forEach(filter => {
    try {
      filter.disconnect();
    } catch (e) {
      // Ignore if already disconnected
    }
  });

  if (gainNode) {
    try {
      gainNode.disconnect();
    } catch (e) {
      // Ignore if already disconnected
    }
  }
}
