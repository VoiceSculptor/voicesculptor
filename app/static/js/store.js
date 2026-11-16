/**
 * Application state, shared constants and a tiny observable store.
 * @module store
 */

/**
 * The six emotions supported by the backend, in display order.
 * @type {ReadonlyArray<{slug: string, cn: string, en: string}>}
 */
export const EMOTIONS = Object.freeze([
  {slug: 'coquettish', cn: '撒娇', en: 'coquettish'},
  {slug: 'happy', cn: '开心', en: 'happy'},
  {slug: 'sad', cn: '难过', en: 'sad'},
  {slug: 'angry', cn: '生气', en: 'angry'},
  {slug: 'calm', cn: '平静', en: 'calm'},
  {slug: 'surprise', cn: '惊讶', en: 'surprise'},
]);

const CN_TO_SLUG = new Map(EMOTIONS.map((item) => [item.cn, item.slug]));
const SLUG_TO_CN = new Map(EMOTIONS.map((item) => [item.slug, item.cn]));
const EN_TO_SLUG = new Map(EMOTIONS.map((item) => [item.en, item.slug]));

/**
 * Map an emotion name in Chinese, English or slug form to its slug.
 * @param {string} name Emotion label from the UI or the backend.
 * @returns {string} Known slug, or an empty string.
 */
export function emotionSlug(name) {
  const text = String(name || '').trim();
  return CN_TO_SLUG.get(text) || EN_TO_SLUG.get(text.toLowerCase()) || '';
}

/**
 * Map an emotion name or slug to its Chinese label.
 * @param {string} name Emotion label or slug.
 * @returns {string} Chinese label, or the original text.
 */
export function emotionCn(name) {
  const text = String(name || '').trim();
  const slug = SLUG_TO_CN.has(text) ? text : emotionSlug(text);
  return SLUG_TO_CN.get(slug) || text;
}

/**
 * Modes accepted by POST /api/tts with their short UI labels.
 * @type {ReadonlyArray<{value: string, label: string}>}
 */
export const MODES = Object.freeze([
  {value: 'auto', label: '自动'},
  {value: 'zero_shot', label: '零样本'},
  {value: 'cross_lingual', label: '跨语种'},
  {value: 'instruct2', label: '指令'},
  {value: 'hybrid', label: '混合'},
  {value: 'split', label: '分段'},
]);

/**
 * Quality presets accepted by POST /api/tts.
 * @type {ReadonlyArray<{value: string, label: string}>}
 */
export const QUALITIES = Object.freeze([
  {value: 'fast', label: '快速'},
  {value: 'balanced', label: '均衡'},
  {value: 'best', label: '最佳'},
]);

/** @type {Object} */
const DEFAULT_SYNTH = Object.freeze({
  text: '',
  emotion: '平静',
  mode: 'auto',
  quality: 'balanced',
  speed: 1,
  bestN: 1,
  verify: true,
  instructText: '',
  emoVoiceId: '',
});

/** @type {Object} */
const DEFAULT_STATE = Object.freeze({
  connection: 'init',
  error: '',
  health: null,
  env: null,
  voices: [],
  selectedVoiceId: null,
  synth: DEFAULT_SYNTH,
  busy: {synth: false, emotion: false, audit: false, env: false},
  lastResult: null,
  lastResultVoiceName: '',
  emotion: null,
  emotionSource: '',
  audit: null,
  view: 'synth',
});

/**
 * Create an observable store holding the whole UI state.
 * @param {Object} [initial] Optional state overrides.
 * @returns {{getState: Function, setState: Function, patchSynth: Function,
 *   subscribe: Function}} Store instance.
 */
export function createStore(initial = {}) {
  const state = {
    ...DEFAULT_STATE,
    ...initial,
    synth: {...DEFAULT_SYNTH, ...(initial.synth || {})},
    busy: {...DEFAULT_STATE.busy, ...(initial.busy || {})},
  };
  const listeners = new Set();

  return {
    /**
     * Read the current state object.
     * @returns {Object} Live state, do not mutate.
     */
    getState() {
      return state;
    },

    /**
     * Merge a patch into the state and notify subscribers.
     * @param {Object} patch Partial state.
     * @returns {void}
     */
    setState(patch) {
      if (!patch) {
        return;
      }
      Object.assign(state, patch);
      for (const listener of listeners) {
        listener(state, patch);
      }
    },

    /**
     * Merge a patch into the synthesis form state.
     * @param {Object} patch Partial synthesis settings.
     * @returns {void}
     */
    patchSynth(patch) {
      state.synth = {...state.synth, ...patch};
      for (const listener of listeners) {
        listener(state, {synth: state.synth});
      }
    },

    /**
     * Listen for state changes.
     * @param {Function} listener Called with (state, patch) on every change.
     * @returns {Function} Unsubscribe function.
     */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

/** Shared singleton store used by the app shell and views. */
export const store = createStore();
