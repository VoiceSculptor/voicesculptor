/**
 * Emotion view: analyze an uploaded clip or the latest synthesis result and
 * show the dominant label plus the probability bars.
 * @module views/emotion-view
 */

import { detectEmotion } from '../api.js';
import { createScoreBars } from '../components/score-bars.js';
import { el, on, setText } from '../dom.js';
import { emotionCn, emotionSlug } from '../store.js';
import { fileFromBase64 } from '../wav.js';

/**
 * Create the emotion view.
 * @param {Object} handlers Dependencies from the app shell.
 * @param {Object} handlers.store Observable store.
 * @param {Object} handlers.toast Toast controller.
 * @param {Object} handlers.log Log drawer logger.
 * @returns {{el: HTMLElement, useResult: Function}} View controller.
 */
export function createEmotionView({store, toast, log}) {
  let busy = false;
  let lastData = null;

  const fileInput = el('input', {
    class: 'vs-input',
    id: 'emotion-file',
    type: 'file',
    accept: 'audio/*,.wav,.mp3,.flac,.m4a,.ogg',
  });
  const useButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--outlined vs-button--sm',
    text: '使用最近一次合成结果',
  });
  const sourceText = el('span', {class: 'vs-hint', text: '未选择音频'});
  const statusText = el('span', {
    class: 'vs-hint',
    'aria-live': 'polite',
    text: '',
  });

  const heroLabel = el('strong', {
    class: 'vs-emotion-hero-label',
    text: '—',
  });
  const heroEn = el('span', {class: 'vs-emotion-hero-en', text: ''});
  const heroReason = el('p', {class: 'vs-emotion-reason'});
  const hero = el('div', {class: 'vs-emotion-hero'}, heroLabel, heroEn,
    heroReason);
  hero.hidden = true;

  const silence = el('div', {class: 'vs-inline-alert'},
    el('span', {text: '提示'}), el('span', {text: ''}));
  silence.hidden = true;
  const silenceText = silence.lastElementChild;

  const bars = createScoreBars();
  const scoreSection = el('div', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '情绪分数'}),
      el('span', {class: 'vs-card-aside',
        text: '按概率从高到低'})),
    bars.el);
  scoreSection.hidden = true;

  const root = el('div', {},
    el('section', {class: 'vs-card'},
      el('div', {class: 'vs-card-head'},
        el('h2', {class: 'vs-card-title', text: '音频来源'}),
        statusText),
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'emotion-file',
          text: '上传音频'}),
        fileInput),
      el('div', {class: 'vs-result-actions'},
        useButton,
        sourceText)),
    hero,
    silence,
    scoreSection);

  /**
   * Paint one emotion payload.
   * @param {?Object} data Response from POST /api/emotion.
   * @param {string} source Description of the analyzed audio.
   * @returns {void}
   */
  function paint(data, source) {
    lastData = data;
    if (!data) {
      hero.hidden = true;
      scoreSection.hidden = true;
      silence.hidden = true;
      setText(sourceText, source || '未选择音频');
      return;
    }
    const cn = data.cn || emotionCn(data.label) || data.label || '—';
    const slug = emotionSlug(cn) || emotionSlug(data.label);
    hero.hidden = false;
    if (slug) {
      hero.dataset.emotion = slug;
    } else {
      delete hero.dataset.emotion;
    }
    setText(heroLabel, cn);
    setText(heroEn, data.label && data.label !== cn ? data.label : '');
    heroReason.hidden = !data.reason;
    setText(heroReason, data.reason ? `依据：${data.reason}` : '');

    const cnScores = data.cn_scores && Object.keys(data.cn_scores).length
      ? data.cn_scores
      : data.scores;
    bars.render(cnScores);
    scoreSection.hidden = false;

    const numeric = Object.values(cnScores || {})
      .filter((value) => Number.isFinite(Number(value)));
    const scale = numeric.some((value) => Number(value) > 1.001) ? 100 : 1;
    const best = numeric.length ? Math.max(...numeric) / scale : 0;
    const silentLabel = /静音|silence|silent/.test(
      `${data.label || ''} ${cn}`,
    );
    const isSilent = silentLabel || (!numeric.length ? false : best < 0.2);
    silence.hidden = !isSilent;
    if (isSilent) {
      setText(silenceText, '这段音频几乎没有有效人声，分数参考意义有限。');
    }
    setText(sourceText, source || '未选择音频');
  }

  /**
   * Classify an audio blob and paint the result.
   * @param {Blob|File} audio Audio payload.
   * @param {string} filename File name for the multipart upload.
   * @param {string} source Human readable source description.
   * @returns {Promise<void>} Resolves when the request settles.
   */
  async function analyze(audio, filename, source) {
    if (busy) {
      return;
    }
    busy = true;
    setText(statusText, '识别中…');
    statusText.classList.add('vs-muted');
    try {
      const data = await detectEmotion(audio, filename);
      store.setState({emotion: data, emotionSource: source});
      paint(data, source);
      setText(statusText, '');
      if (log) {
        log(`情绪识别：${data.cn || data.label} · ${source}`, 'success');
      }
    } catch (error) {
      const message = error && error.message ? error.message : '识别失败';
      setText(statusText, message);
      setText(sourceText, source);
      if (toast) {
        toast.error(message);
      }
      if (log) {
        log(`情绪识别失败：${message}`, 'error');
      }
    } finally {
      busy = false;
      setText(statusText, '');
    }
  }

  /**
   * Analyze a base64 take handed over from the synthesis page.
   * @param {Object} payload Hand-off payload.
   * @param {string} payload.base64 Base64 WAV payload.
   * @param {string} [payload.filename] File name.
   * @param {string} [payload.label] Source description.
   * @returns {boolean} Whether analysis started.
   */
  function useResult(payload) {
    if (!payload || !payload.base64) {
      return false;
    }
    const filename = payload.filename || 'result.wav';
    const file = fileFromBase64(payload.base64, filename);
    const label = payload.label || filename;
    paint(null, label);
    analyze(file, filename, label);
    return true;
  }

  on(fileInput, 'change', () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      return;
    }
    setText(sourceText, file.name);
    analyze(file, file.name, file.name);
    fileInput.value = '';
  });

  on(useButton, 'click', () => {
    const snapshot = store.getState();
    const result = snapshot.lastResult;
    if (!result || !result.audio_base64) {
      return;
    }
    const emotion = emotionCn(result.emotion_target || '');
    const label = [
      snapshot.lastResultVoiceName,
      emotion,
      '最近一次合成',
    ].filter(Boolean).join(' · ');
    useResult({
      base64: result.audio_base64,
      filename: 'result.wav',
      label,
    });
  });

  /**
   * Re-render from store state.
   * @param {Object} snapshot Store state.
   * @returns {void}
   */
  function render(snapshot) {
    const available = Boolean(snapshot.lastResult
      && snapshot.lastResult.audio_base64);
    useButton.disabled = busy || !available;
    if (snapshot.emotion && snapshot.emotion !== lastData) {
      paint(snapshot.emotion, snapshot.emotionSource || '');
    }
  }

  store.subscribe(render);
  render(store.getState());

  return {el: root, useResult};
}
