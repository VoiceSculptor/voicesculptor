"""Tests for the emotion service HTTP API."""

# pytest 的 fixture 注入会与模块级同名函数重名，这里按 pytest 惯例放行。
# pylint: disable=redefined-outer-name

import io
import math

from fastapi import testclient
import numpy as np
import pytest
import soundfile

from voicesculptor_emotion import api
from voicesculptor_emotion import classifier as emotion_classifier
from voicesculptor_emotion import config

SAMPLE_RATE = 16000


class FakeModel:
    """Stand-in for a FunASR AutoModel that always returns fixed scores."""

    def generate(self, path, granularity='utterance', extract_embedding=False):
        """Ignores its input and returns one fixed result entry."""
        del path, granularity, extract_embedding
        return [{
            'labels': ['生气/angry', '开心/happy', '平静/neutral'],
            'scores': [0.7, 0.2, 0.1],
        }]


def make_wav(seconds=1.0, amplitude=0.5, frequency=440.0):
    """Returns WAV bytes for a sine tone (silence when amplitude is 0)."""
    frames = int(seconds * SAMPLE_RATE)
    times = np.arange(frames) / SAMPLE_RATE
    samples = amplitude * np.sin(2 * math.pi * frequency * times)
    buffer = io.BytesIO()
    audio = samples.astype(np.float32)
    soundfile.write(buffer, audio, SAMPLE_RATE, format='WAV')
    return buffer.getvalue()


@pytest.fixture()
def client():
    """Returns a TestClient backed by a classifier with a fake model."""
    settings = config.Settings(model='fake-model', device='cpu')
    service = emotion_classifier.EmotionClassifier(
        settings, model_factory=lambda **kwargs: FakeModel())
    return testclient.TestClient(api.create_app(service))


def test_empty_file_returns_422(client):
    response = client.post('/emotion', files={'file': ('a.wav', b'')})
    assert response.status_code == 422
    assert response.json()['detail'] == '音频为空'


def test_oversized_file_returns_413(client):
    payload = b'\x00' * (20 * 1024 * 1024 + 1)
    response = client.post('/emotion', files={'file': ('a.wav', payload)})
    assert response.status_code == 413
    assert response.json()['detail'] == '音频过大（上限 20MB）'


def test_short_file_returns_422(client):
    response = client.post('/emotion', files={'file': ('a.wav', make_wav(0.1))})
    assert response.status_code == 422
    assert response.json()['detail'] == '音频短于 0.3 秒'


def test_undecodable_file_returns_422(client):
    response = client.post('/emotion',
                           files={'file': ('a.wav', b'not an audio file')})
    assert response.status_code == 422
    assert response.json()['detail'] == '无法识别的音频文件'


def test_silence_returns_unknown(client):
    response = client.post('/emotion',
                           files={'file': ('a.wav', make_wav(1.0, 0.0))})
    body = response.json()
    assert response.status_code == 200
    assert body['label'] == 'unknown'
    assert body['cn'] == '未知'
    assert body['reason'] == 'silence'
    assert body['scores'] == {}
    assert body['cn_scores'] == {}


def test_normal_audio_returns_chinese_label(client):
    response = client.post('/emotion', files={'file': ('a.wav', make_wav())})
    body = response.json()
    assert response.status_code == 200
    assert body['label'] == 'angry'
    assert body['cn'] == '生气'
    assert body['cn_scores'] == {'生气': 0.7, '开心': 0.2, '平静': 0.1}
    assert 'reason' not in body


def test_health_reports_fields(client):
    body = client.get('/health').json()
    assert body == {
        'ok': True,
        'model': 'fake-model',
        'device': 'cpu',
        'loaded': False,
    }


def test_health_reports_loaded_after_classify(client):
    client.post('/emotion', files={'file': ('a.wav', make_wav())})
    body = client.get('/health').json()
    assert body['loaded'] is True
