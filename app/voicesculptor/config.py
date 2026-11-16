"""路径常量与运行时配置。

所有环境变量只在这里读取一次，其余模块通过 Settings 拿到配置，
避免同一变量在不同模块里被解析成不同值。
"""

import dataclasses
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(APP_DIR)
STATIC_DIR = os.path.join(APP_DIR, 'static')
DEFAULT_VOICE_DIR = os.path.join(APP_DIR, 'voices')
DEFAULT_LOG_DIR = os.path.join(ROOT_DIR, 'logs')
ROXY_SEL = os.path.join(ROOT_DIR, 'runtime', 'roxy-refs-selected')
ROXY_ORIG = os.path.join(ROOT_DIR, 'runtime', 'roxy-emotions-orig')
DEFAULT_MODEL_DIR = os.path.join(ROOT_DIR, 'engine', 'CosyVoice',
                                 'pretrained_models', 'Fun-CosyVoice3-0.5B')

DEFAULT_COSYVOICE_BASE = 'http://127.0.0.1:50000'
DEFAULT_EMOTION_BASE = 'http://127.0.0.1:50001'
DEFAULT_PORT = 8091
DEFAULT_HOST = '127.0.0.1'


def _clean_path(value: str) -> str:
    """去掉用户填写的引号与尾部斜杠；空值返回空串。"""
    return (value or '').strip().strip('"').rstrip('\\/')


@dataclasses.dataclass(frozen=True)
class Settings:
    """进程级配置快照。"""

    model_dir: str
    voice_dir: str
    log_dir: str
    cosyvoice_base: str
    emotion_base: str
    emotion_rank: bool
    max_text_chars: int
    max_synth_per_req: int
    tts_concurrency: int
    tts_queue_timeout: float

    @property
    def campplus_path(self) -> str:
        """CAM++ 说话人评测模型的绝对路径。"""
        return os.path.join(self.model_dir, 'campplus.onnx')

    @classmethod
    def from_env(cls) -> 'Settings':
        """从环境变量构造配置；未设置的项使用默认值。"""
        model_dir = _clean_path(os.environ.get('COSYVOICE_MODEL_DIR', ''))
        return cls(
            model_dir=model_dir or DEFAULT_MODEL_DIR,
            voice_dir=_clean_path(os.environ.get('VS_VOICE_DIR', '')) or
            DEFAULT_VOICE_DIR,
            log_dir=_clean_path(os.environ.get('VS_LOG_DIR', '')) or
            DEFAULT_LOG_DIR,
            cosyvoice_base=os.environ.get('COSYVOICE_BASE',
                                          DEFAULT_COSYVOICE_BASE),
            emotion_base=os.environ.get('EMOTION_BASE', DEFAULT_EMOTION_BASE),
            emotion_rank=os.environ.get('VS_EMOTION_RANK', '1') == '1',
            max_text_chars=int(os.environ.get('VS_MAX_TEXT_CHARS', '500')),
            max_synth_per_req=int(os.environ.get('VS_MAX_SYNTH_PER_REQ', '5')),
            tts_concurrency=int(os.environ.get('VS_TTS_CONCURRENCY', '1')),
            tts_queue_timeout=float(
                os.environ.get('VS_TTS_QUEUE_TIMEOUT', '120')),
        )
