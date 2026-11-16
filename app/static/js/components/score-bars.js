/**
 * Horizontal score bars for emotion probabilities. Accepts either the nine
 * Chinese classes from `/api/emotion` or the six-class English map.
 * @module components/score-bars
 */

import { clear, el } from '../dom.js';
import { emotionCn, emotionSlug } from '../store.js';

const EMPTY = '暂无分数';

/**
 * Create the score bar list.
 * @returns {{el: HTMLElement, render: Function}} Controller.
 */
export function createScoreBars() {
  const root = el('div', {class: 'vs-score-list'});

  /**
   * Render scores sorted from highest to lowest.
   * @param {?Object<string, number>} scores Mapping of label to score.
   * @returns {void}
   */
  function render(scores) {
    clear(root);
    const entries = Object.entries(scores || {})
      .filter(([, value]) => Number.isFinite(Number(value)))
      .map(([label, value]) => ({label, value: Number(value)}))
      .sort((left, right) => right.value - left.value);

    if (!entries.length) {
      root.appendChild(el('p', {class: 'vs-muted', text: EMPTY}));
      return;
    }

    const scale = entries.some((entry) => entry.value > 1.001) ? 100 : 1;
    const best = entries[0].value;
    entries.forEach((entry, index) => {
      const percent = Math.min(100, Math.max(0, entry.value / scale * 100));
      const slug = emotionSlug(entry.label);
      const row = el('div', {
        class: index === 0 && best > 0 ? 'vs-score vs-score--top' : 'vs-score',
      });
      if (slug) {
        row.dataset.emotion = slug;
      }
      const fill = el('span', {class: 'vs-score-fill'});
      fill.style.setProperty('--vs-value', `${percent.toFixed(1)}%`);
      const value = el('span', {
        class: 'vs-score-value',
        text: `${percent.toFixed(0)}%`,
      });
      const label = el('span', {
        class: 'vs-score-label',
        text: emotionCn(entry.label),
      });
      row.appendChild(label);
      row.appendChild(el('span', {class: 'vs-score-track'}, fill));
      row.appendChild(value);
      root.appendChild(row);
    });
  }

  return {el: root, render};
}
