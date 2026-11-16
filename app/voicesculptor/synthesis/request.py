"""TTS 请求的校验与规范化。"""

import dataclasses

from voicesculptor import emotions
from voicesculptor.config import Settings
from voicesculptor.errors import ValidationError

MODES = ('auto', 'zero_shot', 'cross_lingual', 'instruct2', 'hybrid', 'split')
QUALITIES = ('fast', 'balanced', 'best')
MIN_SPEED = 0.5
MAX_SPEED = 2.0
MAX_INSTRUCT_CHARS = 200
INVALID_INSTRUCT_PREFIX = '<|'
TRUE_WORDS = ('1', 'true', 'yes', 'on')


@dataclasses.dataclass(frozen=True)
class TtsRequest:
    """一次合成请求的规范化参数。"""

    voice_id: str
    text: str
    emotion: str
    mode: str
    speed: float
    quality: str
    best_n: int
    verify: bool
    instruct_text: str
    emo_voice_id: str


def _as_bool(value: object) -> bool:
    """把表单或 JSON 里的布尔值统一成 bool。"""
    if isinstance(value, str):
        return value.strip().lower() in TRUE_WORDS
    return bool(value)


def _as_int(value: object, default: int) -> int:
    """把值转成整数，缺失时用默认值。"""
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('best_n 必须是整数') from exc


def _as_speed(value: object) -> float:
    """把值转成语速并夹到 0.5~2.0。"""
    if value is None or value == '':
        return 1.0
    try:
        speed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('speed 必须是数字') from exc
    return max(MIN_SPEED, min(MAX_SPEED, speed))


def validate(payload: dict, settings: Settings) -> TtsRequest:
    """校验合成请求并返回不可变的 TtsRequest。

    Args:
        payload: 表单或 JSON 解析出的字段字典。
        settings: 当前配置，提供文本长度上限。

    Returns:
        校验、裁剪后的请求对象。

    Raises:
        ValidationError: 文本、模式、质量、语速或指令不合法。
    """
    voice_id = str(payload.get('voice_id') or '')
    text = str(payload.get('text') or '')
    stripped = text.strip()
    if not stripped:
        raise ValidationError('文本为空')
    if len(stripped) > settings.max_text_chars:
        raise ValidationError(
            f'文本过长：最多 {settings.max_text_chars} 字（当前 {len(stripped)} 字）')
    emotion = str(payload.get('emotion') or emotions.DEFAULT_EMOTION)
    mode = str(payload.get('mode') or 'auto')
    if mode not in MODES:
        raise ValidationError('mode 只能是 ' + '/'.join(MODES))
    quality = str(payload.get('quality') or 'balanced')
    if quality not in QUALITIES:
        raise ValidationError('quality 只能是 ' + '/'.join(QUALITIES))
    speed = _as_speed(payload.get('speed'))
    best_n = _as_int(payload.get('best_n'), 1)
    verify = _as_bool(payload.get('verify'))
    instruct_text = str(payload.get('instruct_text') or '').strip()
    if (len(instruct_text) > MAX_INSTRUCT_CHARS or
            INVALID_INSTRUCT_PREFIX in instruct_text):
        raise ValidationError('instruct_text 不能超过 200 字，且不能含 <|')
    emo_voice_id = str(payload.get('emo_voice_id') or '')
    return TtsRequest(voice_id=voice_id,
                      text=text,
                      emotion=emotion,
                      mode=mode,
                      speed=speed,
                      quality=quality,
                      best_n=best_n,
                      verify=verify,
                      instruct_text=instruct_text,
                      emo_voice_id=emo_voice_id)
