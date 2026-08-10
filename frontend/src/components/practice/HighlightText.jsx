import React, { useMemo } from 'react';
import { useSelector } from 'react-redux';

/**
 * HighlightText component - Displays text with synchronized highlighting during playback
 * Highlights characters/words based on current playback position
 */
export const HighlightText = ({ text, sentenceStart, sentenceEnd, className = '' }) => {
  const currentTime = useSelector((state) => state.player.currentTime);
  const isPlaying = useSelector((state) => state.player.isPlaying);

  // Calculate highlight progress
  const highlightProgress = useMemo(() => {
    if (!sentenceStart || !sentenceEnd) return 0;

    const duration = sentenceEnd - sentenceStart;
    if (duration <= 0) return 0;

    const elapsed = currentTime - sentenceStart;
    const progress = Math.max(0, Math.min(1, elapsed / duration));

    return progress;
  }, [currentTime, sentenceStart, sentenceEnd]);

  // Calculate the index of characters to highlight
  const { highlightedText, remainingText } = useMemo(() => {
    const totalChars = text.length;
    const highlightCount = Math.floor(totalChars * highlightProgress);

    return {
      highlightedText: text.slice(0, highlightCount),
      remainingText: text.slice(highlightCount),
    };
  }, [text, highlightProgress]);

  return (
    <div className={`relative ${className}`}>
      {/* Text with inline highlighting */}
      <p className="text-xl text-text-primary leading-relaxed">
        <span className="text-primary font-semibold transition-colors duration-100">
          {highlightedText}
        </span>
        <span className="text-text-secondary">
          {remainingText}
        </span>
      </p>
    </div>
  );
};

/**
 * Alternative version with word-by-word highlighting
 * Useful when you have word-level timestamps from the backend
 */
export const WordHighlightText = ({ words, className = '' }) => {
  const currentTime = useSelector((state) => state.player.currentTime);

  // Calculate which words should be highlighted
  const { highlightedWords, upcomingWords } = useMemo(() => {
    const highlighted = [];
    const upcoming = [];

    words.forEach((word, index) => {
      if (word.end <= currentTime) {
        highlighted.push({ ...word, index });
      } else if (word.start > currentTime) {
        upcoming.push({ ...word, index });
      } else {
        // Currently being spoken
        highlighted.push({ ...word, index, isSpeaking: true });
      }
    });

    return { highlightedWords: highlighted, upcomingWords: upcoming };
  }, [words, currentTime]);

  return (
    <div className={`relative ${className}`}>
      <p className="text-xl leading-relaxed">
        {highlightedWords.map((word) => (
          <span
            key={word.index}
            className={`px-1 rounded transition-colors duration-150 ${
              word.isSpeaking
                ? 'bg-primary text-white font-semibold'
                : 'bg-primary/20 text-primary'
            }`}
          >
            {word.text}
          </span>
        ))}
        {upcomingWords.map((word) => (
          <span key={word.index} className="text-text-secondary">
            {word.text}
          </span>
        ))}
      </p>
    </div>
  );
};
