/**
 * Thin fetch wrapper around the local backend. Every call rejects with
 * {@link ApiError}; successful calls resolve to the parsed JSON body.
 * @module api
 */

const API_BASE = '/api';
const DEFAULT_TIMEOUT = 30000;
const JOB_TIMEOUT = 300000;

/**
 * Error carrying an HTTP status and a human readable message.
 */
export class ApiError extends Error {
  /**
   * @param {string} message Message to show to the user.
   * @param {number} [status] HTTP status, or 0 for a network failure.
   */
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Perform a JSON request with a timeout and uniform error handling.
 * @param {string} path Path below `/api`.
 * @param {RequestInit} [options] Fetch options.
 * @param {number} [timeout] Timeout in milliseconds.
 * @returns {Promise<?Object>} Parsed body, or null for an empty response.
 */
async function request(path, options = {}, timeout = DEFAULT_TIMEOUT) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw new ApiError('请求超时，请稍后重试', 0);
    }
    throw new ApiError('无法连接后端服务', 0);
  } finally {
    window.clearTimeout(timer);
  }

  let body = null;
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) {
    try {
      body = await response.json();
    } catch (error) {
      body = null;
    }
  }

  if (!response.ok) {
    const detail = body && typeof body.detail === 'string'
      ? body.detail
      : `请求失败（HTTP ${response.status}）`;
    throw new ApiError(detail, response.status);
  }
  return body;
}

/**
 * Read backend health, including engine and capability flags.
 * @returns {Promise<Object>} Health payload.
 */
export function getHealth() {
  return request('/health', {cache: 'no-store'});
}

/**
 * Read environment checks, optionally forcing a fresh probe.
 * @param {boolean} [refresh] Ask the backend to re-run all checks.
 * @returns {Promise<Object>} Environment payload.
 */
export function getEnv(refresh = false) {
  const query = refresh ? '?refresh=1' : '';
  return request(`/env${query}`, {cache: 'no-store'});
}

/**
 * Read the voice library.
 * @returns {Promise<{voices: Array<Object>}>} Voice list payload.
 */
export function getVoices() {
  return request('/voices', {cache: 'no-store'});
}

/**
 * Create a voice from a multipart form.
 * @param {FormData} form Fields name, prompt, emoji, emotion, group, ref.
 * @returns {Promise<Object>} Created voice metadata plus warnings.
 */
export function createVoice(form) {
  return request('/voices', {method: 'POST', body: form}, JOB_TIMEOUT);
}

/**
 * Delete one voice.
 * @param {string} voiceId Voice identifier.
 * @returns {Promise<{ok: boolean}>} Deletion result.
 */
export function deleteVoice(voiceId) {
  return request(`/voices/${encodeURIComponent(voiceId)}`, {
    method: 'DELETE',
  });
}

/**
 * Synthesize speech.
 * @param {FormData} form Multipart payload described by the API contract.
 * @returns {Promise<Object>} Audio, metrics and warnings.
 */
export function synthesize(form) {
  return request('/tts', {method: 'POST', body: form}, JOB_TIMEOUT);
}

/**
 * Classify the emotion of an audio file.
 * @param {Blob|File} audio Audio payload.
 * @param {string} [filename] File name to send with the payload.
 * @returns {Promise<Object>} Emotion label and score maps.
 */
export function detectEmotion(audio, filename = 'audio.wav') {
  const form = new FormData();
  form.append('file', audio, filename);
  return request('/emotion', {method: 'POST', body: form}, JOB_TIMEOUT);
}

/**
 * Audit a directory of recording material.
 * @param {string} dirPath Absolute or workspace relative directory path.
 * @returns {Promise<Object>} Markdown report plus summary counts.
 */
export function runAudit(dirPath) {
  const form = new FormData();
  form.append('dir_path', dirPath);
  return request('/audit', {method: 'POST', body: form}, JOB_TIMEOUT);
}
