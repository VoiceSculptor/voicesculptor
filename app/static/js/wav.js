/**
 * Minimal WAV decoder and waveform analysis. No dependencies; used to draw
 * the result waveform and to download synthesized audio.
 * @module wav
 */

const DEFAULT_BUCKETS = 320;

/**
 * Read a four character chunk tag.
 * @param {Uint8Array} bytes Raw file bytes.
 * @param {number} offset Byte offset.
 * @returns {string} Tag such as `RIFF` or `data`.
 */
function readTag(bytes, offset) {
  return String.fromCharCode(
    bytes[offset],
    bytes[offset + 1],
    bytes[offset + 2],
    bytes[offset + 3],
  );
}

/**
 * Decode a base64 string, accepting an optional data URL prefix.
 * @param {string} base64 Base64 payload.
 * @returns {Uint8Array} Decoded bytes, empty when input is blank.
 */
export function base64ToBytes(base64) {
  const clean = String(base64 || '')
    .replace(/^data:[^,]*,/, '')
    .replace(/\s+/g, '');
  if (!clean) {
    return new Uint8Array(0);
  }
  const binary = atob(clean);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

/**
 * Build a WAV blob from a base64 payload.
 * @param {string} base64 Base64 audio.
 * @returns {Blob} Blob with the audio/wav type.
 */
export function blobFromBase64(base64) {
  return new Blob([base64ToBytes(base64)], {type: 'audio/wav'});
}

/**
 * Build a File from a base64 payload for multipart uploads.
 * @param {string} base64 Base64 audio.
 * @param {string} [filename] Name to expose to the backend.
 * @returns {File} WAV file.
 */
export function fileFromBase64(base64, filename = 'result.wav') {
  return new File([base64ToBytes(base64)], filename, {type: 'audio/wav'});
}

/**
 * Read one PCM sample as a float in [-1, 1].
 * @param {DataView} view Data view over the whole file.
 * @param {number} offset Byte offset of the sample.
 * @param {{format: number, bits: number}} info Format information.
 * @returns {number} Sample value.
 */
function readSample(view, offset, info) {
  if (info.format === 3 && info.bits === 32) {
    return view.getFloat32(offset, true);
  }
  if (info.bits === 8) {
    return (view.getUint8(offset) - 128) / 128;
  }
  if (info.bits === 16) {
    return view.getInt16(offset, true) / 32768;
  }
  if (info.bits === 24) {
    let value = view.getUint8(offset)
      | (view.getUint8(offset + 1) << 8)
      | (view.getUint8(offset + 2) << 16);
    if (value & 0x800000) {
      value -= 0x1000000;
    }
    return value / 8388608;
  }
  if (info.bits === 32) {
    return view.getInt32(offset, true) / 2147483648;
  }
  return 0;
}

/**
 * Parse a WAV file and reduce it to peak buckets plus duration.
 * @param {string} base64 Base64 WAV payload.
 * @param {number} [buckets] Number of peak buckets to produce.
 * @returns {?{peaks: Float32Array, duration: number, sampleRate: number}}
 *   Analysis result, or null when the payload is not a readable WAV.
 */
export function analyzeWaveform(base64, buckets = DEFAULT_BUCKETS) {
  const bytes = base64ToBytes(base64);
  if (bytes.length < 44) {
    return null;
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (readTag(bytes, 0) !== 'RIFF' || readTag(bytes, 8) !== 'WAVE') {
    return null;
  }

  let cursor = 12;
  let format = null;
  let dataStart = 0;
  let dataSize = 0;
  while (cursor + 8 <= bytes.length) {
    const id = readTag(bytes, cursor);
    const size = view.getUint32(cursor + 4, true);
    const body = cursor + 8;
    if (id === 'fmt ') {
      const audioFormat = view.getUint16(body, true);
      format = {
        format: audioFormat === 0xfffe
          ? view.getUint16(body + 24, true) || audioFormat
          : audioFormat,
        channels: view.getUint16(body + 2, true),
        sampleRate: view.getUint32(body + 4, true),
        blockAlign: view.getUint16(body + 12, true),
        bits: view.getUint16(body + 14, true),
      };
    } else if (id === 'data') {
      dataStart = body;
      dataSize = Math.min(size, bytes.length - body);
      break;
    }
    cursor = body + size + (size % 2);
  }

  if (!format || !dataSize || !format.sampleRate || !format.blockAlign) {
    return null;
  }

  const frames = Math.floor(dataSize / format.blockAlign);
  const duration = frames / format.sampleRate;
  const peaks = new Float32Array(buckets);
  const framesPerBucket = Math.max(1, Math.ceil(frames / buckets));
  const sampleBytes = Math.max(1, format.bits / 8);
  const channels = Math.max(1, format.channels);
  let loudest = 0;

  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const start = bucket * framesPerBucket;
    const end = Math.min(frames, start + framesPerBucket);
    let peak = 0;
    for (let frame = start; frame < end; frame += 1) {
      for (let channel = 0; channel < channels; channel += 1) {
        const offset = dataStart
          + frame * format.blockAlign
          + channel * sampleBytes;
        if (offset + sampleBytes > dataStart + dataSize) {
          break;
        }
        const value = Math.abs(readSample(view, offset, format));
        if (value > peak) {
          peak = value;
        }
      }
    }
    peaks[bucket] = peak;
    if (peak > loudest) {
      loudest = peak;
    }
  }

  if (loudest > 0) {
    for (let index = 0; index < peaks.length; index += 1) {
      peaks[index] /= loudest;
    }
  }
  return {peaks, duration, sampleRate: format.sampleRate};
}
