"""audio 子包的单测：WAV 头、时长换算、预处理与解码。"""

import io

import numpy as np
import pytest
import soundfile as sf

from voicesculptor.audio import preprocess
from voicesculptor.audio import prosody
from voicesculptor.audio import wav
from voicesculptor.errors import ValidationError


def test_wrap_wav_header():
    pcm = b'\x00\x00' * 100
    data = wav.wrap_wav(pcm, 24000)
    assert data[:4] == b'RIFF'
    assert data[8:12] == b'WAVE'
    assert data[36:40] == b'data'
    assert len(data) == wav.HEADER_BYTES + len(pcm)
    assert data[24:28] == (24000).to_bytes(4, 'little')


def test_pcm_duration_and_even_bytes():
    assert wav.pcm_duration(b'\x00\x00' * 24000) == pytest.approx(1.0)
    assert wav.even_bytes(b'abc') == b'ab'
    assert wav.pcm16_to_float(b'\x00\x00\x00\x40')[1] == pytest.approx(0.5)


def test_decode_audio_rejects_garbage():
    with pytest.raises(ValidationError):
        wav.decode_audio(b'not-an-audio-file')


def test_decode_audio_accepts_wav():
    buf = io.BytesIO()
    sf.write(buf, np.zeros(24000, dtype=np.float32), 24000, format='WAV')
    wave, sample_rate = wav.decode_audio(buf.getvalue())
    assert sample_rate == 24000
    assert len(wave) == 24000


def test_preprocess_pads_tail():
    wave = np.full(24000, 0.1, dtype=np.float32)
    out = preprocess.preprocess_reference(wave, 24000)
    tail = int(24000 * preprocess.TAIL_PAD_SECONDS)
    assert len(out) == len(wave) + tail
    assert np.allclose(out[-tail:], 0)


def test_preprocess_normalizes_loud_peak():
    wave = np.full(24000, 0.9, dtype=np.float32)
    out = preprocess.preprocess_reference(wave, 24000)
    assert float(np.abs(out).max()) == pytest.approx(0.8, abs=1e-6)


def test_preprocess_normalizes_quiet_peak():
    wave = np.full(24000, 0.1, dtype=np.float32)
    out = preprocess.preprocess_reference(wave, 24000)
    assert float(np.abs(out).max()) == pytest.approx(0.6, abs=1e-6)


def test_zscore_handles_constant_values():
    assert prosody.zscore([3.0, 3.0, 3.0]) == [0.0, 0.0, 0.0]
    scaled = prosody.zscore([1.0, 2.0, 3.0])
    assert scaled[1] == pytest.approx(0.0)


def test_prosody_returns_pair_for_silence():
    pitch, energy = prosody.prosody(b'\x00\x00' * 24000)
    assert pitch >= 0.0
    assert energy >= 0.0
