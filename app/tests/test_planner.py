"""SynthesisPlan 的单元测试：auto 判定、换参考与模式降级。"""

import pytest

from voicesculptor import emotions
from voicesculptor.errors import ValidationError
from voicesculptor.synthesis.planner import make_plan
from voicesculptor.synthesis.request import TtsRequest

REF_PATH = '/tmp/ref.wav'


def _request(**overrides):
    """构造一个默认的合法请求，测试里只覆盖关心的字段。"""
    params = {
        'voice_id': 'v_demo',
        'text': '你好',
        'emotion': emotions.DEFAULT_EMOTION,
        'mode': 'auto',
        'speed': 1.0,
        'quality': 'balanced',
        'best_n': 1,
        'verify': False,
        'instruct_text': '',
        'emo_voice_id': '',
    }
    params.update(overrides)
    return TtsRequest(**params)


def _meta(prompt='こんにちは', emotion=None, group='g1', voice_id='v_demo'):
    """构造一份音色元数据。"""
    return {
        'voice_id': voice_id,
        'name': '演示',
        'prompt': prompt,
        'emotion': emotion or emotions.DEFAULT_EMOTION,
        'group': group,
        'source': 'upload',
    }


class _FakeStore:
    """只实现 planner 用到的两个查询。"""

    def __init__(self, sibling=None, emotion_ref=None):
        self.sibling = sibling
        self.emotion_ref = emotion_ref

    def find_emotion_reference(self, meta, emotion):
        """返回预置的兄弟参考。"""
        del meta, emotion
        return self.sibling

    def resolve(self, voice_id):
        """返回预置的情绪参考音色。"""
        del voice_id
        return self.emotion_ref


def test_auto_same_emotion_uses_zero_shot():
    """auto 且情绪与参考一致时直接用 zero_shot。"""
    request = _request(emotion='平静')
    plan = make_plan(request, _meta(emotion='平静'), REF_PATH, _FakeStore())
    assert plan.kind == 'zero_shot'
    assert plan.ref_path == REF_PATH
    assert plan.instruct is None
    assert plan.prompt == 'こんにちは'


def test_auto_prefers_sibling_reference():
    """auto 且同组有目标情绪参考时换用兄弟音色。"""
    sibling_meta = _meta(prompt='兄弟文本', emotion='难过', voice_id='v_sib')
    sibling = (sibling_meta, '/tmp/sib.wav')
    request = _request(emotion='难过')
    plan = make_plan(request, _meta(emotion='平静'), REF_PATH,
                     _FakeStore(sibling=sibling))
    assert plan.kind == 'zero_shot'
    assert plan.ref_meta is sibling_meta
    assert plan.ref_path == '/tmp/sib.wav'
    assert plan.prompt == '兄弟文本'


def test_auto_without_sibling_uses_instruct2():
    """auto 且没有兄弟参考时用 instruct2 表达目标情绪。"""
    request = _request(emotion='难过')
    plan = make_plan(request, _meta(emotion='平静'), REF_PATH, _FakeStore())
    assert plan.kind == 'instruct2'
    assert plan.instruct == emotions.EMOTION_INSTRUCT['难过']
    assert plan.emotion_prompt == emotions.EMOTION_INSTRUCT['难过']


def test_explicit_mode_kept():
    """显式指定模式时不做 auto 判定。"""
    request = _request(mode='instruct2', emotion='开心')
    plan = make_plan(request, _meta(), REF_PATH, _FakeStore())
    assert plan.kind == 'instruct2'


def test_empty_prompt_downgrades_to_cross_lingual():
    """zero_shot 缺转录文本时降级为 cross_lingual。"""
    request = _request(mode='zero_shot')
    plan = make_plan(request, _meta(prompt=''), REF_PATH, _FakeStore())
    assert plan.kind == 'cross_lingual'
    assert plan.prompt == ''


def test_hybrid_without_prompt_uses_instruct2():
    """hybrid 缺转录文本时退到 instruct2，保留指令。"""
    request = _request(mode='hybrid', instruct_text='温柔一点')
    plan = make_plan(request, _meta(prompt=''), REF_PATH, _FakeStore())
    assert plan.kind == 'instruct2'
    assert plan.instruct == '温柔一点'


def test_instruct_without_text_uses_zero_shot():
    """instruct2 既无指令也无内置情绪文案时降级为 zero_shot。"""
    request = _request(mode='instruct2', emotion='古怪')
    plan = make_plan(request, _meta(), REF_PATH, _FakeStore())
    assert plan.kind == 'zero_shot'
    assert plan.instruct is None


def test_split_requires_emo_voice_id():
    """split 缺少情绪参考音色时拒绝。"""
    request = _request(mode='split')
    with pytest.raises(ValidationError) as caught:
        make_plan(request, _meta(), REF_PATH, _FakeStore())
    assert 'emo_voice_id' in str(caught.value)


def test_split_uses_emotion_reference():
    """split 使用情绪音色的参考与转录文本。"""
    emotion_ref = ({'voice_id': 'v_emo', 'prompt': '情绪文本'}, '/tmp/emo.wav')
    request = _request(mode='split', emo_voice_id='v_emo')
    plan = make_plan(request, _meta(), REF_PATH,
                     _FakeStore(emotion_ref=emotion_ref))
    assert plan.kind == 'split'
    assert plan.emo_ref == '/tmp/emo.wav'
    assert plan.emo_prompt == '情绪文本'


def test_split_without_emotion_prompt_rejected():
    """情绪参考音色缺转录文本时 split 不可用。"""
    emotion_ref = ({'voice_id': 'v_emo', 'prompt': ''}, '/tmp/emo.wav')
    request = _request(mode='split', emo_voice_id='v_emo')
    with pytest.raises(ValidationError) as caught:
        make_plan(request, _meta(), REF_PATH,
                  _FakeStore(emotion_ref=emotion_ref))
    assert '缺少转录文本' in str(caught.value)
