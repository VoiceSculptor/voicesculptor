"""音色库的磁盘存储：列表、校验、创建、删除与种子音色。"""

import json
import logging
import os
import re
import shutil
import time
import uuid

import soundfile as sf

from voicesculptor import emotions
from voicesculptor.audio import preprocess
from voicesculptor.audio import wav
from voicesculptor.errors import PayloadTooLargeError
from voicesculptor.errors import StorageError
from voicesculptor.errors import ValidationError
from voicesculptor.errors import VoiceNotFoundError
from voicesculptor.voices import seeds

LOG = logging.getLogger(__name__)

VOICE_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,64}')
GROUP_PATTERN = re.compile(r'[A-Za-z0-9_\-\u4e00-\u9fff]{1,32}')

META_FILE = 'meta.json'
REF_FILE = 'ref.wav'
TMP_PREFIX = '.tmp-'
DEFAULT_EMOJI = '★'
SEED_GROUP = 'roxy'
SEED_SOURCE = 'seed'
UPLOAD_SOURCE = 'upload'

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_SOURCE_SECONDS = 0.5
MAX_SOURCE_SECONDS = 30.0
MIN_EFFECTIVE_SECONDS = 0.3
SHORT_WARNING_SECONDS = 3.0
LONG_WARNING_SECONDS = 15.0
MAX_NAME_LENGTH = 32

SHORT_WARNING = '参考音频短于 3 秒，音色还原会下降'
LONG_WARNING = '参考音频超过 15 秒，建议截取 5~12 秒的单句'
NO_PROMPT_WARNING = '未填写转录文本：将以跨语种模式合成，音色与韵律会弱于 zero_shot'


def voice_group(meta: dict[str, object]) -> str:
    """返回音色所属分组；老的种子 meta 没有该字段时按 roxy 处理。"""
    group = meta.get('group')
    if group:
        return str(group)
    if meta.get('source') == SEED_SOURCE:
        return SEED_GROUP
    return ''


def voice_emotion(meta: dict[str, object]) -> str:
    """返回参考音频本身的情绪；老 meta 按种子名或平静兜底。"""
    emotion = meta.get('emotion')
    if emotion:
        return str(emotion)
    if meta.get('source') == SEED_SOURCE:
        name = meta.get('name')
        if name:
            return str(name)
    return emotions.DEFAULT_EMOTION


