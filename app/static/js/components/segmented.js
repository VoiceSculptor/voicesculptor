/**
 * Segmented control with radio group semantics and arrow key support.
 * @module components/segmented
 */

import { el, on } from '../dom.js';

/**
 * Create a segmented control.
 * @param {Object} options Configuration.
 * @param {Array<{value: string, label: string}>} options.options Choices.
 * @param {string} options.value Initially selected value.
 * @param {string} options.label Accessible group label.
 * @param {Function} [options.onChange] Called with the next value.
 * @returns {{el: HTMLElement, setValue: Function, getValue: Function,
 *   setDisabled: Function}} Controller.
 */
export function createSegmented({options, value, label, onChange}) {
  const root = el('div', {
    class: 'vs-segmented',
    role: 'radiogroup',
    'aria-label': label,
  });
  let current = value;

  const buttons = options.map((option) => {
    const button = el('button', {
      type: 'button',
      class: 'vs-segmented-option',
      role: 'radio',
      'data-value': option.value,
      text: option.label,
    });
    button.dataset.value = option.value;
    return button;
  });
  buttons.forEach((button) => root.appendChild(button));

  /**
   * Paint the selected state without firing onChange.
   * @returns {void}
   */
  function paint() {
    for (const button of buttons) {
      const selected = button.dataset.value === current;
      button.setAttribute('aria-checked', String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
  }

  /**
   * Select a value.
   * @param {string} next Next value.
   * @param {boolean} notify Whether to call onChange.
   * @returns {void}
   */
  function select(next, notify) {
    if (!options.some((option) => option.value === next)) {
      return;
    }
    current = next;
    paint();
    if (notify && onChange) {
      onChange(current);
    }
  }

  buttons.forEach((button) => {
    on(button, 'click', () => select(button.dataset.value, true));
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
      select(buttons[nextIndex].dataset.value, true);
    });
  });

  paint();

  return {
    el: root,
    /**
     * Set the value without notifying the listener.
     * @param {string} next Next value.
     * @returns {void}
     */
    setValue(next) {
      select(next, false);
    },
    /**
     * Read the selected value.
     * @returns {string} Current value.
     */
    getValue() {
      return current;
    },
    /**
     * Disable or enable every option.
     * @param {boolean} disabled Target state.
     * @returns {void}
     */
    setDisabled(disabled) {
      for (const button of buttons) {
        button.disabled = Boolean(disabled);
      }
    },
  };
}
