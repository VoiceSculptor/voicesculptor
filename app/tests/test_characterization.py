"""特征测试：锁定旧接口的对外行为，重构后必须保持一致。"""

# pytest 的 fixture 注入会与模块级同名函数重名，这里按 pytest 惯例放行。
# pylint: disable=redefined-outer-name

import base64
import io
import os

from fastapi.testclient import TestClient
import numpy as np
import pytest
import soundfile as sf

from voicesculptor import config
from voicesculptor import main as app_main

SETTINGS = config.Settings.from_env()
client = TestClient(app_main.create_app(), raise_server_exceptions=False)
MODEL_ONNX = SETTINGS.campplus_path
HAS_MODEL = os.path.isfile(MODEL_ONNX)


def _wav_bytes(seconds=6.0, sr=24000, freq=180.0):
    """生成一段可被 soundfile 解析的正弦波 WAV。"""
    count = int(seconds * sr)
    t = np.arange(count, dtype=np.float32) / sr
    wave = 0.12 * np.sin(2.0 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, wave, sr, format='WAV')
    return buf.getvalue()


@pytest.fixture(scope='module')
def sample_voice():
    """建一个临时音色，测试结束后删除。"""
    resp = client.post('/api/voices',
                       data={
                           'name': '特征测试',
                           'prompt': '你好',
                           'emotion': '平静',
                           'emoji': 'T',
                           'group': ''
                       },
                       files={'ref': ('ref.wav', _wav_bytes(), 'audio/wav')})
    assert resp.status_code == 200, resp.text
    meta = resp.json()
    assert 'warnings' in meta
    try:
        yield meta
    finally:
        client.delete('/api/voices/' + meta['voice_id'])


def test_health_contains_engines():
    resp = client.get('/api/health')
    assert resp.status_code == 200
    body = resp.json()
    assert 'engines' in body
    assert 'voices' in body
    assert 'cosyvoice' in body['engines']
    assert 'model' in body['engines']
    assert 'broken_voices' in body


def test_voices_list_shape():
    resp = client.get('/api/voices')
    assert resp.status_code == 200
    voices = resp.json()['voices']
    assert isinstance(voices, list)
    for meta in voices:
        assert 'voice_id' in meta
        assert os.path.isdir(os.path.join(SETTINGS.voice_dir, meta['voice_id']))
        assert os.path.isfile(
            os.path.join(SETTINGS.voice_dir, meta['voice_id'], 'ref.wav'))


def test_create_and_delete_voice():
    resp = client.post('/api/voices',
                       data={
                           'name': '临时',
                           'prompt': '',
                           'emotion': '开心'
                       },
                       files={'ref': ('ref.wav', _wav_bytes(3.0), 'audio/wav')})
    assert resp.status_code == 200, resp.text
    meta = resp.json()
    vid = meta['voice_id']
    ids = [v['voice_id'] for v in client.get('/api/voices').json()['voices']]
    assert vid in ids
    assert client.delete('/api/voices/' + vid).status_code == 200
    ids = [v['voice_id'] for v in client.get('/api/voices').json()['voices']]
    assert vid not in ids


def test_delete_missing_voice_404():
    assert client.delete('/api/voices/v_not_exist_9f').status_code == 404


def test_create_voice_rejects_short_audio():
    resp = client.post('/api/voices',
                       data={
                           'name': '太短',
                           'emotion': '平静'
                       },
                       files={'ref': ('ref.wav', _wav_bytes(0.2), 'audio/wav')})
    assert resp.status_code == 422


def test_tts_text_too_long_422(sample_voice):
    resp = client.post('/api/tts',
                       data={
                           'voice_id': sample_voice['voice_id'],
                           'text': '啊' * (SETTINGS.max_text_chars + 1),
                           'mode': 'zero_shot',
                       })
    assert resp.status_code == 422


def test_tts_bad_mode_422(sample_voice):
    resp = client.post('/api/tts',
                       data={
                           'voice_id': sample_voice['voice_id'],
                           'text': '你好',
                           'mode': 'nope',
                       })
    assert resp.status_code == 422


@pytest.mark.skipif(not HAS_MODEL, reason='缺少 campplus.onnx')
def test_tts_normal_path(sample_voice):
    resp = client.post('/api/tts',
                       data={
                           'voice_id': sample_voice['voice_id'],
                           'text': '你好',
                           'emotion': '平静',
                           'mode': 'zero_shot',
                           'quality': 'balanced',
                           'best_n': 1,
                           'verify': 'false',
                       })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 'audio_base64' in body
    raw = base64.b64decode(body['audio_base64'])
    assert raw[:4] == b'RIFF'
    assert len(raw) > 1000
    assert 'duration' in body and body['duration'] > 0
    assert body['engine'] == 'cosyvoice'
    assert body['mode'] in ('zero_shot', 'cross_lingual', 'instruct2', 'hybrid',
                            'split')
