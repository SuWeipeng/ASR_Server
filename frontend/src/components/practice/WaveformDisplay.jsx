import React, { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import api from '../../services/api';

/**
 * WaveformDisplay component - Displays pre-generated waveform data
 * Shows amplitude waveform and pitch curve without interfering with video playback
 */
export const WaveformDisplay = ({ fileId, startTime, endTime, className = '' }) => {
  const canvasRef = useRef(null);
  const [waveformData, setWaveformData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPitch, setShowPitch] = useState(true);
  const [showAmplitude, setShowAmplitude] = useState(true);

  // Get current playback time for position indicator
  const currentTime = useSelector((state) => state.player.currentTime);

  // Fetch waveform data when fileId or time range changes
  useEffect(() => {
    if (!fileId || !startTime) return;

    const fetchWaveform = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.get(`/media/waveform/${fileId}`, {
          params: {
            start_time: startTime,
            end_time: endTime,
            num_points: 500
          }
        });

        if (response.success) {
          setWaveformData(response.waveform);
        }
      } catch (err) {
        console.error('Failed to fetch waveform data:', err);
        setError('Failed to load waveform');
      } finally {
        setLoading(false);
      }
    };

    fetchWaveform();
  }, [fileId, startTime, endTime]);

  // Draw waveform on canvas when data is available
  useEffect(() => {
    if (!waveformData || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const parent = canvas.parentElement;

    if (!parent) return;

    // Set canvas size
    const dpr = window.devicePixelRatio || 1;
    canvas.width = parent.clientWidth * dpr;
    canvas.height = parent.clientHeight * dpr;
    ctx.scale(dpr, dpr);

    const width = parent.clientWidth;
    const height = parent.clientHeight;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw amplitude waveform
    if (showAmplitude && waveformData.amplitude) {
      drawAmplitudeWaveform(ctx, waveformData.amplitude, width, height);
    }

    // Draw pitch curve
    if (showPitch && waveformData.pitch) {
      drawPitchCurve(ctx, waveformData.pitch, width, height);
    }

    // Draw playback position indicator
    if (currentTime >= startTime && endTime) {
      const progress = (currentTime - startTime) / (endTime - startTime);
      const xPos = progress * width;

      // Draw vertical line
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)'; // Red
      ctx.lineWidth = 2;
      ctx.moveTo(xPos, 0);
      ctx.lineTo(xPos, height);
      ctx.stroke();

      // Draw small triangle at top
      ctx.beginPath();
      ctx.fillStyle = 'rgba(239, 68, 68, 1)';
      ctx.moveTo(xPos - 6, 0);
      ctx.lineTo(xPos + 6, 0);
      ctx.lineTo(xPos, 8);
      ctx.closePath();
      ctx.fill();
    }
  }, [waveformData, showAmplitude, showPitch, currentTime, startTime, endTime]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (waveformData && canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const parent = canvas.parentElement;

        if (parent) {
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

          // Draw playback position indicator
          if (currentTime >= startTime && endTime) {
            const progress = (currentTime - startTime) / (endTime - startTime);
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
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [waveformData, showAmplitude, showPitch, currentTime, startTime, endTime]);

  const drawAmplitudeWaveform = (ctx, amplitude, width, height) => {
    if (!amplitude || amplitude.length === 0) return;

    ctx.beginPath();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = 'rgba(139, 92, 246, 0.8)'; // Purple
    ctx.fillStyle = 'rgba(139, 92, 246, 0.15)'; // Light purple fill

    const sliceWidth = width / amplitude.length;
    let x = 0;

    // Draw the waveform
    ctx.moveTo(0, height / 2);

    for (let i = 0; i < amplitude.length; i++) {
      const amp = amplitude[i];
      const y = (amp * 0.8 + 1) / 2 * height; // Scale to 80% of height

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }

      x += sliceWidth;
    }

    ctx.stroke();

    // Fill bottom area
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fill();
  };

  const drawPitchCurve = (ctx, pitch, width, height) => {
    if (!pitch || pitch.length === 0) return;

    // Filter out null values and get valid range
    const validPitches = pitch.filter(p => p !== null && p !== undefined);
    if (validPitches.length < 2) return;

    const minPitch = 80;  // Hz
    const maxPitch = 500; // Hz

    ctx.beginPath();
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

      // Clamp pitch to reasonable range
      const clampedPitch = Math.max(minPitch, Math.min(maxPitch, p));

      // Map pitch to Y position (low pitch = bottom, high pitch = top)
      const normalizedPitch = (clampedPitch - minPitch) / (maxPitch - minPitch);
      const y = height - (normalizedPitch * height * 0.7 + height * 0.15);

      const x = i * sliceWidth;

      // Color based on pitch (blue = low, red = high)
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
      <div className={`flex items-center justify-center ${className}`}>
        <div className="text-sm text-text-secondary">加载波形...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
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

      {/* Toggle controls */}
      <div className="absolute top-2 right-2 flex gap-2 z-20">
        <button
          onClick={() => setShowAmplitude(!showAmplitude)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            showAmplitude
              ? 'bg-primary text-white'
              : 'bg-bg-card text-text-secondary hover:text-text-primary'
          }`}
          title="Toggle amplitude waveform"
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
          title="Toggle pitch curve"
        >
          音高
        </button>
      </div>
    </div>
  );
};
