/**
 * Result waveform drawn on a canvas from peak buckets. Decorative only;
 * the audio element next to it exposes playback to assistive tech.
 * @module components/waveform
 */

import { el, on } from '../dom.js';

const MIN_BAR = 1.5;
const MAX_DPR = 2;

/**
 * Read a CSS custom property from the document root.
 * @param {string} name Custom property such as `--vs-color-primary`.
 * @param {string} fallback Value used when unset.
 * @returns {string} Resolved colour.
 */
function token(name, fallback) {
  const value = window.getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

/**
 * Create the waveform canvas controller.
 * @returns {{el: HTMLCanvasElement, render: Function, reset: Function}}
 *   Canvas element plus render controls.
 */
export function createWaveform() {
  const canvas = el('canvas', {
    class: 'vs-waveform',
    'aria-hidden': 'true',
  });
  let analysis = null;

  /**
   * Fit the backing store to the CSS box and return a scaled context.
   * @returns {{ctx: CanvasRenderingContext2D, width: number,
   *   height: number}} Drawing context and logical size.
   */
  function prepare() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return {ctx, width, height};
  }

  /**
   * Paint the cached analysis.
   * @returns {void}
   */
  function draw() {
    const {ctx, width, height} = prepare();
    ctx.clearRect(0, 0, width, height);
    const outline = token('--vs-color-outline', '#343b4a');
    const primary = token('--vs-color-primary', '#8ab4f8');
    const center = height / 2;

    ctx.fillStyle = outline;
    ctx.fillRect(0, center - 0.5, width, 1);

    if (!analysis || !analysis.peaks || !analysis.peaks.length) {
      return;
    }

    const peaks = analysis.peaks;
    const step = width / peaks.length;
    const gap = Math.min(2, Math.max(1, step * 0.28));
    const barWidth = Math.max(1, step - gap);
    ctx.fillStyle = primary;
    for (let index = 0; index < peaks.length; index += 1) {
      const amplitude = Math.max(MIN_BAR, peaks[index] * (height - 12));
      const x = index * step + gap / 2;
      ctx.fillRect(x, center - amplitude / 2, barWidth, amplitude);
    }
  }

  /**
   * Render new analysis data.
   * @param {?{peaks: Float32Array}} next Analysis from `wav.js`.
   * @returns {void}
   */
  function render(next) {
    analysis = next;
    draw();
  }

  /**
   * Drop the current waveform and draw the empty baseline.
   * @returns {void}
   */
  function reset() {
    analysis = null;
    draw();
  }

  on(window, 'resize', draw);

  return {el: canvas, render, reset};
}
