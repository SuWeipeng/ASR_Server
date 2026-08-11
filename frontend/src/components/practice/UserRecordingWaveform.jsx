import React, { useEffect, useRef, useState } from 'react';
import { detectPitch, smoothPitch } from '../../utils/audioAnalysis';

/**
 * Analyze a recorded audio blob and render its amplitude waveform and
 * pitch curve, mirroring the style used for the reference sentence.
 */
export const UserRecordingWaveform = ({
  audioBlob,
  currentTime = 0,
  duration = 0,
  className = ''
}) => {
  const canvasRef = useRef(null);
  const [waveformData, setWaveformData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPitch, setShowPitch] = useState(true);
  const [showAmplitude, setShowAmplitude] = useState(true);

  // Decode blob -> compute amplitude (RMS) + pitch per chunk
  useEffect(() => {
    if (!audioBlob) {
      setWaveformData(null);
      return;
    }

    const NUM_POINTS = 300;

    let cancelled = false;

    const analyze = async () => {
      setLoading(true);
      setError(null);

      try {
        const arrayBuffer = await audioBlob.arrayBuffer();
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const audioCtx = new AudioCtx();
        let audioBuffer;
        try {
          audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        } finally {
          audioCtx.close();
        }

        const channelData = audioBuffer.getChannelData(0);
        const sampleRate = audioBuffer.sampleRate;
        const totalSamples = channelData.length;
        const samplesPerPoint = Math.max(1, Math.floor(totalSamples / NUM_POINTS));

        const amplitude = [];
        const rawPitches = [];

        for (let i = 0; i < NUM_POINTS; i++) {
          const start = i * samplesPerPoint;
          const end = Math.min(start + samplesPerPoint, totalSamples);
          const chunk = channelData.subarray(start, end);

          // RMS amplitude
          let sumSq = 0;
          for (let j = 0; j < chunk.length; j++) {
            const v = chunk[j];
            sumSq += v * v;
          }
          amplitude.push(Math.sqrt(sumSq / chunk.length));

          // Pitch (autocorrelation) on a small window
          const PITCH_WINDOW = 1024;
          let pitchWindow;
          if (chunk.length >= PITCH_WINDOW) {
            pitchWindow = new Float32Array(PITCH_WINDOW);
            for (let k = 0; k < PITCH_WINDOW; k++) pitchWindow[k] = chunk[k];
          } else {
            pitchWindow = new Float32Array(chunk.length);
            for (let k = 0; k < chunk.length; k++) pitchWindow[k] = chunk[k];
          }
          const f0 = detectPitch(pitchWindow, sampleRate);
          // Reject clearly nonsensical values (autocorrelation is noisy)
          if (f0 && f0 >= 60 && f0 <= 600) {
            rawPitches.push(f0);
          } else {
            rawPitches.push(null);
          }
        }

        // Normalize amplitude to [0, 1] like the backend does
        const maxAmp = Math.max(...amplitude, 0);
        const normAmp = amplitude.map((a) => (maxAmp > 0 ? a / maxAmp : 0));

        if (cancelled) return;

        setWaveformData({
          amplitude: normAmp,
          pitch: smoothPitch(rawPitches, 5),
        });
      } catch (e) {
        console.error('Failed to decode recording:', e);
        if (!cancelled) setError('解析录音失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    analyze();

    return () => {
      cancelled = true;
    };
  }, [audioBlob]);

  // Draw waveform on canvas
  useEffect(() => {
    if (!waveformData || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const parent = canvas.parentElement;
    if (!parent) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = parent.clientWidth * dpr;
    canvas.height = parent.clientHeight * dpr;
    ctx.scale(dpr, dpr);

    const width = parent.clientWidth;
    const height = parent.clientHeight;

    ctx.clearRect(0, 0, width, height);

    if (showAmplitude && waveformData.amplitude) {
      drawAmplitudeWaveform(ctx, waveformData.amplitude, width, height);
    }
    if (showPitch && waveformData.pitch) {
      drawPitchCurve(ctx, waveformData.pitch, width, height);
    }

    // Draw playback position indicator (progress line + triangle)
    if (duration > 0 && currentTime >= 0) {
      const progress = Math.min(1, Math.max(0, currentTime / duration));
      const xPos = progress * width;

      // Draw vertical line
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 2;
      ctx.moveTo(xPos, 0);
      ctx.lineTo(xPos, height);
      ctx.stroke();

      // Draw triangle marker at top
      ctx.beginPath();
      ctx.fillStyle = 'rgba(239, 68, 68, 1)';
      ctx.moveTo(xPos - 6, 0);
      ctx.lineTo(xPos + 6, 0);
      ctx.lineTo(xPos, 8);
      ctx.closePath();
      ctx.fill();
    }
  }, [waveformData, showAmplitude, showPitch, currentTime, duration]);

  // Redraw on resize
  useEffect(() => {
    const handleResize = () => {
      if (waveformData && canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const parent = canvas.parentElement;
        if (!parent) return;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = parent.clientWidth * dpr;
        canvas.height = parent.clientHeight * dpr;
        ctx.scale(dpr, dpr);

        const width = parent.clientWidth;
        const height = parent.clientHeight;
        ctx.clearRect(0, 0, width, height);

        if (showAmplitude && waveformData.amplitude) {
          drawAmplitudeWaveform(ctx, waveformData.amplitude, width, height);
        }
        if (showPitch && waveformData.pitch) {
          drawPitchCurve(ctx, waveformData.pitch, width, height);
        }

        // Draw playback position indicator on resize
        if (duration > 0 && currentTime >= 0) {
          const progress = Math.min(1, Math.max(0, currentTime / duration));
          const xPos = progress * width;

          ctx.beginPath();
          ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
          ctx.lineWidth = 2;
          ctx.moveTo(xPos, 0);
          ctx.lineTo(xPos, height);
          ctx.stroke();

          ctx.beginPath();
          ctx.fillStyle = 'rgba(239, 68, 68, 1)';
          ctx.moveTo(xPos - 6, 0);
          ctx.lineTo(xPos + 6, 0);
          ctx.lineTo(xPos, 8);
          ctx.closePath();
          ctx.fill();
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [waveformData, showAmplitude, showPitch, currentTime, duration]);

  const drawAmplitudeWaveform = (ctx, amplitude, width, height) => {
    if (!amplitude || amplitude.length === 0) return;

    ctx.beginPath();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = 'rgba(139, 92, 246, 0.8)';
    ctx.fillStyle = 'rgba(139, 92, 246, 0.15)';

    const sliceWidth = width / amplitude.length;
    let x = 0;

    ctx.moveTo(0, height / 2);

    for (let i = 0; i < amplitude.length; i++) {
      const amp = amplitude[i];
      const y = (amp * 0.8 + 1) / 2 * height;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      x += sliceWidth;
    }

    ctx.stroke();
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fill();
  };

  const drawPitchCurve = (ctx, pitch, width, height) => {
    if (!pitch || pitch.length === 0) return;

    const validPitches = pitch.filter((p) => p !== null && p !== undefined);
    if (validPitches.length < 2) return;

    const minPitch = 80;
    const maxPitch = 500;

    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const sliceWidth = width / pitch.length;
    let lastX = null;
    let lastY = null;

    for (let i = 0; i < pitch.length; i++) {
      const p = pitch[i];
      if (p === null || p === undefined) {
        lastX = null;
        lastY = null;
        continue;
      }

      const clampedPitch = Math.max(minPitch, Math.min(maxPitch, p));
      const normalizedPitch = (clampedPitch - minPitch) / (maxPitch - minPitch);
      const y = height - (normalizedPitch * height * 0.7 + height * 0.15);
      const x = i * sliceWidth;

      const hue = 240 - normalizedPitch * 240;
      ctx.strokeStyle = `hsl(${hue}, 70%, 50%)`;

      if (lastX !== null && lastY !== null) {
        ctx.beginPath();
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(x, y);
        ctx.stroke();
      }

      lastX = x;
      lastY = y;
    }
  };

  if (loading) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-sm text-text-secondary">解析录音...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-sm text-text-secondary">{error}</div>
      </div>
    );
  }

  if (!waveformData) {
    return null;
  }

  return (
    <div className={`relative w-full h-full ${className}`}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ opacity: 0.6 }}
      />
      <div className="absolute top-2 right-2 flex gap-2 z-20">
        <button
          onClick={() => setShowAmplitude(!showAmplitude)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            showAmplitude
              ? 'bg-primary text-white'
              : 'bg-bg-card text-text-secondary hover:text-text-primary'
          }`}
        >
          振幅
        </button>
        <button
          onClick={() => setShowPitch(!showPitch)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            showPitch
              ? 'bg-primary text-white'
              : 'bg-bg-card text-text-secondary hover:text-text-primary'
          }`}
        >
          音高
        </button>
      </div>
    </div>
  );
};