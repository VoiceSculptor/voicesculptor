/**
 * Six-emotion chip group with radio semantics. Selecting a chip reports
 * the Chinese emotion label expected by POST /api/tts.
 * @module components/emotion-chips
 */

import { el, on } from '../dom.js';
import { EMOTIONS, emotionSlug } from '../store.js';

const FALLBACK = 'calm';

/**
 * Create the emotion chip group.
 * @param {Object} [options] Configuration.
 * @param {string} [options.label] Accessible group label.
 * @param {string} [options.value] Initially selected emotion, Chinese.
 * @param {Function} [options.onChange] Called with the Chinese label.
 * @returns {{el: HTMLElement, setValue: Function, getValue: Function,
 *   setDisabled: Function}} Controller.
 */
export function createEmotionChips({
  label = '情绪',
  value = '平静',
  onChange,
} = {}) {
  const root = el('div', {
    class: 'vs-emotion-group',
    role: 'radiogroup',
    'aria-label': label,
  });
  let current = emotionSlug(value) || FALLBACK;

  const buttons = EMOTIONS.map((emotion) => {
    const button = el('button', {
      type: 'button',
      class: 'vs-emotion-chip',
      role: 'radio',
      'data-emotion': emotion.slug,
    }, el('span', {class: 'vs-emotion-dot'}),
    el('span', {text: emotion.cn}));
    button.dataset.emotion = emotion.slug;
    return button;
  });
  buttons.forEach((button) => root.appendChild(button));

  /**
   * Paint selected state, keeping one chip in the tab order.
   * @returns {void}
   */
  function paint() {
    for (const button of buttons) {
      const selected = button.dataset.emotion === current;
      button.setAttribute('aria-checked', String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
  }

  /**
   * Select a chip.
   * @param {string} slug Emotion slug.
   * @param {boolean} notify Whether to report the change.
   * @returns {void}
   */
  function select(slug, notify) {
    const known = EMOTIONS.some((emotion) => emotion.slug === slug);
    if (!known) {
      return;
    }
    current = slug;
    paint();
    if (notify && onChange) {
      const emotion = EMOTIONS.find((item) => item.slug === slug);
      onChange(emotion ? emotion.cn : '平静');
    }
  }

  buttons.forEach((button) => {
    on(button, 'click', () => select(button.dataset.emotion, true));
    on(button, 'keydown', (event) => {
      const index = buttons.indexOf(button);
      let nextIndex = -1;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        nextIndex = (index + 1) % buttons.length;
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        nextIndex = (index - 1 + buttons.length) % buttons.length;
      } else if (event.key === 'Home') {
        nextIndex = 0;
      } else if (event.key === 'End') {
        nextIndex = buttons.length - 1;
      }
      if (nextIndex < 0) {
        return;
      }
      event.preventDefault();
      buttons[nextIndex].focus();
      select(buttons[nextIndex].dataset.emotion, true);
    });
  });

  paint();

  return {
    el: root,
    /**
     * Select an emotion without notifying the listener.
     * @param {string} next Chinese label or slug.
     * @returns {void}
     */
    setValue(next) {
      select(emotionSlug(next) || FALLBACK, false);
    },
    /**
     * Read the selected Chinese label.
     * @returns {string} Chinese emotion label.
     */
    getValue() {
      const emotion = EMOTIONS.find((item) => item.slug === current);
      return emotion ? emotion.cn : '平静';
    },
    /**
     * Disable or enable every chip.
     * @param {boolean} disabled Target state.
     * @returns {void}
     */
    setDisabled(disabled) {
      root.setAttribute('aria-disabled', String(Boolean(disabled)));
      for (const button of buttons) {
        button.disabled = Boolean(disabled);
      }
    },
  };
}
