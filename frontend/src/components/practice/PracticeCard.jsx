import React, { useEffect, useRef, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Mic, Send, Trash2 } from 'lucide-react';
import { setRecording, setUserAudio, clearUserAudio, clearPractice, setAudioDuration } from '../../store/practiceSlice';
import { evaluateSpeech } from '../../store/practiceSlice';
import { useMediaRecorder } from '../../hooks/useMediaRecorder';
import { HighlightText } from './HighlightText';
import { WaveformDisplay } from './WaveformDisplay';
import { UserRecordingWaveform } from './UserRecordingWaveform';

export const PracticeCard = ({ videoRef }) => {
  const dispatch = useDispatch();
  const fileId = useSelector((state) => state.media.fileId);
  const { currentSubtitleIndex, subtitles } = useSelector(
    (state) => state.subtitle
  );
  const { isRecording, lastScore, diffResult, isProcessing, audioUrl, audioDuration } =
    useSelector((state) => state.practice);

  const {
    isRecording: recorderRecording,
    audioBlob,
    startRecording,
    stopRecording,
    clearRecording,
  } = useMediaRecorder(useSelector((state) => state.ui.selectedMicDeviceId));

  const [recordingStartTime, setRecordingStartTime] = useState(null);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const audioRef = useRef(null);

  // Current sentence
  const currentSentence =
    currentSubtitleIndex >= 0 && subtitles[currentSubtitleIndex]
      ? subtitles[currentSubtitleIndex]
      : null;

  // Clear previous results when sentence changes
  useEffect(() => {
    // Clear all previous practice data when switching to a different sentence
    dispatch(clearPractice());
    dispatch(clearUserAudio());
    clearRecording();  // Also clear the audio blob from useMediaRecorder
    setAudioCurrentTime(0);
  }, [currentSentence?.id, dispatch]); // Use sentence ID as the key

  // Sync recording state (local recorder -> Redux)
  useEffect(() => {
    dispatch(setRecording(recorderRecording));
  }, [recorderRecording, dispatch]);

  // Start recording
  const handleStartRecording = async () => {
    // Clear previous results before starting new recording
    dispatch(clearPractice());
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

      // Auto-evaluate (use the current sentence at recording time)
      dispatch(evaluateSpeech({ audioBlob, targetText: currentSentence?.text || '' }));

      return () => URL.revokeObjectURL(url);
    }
  }, [audioBlob, dispatch]); // Remove currentSentence?.text from dependencies

  // Clear recording
  const handleClearRecording = () => {
    clearRecording();
    dispatch(clearUserAudio());
    dispatch(clearPractice());
    setAudioCurrentTime(0);  // Reset audio progress
  };

  // Handle audio time update for progress synchronization
  const handleAudioTimeUpdate = () => {
    if (audioRef.current) {
      setAudioCurrentTime(audioRef.current.currentTime);
    }
  };

  // Handle audio loaded metadata to get duration
  const handleAudioLoadedMetadata = (e) => {
    dispatch(setAudioDuration(e.target.duration));
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
              ref={audioRef}
              src={audioUrl}
              controls
              onTimeUpdate={handleAudioTimeUpdate}
              onLoadedMetadata={handleAudioLoadedMetadata}
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

          {/* User recording amplitude + pitch */}
          {audioBlob && (
            <div className="relative h-24 -mx-4 my-4">
              <UserRecordingWaveform
                audioBlob={audioBlob}
                currentTime={audioCurrentTime}
                duration={audioDuration}
                className="absolute inset-0"
              />
            </div>
          )}

          {/* Diff display - original word-by-word with progress-based color change for spoken words */}
          {diffResult && diffResult.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {diffResult.map((word, index) => {
                // Determine word color based on status and playback progress
                let wordClass = 'px-2 py-1 rounded text-sm ';

                if (word.status === 'missing') {
                  // Missing words (user didn't say) - static red, no timestamp
                  wordClass += 'bg-error/20 text-error line-through';
                } else {
                  // Calculate effective timestamps (with fallback for missing data)
                  let wordStart = word.start;
                  let wordEnd = word.end;

                  // Estimate timestamp for last word if missing (ASR boundary issue)
                  if (word.start === null || word.end === null) {
                    // Find the previous word's end time
                    const prevWord = index > 0 ? diffResult[index - 1] : null;
                    const prevEnd = prevWord?.end ?? 0;

                    // Estimate: start at previous word's end, end at audio duration
                    wordStart = prevEnd;
                    wordEnd = audioDuration || prevEnd + 1;  // +1 second as fallback
                  }

                  // Change color based on effective timestamps
                  const isSpoken = audioCurrentTime >= wordEnd;
                  const isSpeaking = audioCurrentTime >= wordStart && audioCurrentTime < wordEnd;

                  if (isSpeaking) {
                    wordClass += 'bg-primary text-white font-semibold'; // Currently speaking
                  } else if (isSpoken) {
                    wordClass += 'bg-primary/40 text-primary'; // Already spoken
                  } else {
                    // Not yet spoken - keep original status color
                    if (word.status === 'correct') {
                      wordClass += 'bg-success/20 text-success';
                    } else { // extra
                      wordClass += 'bg-warning/20 text-warning underline';
                    }
                  }
                }

                return (
                  <span key={index} className={wordClass}>
                    {word.word}
                  </span>
                );
              })}
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
