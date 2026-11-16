/**
 * Application entry: theme, navigation, health polling, voice library and
 * the four page views.
 * @module main
 */

import { deleteVoice, getHealth, getVoices } from './api.js';
import { createLogDrawer } from './components/log-drawer.js';
import { createStatusChip } from './components/status-chip.js';
import { createToaster } from './components/toast.js';
import { createVoiceDialog } from './components/voice-dialog.js';
import { createVoiceList } from './components/voice-list.js';
import { qs, qsa, on, setHidden, setText } from './dom.js';
import { store } from './store.js';
import { createAuditView } from './views/audit-view.js';
import { createEmotionView } from './views/emotion-view.js';
import { createEnvView } from './views/env-view.js';
import { createSynthView } from './views/synth-view.js';

const THEME_KEY = 'vs-theme';
const HEALTH_INTERVAL = 15000;
const VIEW_NAMES = ['synth', 'emotion', 'audit', 'env'];
let envLoaded = false;

const dom = {
  statusChip: qs('#status-chip'),
  themeToggle: qs('#theme-toggle'),
  themeGlyph: qs('#theme-glyph'),
  connBanner: qs('#conn-banner'),
  connText: qs('#conn-banner-text'),
  capBanner: qs('#cap-banner'),
  capTitle: qs('#cap-banner-title'),
  capText: qs('#cap-banner-text'),
  voiceCount: qs('#voice-count'),
  newVoice: qs('#new-voice'),
  voiceList: qs('#voice-list'),
  logDrawer: qs('#log-drawer'),
  logToggle: qs('#log-toggle'),
  logList: qs('#log-list'),
  logCount: qs('#log-count'),
  logClear: qs('#log-clear'),
  toasts: qs('#toasts'),
  voiceDialog: qs('#voice-dialog'),
  main: qs('#main'),
  navItems: qsa('.vs-nav-item'),
  views: {},
  roots: {},
};

for (const name of VIEW_NAMES) {
  dom.views[name] = qs(`#view-${name}`);
  dom.roots[name] = qs(`#${name}-root`);
}

/**
 * Read the stored theme preference without throwing in private mode.
 * @returns {?string} 'dark', 'light' or null when unset.
 */
function readTheme() {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === 'dark' || value === 'light' ? value : null;
  } catch (error) {
    return null;
  }
}

/**
 * Store the theme preference, ignoring storage failures.
 * @param {string} theme Theme name.
 * @returns {void}
 */
function saveTheme(theme) {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    /* Private mode: theme still applies for this session. */
  }
}

/**
 * Apply a theme and refresh the toggle affordance.
 * @param {string} theme Theme name.
 * @returns {void}
 */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const light = theme === 'light';
  setText(dom.themeGlyph, light ? '☀' : '☾');
  dom.themeToggle.setAttribute('aria-label',
    light ? '切换到深色主题' : '切换到浅色主题');
}

/**
 * Initialise the theme from storage, defaulting to dark.
 * @returns {void}
 */
function initTheme() {
  applyTheme(readTheme() || 'dark');
}

/**
 * Create every view and mount it into its root element.
 * @param {Object} deps Shared dependencies.
 * @param {Object} deps.toast Toast controller.
 * @param {Function} deps.log Log writer.
 * @returns {Object} View controllers.
 */
function mountViews({toast, log}) {
  let emotionView = null;
  const synthView = createSynthView({
    store,
    toast,
    log,
    onAnalyze: (payload) => {
      setView('emotion');
      if (emotionView) {
        emotionView.useResult(payload);
      }
    },
  });
  emotionView = createEmotionView({store, toast, log});
  const auditView = createAuditView({store, toast, log});
  const envView = createEnvView({store, toast, log});

  dom.roots.synth.appendChild(synthView.el);
  dom.roots.emotion.appendChild(emotionView.el);
  dom.roots.audit.appendChild(auditView.el);
  dom.roots.env.appendChild(envView.el);
  return {synthView, emotionView, auditView, envView};
}

/**
 * Show one page view and update the navigation state.
 * @param {string} name View name.
 * @returns {void}
 */
function setView(name) {
  const next = VIEW_NAMES.includes(name) ? name : 'synth';
  store.setState({view: next});
  for (const viewName of VIEW_NAMES) {
    setHidden(dom.views[viewName], viewName !== next);
  }
  for (const item of dom.navItems) {
    if (item.dataset.view === next) {
      item.setAttribute('aria-current', 'page');
    } else {
      item.removeAttribute('aria-current');
    }
  }
  if (dom.main) {
    dom.main.scrollTop = 0;
  }
  if (next === 'env' && !envLoaded) {
    envLoaded = true;
    views.envView.load();
  }
}

/**
 * Update the connection and capability banners.
 * @param {Object} state Store state.
 * @returns {void}
 */