class VoiceStore:
    """voices 目录的读写封装。

    Args:
        voice_dir: 音色根目录，每个音色是其中一个子目录。
    """

    def __init__(self, voice_dir: str) -> None:
        self._voice_dir = voice_dir

    @property
    def voice_dir(self) -> str:
        """音色根目录。"""
        return self._voice_dir

    def _entries(self) -> list[str]:
        """列出根目录下的可见条目名，跳过以 . 开头的临时目录。"""
        try:
            names = sorted(os.listdir(self._voice_dir))
        except OSError as exc:
            LOG.warning('音色目录读取失败: %s', exc)
            return []
        return [name for name in names if not name.startswith('.')]

    @staticmethod
    def _load_meta(directory: str, video_id: str) -> dict[str, object] | None:
        """读取并校验一个音色的 meta.json，损坏时返回 None。"""
        meta_path = os.path.join(directory, META_FILE)
        if not os.path.isfile(meta_path):
            return None
        try:
            with open(meta_path, encoding='utf-8-sig') as handle:
                meta = json.load(handle)
        except (OSError, ValueError) as exc:
            LOG.warning('音色 %s 的 meta.json 读取失败: %s', video_id, exc)
            return None
        if not isinstance(meta, dict) or meta.get('voice_id') != video_id:
            return None
        return meta

    def list_voices(self) -> list[dict[str, object]]:
        """返回磁盘上完整可用的音色元数据列表。"""
        voices = []
        for video_id in self._entries():
            directory = os.path.join(self._voice_dir, video_id)
            meta = self._load_meta(directory, video_id)
            if meta is None:
                continue
            if os.path.isfile(os.path.join(directory, REF_FILE)):
                voices.append(meta)
        return voices

    def broken_voices(self) -> list[str]:
        """返回 meta 有效但缺少 ref.wav 的音色 id。"""
        broken = []
        for video_id in self._entries():
            directory = os.path.join(self._voice_dir, video_id)
            meta = self._load_meta(directory, video_id)
            if meta is not None and not os.path.isfile(
                    os.path.join(directory, REF_FILE)):
                broken.append(video_id)
        return broken

    def _resolve_dir(self, video_id: str) -> str:
        """把 voice_id 解析成目录；非法 id 一律视为不存在。"""
        if not video_id or not VOICE_ID_PATTERN.fullmatch(video_id):
            raise VoiceNotFoundError('voice not found')
        directory = os.path.join(self._voice_dir, video_id)
        parent = os.path.dirname(os.path.normpath(directory))
        if parent != os.path.normpath(self._voice_dir):
            raise VoiceNotFoundError('voice not found')
        return directory

    def resolve(self, video_id: str) -> tuple[dict[str, object], str]:
        """取出音色元数据与参考音频路径。

        Args:
            video_id: 音色 id。

        Returns:
            (meta, ref.wav 的绝对路径)。

        Raises:
            VoiceNotFoundError: id 非法、meta 缺失或 ref.wav 丢失。
        """
        directory = self._resolve_dir(video_id)
        meta = self._load_meta(directory, video_id)
        if meta is None:
            raise VoiceNotFoundError('voice not found: ' + video_id)
        ref_path = os.path.join(directory, REF_FILE)
        if not os.path.isfile(ref_path):
            raise VoiceNotFoundError('参考音频丢失: ' + video_id)
        return meta, ref_path

    def find_emotion_reference(
            self, meta: dict[str, object],
            emotion: str) -> tuple[dict[str, object], str] | None:
        """在同组里找情绪等于 emotion 的另一条参考。

        Args:
            meta: 当前音色元数据。
            emotion: 目标情绪。

        Returns:
            (兄弟 meta, 兄弟参考路径)，没有时返回 None。
        """
        group = voice_group(meta)
        if not group:
            return None
        for candidate in self.list_voices():
            if candidate.get('voice_id') == meta.get('voice_id'):
                continue
            if voice_group(candidate) != group:
                continue
            if voice_emotion(candidate) != emotion:
                continue
            try:
                return self.resolve(str(candidate['voice_id']))
            except VoiceNotFoundError:
                continue
        return None

    def create(self, name: str, prompt: str, emoji: str, emotion: str,
               group: str, data: bytes) -> tuple[dict[str, object], list[str]]:
        """校验上传音频并原子地写入一个新音色。

        Args:
            name: 展示名称，最长 32 字。
            prompt: 参考音频的转录文本，可为空。
            emoji: 封面字符，空值用默认星号。
            emotion: 参考音频的情绪，必须在白名单内。
            group: 同人多条参考的分组名，可为空。
            data: 上传文件的原始字节。

        Returns:
            (meta, warnings)。

        Raises:
            ValidationError: 音频、情绪、分组或名称不合法。
            PayloadTooLargeError: 上传超过 20MB。
            StorageError: 文件写入失败。
        """
        if not data:
            raise ValidationError('参考音频为空')
        if len(data) > MAX_UPLOAD_BYTES:
            raise PayloadTooLargeError('参考音频过大（上限 20MB）')
        wave, sample_rate = wav.decode_audio(data)
        source_duration = len(wave) / float(sample_rate or 1)
        if not MIN_SOURCE_SECONDS <= source_duration <= MAX_SOURCE_SECONDS:
            raise ValidationError(
                f'参考音频时长需在 0.5~30 秒（当前 {source_duration:.2f} 秒）')
        wave = preprocess.preprocess_reference(wave, sample_rate)
        duration = (len(wave) / float(sample_rate or 1) -
                    preprocess.TAIL_PAD_SECONDS)
        if duration < MIN_EFFECTIVE_SECONDS:
            raise ValidationError(f'参考音频有效语音过短（去静音后 {duration:.2f} 秒）')
        if emotion not in emotions.EMOTION_INSTRUCT:
            raise ValidationError('emotion 只能是: ' +
                                  '/'.join(emotions.EMOTION_INSTRUCT))
        clean_group = group.strip()
        if clean_group and not GROUP_PATTERN.fullmatch(clean_group):
            raise ValidationError('group 只能含中英文、数字、_ -，最长 32')
        clean_name = name.strip()
        if not clean_name or len(clean_name) > MAX_NAME_LENGTH:
            raise ValidationError('名称不能为空且不超过 32 字')

        warnings = []
        if duration < SHORT_WARNING_SECONDS:
            warnings.append(SHORT_WARNING)
        if duration > LONG_WARNING_SECONDS:
            warnings.append(LONG_WARNING)
        if not prompt.strip():
            warnings.append(NO_PROMPT_WARNING)

        video_id = 'v_' + uuid.uuid4().hex[:8]
        tmp_dir = os.path.join(self._voice_dir, TMP_PREFIX + video_id)
        final_dir = os.path.join(self._voice_dir, video_id)
        meta = {
            'voice_id': video_id,
            'name': clean_name,
            'prompt': prompt,
            'emoji': emoji or DEFAULT_EMOJI,
            'created': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': UPLOAD_SOURCE,
            'emotion': emotion,
            'group': clean_group,
            'preproc': 1,
        }
        try:
            os.makedirs(self._voice_dir, exist_ok=True)
            os.makedirs(tmp_dir)
            sf.write(os.path.join(tmp_dir, REF_FILE), wave, sample_rate)
            with open(os.path.join(tmp_dir, META_FILE), 'w',
                      encoding='utf-8') as handle:
                json.dump(meta, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_dir, final_dir)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise StorageError('保存音色失败: ' + str(exc)) from exc
        return meta, warnings

    def delete(self, video_id: str) -> dict[str, bool]:
        """删除一个音色目录。

        Args:
            video_id: 音色 id。

        Returns:
            {'ok': True}，方便 API 层直接返回。

        Raises:
            VoiceNotFoundError: id 非法或目录不存在。
            StorageError: 目录被占用，删除后仍然存在。
        """
        directory = self._resolve_dir(video_id)
        if not os.path.isdir(directory):
            raise VoiceNotFoundError('voice not found')
        shutil.rmtree(directory, ignore_errors=True)
        if os.path.isdir(directory):
            raise StorageError('删除失败：目录仍被占用，请关闭占用的程序后重试')
        return {'ok': True}

    def seed_defaults(self) -> None:
        """把内置参考音频复制成默认音色，已完整存在或源缺失时跳过。"""
        os.makedirs(self._voice_dir, exist_ok=True)
        for seed in seeds.SEED_VOICES:
            directory = os.path.join(self._voice_dir, seed.vid)
            meta_path = os.path.join(directory, META_FILE)
            ref_path = os.path.join(directory, REF_FILE)
            if ((os.path.exists(meta_path) and os.path.exists(ref_path)) or
                    not os.path.exists(seed.source_path)):
                continue
            wave, sample_rate = sf.read(seed.source_path, dtype='float32')
            if wave.ndim > 1:
                wave = wave.mean(axis=1)
            processed = preprocess.preprocess_reference(wave, sample_rate)
            os.makedirs(directory, exist_ok=True)
            sf.write(ref_path, processed, sample_rate)
            meta = {
                'voice_id': seed.vid,
                'name': seed.name,
                'prompt': seed.prompt,
                'emoji': DEFAULT_EMOJI,
                'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': SEED_SOURCE,
                'emotion': seed.name,
                'group': SEED_GROUP,
                'preproc': 1,
            }
            with open(meta_path, 'w', encoding='utf-8') as handle:
                json.dump(meta, handle, ensure_ascii=False, indent=2)

    def is_writable(self) -> bool:
        """目录可写返回 True；只做一次探针写入并删除。"""
        probe = os.path.join(self._voice_dir, '.probe')
        try:
            os.makedirs(self._voice_dir, exist_ok=True)
            with open(probe, 'w', encoding='utf-8') as handle:
                handle.write('ok')
            os.remove(probe)
        except OSError:
            return False
        return True
