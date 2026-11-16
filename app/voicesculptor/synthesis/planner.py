"""把规范化请求规划成一次具体的引擎调用。"""

import dataclasses

from voicesculptor import emotions
from voicesculptor.errors import ValidationError
from voicesculptor.synthesis.request import TtsRequest
from voicesculptor.voices import store as voice_store

INSTRUCT_KINDS = ('instruct2', 'hybrid')


@dataclasses.dataclass
class SynthesisPlan:
    """一次合成要用的参考音频、提示词与引擎模式。"""

    kind: str
    ref_meta: dict[str, object]
    ref_path: str
    prompt: str
    instruct: str | None
    emotion_prompt: str | None
    emo_ref: str | None
    emo_prompt: str


def make_plan(request: TtsRequest, meta: dict[str, object], ref_path: str,
              store: voice_store.VoiceStore) -> SynthesisPlan:
    """按 auto 规则与降级顺序算出本次合成计划。

    Args:
        request: 已校验的合成请求。
        meta: 主音色的元数据。
        ref_path: 主音色的参考音频路径。
        store: 音色库，用于查同组情绪参考与 split 的情绪音色。

    Returns:
        确定模式、参考音频与提示词的计划。

    Raises:
        ValidationError: split 缺少情绪音色或该音色没有转录文本。
    """
    kind = request.mode
    ref_meta = meta
    emo_ref = None
    emo_prompt = ''
    if kind == 'auto':
        if request.emotion == voice_store.voice_emotion(meta):
            kind = 'zero_shot'
        else:
            sibling = store.find_emotion_reference(meta, request.emotion)
            if sibling is not None:
                ref_meta, ref_path = sibling
                kind = 'zero_shot'
            else:
                kind = 'instruct2'
    if kind == 'split':
        if not request.emo_voice_id:
            raise ValidationError('split 模式需要 emo_voice_id（情绪参考音色）')
        emo_meta, emo_ref = store.resolve(request.emo_voice_id)
        emo_prompt = str(emo_meta.get('prompt') or '').strip()
        if not emo_prompt:
            raise ValidationError('情绪参考音色缺少转录文本，split 模式不可用')
    prompt = str(ref_meta.get('prompt') or '').strip()
    emotion_prompt = (request.instruct_text or
                      emotions.EMOTION_INSTRUCT.get(request.emotion))
    instruct = emotion_prompt if kind in INSTRUCT_KINDS else None
    if kind in INSTRUCT_KINDS and not instruct:
        kind = 'zero_shot'
        instruct = None
    if kind == 'hybrid' and not prompt:
        kind = 'instruct2'
    if kind == 'zero_shot' and not prompt:
        kind = 'cross_lingual'
    return SynthesisPlan(kind=kind,
                         ref_meta=ref_meta,
                         ref_path=ref_path,
                         prompt=prompt,
                         instruct=instruct,
                         emotion_prompt=emotion_prompt,
                         emo_ref=emo_ref,
                         emo_prompt=emo_prompt)
