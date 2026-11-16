/**
 * Audit view: run the directory checker and render its markdown report with
 * a text-only markdown renderer built from DOM nodes.
 * @module views/audit-view
 */

import { runAudit } from '../api.js';
import { el, clear, on, setText } from '../dom.js';

const SUMMARY_FIELDS = [
  ['files', '文件数', ''],
  ['total_min', '总时长 (min)', ''],
  ['usable_min', '可用时长 (min)', ''],
  ['median_snr', 'SNR 中位数 (dB)', ''],
  ['verdict', '结论', ''],
];

/**
 * Split a markdown table row into trimmed cells.
 * @param {string} line Raw markdown line.
 * @returns {string[]} Cell contents.
 */
function splitRow(line) {
  let value = line.trim();
  if (value.startsWith('|')) {
    value = value.slice(1);
  }
  if (value.endsWith('|')) {
    value = value.slice(0, -1);
  }
  return value.split('|').map((cell) => cell.trim());
}

/**
 * Test whether a line is a markdown table separator row.
 * @param {string} line Raw markdown line.
 * @returns {boolean} True for `|---|:--:|` style rows.
 */
function isSeparator(line) {
  if (!line || !line.includes('-') || !line.includes('|')) {
    return false;
  }
  return /^[\s|:-]+$/.test(line);
}

/**
 * Test whether a line starts a non-paragraph markdown block.
 * @param {string} line Raw markdown line.
 * @returns {boolean} True when the paragraph should stop.
 */
function isBlockStart(line) {
  const text = line.trim();
  return /^#{1,6}\s+/.test(text)
    || /^```/.test(text)
    || /^\s*([-*+]|\d+[.)])\s+/.test(line)
    || text.startsWith('|')
    || text.startsWith('>')
    || /^\s*([-*_])\1{2,}\s*$/.test(line);
}

/**
 * Append inline markdown (strong and code spans) as real DOM nodes.
 * @param {HTMLElement} parent Element receiving the nodes.
 * @param {string} text Inline markdown source.
 * @returns {void}
 */
function appendInline(parent, text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  for (const part of parts) {
    if (!part) {
      continue;
    }
    if (part.startsWith('**') && part.endsWith('**')
      && part.length > 4) {
      parent.appendChild(el('strong', {
        class: 'vs-md-strong',
        text: part.slice(2, -2),
      }));
    } else if (part.startsWith('`') && part.endsWith('`')
      && part.length > 2) {
      parent.appendChild(el('code', {
        class: 'vs-mono',
        text: part.slice(1, -1),
      }));
    } else {
      parent.appendChild(document.createTextNode(part));
    }
  }
}

/**
 * Render a small markdown subset into a container.
 * @param {HTMLElement} container Destination element.
 * @param {string} markdown Report source.
 * @returns {void}
 */
export function renderMarkdown(container, markdown) {
  clear(container);
  const lines = String(markdown || '')
    .replace(/\r\n?/g, '\n')
    .split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = Math.min(heading[1].length, 3);
      const tag = `h${Math.min(heading[1].length + 2, 6)}`;
      container.appendChild(el(tag, {
        class: `vs-md-h${level}`,
        text: heading[2].trim(),
      }));
      i += 1;
      continue;
    }
    if (/^```/.test(line.trim())) {
      const code = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      container.appendChild(el('pre', {class: 'vs-md-code'},
        el('code', {text: code.join('\n')})));
      continue;
    }
    if (line.trim().startsWith('|')
      && isSeparator(lines[i + 1] || '')) {
      const header = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitRow(lines[i]));
        i += 1;
      }
      const headRow = el('tr', {}, ...header.map((cell) =>
        el('th', {text: cell})));
      const table = el('table', {class: 'vs-md-table'},
        el('thead', {}, headRow),
        el('tbody', {}, ...rows.map((cells) =>
          el('tr', {}, ...cells.map((cell) => el('td', {text: cell}))))));
      container.appendChild(el('div', {class: 'vs-table-wrap'}, table));
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const list = el(ordered ? 'ol' : 'ul', {class: 'vs-md-list'});
      while (i < lines.length
        && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
        const item = el('li');
        appendInline(item,
          lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, ''));
        list.appendChild(item);
        i += 1;
      }
      container.appendChild(list);
      continue;
    }
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      container.appendChild(el('hr'));
      i += 1;
      continue;
    }
    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ''));
        i += 1;
      }
      const paragraph = el('p', {class: 'vs-md-quote'});
      appendInline(paragraph, quote.join(' '));
      container.appendChild(paragraph);
      continue;
    }
    const buffer = [line];
    i += 1;
    while (i < lines.length && lines[i].trim()
      && !isBlockStart(lines[i])) {
      buffer.push(lines[i]);
      i += 1;
    }
    const paragraph = el('p', {class: 'vs-md-p'});
    appendInline(paragraph, buffer.join(' '));
    container.appendChild(paragraph);
  }
}

/**
 * Format one summary value for display.
 * @param {*} value Raw summary value.
 * @returns {string} Display string.
 */
