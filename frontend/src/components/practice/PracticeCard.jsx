import React, { useEffect, useRef, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Mic, Send, Trash2 } from 'lucide-react';
import { setRecording, setUserAudio, clearUserAudio } from '../../store/practiceSlice';
import { evaluateSpeech } from '../../store/practiceSlice';
import { useMediaRecorder } from '../../hooks/useMediaRecorder';
import { HighlightText } from './HighlightText';
import { WaveformDisplay } from './WaveformDisplay';

export const PracticeCard = ({ videoRef }) => {
  const dispatch = useDispatch();
  const fileId = useSelector((state) => state.media.fileId);
  const { currentSubtitleIndex, subtitles } = useSelector(
    (state) => state.subtitle
  );
  const { isRecording, lastScore, diffResult, isProcessing, audioUrl } =
    useSelector((state) => state.practice);

  const {
    isRecording: recorderRecording,
    audioBlob,
    startRecording,
    stopRecording,
    clearRecording,
  } = useMediaRecorder(useSelector((state) => state.ui.selectedMicDeviceId));

  const [recordingStartTime, setRecordingStartTime] = useState(null);

  // Current sentence
  const currentSentence =
    currentSubtitleIndex >= 0 && subtitles[currentSubtitleIndex]
      ? subtitles[currentSubtitleIndex]
      : null;

  // Sync recording state (local recorder -> Redux)
  useEffect(() => {
    dispatch(setRecording(recorderRecording));
  }, [recorderRecording, dispatch]);

  // Start recording
  const handleStartRecording = async () => {
    try {
      setRecordingStartTime(Date.now());
      await startRecording();
    } catch (error) {
      console.error('Failed to start recording:', error);
    }
  };

  // Stop recording
  const handleStopRecording = () => {
    stopRecording();
    setRecordingStartTime(null);
  };

  // Sync recording state (Redux -> local recorder).
  // This handles the keyboard-driven path (L key hold-to-record) where
  // isRecording is flipped by the keyboard hook and the actual MediaRecorder
  // must follow.
  const isRecordingRedux = useSelector((state) => state.practice.isRecording);
  useEffect(() => {
    if (isRecordingRedux && !recorderRecording) {
      handleStartRecording();
    } else if (!isRecordingRedux && recorderRecording) {
      handleStopRecording();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRecordingRedux]);

  // Handle recording
  useEffect(() => {
    if (audioBlob) {
      const url = URL.createObjectURL(audioBlob);
      dispatch(
        setUserAudio({
          blob: audioBlob,
          url,
        })
      );

      // Auto-evaluate
      dispatch(evaluateSpeech({ audioBlob, targetText: currentSentence?.text || '' }));

      return () => URL.revokeObjectURL(url);
    }
  }, [audioBlob, dispatch, currentSentence?.text]);

  // Clear recording
  const handleClearRecording = () => {
    clearRecording();
    dispatch(clearUserAudio());
  };

  if (!currentSentence) {
    return (
      <div className="card">
        <p className="text-text-secondary">请先选择字幕进行练习</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Current sentence with highlight and waveform */}
      <div className="card relative overflow-hidden">
        <h3 className="text-lg font-semibold mb-2 text-text-primary">
          当前练习句
        </h3>

        {/* Waveform background */}
        <div className="relative h-24 -mx-4 -mt-2 mb-2">
          {fileId && currentSentence && (
            <WaveformDisplay
              fileId={fileId}
              startTime={currentSentence.start}
              endTime={currentSentence.end}
              className="absolute inset-0"
            />
          )}
        </div>

        {/* Text with synchronized highlighting */}
        <div className="relative z-10">
          <HighlightText
            text={currentSentence.text}
            sentenceStart={currentSentence.start}
            sentenceEnd={currentSentence.end}
          />
        </div>
      </div>

      {/* Recording controls */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {isRecording ? (
              <button
                onClick={handleStopRecording}
                className="flex items-center space-x-2 px-6 py-3 bg-error text-white rounded-lg hover:bg-error/80 transition-colors"
              >
                <div className="w-3 h-3 bg-white rounded-full animate-pulse" />
                <span>停止录音</span>
              </button>
            ) : (
              <button
                onClick={handleStartRecording}
                disabled={isProcessing}
                className="flex items-center space-x-2 px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
              >
                <Mic size={20} />
                <span>
                  {isProcessing ? '处理中...' : '按住录音 (L键)'}
                </span>
              </button>
            )}

            {audioUrl && (
              <button
                onClick={handleClearRecording}
                className="p-2 text-text-secondary hover:text-text-primary transition-colors"
                title="清除录音"
              >
                <Trash2 size={20} />
              </button>
            )}
          </div>

          {recordingStartTime && (
            <span className="text-sm text-text-secondary">
              {Math.round((Date.now() - recordingStartTime) / 1000)}s
            </span>
          )}
        </div>

        {/* Audio playback */}
        {audioUrl && (
          <div className="mt-4">
            <audio
              src={audioUrl}
              controls
              className="w-full"
              style={{ height: '40px' }}
            />
          </div>
        )}
      </div>

      {/* Score display */}
      {lastScore && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-text-primary">评分结果</h3>
            <div
              className={`text-2xl font-bold ${
                lastScore.score >= 75
                  ? 'text-success'
                  : lastScore.score >= 60
                  ? 'text-warning'
                  : 'text-error'
              }`}
            >
              {lastScore.score} 分
            </div>
          </div>

          <p className="text-sm text-text-secondary mb-2">
            等级: {lastScore.accuracy_level}
          </p>

          {/* Diff display */}
          {diffResult && diffResult.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {diffResult.map((word, index) => (
                <span
                  key={index}
                  className={`px-2 py-1 rounded text-sm ${
                    word.status === 'correct'
                      ? 'bg-success/20 text-success'
                      : word.status === 'missing'
                      ? 'bg-error/20 text-error line-through'
                      : 'bg-warning/20 text-warning underline'
                  }`}
                >
                  {word.word}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {isProcessing && (
        <div className="card">
          <p className="text-text-secondary">正在评估您的发音...</p>
        </div>
      )}
    </div>
  );
};
