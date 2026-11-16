/**
 * Top bar health chip: green when everything works, amber on warnings,
 * red when an engine is missing or the backend is unreachable.
 * @module components/status-chip
 */

import { on, qs } from '../dom.js';

/**
 * Create the status chip controller.
 * @param {HTMLElement} root The chip button.
 * @param {Object} [handlers] Callbacks.
 * @param {Function} [handlers.onActivate] Runs when the chip is clicked.
 * @returns {{update: Function}} Controller.
 */
export function createStatusChip(root, {onActivate} = {}) {
  const text = root ? qs('.vs-status-text', root) : null;
  if (root && onActivate) {
    on(root, 'click', onActivate);
  }

  /**
   * Recompute the chip state from health and connection data.
   * @param {Object} state Store state with connection and health.
   * @returns {void}
   */
  function update(state) {
    if (!root) {
      return;
    }
    const health = state.health;
    const caps = health && health.capabilities ? health.capabilities : {};
    let level = 'pending';
    let label = '检测中';
    let detail = '正在读取后端状态';

    if (state.connection === 'error') {
      level = 'fail';
      label = '后端未连接';
      detail = state.error || '无法连接后端服务';
    } else if (health) {
      const engines = health.engines || {};
      const broken = Array.isArray(health.broken_voices)
        ? health.broken_voices.length
        : 0;
      if (!health.ok || !engines.cosyvoice || !engines.model) {
        level = 'fail';
        label = '引擎异常';
        detail = '语音引擎未就绪，生成已禁用';
      } else if (broken > 0) {
        level = 'warn';
        label = `${broken} 个音色异常`;
        detail = health.broken_voices.join('、');
      } else if (caps.synthesize === false) {
        level = 'fail';
        label = '生成不可用';
        detail = '后端没有可用的合成能力';
      } else if (caps.emotion === false) {
        level = 'warn';
        label = '情绪服务不可用';
        detail = '情绪识别与校验暂时关闭';
      } else {
        level = 'ok';
        label = '全部正常';
        detail = '后端、引擎与音色库均正常';
      }
    }

    root.dataset.level = level;
    root.title = `${label} · ${detail}`;
    if (text) {
      text.textContent = label;
    }
  }

  return {update};
}
