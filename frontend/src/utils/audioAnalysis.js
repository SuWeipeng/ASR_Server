/**
 * Audio analysis utilities for pitch detection and waveform visualization
 */

/**
 * Detect pitch using autocorrelation algorithm
 * @param {Float32Array} buffer - Audio buffer data
 * @param {number} sampleRate - Audio sample rate
 * @returns {number|null} - Detected pitch in Hz, or null if no pitch detected
 */
export function detectPitch(buffer, sampleRate) {
  // Autocorrelation algorithm for pitch detection
  const SIZE = buffer.length;
  let rms = 0;

  // Calculate RMS (Root Mean Square) to determine if there's enough signal
  for (let i = 0; i < SIZE; i++) {
    const val = buffer[i];
    rms += val * val;
  }
  rms = Math.sqrt(rms / SIZE);

  // Signal too weak - no pitch detected
  if (rms < 0.01) return null;

  // Autocorrelation
  let r1 = 0, r2 = SIZE - 1;
  const threshold = 0.2;

  for (let i = 0; i < SIZE / 2; i++) {
    if (Math.abs(buffer[i]) < threshold) { r1 = i; break; }
  }
  for (let i = 1; i < SIZE / 2; i++) {
    if (Math.abs(buffer[SIZE - i]) < threshold) { r2 = SIZE - i; break; }
  }

  const buf = buffer.slice(r1, r2);
  const c = new Array(buf.length).fill(0);

  for (let i = 0; i < buf.length; i++) {
    for (let j = 0; j < buf.length - i; j++) {
      c[i] = c[i] + buf[j] * buf[j + i];
    }
  }

  let d = 0;
  while (c[d] > c[d + 1]) d++;
  let maxval = -1, maxpos = -1;

  for (let i = d; i < buf.length; i++) {
    if (c[i] > maxval) {
      maxval = c[i];
      maxpos = i;
    }
  }

  let T0 = maxpos;

  // Parabolic interpolation for better precision
  const x1 = c[T0 - 1], x2 = c[T0], x3 = c[T0 + 1];
  const a = (x1 + x3 - 2 * x2) / 2;
  const b = (x3 - x1) / 2;

  if (a) T0 = T0 - b / (2 * a);

  return sampleRate / T0;
}

/**
 * Smooth pitch values to reduce jitter
 * @param {Array<number>} pitches - Array of pitch values
 * @param {number} windowSize - Smoothing window size
 * @returns {Array<number>} - Smoothed pitch values
 */
export function smoothPitch(pitches, windowSize = 5) {
  const smoothed = [];
  const halfWindow = Math.floor(windowSize / 2);

  for (let i = 0; i < pitches.length; i++) {
    let sum = 0;
    let count = 0;

    for (let j = Math.max(0, i - halfWindow); j <= Math.min(pitches.length - 1, i + halfWindow); j++) {
      if (pitches[j] !== null) {
        sum += pitches[j];
        count++;
      }
    }

    smoothed[i] = count > 0 ? sum / count : null;
  }

  return smoothed;
}

/**
 * Convert frequency to musical note
 * @param {number} frequency - Frequency in Hz
 * @returns {string} - Musical note name
 */
export function frequencyToNote(frequency) {
  const noteStrings = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const pitch = 12 * (Math.log2(frequency / 440));
  const noteIndex = Math.round(pitch) + 69;
  const octave = Math.floor(noteIndex / 12) - 1;
  const noteName = noteStrings[noteIndex % 12];

  return `${noteName}${octave}`;
}

/**
 * Get color based on pitch/frequency
 * @param {number} frequency - Frequency in Hz
 * @param {number} minFreq - Minimum frequency range
 * @param {number} maxFreq - Maximum frequency range
 * @returns {string} - CSS color value
 */
export function getPitchColor(frequency, minFreq = 80, maxFreq = 400) {
  // Map frequency to hue (blue = low pitch, red = high pitch)
  const normalized = Math.max(0, Math.min(1, (frequency - minFreq) / (maxFreq - minFreq)));
  const hue = 240 - normalized * 240; // 240 (blue) to 0 (red)
  return `hsl(${hue}, 70%, 50%)`;
}

/**
 * Calculate amplitude from audio buffer
 * @param {Float32Array} data - Audio data
 * @returns {number} - Amplitude value (0-1)
 */
export function calculateAmplitude(data) {
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    sum += Math.abs(data[i]);
  }
  return sum / data.length;
}

/**
 * Get amplitude color based on intensity
 * @param {number} amplitude - Amplitude value (0-1)
 * @returns {string} - CSS color value
 */
export function getAmplitudeColor(amplitude) {
  // Map amplitude to color (dark blue to bright pink)
  const intensity = Math.min(1, amplitude * 3); // Amplify for better visualization
  const lightness = 30 + intensity * 50; // 30% to 80% lightness
  return `hsl(260, 70%, ${lightness}%)`;
}
