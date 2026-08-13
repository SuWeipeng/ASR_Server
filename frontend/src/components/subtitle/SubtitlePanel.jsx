import React, { useEffect, useRef, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Play } from 'lucide-react';
import { requestSeekToSubtitle, setCurrentSubtitleIndex } from '../../store/subtitleSlice';

export const SubtitlePanel = () => {
  const dispatch = useDispatch();
  const subtitles = useSelector((state) => state.subtitle.subtitles);
  const currentSubtitleIndex = useSelector(
    (state) => state.subtitle.currentSubtitleIndex
  );
  const isSeeking = useSelector((state) => state.player.isSeeking);
  const isDetached = useSelector((state) => state.player.isDetached);
  const [selectedStartTime, setSelectedStartTime] = useState('');

  // MSG_TYPES should match the one defined in App.jsx
  const MSG_TYPES = window.playerMsgTypes || {
    SEEK_TO_SUBTITLE: 'SEEK_TO_SUBTITLE',
  };

  const subtitleListRef = useRef(null);
  const subtitleRefs = useRef([]);
  const [isUserScrolling, setIsUserScrolling] = useState(false);
  const scrollTimeoutRef = useRef(null);

  // 生成时间选项
  const timeOptions = subtitles.map((sub) => {
    const minutes = Math.floor(sub.start / 60);
    const seconds = Math.floor(sub.start % 60);
    return {
      value: sub.start,
      label: `${minutes}:${seconds.toString().padStart(2, '0')}`,
    };
  });

  // 跳转处理函数 - 下拉值变化时自动跳转
  const handleStartTimeChange = (e) => {
    const value = e.target.value;
    setSelectedStartTime(value);

    // 只在选择了有效值时才跳转
    if (value) {
      const index = subtitles.findIndex((sub) => sub.start === parseFloat(value));
      if (index >= 0) {
        handleSubtitleClick(index);
      }
    }
  };

  const handleSubtitleClick = (index) => {
    const subtitle = subtitles[index];
    if (!subtitle) return;

    // Optimistically highlight the clicked subtitle
    dispatch(setCurrentSubtitleIndex(index));

    // If player is detached, send message to player window
    if (isDetached && window.playerWindowChannel) {
      const message = {
        type: MSG_TYPES.SEEK_TO_SUBTITLE,
        payload: { start: subtitle.start, end: subtitle.end },
      };
      window.playerWindowChannel.postMessage(message);
      return;
    }

    // Otherwise, request the video to seek via redux state
    dispatch(requestSeekToSubtitle(index));
  };

  // Detect user scrolling
  const handleUserScroll = () => {
    setIsUserScrolling(true);

    // Clear existing timeout
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // Reset user scrolling state after 2 seconds of no scroll activity
    scrollTimeoutRef.current = setTimeout(() => {
      setIsUserScrolling(false);
    }, 2000);
  };

  // Auto-scroll to current subtitle.
  // - While the user is dragging the progress bar, follow the seek position
  //   immediately with `behavior: 'auto'` so the list doesn't lag behind.
  // - While the user is freely scrolling the subtitle list, don't fight them.
  // - Otherwise, smooth-scroll to the current subtitle.
  useEffect(() => {
    if (currentSubtitleIndex < 0 || !subtitleRefs.current[currentSubtitleIndex]) return;
    if (isUserScrolling && !isSeeking) return;

    const currentElement = subtitleRefs.current[currentSubtitleIndex];
    const container = subtitleListRef.current;
    if (!currentElement || !container) return;

    const behavior = isSeeking ? 'auto' : 'smooth';
    const delay = isSeeking ? 0 : 100;

    const timeoutId = setTimeout(() => {
      const containerRect = container.getBoundingClientRect();
      const elementRect = currentElement.getBoundingClientRect();
      const relativeTop = elementRect.top - containerRect.top;
      const centerOffset = (containerRect.height - elementRect.height) / 2;

      container.scrollTo({
        top: relativeTop + container.scrollTop - centerOffset,
        behavior,
      });
    }, delay);

    return () => clearTimeout(timeoutId);
  }, [currentSubtitleIndex, isUserScrolling, isSeeking]);

  // Clean up refs when subtitles change
  useEffect(() => {
    subtitleRefs.current = [];
    // Reset selected start time when subtitles change
    setSelectedStartTime('');
  }, [subtitles]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-bg-secondary rounded-lg border border-bg-card">
      {/* Jump to time selector */}
      <div className="p-4 border-b border-bg-card flex-shrink-0">
        <select
          value={selectedStartTime}
          onChange={handleStartTimeChange}
          className="input w-full"
          data-jump-select
        >
          <option value="">跳转到...</option>
          {timeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Subtitle list */}
      <div
        ref={subtitleListRef}
        onScroll={handleUserScroll}
        className="flex-1 overflow-y-auto scrollbar-thin"
      >
        {subtitles.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-text-secondary">
              暂无字幕
            </p>
          </div>
        ) : (
          <div className="divide-y divide-bg-card">
            {subtitles.map((subtitle, index) => (
              <div
                key={subtitle.id}
                ref={(el) => (subtitleRefs.current[index] = el)}
                onClick={() => handleSubtitleClick(index)}
                className={`p-4 cursor-pointer transition-colors hover:bg-bg-card ${
                  index === currentSubtitleIndex
                    ? 'bg-bg-card border-l-4 border-primary'
                    : ''
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-sm font-mono text-text-secondary">
                    {Math.floor(subtitle.start / 60)}:
                    {Math.floor(subtitle.start % 60)
                      .toString()
                      .padStart(2, '0')}
                  </span>
                  {index === currentSubtitleIndex && (
                    <Play size={16} className="text-primary flex-shrink-0" />
                  )}
                </div>
                <p className="text-text-primary">{subtitle.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
