/**
 * New voice dialog: multipart upload of name, prompt, emoji, emotion,
 * group and a reference clip, with emotion guessed from the file name.
 * @module components/voice-dialog
 */

import { createVoice } from '../api.js';
import { el, on } from '../dom.js';
import { EMOTIONS } from '../store.js';

/**
 * Build the dialog body once and return a controller.
 * @param {HTMLDialogElement} dialog Native dialog element.
 * @param {Object} [handlers] Callbacks.
 * @param {Object} [handlers.toast] Toast controller.
 * @param {Function} [handlers.onCreated] Receives the created voice.
 * @param {Function} [handlers.getGroups] Returns known group names.
 * @returns {{open: Function}} Dialog controller.
 */
export function createVoiceDialog(dialog, {
  toast,
  onCreated,
  getGroups,
} = {}) {
  let emotionTouched = false;
  let busy = false;

  const nameInput = el('input', {
    class: 'vs-input',
    id: 'voice-name',
    name: 'name',
    type: 'text',
    required: true,
    maxlength: 40,
    placeholder: '例如：清亮女声',
    autocomplete: 'off',
  });
  const emojiInput = el('input', {
    class: 'vs-input',
    id: 'voice-emoji',
    name: 'emoji',
    type: 'text',
    maxlength: 8,
    value: '🎙',
    autocomplete: 'off',
  });
  const promptInput = el('textarea', {
    class: 'vs-textarea',
    id: 'voice-prompt',
    name: 'prompt',
    rows: 2,
    placeholder: '参考音频里说了什么，可留空',
  });
  const emotionSelect = el('select', {
    class: 'vs-select',
    id: 'voice-emotion',
    name: 'emotion',
  }, EMOTIONS.map((emotion) => el('option', {
    value: emotion.cn,
    text: emotion.cn,
  })));
  emotionSelect.value = '平静';
  const groupInput = el('input', {
    class: 'vs-input',
    id: 'voice-group',
    name: 'group',
    type: 'text',
    value: '默认',
    maxlength: 24,
    list: 'voice-group-options',
    autocomplete: 'off',
  });
  const groupList = el('datalist', {id: 'voice-group-options'});
  emojiInput.defaultValue = '🎙';
  groupInput.defaultValue = '默认';
  const refInput = el('input', {
    class: 'vs-input',
    id: 'voice-ref',
    name: 'ref',
    type: 'file',
    required: true,
    accept: 'audio/*,.wav,.mp3,.flac,.m4a,.ogg',
  });
  const inferNote = el('p', {class: 'vs-dialog-note'});

  const closeButton = el('button', {
    type: 'button',
    class: 'vs-icon-button',
    'aria-label': '关闭',
    text: '✕',
  });
  const cancelButton = el('button', {
    type: 'button',
    class: 'vs-button vs-button--text',
    text: '取消',
  });
  const submitButton = el('button', {
    type: 'submit',
    class: 'vs-button',
    text: '创建音色',
  });

  const form = el('form', {
    class: 'vs-dialog-form',
    'aria-labelledby': 'voice-dialog-title',
  },
  el('div', {class: 'vs-dialog-head'},
    el('h2', {class: 'vs-dialog-title', id: 'voice-dialog-title',
      text: '新建音色'}),
    closeButton),
  el('div', {class: 'vs-dialog-body'},
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'voice-name', text: '名称'}),
      nameInput),
    el('div', {class: 'vs-dialog-grid'},
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'voice-emoji', text: '图标'}),
        emojiInput),
      el('div', {class: 'vs-field'},
        el('label', {class: 'vs-label', for: 'voice-emotion',
          text: '情绪'}), emotionSelect)),
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'voice-prompt', text: '提示词'}),
      promptInput),
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'voice-group', text: '分组'}),
      groupInput, groupList),
    el('div', {class: 'vs-field'},
      el('label', {class: 'vs-label', for: 'voice-ref',
        text: '参考音频'}), refInput, inferNote)),
  el('div', {class: 'vs-dialog-foot'},
    el('span', {class: 'vs-dialog-note', text: '建议 3–30 秒干净人声'}),
    cancelButton,
    submitButton));

  dialog.replaceChildren(form);

  /**
   * Refresh the group suggestions from the current voice library.
   * @returns {void}
   */
  function refreshGroups() {
    groupList.replaceChildren();
    const groups = typeof getGroups === 'function' ? getGroups() : [];
    for (const name of new Set(groups)) {
      groupList.appendChild(el('option', {value: String(name)}));
    }
  }

  /**
   * Guess an emotion from the selected file path.
   * @param {File} file Chosen reference clip.
   * @returns {string} Matched Chinese label, or an empty string.
   */
  function guessEmotion(file) {
    if (!file) {
      return '';
    }
    const path = String(file.webkitRelativePath || '');
    const haystack = `${path} ${file.name}`.toLowerCase();
    for (const emotion of EMOTIONS) {
      if (haystack.includes(emotion.slug)
        || haystack.includes(emotion.en)
        || haystack.includes(emotion.cn)) {
        return emotion.cn;
      }
    }
    return '';
  }

  on(refInput, 'change', () => {
    const file = refInput.files && refInput.files[0];
    if (!file) {
      inferNote.textContent = '';
      return;
    }
    const guessed = guessEmotion(file);
    if (guessed && !emotionTouched) {
      emotionSelect.value = guessed;
      inferNote.textContent = `已根据文件名预选「${guessed}」`;
    } else {
      inferNote.textContent = `文件：${file.name}`;
    }
  });

  on(emotionSelect, 'change', () => {
    emotionTouched = true;
  });

  on(closeButton, 'click', () => dialog.close());
  on(cancelButton, 'click', () => dialog.close());

  on(dialog, 'click', (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });

  on(form, 'submit', async (event) => {
    event.preventDefault();
    if (busy) {
      return;
    }
    busy = true;
    submitButton.disabled = true;
    submitButton.textContent = '创建中…';
    try {
      const data = await createVoice(new FormData(form));
      const created = data && data.voice ? data.voice : data;
      const warnings = data && Array.isArray(data.warnings)
        ? data.warnings
        : [];
      if (toast) {
        toast.success(`已创建音色「${created && created.name
          ? created.name
          : nameInput.value}」`);
        for (const warning of warnings.slice(0, 3)) {
          toast.warn(String(warning));
        }
      }
      if (onCreated) {
        onCreated(created || null);
      }
      dialog.close();
      form.reset();
      emotionSelect.value = '平静';
      emotionTouched = false;
      inferNote.textContent = '';
    } catch (error) {
      if (toast) {
        toast.error(error && error.message ? error.message : '创建失败');
      }
    } finally {
      busy = false;
      submitButton.disabled = false;
      submitButton.textContent = '创建音色';
    }
  });

  /**
   * Open the dialog with a clean form.
   * @returns {void}
   */
  function open() {
    refreshGroups();
    form.reset();
    emotionSelect.value = '平静';
    emotionTouched = false;
    inferNote.textContent = '';
    if (!dialog.open) {
      dialog.showModal();
    }
    window.requestAnimationFrame(() => nameInput.focus());
  }

  return {open};
}
