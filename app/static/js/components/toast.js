/**
 * Toast notifications rendered into the live region at the page bottom.
 * @module components/toast
 */

import { el, on } from '../dom.js';

const MAX_TOASTS = 4;
const INFO_TIMEOUT = 3600;
const ERROR_TIMEOUT = 6000;

/**
 * Create a toast controller.
 * @param {HTMLElement} container Host element with aria-live set.
 * @returns {{show: Function, success: Function, warn: Function,
 *   error: Function}} Controller with level shortcuts.
 */
export function createToaster(container) {
  /**
   * Push one toast; older toasts are dropped once the cap is reached.
   * @param {string} message Message text.
   * @param {string} level One of info, success, warn, error.
   * @param {number} timeout Milliseconds before auto removal.
   * @returns {void}
   */
  function show(message, level = 'info', timeout = INFO_TIMEOUT) {
    if (!container || !message) {
      return;
    }
    const node = el('div', {class: 'vs-toast', 'data-level': level},
      el('span', {class: 'vs-toast-text', text: message}));
    const dismiss = () => {
      if (node.isConnected) {
        node.remove();
      }
    };
    on(node, 'click', dismiss);
    container.appendChild(node);
    while (container.children.length > MAX_TOASTS) {
      container.firstElementChild.remove();
    }
    window.setTimeout(dismiss, timeout);
  }

  return {
    show,
    /**
     * Show a success toast.
     * @param {string} message Message text.
     * @returns {void}
     */
    success(message) {
      show(message, 'success');
    },
    /**
     * Show a warning toast.
     * @param {string} message Message text.
     * @returns {void}
     */
    warn(message) {
      show(message, 'warn', ERROR_TIMEOUT);
    },
    /**
     * Show an error toast.
     * @param {string} message Message text.
     * @returns {void}
     */
    error(message) {
      show(message, 'error', ERROR_TIMEOUT);
    },
  };
}
