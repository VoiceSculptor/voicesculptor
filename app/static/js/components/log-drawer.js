/**
 * Collapsible log drawer pinned to the bottom of the window.
 * @module components/log-drawer
 */

import { el, formatClock, on } from '../dom.js';

const MAX_ENTRIES = 200;

/**
 * Wire the log drawer and return a logger that writes into it.
 * @param {Object} nodes Elements from the page shell.
 * @param {HTMLElement} nodes.drawer Drawer container.
 * @param {HTMLElement} nodes.toggle Toggle button.
 * @param {HTMLElement} nodes.list Ordered list holding entries.
 * @param {HTMLElement} nodes.count Entry counter badge.
 * @param {HTMLElement} nodes.clearButton Button that empties the log.
 * @returns {{log: Function, clear: Function}} Logger instance.
 */
export function createLogDrawer({drawer, toggle, list, count, clearButton}) {
  let total = 0;

  /**
   * Update the badge.
   * @returns {void}
   */
  function syncCount() {
    if (count) {
      count.textContent = String(total);
    }
  }

  /**
   * Clear every entry.
   * @returns {void}
   */
  function clear() {
    while (list.firstChild) {
      list.removeChild(list.firstChild);
    }
    total = 0;
    syncCount();
  }

  /**
   * Append one log line and trim the oldest entries past the cap.
   * @param {string} message Message text.
   * @param {string} [level] One of info, success, warn, error.
   * @returns {void}
   */
  function log(message, level = 'info') {
    if (!list) {
      return;
    }
    const entry = el('li', {class: 'vs-log-item', 'data-level': level},
      el('span', {class: 'vs-log-time', text: formatClock()}),
      el('span', {class: 'vs-log-msg', text: String(message)}));
    list.appendChild(entry);
    total += 1;
    while (list.children.length > MAX_ENTRIES) {
      list.firstElementChild.remove();
    }
    total = Math.min(total, MAX_ENTRIES);
    syncCount();
    if (drawer && drawer.dataset.open === 'true') {
      list.scrollTop = list.scrollHeight;
    }
  }

  /**
   * Expand or collapse the drawer.
   * @param {boolean} open Target state.
   * @returns {void}
   */
  function setOpen(open) {
    drawer.dataset.open = open ? 'true' : 'false';
    toggle.setAttribute('aria-expanded', String(open));
    if (open) {
      list.scrollTop = list.scrollHeight;
    }
  }

  if (toggle) {
    on(toggle, 'click', () => {
      setOpen(drawer.dataset.open !== 'true');
    });
  }
  if (clearButton) {
    on(clearButton, 'click', clear);
  }

  syncCount();

  return {log, clear};
}
