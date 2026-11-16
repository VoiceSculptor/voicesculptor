"""FastAPI application factory for the emotion service."""

import io

import fastapi
import numpy as np
import soundfile as sf

from voicesculptor_emotion import __version__
from voicesculptor_emotion import classifier as emotion_classifier
from voicesculptor_emotion import labels

# 上传上限与最短音频，与原 server.py 保持一致。
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_AUDIO_SECONDS = 0.3

# FastAPI 的表单字段声明，单独命名以便路由签名保持一行。
_FILE = fastapi.File(...)


def create_app(
        classifier: emotion_classifier.EmotionClassifier) -> fastapi.FastAPI:
    """Creates the FastAPI application bound to ``classifier``.

    Args:
      classifier: Classifier used by ``POST /emotion`` and reported by
        ``GET /health``.

    Returns:
      A configured FastAPI application.
    """
    app = fastapi.FastAPI(
        title='voicesculptor-emotion',
        version=__version__,
    )

    @app.get('/health', response_model=None)
    def health() -> dict[str, object]:
        """Reports model identity, device and load state."""
        return {
            'ok': True,
            'model': classifier.model_name,
            'device': classifier.device,
            'loaded': classifier.is_loaded(),
        }

    @app.post('/emotion', response_model=None)
    def emotion(file: fastapi.UploadFile = _FILE) -> dict[str, object]:
        """Classifies one uploaded audio file."""
        data = file.file.read()
        if not data:
            raise fastapi.HTTPException(422, '音频为空')
        if len(data) > MAX_UPLOAD_BYTES:
            raise fastapi.HTTPException(413, '音频过大（上限 20MB）')
        try:
            wav, sr = sf.read(io.BytesIO(data), dtype='float32')
        except Exception:  # pylint: disable=broad-exception-caught
            raise fastapi.HTTPException(422, '无法识别的音频文件') from None
        if len(wav) < MIN_AUDIO_SECONDS * sr:
            raise fastapi.HTTPException(422, '音频短于 0.3 秒')
        mono = wav.mean(axis=1) if wav.ndim > 1 else wav
        rms = float(np.sqrt(np.mean(np.square(mono))))
        if rms < emotion_classifier.SILENCE_RMS:
            return {
                'label': 'unknown',
                'cn': labels.to_cn('unknown'),
                'scores': {},
                'cn_scores': {},
                'reason': 'silence',
            }
        top, scores = classifier.classify(wav, sr)
        return {
            'label': top,
            'cn': labels.to_cn(top),
            'scores': scores,
            'cn_scores': {
                labels.to_cn(key): value for key, value in scores.items()
            },
        }

    return app
