/**
 * Result card: audio player, waveform, four metrics, download and the
 * hand-off button that sends the take to the emotion page.
 * @module components/result-card
 */

import {
  downloadBlob,
  el,
  formatDuration,
  formatNumber,
  on,
  setHidden,
  setText,
} from '../dom.js';
import { emotionCn } from '../store.js';
import { analyzeWaveform, blobFromBase64 } from '../wav.js';
import { createWaveform } from './waveform.js';

const SAFE = /[\\/:*?"<>|]/g;

/**
 * Build one metric block.
 * @param {string} label Metric label.
 * @returns {{node: HTMLElement, value: HTMLElement}} Block and value node.
 */
function metric(label) {
  const value = el('span', {class: 'vs-metric-value', text: '—'});
  const node = el('div', {class: 'vs-metric'},
    el('span', {class: 'vs-metric-label', text: label}),
    value);
  return {node, value};
}

/**
 * Create the result card.
 * @param {Object} [handlers] Callbacks.
 * @param {Function} [handlers.onAnalyze] Receives `{base64, label, filename}`.
 * @returns {{el: HTMLElement, show: Function, clear: Function,
 *   current: Function}} Controller.
 */
export function createResultCard({onAnalyze} = {}) {
  let take = null;
  let voiceName = '';
  let objectUrl = '';

  const audio = el('audio', {
    class: 'vs-audio',
    controls: true,
    preload: 'metadata',
    'aria-label': '合成音频',
  });
  const waveform = createWaveform();
  const sim = metric('SIM');
  const duration = metric('时长');
  const latency = metric('延迟');
  const candidates = metric('候选数');
  const meta = el('div', {class: 'vs-result-meta'});
  const warnings = el('ul', {class: 'vs-notes'});
  warnings.hidden = true;

  const downloadButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--outlined vs-button--sm',
    text: '下载 WAV',
  });
  const analyzeButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--tonal vs-button--sm',
    text: '分析情绪',
  });
  const actions = el('div', {class: 'vs-result-actions'},
    downloadButton, analyzeButton);

  const aside = el('span', {class: 'vs-card-aside'});
  const card = el('section', {
    class: 'vs-card',
    'aria-label': '合成结果',
  },
  el('div', {class: 'vs-card-head'},
    el('h2', {class: 'vs-card-title', text: '合成结果'}),
    aside),
  audio,
  waveform.el,
  el('div', {class: 'vs-metrics'},
    sim.node, duration.node, latency.node, candidates.node),
  meta,
  warnings,
  actions);
  card.hidden = true;

  /**
   * Append one meta tag.
   * @param {string} text Tag text.
   * @param {string} [tone] Optional modifier: ok, warn or mute.
   * @returns {void}
   */
  function tag(text, tone = '') {
    const className = tone ? `vs-tag vs-tag--${tone}` : 'vs-tag';
    meta.appendChild(el('span', {class: className, text}));
  }

  /**
   * Replace the object URL used by the audio element.
   * @param {string} base64 Base64 WAV payload.
   * @returns {void}
   */
  function setAudio(base64) {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = '';
    }
    if (!base64) {
      audio.removeAttribute('src');
      audio.load();
      return;
    }
    objectUrl = URL.createObjectURL(blobFromBase64(base64));
    audio.src = objectUrl;
    audio.load();
  }

  /**
   * Render a synthesis response.
   * @param {Object} result Payload from POST /api/tts.
   * @param {string} name Display name of the voice used.
   * @returns {void}
   */
  function show(result, name) {
    if (!result) {
      clear();
      return;
    }
    take = result;
    voiceName = name || result.ref_voice || 'voice';
    card.hidden = false;

    const target = result.emotion_target
      ? emotionCn(result.emotion_target)
      : '';
    setText(aside, target ? `目标情绪 ${target}` : '');
    setAudio(result.audio_base64);
    waveform.render(analyzeWaveform(result.audio_base64 || ''));

    setText(sim.value, result.sim === null || result.sim === undefined
      ? '—'
      : formatNumber(result.sim, 3));
    setText(duration.value, formatDuration(Number(result.duration)));
    setText(latency.value, formatDuration(Number(result.latency)));
    const got = result.candidates === undefined ? '—' : result.candidates;
    const want = result.candidates_requested === undefined
      ? '—'
      : result.candidates_requested;
    setText(candidates.value, `${got} / ${want}`);

    meta.textContent = '';
    if (result.engine) {
      tag(String(result.engine));
    }
    if (result.mode) {
      tag(`模式 ${result.mode}`);
    }
    if (result.ref_voice) {
      tag(`参考 ${result.ref_voice}`);
    }
    if (result.emo_voice) {
      tag(`情绪参考 ${result.emo_voice}`);
    }
    if (result.emotion_target) {
      tag(`目标 ${emotionCn(result.emotion_target)}`);
    }
    if (result.emotion_detected) {
      const detected = emotionCn(result.emotion_detected);
      tag(`识别 ${detected}`, target && detected === target ? 'ok' : 'warn');
    }
    if (result.emotion_rank === true) {
      tag('情绪排序生效', 'ok');
    }
    if (Array.isArray(result.warnings) && result.warnings.length) {
      tag(`${result.warnings.length} 条提示`, 'warn');
    }

    while (warnings.firstChild) {
      warnings.removeChild(warnings.firstChild);
    }
    const notes = Array.isArray(result.warnings) ? result.warnings : [];
    for (const note of notes) {
      warnings.appendChild(el('li', {text: String(note)}));
    }
    setHidden(warnings, notes.length === 0);
  }

  /**
   * Hide the card and release the current audio URL.
   * @returns {void}
   */
  function clear() {
    take = null;
    card.hidden = true;
    setAudio('');
    waveform.reset();
    meta.textContent = '';
    while (warnings.firstChild) {
      warnings.removeChild(warnings.firstChild);
    }
    warnings.hidden = true;
    setText(sim.value, '—');
    setText(duration.value, '—');
    setText(latency.value, '—');
    setText(candidates.value, '—');
    setText(aside, '');
  }

  /**
   * Read the last rendered synthesis result.
   * @returns {?Object} Latest result, or null.
   */
  function current() {
    return take;
  }

  on(downloadButton, 'click', () => {
    if (!take || !take.audio_base64) {
      return;
    }
    const target = emotionCn(take.emotion_target || '');
    const stamp = Date.now();
    const parts = [voiceName, target, stamp].filter(Boolean);
    const filename = `${parts.join('_').replace(SAFE, '_')}.wav`;
    downloadBlob(blobFromBase64(take.audio_base64), filename);
  });

  on(analyzeButton, 'click', () => {
    if (!take || !take.audio_base64 || !onAnalyze) {
      return;
    }
    const target = emotionCn(take.emotion_target || '');
    const label = [voiceName, target].filter(Boolean).join(' · ');
    onAnalyze({
      base64: take.audio_base64,
      label,
      filename: `${voiceName}`.replace(SAFE, '_') + '.wav',
    });
  });

  return {el: card, show, clear, current};
}
