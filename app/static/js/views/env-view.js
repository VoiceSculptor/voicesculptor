/**
 * Environment view: render the 12 checks, capability badges and a refresh
 * action backed by GET /api/env.
 * @module views/env-view
 */

import { getEnv } from '../api.js';
import { el, clear, on, setText } from '../dom.js';

const CAP_LABELS = {
  synthesize: '语音合成',
  similarity: '相似度打分',
  emotion: '情绪识别',
  clone: '音色克隆',
};

/**
 * Format an epoch number (seconds or milliseconds) as local time.
 * @param {number} timestamp Generated-at timestamp.
 * @returns {string} Localized time or an empty string.
 */
function formatGeneratedAt(timestamp) {
  if (!timestamp) {
    return '';
  }
  const millis = timestamp < 1e12 ? timestamp * 1000 : timestamp;
  const date = new Date(millis);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString('zh-CN', {hour12: false});
}

/**
 * Create the environment view.
 * @param {Object} handlers Dependencies from the app shell.
 * @param {Object} handlers.store Observable store.
 * @param {Object} handlers.toast Toast controller.
 * @param {Object} handlers.log Log drawer logger.
 * @returns {{el: HTMLElement, load: Function}} View controller.
 */
export function createEnvView({store, toast, log}) {
  let busy = false;

  const generatedText = el('span', {class: 'vs-card-aside'});
  const refreshButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--outlined vs-button--sm',
    text: '重新检测',
  });
  const statusLine = el('p', {
    class: 'vs-hint',
    'aria-live': 'polite',
  });
  const capsBox = el('div', {class: 'vs-caps'});
  const capsSection = el('section', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '能力'})),
    capsBox);
  capsSection.hidden = true;

  const tableHead = el('tr', {},
    el('th', {text: '检测项'}),
    el('th', {text: '状态'}),
    el('th', {text: '说明'}),
    el('th', {text: '耗时'}));
  const tableBody = el('tbody');
  const table = el('table', {class: 'vs-md-table vs-env-table'},
    el('thead', {}, tableHead),
    tableBody);
  const tableAside = el('span', {class: 'vs-card-aside'});
  const checksCard = el('section', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '12 项检测'}),
      tableAside),
    el('div', {class: 'vs-table-wrap'}, table));
  checksCard.hidden = true;

  const root = el('div', {},
    el('section', {class: 'vs-card'},
      el('div', {class: 'vs-card-head'},
        el('h2', {class: 'vs-card-title', text: '环境检测'}),
        generatedText),
      el('div', {class: 'vs-result-actions'}, refreshButton),
      statusLine),
    capsSection,
    checksCard);

  /**
   * Render capability badges.
   * @param {Object} capabilities Capability map from the API.
   * @returns {void}
   */
  function paintCapabilities(capabilities) {
    clear(capsBox);
    if (!capabilities) {
      capsSection.hidden = true;
      return;
    }
    capsSection.hidden = false;
    const known = new Set(Object.keys(CAP_LABELS));
    for (const [key, label] of Object.entries(CAP_LABELS)) {
      if (!(key in capabilities)) {
        continue;
      }
      const onOff = Boolean(capabilities[key]);
      capsBox.appendChild(el('span', {
        class: 'vs-cap',
        'data-on': String(onOff),
      }, el('span', {class: 'vs-cap-dot', 'aria-hidden': 'true'}),
      el('span', {text: `${label} ${onOff ? '可用' : '不可用'}`})));
    }
    for (const [key, value] of Object.entries(capabilities)) {
      if (known.has(key) || typeof value !== 'boolean') {
        continue;
      }
      capsBox.appendChild(el('span', {
        class: 'vs-cap',
        'data-on': String(value),
      }, el('span', {class: 'vs-cap-dot', 'aria-hidden': 'true'}),
      el('span', {text: `${key} ${value ? '可用' : '不可用'}`})));
    }
    if (Array.isArray(capabilities.formats)
      && capabilities.formats.length) {
      capsBox.appendChild(el('span', {class: 'vs-cap',
        'data-on': 'true'},
      el('span', {class: 'vs-cap-dot', 'aria-hidden': 'true'}),
      el('span', {text: `格式 ${capabilities.formats.join(' / ')}`})));
    }
  }

  /**
   * Render one environment payload.
   * @param {?Object} data Response from GET /api/env.
   * @returns {void}
   */
  function paint(data) {
    if (!data) {
      checksCard.hidden = true;
      paintCapabilities(null);
      setText(generatedText, '');
      return;
    }
    const checks = Array.isArray(data.checks) ? data.checks : [];
    clear(tableBody);
    const counts = {OK: 0, WARN: 0, FAIL: 0};
    for (const check of checks) {
      const level = String(check.level || 'WARN').toUpperCase();
      if (level in counts) {
        counts[level] += 1;
      }
      const hint = check.hint
        ? el('div', {class: 'vs-check-hint', text: check.hint})
        : '';
      const time = Number.isFinite(Number(check.elapsed_ms))
        ? `${Number(check.elapsed_ms)} ms`
        : '—';
      tableBody.appendChild(el('tr', {},
        el('td', {},
          el('div', {class: 'vs-check-title', text: check.title || ''}),
          hint),
        el('td', {},
          el('span', {class: 'vs-check-level',
            'data-level': level, text: level})),
        el('td', {},
          el('span', {class: 'vs-check-msg',
            text: check.message || '—'})),
        el('td', {},
          el('span', {class: 'vs-check-time', text: time}))));
    }
    if (!checks.length) {
      tableBody.appendChild(el('tr', {},
        el('td', {colspan: '4'},
          el('span', {class: 'vs-hint',
            text: '后端没有返回检测项。'}))));
    }
    setText(tableAside,
      `合格 ${counts.OK} · 警告 ${counts.WARN} · 失败 ${counts.FAIL}`);
    checksCard.hidden = false;
    paintCapabilities(data.capabilities);
    const generated = formatGeneratedAt(data.generated_at);
    setText(generatedText, generated ? `检测于 ${generated}` : '');
  }

  /**
   * Fetch the environment report.
   * @param {boolean} [force] Ask the backend to bypass its cache.
   * @returns {Promise<void>} Resolves when the request settles.
   */
  async function load(force = false) {
    if (busy) {
      return;
    }
    busy = true;
    refreshButton.disabled = true;
    setText(refreshButton, '检测中…');
    setText(statusLine, '正在检查后端与模型环境…');
    try {
      const data = await getEnv(force);
      store.setState({env: data});
      paint(data);
      setText(statusLine, '');
      if (log) {
        log('环境检测完成', 'success');
      }
    } catch (error) {
      const message = error && error.message ? error.message : '检测失败';
      setText(statusLine, message);
      if (toast) {
        toast.error(message);
      }
      if (log) {
        log(`环境检测失败：${message}`, 'error');
      }
    } finally {
      busy = false;
      refreshButton.disabled = false;
      setText(refreshButton, '重新检测');
    }
  }

  on(refreshButton, 'click', () => {
    load(true);
  });

  const snapshot = store.getState();
  if (snapshot.env) {
    paint(snapshot.env);
  }

  return {el: root, load};
}
