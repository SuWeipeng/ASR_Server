/**
 * Keyboard shortcuts configuration
 */
export const SHORTCUTS = {
  // Playback controls
  PLAY_PAUSE: 'Space',
  PREVIOUS_SENTENCE: 'a',
  NEXT_SENTENCE: 'd',
  REPLAY_CURRENT: 'r',
  TOGGLE_LOOP: 's',

  // Recording
  START_RECORDING: 'l',

  // Playback speed
  SPEED_0_5X: '1',
  SPEED_0_75X: '2',
  SPEED_1_0X: '3',
  SPEED_1_25X: '4',

  // Other
  CLOSE_MODAL: 'Escape',
  SHOW_HELP: '?',
};

/**
 * Shortcut descriptions for help display
 */
export const SHORTCUT_DESCRIPTIONS = [
  { key: SHORTCUTS.PLAY_PAUSE, description: '播放/暂停' },
  { key: SHORTCUTS.PREVIOUS_SENTENCE, description: '上一句' },
  { key: SHORTCUTS.NEXT_SENTENCE, description: '下一句' },
  { key: SHORTCUTS.REPLAY_CURRENT, description: '重播当前句' },
  { key: SHORTCUTS.TOGGLE_LOOP, description: '切换循环' },
  { key: SHORTCUTS.START_RECORDING, description: '按住录音' },
  { key: SHORTCUTS.SPEED_0_5X, description: '0.5倍速' },
  { key: SHORTCUTS.SPEED_0_75X, description: '0.75倍速' },
  { key: SHORTCUTS.SPEED_1_0X, description: '1.0倍速' },
  { key: SHORTCUTS.SPEED_1_25X, description: '1.25倍速' },
  { key: SHORTCUTS.CLOSE_MODAL, description: '关闭弹窗' },
  { key: SHORTCUTS.SHOW_HELP, description: '显示帮助' },
];

/**
 * Format shortcut key for display
 * @param {string} key - Key combination
 * @returns {string} Formatted key
 */
export const formatShortcut = (key) => {
  if (key.includes('+')) {
    return key.split('+').map(formatShortcut).join(' + ');
  }

  if (key === 'Space') return '空格';
  if (key === 'Control') return 'Ctrl';
  if (key === 'Escape') return 'Esc';

  return key.toUpperCase();
};

/**
 * Check if event matches shortcut
 * @param {KeyboardEvent} event - Keyboard event
 * @param {string} shortcut - Shortcut key(s)
 * @returns {boolean} Is match
 */
export const isShortcutMatch = (event, shortcut) => {
  if (shortcut.includes('+')) {
    const keys = shortcut.split('+');
    const [modifier, key] = keys;

    if (modifier === 'Control') {
      return event.ctrlKey && event.key.toLowerCase() === key.toLowerCase();
    }

    return false;
  }

  return event.key === shortcut || event.key.toLowerCase() === shortcut.toLowerCase();
};
