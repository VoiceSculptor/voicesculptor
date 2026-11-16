"""应用上下文：把各模块组装成一份依赖图，挂在 app.state 上。"""

import dataclasses

import requests

from voicesculptor.clients import cosyvoice as cosyvoice_client
from voicesculptor.clients import emotion as emotion_client
from voicesculptor.config import Settings
from voicesculptor.envcheck import runner as env_runner
from voicesculptor.speaker import encoder as speaker_encoder
from voicesculptor.synthesis import pipeline as synthesis_pipeline
from voicesculptor.voices import store as voice_store


@dataclasses.dataclass
class AppContext:
    """一次进程内共享的依赖集合。"""

    settings: Settings
    store: voice_store.VoiceStore
    encoder: speaker_encoder.SpeakerEncoder
    cosyvoice: cosyvoice_client.CosyVoiceClient
    emotion: emotion_client.EmotionClient
    pipeline: synthesis_pipeline.SynthesisPipeline
    env_cache: env_runner.EnvCache


def _make_session() -> requests.Session:
    """创建绕开系统代理的会话：本机回环请求不该走代理。"""
    session = requests.Session()
    session.trust_env = False
    return session


def build_context(settings: Settings) -> AppContext:
    """按配置构造全部依赖。"""
    store = voice_store.VoiceStore(settings.voice_dir)
    encoder = speaker_encoder.SpeakerEncoder(settings.model_dir)
    cosyvoice = cosyvoice_client.CosyVoiceClient(settings.cosyvoice_base,
                                                 _make_session())
    emotion = emotion_client.EmotionClient(settings.emotion_base,
                                           _make_session())
    pipeline = synthesis_pipeline.SynthesisPipeline(settings, store, encoder,
                                                    cosyvoice, emotion)
    return AppContext(settings=settings,
                      store=store,
                      encoder=encoder,
                      cosyvoice=cosyvoice,
                      emotion=emotion,
                      pipeline=pipeline,
                      env_cache=env_runner.EnvCache())


def get_context(request) -> AppContext:
    """从请求里取应用上下文。"""
    return request.app.state.ctx
