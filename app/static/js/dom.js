/**
 * DOM helpers shared by every view.
 *
 * All rendering goes through `el()` / text nodes; the app never parses
 * untrusted strings as markup, so arbitrary text is inserted safely.
 * @module dom
 */

/**
 * Create an element.
 * @param {string} tag Tag name such as `button` or `div`.
 * @param {?Object<string, *>} attrs Attribute map; `text` sets textContent.
 * @param {...*} children Child nodes, strings or nested arrays of either.
 * @returns {HTMLElement} The new element.
 */
export function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) {
        continue;
      }
      if (key === 'text') {
        node.textContent = String(value);
      } else if (key === 'class') {
        node.className = String(value);
      } else if (key === 'value') {
        node.value = String(value);
      } else if (value === true) {
        node.setAttribute(key, '');
      } else {
        node.setAttribute(key, String(value));
      }
    }
  }
  append(node, children);
  return node;
}

/**
 * Append children to a parent, flattening arrays and skipping empties.
 * @param {Node} parent Parent node.
 * @param {...*} children Child nodes, strings or nested arrays.
 * @returns {void}
 */
export function append(parent, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) {
      continue;
    }
    if (Array.isArray(child)) {
      append(parent, child);
      continue;
    }
    parent.appendChild(
      child instanceof Node
        ? child
        : document.createTextNode(String(child)),
    );
  }
}

/**
 * Remove every child of a node.
 * @param {Node} node Parent node.
 * @returns {void}
 */
export function clear(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

/**
 * Query one element.
 * @param {string} selector CSS selector.
 * @param {ParentNode} [root] Search root, defaults to the document.
 * @returns {?HTMLElement} First match or null.
 */
export function qs(selector, root = document) {
  return root.querySelector(selector);
}

/**
 * Query all elements as a real array.
 * @param {string} selector CSS selector.
 * @param {ParentNode} [root] Search root, defaults to the document.
 * @returns {Array<HTMLElement>} Matching elements.
 */
export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

/**
 * Add an event listener and return a remover.
 * @param {EventTarget} target Listener target.
 * @param {string} type Event name.
 * @param {EventListener} handler Callback.
 * @param {boolean|AddEventListenerOptions} [options] Listener options.
 * @returns {Function} Removes the listener when called.
 */
export function on(target, type, handler, options) {
  target.addEventListener(type, handler, options);
  return () => target.removeEventListener(type, handler, options);
}

/**
 * Show or hide a node.
 * @param {HTMLElement} node Target node.
 * @param {boolean} hidden Whether it should be hidden.
 * @returns {void}
 */
export function setHidden(node, hidden) {
  if (node) {
    node.hidden = Boolean(hidden);
  }
}

/**
 * Format a timestamp as a local wall clock time.
 * @param {number} [timestamp] Milliseconds since the epoch.
 * @returns {string} `HH:MM:SS`.
 */
export function formatClock(timestamp = Date.now()) {
  const date = new Date(timestamp);
  const parts = [
    date.getHours(),
    date.getMinutes(),
    date.getSeconds(),
  ].map((part) => String(part).padStart(2, '0'));
  return parts.join(':');
}

/**
 * Format a duration in seconds for humans.
 * @param {number} seconds Raw seconds.
 * @returns {string} For example `1.24 s` or `2 分 03 秒`.
 */
export function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) {
    return '—';
  }
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return `${minutes} 分 ${String(rest).padStart(2, '0')} 秒`;
  }
  return `${seconds.toFixed(2)} s`;
}

/**
 * Format a number with a fixed number of decimals, or a dash when absent.
 * @param {?number} value Value to format.
 * @param {number} [digits] Decimal digits.
 * @returns {string} Formatted text.
 */
export function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—';
  }
  return Number(value).toFixed(digits);
}

/**
 * Clamp a number into an inclusive range.
 * @param {number} value Input value.
 * @param {number} min Lower bound.
 * @param {number} max Upper bound.
 * @returns {number} Clamped value.
 */
export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

/**
 * Trigger a browser download for a blob.
 * @param {Blob} blob Payload to save.
 * @param {string} filename Suggested file name.
 * @returns {void}
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = el('a', {href: url, download: filename});
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Replace text only when it changed, to avoid pointless layout work.
 * @param {HTMLElement} node Target element.
 * @param {string} text New text.
 * @returns {void}
 */
export function setText(node, text) {
  const next = text === null || text === undefined ? '' : String(text);
  if (node.textContent !== next) {
    node.textContent = next;
  }
}
