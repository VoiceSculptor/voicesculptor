/**
 * Synthesis view: voice picker, text, emotion, mode, quality, speed,
 * candidate count, verify switch and the result card.
 * @module views/synth-view
 */

import { synthesize } from '../api.js';
import { createEmotionChips } from '../components/emotion-chips.js';
import { createResultCard } from '../components/result-card.js';
import { createSegmented } from '../components/segmented.js';
import { el, on, setHidden, setText } from '../dom.js';
import { MODES, QUALITIES } from '../store.js';

/**
 * Build the synthesis view.
 * @param {Object} handlers Dependencies from the app shell.
 * @param {Object} handlers.store Observable store.
 * @param {Object} handlers.toast Toast controller.
 * @param {Object} handlers.log Log drawer logger.
 * @param {Function} handlers.onAnalyze Sends a take to the emotion page.
 * @returns {{el: HTMLElement}} View controller.
 */
export function createSynthView({store, toast, log, onAnalyze}) {
  const state = store.getState();

  const voiceSelect = el('select', {
    class: 'vs-select',
    id: 'synth-voice',
  });
  const textarea = el('textarea', {
    class: 'vs-textarea',
    id: 'synth-text',
    rows: 5,
    maxlength: 500,
    placeholder: '输入要合成的内容，建议 1–3 句。',
  });
  textarea.value = state.synth.text;
  const counter = el('span', {class: 'vs-counter', text: '0 字'});

  const chips = createEmotionChips({
    value: state.synth.emotion,
    onChange: (value) => store.patchSynth({emotion: value}),
  });

  const modeControl = createSegmented({
    options: MODES,
    value: state.synth.mode,
    label: '合成模式',
    onChange: (value) => store.patchSynth({mode: value}),
  });
  const qualityControl = createSegmented({
    options: QUALITIES,
    value: state.synth.quality,
    label: '质量档位',
    onChange: (value) => {
      store.patchSynth({quality: value});
      if (value !== 'best') {
        bestRange.value = '1';
        store.patchSynth({bestN: 1});
      }
    },
  });

  const speedRange = el('input', {
    type: 'range',
    id: 'synth-speed',
    min: '0.5',
    max: '2',
    step: '0.05',
    value: String(state.synth.speed),
  });
  const speedValue = el('span', {
    class: 'vs-range-value',
    text: `${Number(state.synth.speed).toFixed(2)}×`,
  });
  const bestRange = el('input', {
    type: 'range',
    id: 'synth-best',
    min: '1',
    max: '4',
    step: '1',
    value: String(state.synth.bestN),
  });
  const bestValue = el('span', {
    class: 'vs-range-value',
    text: String(state.synth.bestN),
  });
  const bestHint = el('span', {class: 'vs-hint'});
  const verifySwitch = el('button', {
    type: 'button',
    class: 'vs-switch',
    role: 'switch',
    'aria-checked': String(state.synth.verify),
    'aria-label': '情绪校验',
  });
  const verifyNote = el('span', {class: 'vs-hint'});

  const instructInput = el('input', {
    class: 'vs-input',
    id: 'synth-instruct',
    type: 'text',
    maxlength: 160,
    placeholder: '例如：用温柔的语气，语速稍慢',
  });
  instructInput.value = state.synth.instructText;
  const instructField = el('div', {class: 'vs-field'},
    el('label', {class: 'vs-label', for: 'synth-instruct',
      text: '指令文本（instruct2 / hybrid）'}),
    instructInput);

  const emoSelect = el('select', {
    class: 'vs-select',
    id: 'synth-emo-voice',
  });
  const emoField = el('div', {class: 'vs-field'},
    el('label', {class: 'vs-label', for: 'synth-emo-voice',
      text: '情绪参考音色（可选）'}),
    emoSelect);

  const generateButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--lg vs-button--block',
    text: '生成语音',
  });
  const generateHint = el('p', {class: 'vs-hint'});

  const empty = el('p', {
    class: 'vs-empty',
    text: '还没有结果。输入文本并点击「生成语音」，结果会出现在这里。',
  });
  const resultCard = createResultCard({
    onAnalyze: (payload) => {
      if (onAnalyze) {
        onAnalyze(payload);
      }
    },
  });

  const card = el('section', {class: 'vs-card'},
    el('div', {class: 'vs-card-head'},
      el('h2', {class: 'vs-card-title', text: '合成设置'}),
      el('span', {class: 'vs-card-aside', text: 'Ctrl+Enter 生成'})),
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'synth-voice', text: '音色'}),
      voiceSelect),
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'synth-text', text: '文本'}),
      textarea,
      counter),
    el('div', {class: 'vs-fieldset'},
      el('span', {class: 'vs-label', text: '情绪'}),
      chips.el),
    el('div', {class: 'vs-field-row'},
      el('div', {class: 'vs-fieldset'},
        el('span', {class: 'vs-label', id: 'mode-label', text: '模式'}),
        modeControl.el),
      el('div', {class: 'vs-fieldset'},
        el('span', {class: 'vs-label', id: 'quality-label', text: '质量'}),
        qualityControl.el)),
    el('div', {class: 'vs-field-row'},
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'synth-speed',
          text: '语速'}),
        el('div', {class: 'vs-range'}, speedRange, speedValue)),
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'synth-best',
          text: '候选数量'}),
        el('div', {class: 'vs-range'}, bestRange, bestValue),
        bestHint)),
    el('div', {class: 'vs-switch-row'},
      el('div', {class: 'vs-fieldset'},
        el('span', {class: 'vs-label', text: '情绪校验'}),
        verifyNote),
      verifySwitch),
    el('div', {class: 'vs-field-row'},
      instructField,
      emoField),
    generateButton,
    generateHint);

  const root = el('div', {}, card,
    empty,
    resultCard.el);

  let voicesSignature = null;
  let emoSignature = null;
  let renderedResult = null;
  let busy = false;

  /**
   * Text limit announced by the backend, with a safe fallback.
   * @param {Object} snapshot Store state.
   * @returns {number} Maximum characters.
   */
  const textLimit = (snapshot) => {
    const health = snapshot && snapshot.health;
    const limit = health ? Number(health.max_text_chars) : NaN;
    return Number.isFinite(limit) && limit > 0 ? limit : 500;
  };

  const updateCounter = () => {
    const length = textarea.value.length;
    setText(counter, `${length} / ${textLimit(store.getState())} 字`);
  };
  updateCounter();

  /**
   * Derive a stable signature to decide whether option lists need a rebuild.
   * @param {Array<Object>} voices Voice list.
   * @returns {string} Signature string.
   */
  function signatureFor(voices) {
    return voices.map((voice) => [
      voice.voice_id,
      voice.name,
      voice.emoji,
      voice.group,
    ].join(':')).join('|');
  }

  /**
   * Group voices and fill a select element.
   * @param {HTMLSelectElement} select Target select.
   * @param {Array<Object>} voices Voice list.
   * @param {boolean} withEmpty Whether to prepend an empty option.
   * @returns {void}
   */
  function fillVoices(select, voices, withEmpty) {
    select.replaceChildren();
    if (withEmpty) {
      select.appendChild(el('option', {value: '', text: '不启用'}));
    }
    if (!voices.length) {
      select.appendChild(el('option', {value: '', text: '（暂无音色）'}));
      select.disabled = true;
      return;
    }
    select.disabled = false;
    const groups = new Map();
    for (const voice of voices) {
      const name = String(voice.group || '默认').trim() || '默认';
      if (!groups.has(name)) {
        groups.set(name, []);
      }
      groups.get(name).push(voice);
    }
    for (const [name, items] of groups.entries()) {
      const group = el('optgroup', {label: name});
      for (const voice of items) {
        group.appendChild(el('option', {
          value: String(voice.voice_id),
          text: `${voice.emoji || '🎙'} ${voice.name}`,
        }));
      }
      select.appendChild(group);
    }
  }

  /**
   * Recompute disabled state, hints and the generate button label.
   * @param {Object} snapshot Store state.
   * @returns {void}
   */
  function syncAvailability(snapshot) {
    const health = snapshot.health;
    const caps = health && health.capabilities ? health.capabilities : {};
    const broken = new Set(
      health && Array.isArray(health.broken_voices)
        ? health.broken_voices.map(String)
        : [],
    );
    const selectedBroken = Boolean(snapshot.selectedVoiceId)
      && broken.has(String(snapshot.selectedVoiceId));
    const armed = snapshot.connection === 'ok'
      && health
      && health.ok
      && caps.synthesize !== false;
    const text = textarea.value.trim();
    let reason = '';
    if (snapshot.connection === 'error') {
      reason = '后端未连接，暂时无法生成。';
    } else if (snapshot.connection === 'init') {
      reason = '正在检测后端状态…';
    } else if (!armed) {
      reason = '语音引擎未就绪，生成已禁用。';
    } else if (!snapshot.voices.length) {
      reason = '先在左侧新建一个音色。';
    } else if (!snapshot.selectedVoiceId) {
      reason = '先选择一个音色。';
    } else if (selectedBroken) {
      reason = '选中的音色文件缺失，请换一个。';
    } else if (!text) {
      reason = '输入要合成的文本。';
    } else {
      reason = 'Ctrl+Enter 也可以生成。';
    }
    generateButton.disabled = Boolean(busy
      || !armed
      || selectedBroken
      || !snapshot.selectedVoiceId
      || !snapshot.voices.length
      || !text);
    generateButton.textContent = busy ? '生成中…' : '生成语音';
    setText(generateHint, reason);

    const emotionReady = Boolean(armed && caps.emotion !== false);
    verifySwitch.disabled = busy || !emotionReady;
    verifySwitch.setAttribute(
      'aria-checked',
      String(Boolean(snapshot.synth.verify) && emotionReady),
    );
    setText(
      verifyNote,
      caps.emotion === false
        ? '情绪服务不可用，校验已关闭。'
        : '用情绪模型复核并排序候选。',
    );

    const qualityBest = snapshot.synth.quality === 'best';
    bestRange.disabled = !qualityBest || busy;
    speedRange.disabled = busy;
    chips.setDisabled(busy);
    modeControl.setDisabled(busy);
    qualityControl.setDisabled(busy);
    setText(bestHint, qualityBest ? '' : '质量选「最佳」后可用');
  }

  /**
   * Send the form to POST /api/tts.
   * @returns {Promise<void>} Resolves when the request settles.
   */
  async function generate() {
    const snapshot = store.getState();
    if (busy || generateButton.disabled) {
      return;
    }
    const text = textarea.value.trim();
    const voice = snapshot.voices.find(
      (item) => String(item.voice_id) === snapshot.selectedVoiceId,
    );
    busy = true;
    store.setState({
      busy: {...snapshot.busy, synth: true},
    });
    syncAvailability(store.getState());

    const form = new FormData();
    const caps = snapshot.health && snapshot.health.capabilities
      ? snapshot.health.capabilities
      : {};
    const verify = Boolean(snapshot.synth.verify) && caps.emotion !== false;
    form.append('voice_id', snapshot.selectedVoiceId || '');
    form.append('text', text);
    form.append('emotion', chips.getValue());
    form.append('mode', snapshot.synth.mode);
    form.append('speed', String(snapshot.synth.speed));
    form.append('quality', snapshot.synth.quality);
    form.append(
      'best_n',
      String(snapshot.synth.quality === 'best' ? snapshot.synth.bestN : 1),
    );
    form.append('verify', verify ? 'true' : 'false');
    if (snapshot.synth.instructText.trim()) {
      form.append('instruct_text', snapshot.synth.instructText.trim());
    }
    if (snapshot.synth.emoVoiceId) {
      form.append('emo_voice_id', snapshot.synth.emoVoiceId);
    }

    try {
      const result = await synthesize(form);
      store.setState({
        lastResult: result,
        lastResultVoiceName: (voice && voice.name) || '',
      });
      if (log) {
        log(`合成完成：${result.engine || 'unknown'} · `
          + `${result.mode || ''} · ${result.latency}s`, 'success');
      }
      if (Array.isArray(result.warnings) && result.warnings.length) {
        toast.warn(result.warnings[0]);
      }
    } catch (error) {
      const message = error && error.message ? error.message : '合成失败';
      toast.error(message);
      if (log) {
        log(`合成失败：${message}`, 'error');
      }
    } finally {
      busy = false;
      store.setState({busy: {...store.getState().busy, synth: false}});
      syncAvailability(store.getState());
    }
  }

  on(voiceSelect, 'change', () => {
    store.setState({selectedVoiceId: voiceSelect.value});
  });
  on(textarea, 'input', () => {
    updateCounter();
    store.patchSynth({text: textarea.value});
    syncAvailability(store.getState());
  });
  on(textarea, 'keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      generate();
    }
  });
  on(speedRange, 'input', () => {
    setText(speedValue, `${Number(speedRange.value).toFixed(2)}×`);
    store.patchSynth({speed: Number(speedRange.value)});
  });
  on(bestRange, 'input', () => {
    setText(bestValue, bestRange.value);
    store.patchSynth({bestN: Number(bestRange.value)});
  });
  on(verifySwitch, 'click', () => {
    if (verifySwitch.disabled) {
      return;
    }
    store.patchSynth({verify: !store.getState().synth.verify});
  });
  on(instructInput, 'input', () => {
    store.patchSynth({instructText: instructInput.value});
  });
  on(emoSelect, 'change', () => {
    store.patchSynth({emoVoiceId: emoSelect.value});
  });
  on(generateButton, 'click', generate);

  /**
   * Render the view from store state.
   * @param {Object} snapshot Store state.
   * @returns {void}
   */
  function render(snapshot) {
    const voices = Array.isArray(snapshot.voices) ? snapshot.voices : [];
    const signature = signatureFor(voices);
    if (signature !== voicesSignature) {
      voicesSignature = signature;
      fillVoices(voiceSelect, voices, false);
    }
    if (voiceSelect.value !== (snapshot.selectedVoiceId || '')
      && snapshot.selectedVoiceId) {
      voiceSelect.value = snapshot.selectedVoiceId;
    }

    const emoSignatureNext = signature;
    if (emoSignatureNext !== emoSignature) {
      emoSignature = emoSignatureNext;
      fillVoices(emoSelect, voices, true);
    }
    if (emoSelect.value !== snapshot.synth.emoVoiceId) {
      emoSelect.value = snapshot.synth.emoVoiceId;
    }

    if (snapshot.synth.text !== textarea.value
      && document.activeElement !== textarea) {
      textarea.value = snapshot.synth.text;
      updateCounter();
    }
    if (snapshot.synth.emotion
      && chips.getValue() !== snapshot.synth.emotion) {
      chips.setValue(snapshot.synth.emotion);
    }
    if (modeControl.getValue() !== snapshot.synth.mode) {
      modeControl.setValue(snapshot.synth.mode);
    }
    if (qualityControl.getValue() !== snapshot.synth.quality) {
      qualityControl.setValue(snapshot.synth.quality);
    }
    if (speedRange.value !== String(snapshot.synth.speed)) {
      speedRange.value = String(snapshot.synth.speed);
      setText(speedValue, `${Number(snapshot.synth.speed).toFixed(2)}×`);
    }
    if (bestRange.value !== String(snapshot.synth.bestN)) {
      bestRange.value = String(snapshot.synth.bestN);
      setText(bestValue, String(snapshot.synth.bestN));
    }
    if (instructInput.value !== snapshot.synth.instructText) {
      instructInput.value = snapshot.synth.instructText;
    }
    setHidden(
      instructField,
      !['instruct2', 'hybrid'].includes(snapshot.synth.mode),
    );

    if (snapshot.lastResult !== renderedResult) {
      renderedResult = snapshot.lastResult;
      if (snapshot.lastResult) {
        resultCard.show(snapshot.lastResult, snapshot.lastResultVoiceName);
        setHidden(empty, true);
      } else {
        resultCard.clear();
        setHidden(empty, false);
      }
    }

    const limit = textLimit(snapshot);
    if (textarea.maxLength !== limit) {
      textarea.maxLength = limit;
      updateCounter();
    }

    syncAvailability(snapshot);
  }

  store.subscribe(render);
  render(store.getState());

  return {el: root};
}
