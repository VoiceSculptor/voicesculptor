"""VoiceStore 的单元测试：创建、列表、删除与校验。"""

import io
import json
import os

import numpy as np
import pytest
import soundfile as sf

from voicesculptor.errors import ValidationError
from voicesculptor.errors import VoiceNotFoundError
from voicesculptor.voices.seeds import SeedVoice
from voicesculptor.voices.store import VoiceStore


def _wav_bytes(seconds=6.0, sr=24000, freq=180.0):
    """生成一段可被 soundfile 解析的正弦波 WAV。"""
    count = int(seconds * sr)
    timeline = np.arange(count, dtype=np.float32) / sr
    wave = 0.12 * np.sin(2.0 * np.pi * freq * timeline)
    buffer = io.BytesIO()
    sf.write(buffer, wave, sr, format='WAV')
    return buffer.getvalue()


@pytest.fixture
def store(tmp_path):
    """在临时目录上建一个空的 VoiceStore。"""
    return VoiceStore(str(tmp_path / 'voices'))


def _create(store, **overrides):
    """用一组默认参数创建音色，测试里只覆盖关心的字段。"""
    params = {
        'name': '测试音色',
        'prompt': 'こんにちは',
        'emoji': '',
        'emotion': '开心',
        'group': 'demo',
        'data': _wav_bytes(),
    }
    params.update(overrides)
    return store.create(**params)


def test_create_list_and_delete(store):
    """创建后可列表、可解析，删除后彻底消失。"""
    meta, warnings = _create(store)
    assert warnings == []
    assert meta['voice_id'].startswith('v_')
    assert meta['source'] == 'upload'
    assert meta['preproc'] == 1
    assert meta['emoji'] == '★'
    assert os.path.isfile(
        os.path.join(store.voice_dir, meta['voice_id'], 'ref.wav'))
    listed = store.list_voices()
    assert [item['voice_id'] for item in listed] == [meta['voice_id']]
    loaded, ref_path = store.resolve(meta['voice_id'])
    assert loaded['name'] == '测试音色'
    assert os.path.isfile(ref_path)
    assert store.delete(meta['voice_id']) == {'ok': True}
    assert store.list_voices() == []
    with pytest.raises(VoiceNotFoundError):
        store.resolve(meta['voice_id'])


def test_create_short_audio_rejected(store):
    """原始音频短于 0.5 秒时拒绝创建。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, data=_wav_bytes(0.2))
    assert '0.5~30' in str(caught.value)


def test_create_long_audio_rejected(store):
    """原始音频超过 30 秒时拒绝创建。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, data=_wav_bytes(31.0))
    assert '0.5~30' in str(caught.value)


def test_create_empty_audio_rejected(store):
    """空上传直接拒绝。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, data=b'')
    assert '参考音频为空' in str(caught.value)


def test_create_invalid_emotion_rejected(store):
    """情绪不在白名单时拒绝。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, emotion='暴躁')
    assert 'emotion 只能是' in str(caught.value)


def test_create_invalid_group_rejected(store):
    """分组名含不允许字符时拒绝。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, group='bad group!')
    assert 'group 只能含' in str(caught.value)


def test_create_empty_name_rejected(store):
    """名称只有空白时拒绝。"""
    with pytest.raises(ValidationError) as caught:
        _create(store, name='   ')
    assert str(caught.value) == '名称不能为空且不超过 32 字'


def test_create_too_long_name_rejected(store):
    """名称超过 32 字时拒绝。"""
    with pytest.raises(ValidationError):
        _create(store, name='字' * 33)


def test_create_without_prompt_warns(store):
    """没有转录文本时给出跨语种降级警告。"""
    _meta, warnings = _create(store, prompt='')
    assert any('未填写转录文本' in item for item in warnings)


def test_create_short_reference_warns(store):
    """参考音频短于 3 秒时提示还原度下降。"""
    _meta, warnings = _create(store, data=_wav_bytes(2.0))
    assert any('短于 3 秒' in item for item in warnings)


def test_broken_voice_has_meta_without_ref(store):
    """meta 有效但缺 ref.wav 的音色记为损坏且不可解析。"""
    video_id = 'v_broken01'
    directory = os.path.join(store.voice_dir, video_id)
    os.makedirs(directory)
    with open(os.path.join(directory, 'meta.json'), 'w',
              encoding='utf-8') as handle:
        json.dump({'voice_id': video_id, 'name': '坏'}, handle)
    assert store.broken_voices() == [video_id]
    assert store.list_voices() == []
    with pytest.raises(VoiceNotFoundError) as caught:
        store.resolve(video_id)
    assert '参考音频丢失' in str(caught.value)


def test_corrupted_meta_is_ignored(store):
    """meta.json 不是合法 JSON 时既不列表也不报错。"""
    video_id = 'v_badmeta1'
    directory = os.path.join(store.voice_dir, video_id)
    os.makedirs(directory)
    with open(os.path.join(directory, 'meta.json'), 'w', encoding='utf-8') as f:
        f.write('{not json')
    assert store.list_voices() == []
    assert store.broken_voices() == []


def test_invalid_voice_id_is_not_found(store):
    """非法 id 与路径穿越都按 404 处理。"""
    with pytest.raises(VoiceNotFoundError):
        store.resolve('../etc')
    with pytest.raises(VoiceNotFoundError):
        store.delete('bad id!')


def test_delete_missing_voice_raises(store):
    """删除不存在的音色抛 404。"""
    with pytest.raises(VoiceNotFoundError):
        store.delete('v_not_exist')


def test_hidden_directories_skipped(store):
    """以 . 开头的临时目录不会被当成音色。"""
    os.makedirs(os.path.join(store.voice_dir, '.tmp-v_demo'))
    assert store.list_voices() == []
    assert store.broken_voices() == []


def test_seed_defaults_creates_and_skips(store, tmp_path, monkeypatch):
    """种子音色首次复制，第二次因已存在而跳过。"""
    source = tmp_path / 'seed.wav'
    source.write_bytes(_wav_bytes(2.0))
    seed = SeedVoice('coquettish', '撒娇', str(source), 'テスト')
    monkeypatch.setattr('voicesculptor.voices.seeds.SEED_VOICES', (seed,))
    store.seed_defaults()
    meta, _ref = store.resolve('coquettish')
    assert meta['source'] == 'seed'
    assert meta['group'] == 'roxy'
    assert meta['emotion'] == '撒娇'
    mtime = os.path.getmtime(
        os.path.join(store.voice_dir, 'coquettish', 'ref.wav'))
    store.seed_defaults()
    assert os.path.getmtime(
        os.path.join(store.voice_dir, 'coquettish', 'ref.wav')) == mtime
