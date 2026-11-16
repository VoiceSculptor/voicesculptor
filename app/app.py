"""兼容入口。

- uvicorn app:app 与 python app.py --port 8091 都走这里；
- 为 demo/batch_voices.py 保留旧名字：VOICE_DIR、list_voices()、
  preprocess_ref()、seed_defaults()、voice_emotion()。
"""

import sys

from voicesculptor import config
from voicesculptor import main as app_main
from voicesculptor.audio import preprocess as audio_preprocess
from voicesculptor.voices import store as voice_store

app = app_main.create_app()

VOICE_DIR = config.DEFAULT_VOICE_DIR


def list_voices() -> list[dict]:
    """列出音色库；旧 demo 依赖这个接口。"""
    return voice_store.VoiceStore(VOICE_DIR).list_voices()


def preprocess_ref(wave, sample_rate: int):
    """参考音频预处理；旧名字是 preprocess_ref。"""
    return audio_preprocess.preprocess_reference(wave, sample_rate)


def seed_defaults() -> None:
    """补齐内置种子音色。"""
    voice_store.VoiceStore(VOICE_DIR).seed_defaults()


def voice_emotion(meta: dict) -> str:
    """从 meta 推导情绪；旧 demo 依赖这个接口。"""
    return voice_store.voice_emotion(meta)


if __name__ == '__main__':
    sys.exit(app_main.main(sys.argv[1:]))