function updateBanners(state) {
  const disconnected = state.connection === 'error';
  setHidden(dom.connBanner, !disconnected);
  if (disconnected) {
    const detail = state.error && state.error !== '无法连接后端服务'
      ? state.error
      : '请确认后端服务已启动（默认端口 8091）。';
    setText(dom.connText, detail);
  }

  let title = '';
  let text = '';
  const health = state.health;
  if (health) {
    const engines = health.engines || {};
    const broken = [];
    if (!engines.cosyvoice) {
      broken.push('CosyVoice');
    }
    if (!engines.model) {
      broken.push('声学模型');
    }
    const caps = health.capabilities || {};
    if (health.ok === false) {
      title = '后端自检未通过';
      text = '打开环境检测查看失败项，修复后会自动解除。';
    } else if (broken.length) {
      title = '合成引擎不可用';
      text = `${broken.join(' / ')} 未就绪，生成已禁用。`;
    } else if (caps.synthesize === false) {
      title = '合成能力不可用';
      text = '后端未启用语音合成，生成已禁用。';
    }
  }
  setHidden(dom.capBanner, !title);
  if (title) {
    setText(dom.capTitle, title);
    setText(dom.capText, text);
  }
}

/**
 * Repaint chrome that depends on shared state.
 * @param {Object} state Store state.
 * @returns {void}
 */
function renderChrome(state) {
  chip.update(state);
  updateBanners(state);
  setText(dom.voiceCount, String(state.voices.length));
  voiceList.render(state);
}

/**
 * Fetch /api/health and fold the result into the store.
 * @returns {Promise<void>} Resolves when the request settles.
 */
async function refreshHealth() {
  const previous = store.getState().connection;
  try {
    const health = await getHealth();
    store.setState({connection: 'ok', error: '', health});
    const broken = health && Array.isArray(health.broken_voices)
      ? health.broken_voices
      : [];
    const selected = store.getState().selectedVoiceId;
    if (selected && broken.includes(selected)) {
      loadVoices();
    }
    if (previous === 'error') {
      log('后端连接已恢复', 'success');
    }
  } catch (error) {
    const message = error && error.message
      ? error.message
      : '无法连接后端服务';
    store.setState({connection: 'error', error: message, health: null});
    if (previous !== 'error') {
      log(`后端连接失败：${message}`, 'error');
    }
  }
}

/**
 * Load the voice library and keep a valid selection.
 * @param {string} [preferredId] Voice to select after the reload.
 * @returns {Promise<void>} Resolves when the request settles.
 */
async function loadVoices(preferredId) {
  try {
    const data = await getVoices();
    const voices = Array.isArray(data.voices) ? data.voices : [];
    const state = store.getState();
    const broken = new Set(
      state.health && Array.isArray(state.health.broken_voices)
        ? state.health.broken_voices
        : [],
    );
    let selected = state.selectedVoiceId;
    const exists = voices.some((voice) => voice.voice_id === selected);
    if (!exists) {
      const first = voices.find((voice) => !broken.has(voice.voice_id))
        || voices[0];
      selected = first ? first.voice_id : null;
    }
    if (preferredId
      && voices.some((voice) => voice.voice_id === preferredId)) {
      selected = preferredId;
    }
    store.setState({voices, selectedVoiceId: selected});
  } catch (error) {
    const message = error && error.message
      ? error.message
      : '音色列表加载失败';
    store.setState({voices: [], selectedVoiceId: null});
    toast.error(message);
    log(`音色列表加载失败：${message}`, 'error');
  }
}

/**
 * Delete one voice after confirmation.
 * @param {Object} voice Voice metadata.
 * @returns {Promise<void>} Resolves when the request settles.
 */
async function removeVoice(voice) {
  const confirmed = window.confirm(
    `删除音色「${voice.name}」？此操作不可撤销。`,
  );
  if (!confirmed) {
    return;
  }
  try {
    await deleteVoice(voice.voice_id);
    toast.success(`已删除「${voice.name}」`);
    log(`已删除音色：${voice.name}`, 'success');
    await loadVoices();
  } catch (error) {
    const message = error && error.message ? error.message : '删除失败';
    toast.error(message);
    log(`删除音色失败：${message}`, 'error');
  }
}

initTheme();

const toast = createToaster(dom.toasts);
const logDrawer = createLogDrawer({
  drawer: dom.logDrawer,
  toggle: dom.logToggle,
  list: dom.logList,
  count: dom.logCount,
  clearButton: dom.logClear,
});
const log = logDrawer.log;

const voiceList = createVoiceList(dom.voiceList, {
  onSelect: (voice) => store.setState({selectedVoiceId: voice.voice_id}),
  onDelete: removeVoice,
});

const views = mountViews({toast, log});

const dialog = createVoiceDialog(dom.voiceDialog, {
  toast,
  getGroups: () => [...new Set(store.getState().voices
    .map((voice) => voice.group)
    .filter(Boolean))],
  onCreated: async (voice) => {
    await loadVoices(voice && voice.voice_id);
    if (voice && voice.name) {
      log(`已创建音色：${voice.name}`, 'success');
    }
  },
});

const chip = createStatusChip(dom.statusChip, {
  onActivate: () => setView('env'),
});

for (const item of dom.navItems) {
  on(item, 'click', () => setView(item.dataset.view));
}

on(dom.newVoice, 'click', () => dialog.open());

on(dom.themeToggle, 'click', () => {
  const next = document.documentElement.dataset.theme === 'light'
    ? 'dark'
    : 'light';
  applyTheme(next);
  saveTheme(next);
});

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    refreshHealth();
  }
});

store.subscribe(renderChrome);
renderChrome(store.getState());
setView('synth');
log('声刻 Studio 已加载', 'info');
loadVoices();
refreshHealth();
window.setInterval(refreshHealth, HEALTH_INTERVAL);
