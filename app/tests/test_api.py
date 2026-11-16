"""API 层测试：健康、环境检测、情绪代理、错误格式、素材体检。"""

import dataclasses
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


def _wav_bytes(seconds=2.0, sr=24000, freq=200.0):
    """生成一段可被 soundfile 解析的正弦波 WAV。"""
    count = int(seconds * sr)
    t = np.arange(count, dtype=np.float32) / sr
    wave = 0.12 * np.sin(2.0 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, wave, sr, format='WAV')
    return buf.getvalue()


def test_health_has_capabilities():
    resp = client.get('/api/health')
    assert resp.status_code == 200
    body = resp.json()
    caps = body['capabilities']
    for key in ('synthesize', 'similarity', 'emotion', 'clone'):
        assert isinstance(caps[key], bool)
    assert isinstance(caps['formats'], list)
    assert 'wav' in caps['formats']


def test_env_returns_twelve_checks():
    resp = client.get('/api/env', params={'refresh': 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body['checks']) == 12
    ids = [item['id'] for item in body['checks']]
    assert 'python' in ids
    assert 'cosyvoice' in ids
    assert 'proxy' in ids
    for item in body['checks']:
        assert item['level'] in ('OK', 'WARN', 'FAIL')
        assert isinstance(item['message'], str)


def test_env_never_returns_error():
    resp = client.get('/api/env')
    assert resp.status_code == 200


def test_emotion_proxy_returns_label():
    resp = client.post('/api/emotion',
                       files={'file': ('a.wav', _wav_bytes(), 'audio/wav')})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['label'] == 'happy'
    assert body['cn'] == '开心'


def test_emotion_rejects_empty_file():
    resp = client.post('/api/emotion',
                       files={'file': ('a.wav', b'', 'audio/wav')})
    assert resp.status_code == 422


def test_error_envelope_has_code():
    resp = client.delete('/api/voices/v_not_exist_9f')
    assert resp.status_code == 404
    body = resp.json()
    assert body['code'] == 'VoiceNotFoundError'
    assert 'detail' in body


def test_index_page_served():
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'text/html' in resp.headers['content-type']


def test_static_js_served_with_module_mime():
    resp = client.get('/static/js/main.js')
    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('text/javascript')


def test_audit_writes_report(tmp_path):
    wav_path = tmp_path / 'a.wav'
    wav_path.write_bytes(_wav_bytes(3.0))
    resp = client.post('/api/audit', data={'dir_path': str(tmp_path)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['ok'] is True
    assert os.path.isfile(body['report_path'])
    assert '# 素材体检报告' in body['report']


def _client_with(**overrides):
    """用改过的配置另建一个应用，避免影响共享 client。"""
    settings = dataclasses.replace(SETTINGS, **overrides)
    return TestClient(app_main.create_app(settings),
                      raise_server_exceptions=False)


def test_emotion_service_down_503():
    down = _client_with(emotion_base='http://127.0.0.1:1')
    resp = down.post('/api/emotion',
                     files={'file': ('a.wav', _wav_bytes(), 'audio/wav')})
    assert resp.status_code == 503


def test_tts_engine_down_503():
    down = _client_with(cosyvoice_base='http://127.0.0.1:1')
    created = down.post(
        '/api/voices',
        data={
            'name': '引擎宕机',
            'prompt': '你好',
            'emotion': '平静'
        },
        files={'ref': ('ref.wav', _wav_bytes(3.0), 'audio/wav')})
    assert created.status_code == 200, created.text
    vid = created.json()['voice_id']
    try:
        resp = down.post('/api/tts',
                         data={
                             'voice_id': vid,
                             'text': '你好',
                             'emotion': '平静'
                         })
        assert resp.status_code == 503
    finally:
        down.delete('/api/voices/' + vid)


@pytest.mark.skipif(not os.path.isfile(SETTINGS.campplus_path),
                    reason='缺少 campplus.onnx')
def test_tts_response_has_warnings_and_scores():
    created = client.post(
        '/api/voices',
        data={
            'name': '临时合成',
            'prompt': '你好',
            'emotion': '平静'
        },
        files={'ref': ('ref.wav', _wav_bytes(3.0), 'audio/wav')})
    assert created.status_code == 200, created.text
    vid = created.json()['voice_id']
    try:
        resp = client.post('/api/tts',
                           data={
                               'voice_id': vid,
                               'text': '你好，世界',
                               'emotion': '平静'
                           })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert 'warnings' in body
        assert 'emotion_scores' in body
        assert body['audio_base64']
    finally:
        client.delete('/api/voices/' + vid)
