/**
 * Sidebar voice library: search, group headings, selection and deletion.
 * @module components/voice-list
 */

import { clear, el, on } from '../dom.js';
import { emotionCn, emotionSlug } from '../store.js';

/**
 * Group voices by their `group` field, keeping 默认 on top.
 * @param {Array<Object>} voices Voice metadata.
 * @returns {Map<string, Array<Object>>} Group name to voices.
 */
function groupVoices(voices) {
  const groups = new Map();
  for (const voice of voices) {
    const name = String(voice.group || '默认').trim() || '默认';
    if (!groups.has(name)) {
      groups.set(name, []);
    }
    groups.get(name).push(voice);
  }
  return new Map(
    Array.from(groups.entries()).sort(([left], [right]) => {
      if (left === right) {
        return 0;
      }
      if (left === '默认') {
        return -1;
      }
      if (right === '默认') {
        return 1;
      }
      return left.localeCompare(right, 'zh-CN');
    }),
  );
}

/**
 * Create the voice list controller.
 * @param {HTMLElement} container Host element.
 * @param {Object} [handlers] Callbacks.
 * @param {Function} [handlers.onSelect] Receives the chosen voice.
 * @param {Function} [handlers.onDelete] Receives the voice to remove.
 * @returns {{render: Function}} Controller.
 */
export function createVoiceList(container, {onSelect, onDelete} = {}) {
  const search = el('input', {
    class: 'vs-input',
    type: 'search',
    placeholder: '搜索音色',
    'aria-label': '搜索音色',
    autocomplete: 'off',
  });
  const list = el('div', {class: 'vs-voice-groups'});
  container.replaceChildren(
    el('div', {class: 'vs-voice-search'}, search),
    list,
  );

  let voices = [];
  let selectedId = null;
  let broken = new Set();

  /**
   * Render the currently filtered voice list.
   * @returns {void}
   */
  function renderList() {
    clear(list);
    const query = search.value.trim().toLowerCase();
    const filtered = voices.filter((voice) => {
      if (!query) {
        return true;
      }
      const haystack = [
        voice.name,
        voice.prompt,
        voice.group,
        voice.emotion,
      ].join(' ').toLowerCase();
      return haystack.includes(query);
    });

    if (!filtered.length) {
      list.appendChild(el('p', {
        class: 'vs-voice-empty',
        text: voices.length ? '没有匹配的音色' : '还没有音色，点「新建音色」',
      }));
      return;
    }

    for (const [groupName, items] of groupVoices(filtered)) {
      const group = el('div', {class: 'vs-voice-group'},
        el('h3', {class: 'vs-voice-group-title', text: groupName}));
      for (const voice of items) {
        group.appendChild(voiceRow(voice));
      }
      list.appendChild(group);
    }
  }

  /**
   * Build one selectable voice row.
   * @param {Object} voice Voice metadata.
   * @returns {HTMLElement} Row element.
   */
  function voiceRow(voice) {
    const id = String(voice.voice_id || '');
    const isBroken = broken.has(id);
    const selected = id === selectedId;
    const slug = emotionSlug(voice.emotion);
    const emoji = el('span', {
      class: 'vs-voice-emoji',
      text: voice.emoji || '🎙',
    });
    const dot = el('span', {class: 'vs-voice-dot', title: '情绪色点'});
    if (slug) {
      dot.dataset.emotion = slug;
      dot.title = `情绪：${emotionCn(slug)}`;
    }
    const meta = el('span', {class: 'vs-voice-meta'},
      el('span', {class: 'vs-voice-name', text: voice.name || id}),
      el('span', {
        class: 'vs-voice-sub',
        text: voice.prompt || voice.source || '无描述',
      }));

    const button = el('button', {
      type: 'button',
      class: 'vs-voice-item',
      'aria-pressed': String(selected),
    }, emoji, meta, dot);
    if (isBroken) {
      button.disabled = true;
      button.title = '该音色文件缺失或损坏';
    }
    on(button, 'click', () => {
      if (onSelect) {
        onSelect(voice);
      }
    });

    const remove = el('button', {
      type: 'button',
      class: 'vs-icon-button vs-voice-delete',
      'aria-label': `删除音色 ${voice.name || id}`,
      title: '删除音色',
      text: '✕',
    });
    on(remove, 'click', () => {
      if (onDelete) {
        onDelete(voice);
      }
    });

    return el('div', {class: 'vs-voice-row'}, button, remove);
  }

  on(search, 'input', renderList);

  return {
    /**
     * Update the list from store state.
     * @param {Object} state Store state with voices and selection.
     * @returns {void}
     */
    render(state) {
      voices = Array.isArray(state.voices) ? state.voices : [];
      selectedId = state.selectedVoiceId;
      const health = state.health || {};
      broken = new Set(Array.isArray(health.broken_voices)
        ? health.broken_voices.map(String)
        : []);
      renderList();
    },
  };
}
