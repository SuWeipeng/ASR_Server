import React, { useEffect, useRef, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Search, Play } from 'lucide-react';
import { setSearchQuery, requestSeekToSubtitle, setCurrentSubtitleIndex } from '../../store/subtitleSlice';

export const SubtitlePanel = () => {
  const dispatch = useDispatch();
  const subtitles = useSelector((state) => state.subtitle.filteredSubtitles);
  const currentSubtitleIndex = useSelector(
    (state) => state.subtitle.currentSubtitleIndex
  );
  const searchQuery = useSelector((state) => state.subtitle.searchQuery);
  const isSeeking = useSelector((state) => state.player.isSeeking);

  const subtitleListRef = useRef(null);
  const subtitleRefs = useRef([]);
  const [isUserScrolling, setIsUserScrolling] = useState(false);
  const scrollTimeoutRef = useRef(null);

  const handleSearchChange = (e) => {
    dispatch(setSearchQuery(e.target.value));
  };

  const handleSubtitleClick = (index) => {
    // Optimistically highlight the clicked subtitle
    dispatch(setCurrentSubtitleIndex(index));
    // Request the video to seek via redux state
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
      {/* Search bar */}
      <div className="p-4 border-b border-bg-card flex-shrink-0">
        <div className="relative">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="搜索字幕..."
            className="input w-full pl-10"
            data-search-input
          />
        </div>
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
              {searchQuery ? '未找到匹配的字幕' : '暂无字幕'}
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