function formatSummaryValue(value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  return String(value);
}

/**
 * Create the audit view.
 * @param {Object} handlers Dependencies from the app shell.
 * @param {Object} handlers.store Observable store.
 * @param {Object} handlers.toast Toast controller.
 * @param {Object} handlers.log Log drawer logger.
 * @returns {{el: HTMLElement}} View controller.
 */
export function createAuditView({store, toast, log}) {
  let busy = false;

  const input = el('input', {
    class: 'vs-input',
    id: 'audit-dir',
    type: 'text',
    placeholder: '例如 D:\\voices\\happy',
    autocomplete: 'off',
    spellcheck: 'false',
  });
  const runButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--filled vs-button--block',
    text: '开始体检',
  });
  const statusLine = el('p', {
    class: 'vs-hint',
    'aria-live': 'polite',
  });

  const summaryMetrics = el('div', {class: 'vs-metrics'});
  const summaryCard = el('section', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '摘要'})),
    summaryMetrics);
  summaryCard.hidden = true;

  const reportPath = el('span', {class: 'vs-card-aside'});
  const reportBody = el('div', {class: 'vs-report'});
  const reportCard = el('section', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '体检报告'}),
      reportPath),
    reportBody);
  reportCard.hidden = true;

  const root = el('div', {},
    el('section', {class: 'vs-card'},
      el('div', {class: 'vs-card-head'},
        el('h2', {class: 'vs-card-title', text: '素材体检'}),
        el('span', {class: 'vs-card-aside', text: '本地分析'})),
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'audit-dir',
          text: '素材目录'}),
        input),
      el('p', {class: 'vs-hint',
        text: '填入一个本地录音目录，检查时长、采样率与信噪比。'}),
      runButton,
      statusLine),
    summaryCard,
    reportCard);

  /**
   * Paint a completed audit payload.
   * @param {Object|null} audit Stored audit state.
   * @returns {void}
   */
  function paint(audit) {
    lastAudit = audit;
    if (!audit) {
      summaryCard.hidden = true;
      reportCard.hidden = true;
      return;
    }
    const summary = audit.summary || {};
    clear(summaryMetrics);
    const known = new Set();
    for (const [key, label] of SUMMARY_FIELDS) {
      if (!(key in summary)) {
        continue;
      }
      known.add(key);
      summaryMetrics.appendChild(el('div', {class: 'vs-metric'},
        el('span', {class: 'vs-metric-label', text: label}),
        el('span', {class: 'vs-metric-value',
          text: formatSummaryValue(summary[key])})));
    }
    for (const [key, value] of Object.entries(summary)) {
      if (known.has(key)) {
        continue;
      }
      summaryMetrics.appendChild(el('div', {class: 'vs-metric'},
        el('span', {class: 'vs-metric-label', text: key}),
        el('span', {class: 'vs-metric-value',
          text: formatSummaryValue(value)})));
    }
    summaryCard.hidden = false;
    setText(reportPath, audit.reportPath ? `已写入 ${audit.reportPath}`
      : '');
    if (audit.reportPath) {
      reportPath.title = audit.reportPath;
    } else {
      reportPath.removeAttribute('title');
    }
    renderMarkdown(reportBody, audit.report);
    reportCard.hidden = false;
  }

  /**
   * Send the current directory to the audit endpoint.
   * @returns {Promise<void>} Resolves when the request settles.
   */
  async function run() {
    if (busy) {
      return;
    }
    const dirPath = input.value.trim();
    if (!dirPath) {
      setText(statusLine, '请先填写素材目录。');
      input.focus();
      return;
    }
    busy = true;
    runButton.disabled = true;
    setText(runButton, '体检中…');
    setText(statusLine, '正在分析目录，请稍候…');
    try {
      const data = await runAudit(dirPath);
      const audit = {
        dirPath,
        report: data.report || '',
        summary: data.summary || null,
        reportPath: data.report_path || '',
        at: Date.now(),
      };
      store.setState({audit});
      paint(audit);
      setText(statusLine, '体检完成。');
      if (data.ok === false && data.detail) {
        setText(statusLine, data.detail);
      }
      if (toast) {
        toast.success('体检完成');
      }
      if (log) {
        log(`素材体检完成：${dirPath}`, 'success');
      }
    } catch (error) {
      const message = error && error.message ? error.message : '体检失败';
      setText(statusLine, message);
      if (toast) {
        toast.error(message);
      }
      if (log) {
        log(`素材体检失败：${message}`, 'error');
      }
    } finally {
      busy = false;
      runButton.disabled = false;
      setText(runButton, '开始体检');
    }
  }

  on(runButton, 'click', run);
  on(input, 'keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      run();
    }
  });

  const snapshot = store.getState();
  let lastAudit = snapshot.audit || null;
  if (snapshot.audit) {
    input.value = snapshot.audit.dirPath || '';
    paint(snapshot.audit);
  }
  store.subscribe((state) => {
    if (state.audit && state.audit !== lastAudit) {
      paint(state.audit);
    }
  });

  return {el: root};
}
