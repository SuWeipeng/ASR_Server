import { useState, useRef, useCallback } from 'react';

/**
 * Custom hook for media recording functionality
 * @param {string|null} deviceId - Optional audio input deviceId to record from
 * @returns {Object} Recording state and controls
 */
export const useMediaRecorder = (deviceId = null) => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const deviceIdRef = useRef(deviceId);
  deviceIdRef.current = deviceId;

  /**
   * Start recording
   */
  const startRecording = useCallback(async () => {
    try {
      const audioConstraints = deviceIdRef.current
        ? { deviceId: { exact: deviceIdRef.current } }
        : true;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints,
      });

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);

        // Create URL for playback
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
      throw error;
    }
  }, []);

  /**
   * Stop recording
   */
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  /**
   * Clear recording
   */
  const clearRecording = useCallback(() => {
    setAudioBlob(null);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    chunksRef.current = [];
  }, [audioUrl]);

  /**
   * Cancel recording and cleanup
   */
  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
    clearRecording();
  }, [isRecording, clearRecording]);

  return {
    isRecording,
    audioBlob,
    audioUrl,
    startRecording,
    stopRecording,
    clearRecording,
    cancelRecording,
  };
};
