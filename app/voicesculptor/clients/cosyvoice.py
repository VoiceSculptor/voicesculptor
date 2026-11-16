"""CosyVoice 引擎的 HTTP 客户端。"""

import hashlib
import logging
import os

import requests

from voicesculptor import emotions
from voicesculptor.errors import EngineUnavailableError

LOG = logging.getLogger(__name__)

PROMPT_PREFIX = 'You are a helpful assistant.<|endofprompt|>'
HEALTH_TIMEOUT = 5
REGISTER_TIMEOUT = 120
SYNTH_TIMEOUT = 300
NOT_FOUND = 404
EMOTION_CODE_PREFIX = 'x'


class CosyVoiceClient:
    """调用本机 CosyVoice 服务的薄封装。

    Args:
        base_url: 引擎地址，例如 http://127.0.0.1:50000。
        session: 已配置好的 requests 会话。
    """

    def __init__(self, base_url: str, session: requests.Session) -> None:
        self._base_url = base_url.rstrip('/')
        self._session = session
        self._session.trust_env = False
        self._registered: set[str] = set()

    def health(self) -> dict | None:
        """返回引擎 /health 的 JSON，未启动时返回 None。"""
        try:
            response = self._session.get(self._base_url + '/health',
                                         timeout=HEALTH_TIMEOUT)
            if not response.ok:
                return None
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def synthesize(self,
                   kind: str,
                   ref_path: str,
                   prompt: str,
                   text: str,
                   instruct: str | None,
                   speed: float,
                   emo_ref: str | None = None,
                   emo_prompt: str = '') -> bytes:
        """按合成模式请求引擎，返回裸 PCM 字节。

        Args:
            kind: zero_shot/cross_lingual/instruct2/hybrid/split。
            ref_path: 参考音频路径。
            prompt: 参考音频转录文本。
            text: 待合成文本。
            instruct: 自然语言指令，instruct2/hybrid 使用。
            speed: 语速倍率。
            emo_ref: split 模式的情绪参考音频路径。
            emo_prompt: split 模式情绪参考音频的转录文本。

        Returns:
            16bit 单声道 24 kHz PCM。

        Raises:
            EngineUnavailableError: 连接、超时、HTTP 错误或参数缺失。
        """
        try:
            if kind == 'split':
                return self._split(ref_path, text, speed, emo_ref, emo_prompt)
            if kind == 'zero_shot':
                return self._zero_shot(ref_path, prompt, text, speed)
            if kind == 'cross_lingual':
                return self._cross_lingual(ref_path, text, speed)
            if kind == 'instruct2':
                return self._instruct2(ref_path, text, speed, instruct)
            if kind == 'hybrid':
                return self._hybrid(ref_path, prompt, text, speed, instruct)
        except requests.RequestException as exc:
            raise EngineUnavailableError('合成失败: ' + str(exc)) from exc
        raise EngineUnavailableError('合成失败: 未知合成模式 ' + str(kind))

    @staticmethod
    def _spk_id(ref_path: str) -> str:
        """参考音频对应的说话人 id：目录名加 mtime。"""
        return (os.path.basename(os.path.dirname(ref_path)) + '_' +
                str(int(os.path.getmtime(ref_path))))

    def _register(self, ref_path: str, prompt: str) -> str:
        """确保参考音频已在引擎注册，返回说话人 id。"""
        spk_id = self._spk_id(ref_path)
        if spk_id in self._registered:
            return spk_id
        with open(ref_path, 'rb') as handle:
            response = self._session.post(
                self._base_url + '/add_zero_shot_spk',
                data={
                    'spk_id': spk_id,
                    'prompt_text': PROMPT_PREFIX + prompt,
                },
                files={'prompt_wav': handle},
                timeout=REGISTER_TIMEOUT)
        response.raise_for_status()
        self._registered.add(spk_id)
        return spk_id

    def _post_zero_shot(self, data: dict, ref_path: str) -> requests.Response:
        """发一次 zero_shot 推理，文件句柄随请求关闭。"""
        with open(ref_path, 'rb') as handle:
            return self._session.post(self._base_url +
                                      '/inference_zero_shot_spk',
                                      data=data,
                                      files={'prompt_wav': handle},
                                      timeout=SYNTH_TIMEOUT)

    def _zero_shot(self,
                   ref_path: str,
                   prompt: str,
                   text: str,
                   speed: float,
                   suffix: str = '',
                   spk_prompt: str | None = None) -> bytes:
        """zero_shot 推理；404 时丢弃注册缓存后重试一次。"""
        spk_id = self._register(ref_path, prompt)
        data = {
            'tts_text': text,
            'spk_id': spk_id + suffix,
            'speed': str(speed),
        }
        if spk_prompt is not None:
            data['prompt_text'] = spk_prompt
        response = self._post_zero_shot(data, ref_path)
        if response.status_code == NOT_FOUND:
            self._registered.discard(spk_id)
            spk_id = self._register(ref_path, prompt)
            data['spk_id'] = spk_id + suffix
            response = self._post_zero_shot(data, ref_path)
        response.raise_for_status()
        return response.content

    def _cross_lingual(self, ref_path: str, text: str, speed: float) -> bytes:
        """cross_lingual 推理：参考音频只提供音色。"""
        with open(ref_path, 'rb') as handle:
            response = self._session.post(self._base_url +
                                          '/inference_cross_lingual',
                                          data={
                                              'tts_text': PROMPT_PREFIX + text,
                                              'speed': str(speed),
                                          },
                                          files={'prompt_wav': handle},
                                          timeout=SYNTH_TIMEOUT)
        response.raise_for_status()
        return response.content

    def _instruct2(self, ref_path: str, text: str, speed: float,
                   instruct: str | None) -> bytes:
        """instruct2 推理：自然语言控制情绪与风格。"""
        if not instruct:
            raise EngineUnavailableError('合成失败: instruct2 模式缺少 instruct')
        with open(ref_path, 'rb') as handle:
            response = self._session.post(
                self._base_url + '/inference_instruct2',
                data={
                    'tts_text': text,
                    'instruct_text': instruct + '<|endofprompt|>',
                    'speed': str(speed),
                },
                files={'prompt_wav': handle},
                timeout=SYNTH_TIMEOUT)
        response.raise_for_status()
        return response.content

    def _hybrid(self, ref_path: str, prompt: str, text: str, speed: float,
                instruct: str | None) -> bytes:
        """hybrid 推理：克隆音色后再叠加情绪代码。"""
        if not instruct:
            raise EngineUnavailableError('合成失败: hybrid 模式缺少 instruct')
        code = self._emotion_code(instruct)
        return self._zero_shot(ref_path,
                               prompt,
                               text,
                               speed,
                               suffix='_' + code,
                               spk_prompt=instruct + '<|endofprompt|>' + prompt)

    @staticmethod
    def _emotion_code(instruct: str) -> str:
        """把指令映射成引擎认识的情绪代码，未知时用哈希短码。"""
        for code, value in emotions.EMO_CODE.items():
            if value == instruct:
                return code
        digest = hashlib.md5(instruct.encode('utf-8')).hexdigest()[:8]
        return EMOTION_CODE_PREFIX + digest

    def _split(self, ref_path: str, text: str, speed: float,
               emo_ref: str | None, emo_prompt: str) -> bytes:
        """split 推理：音色与情绪分别来自两段参考音频。"""
        if not emo_ref:
            raise EngineUnavailableError('合成失败: split 模式缺少情绪参考音频')
        with open(emo_ref, 'rb') as emo_handle, open(ref_path,
                                                     'rb') as ref_handle:
            response = self._session.post(
                self._base_url + '/inference_split_prompt',
                data={
                    'tts_text': text,
                    'speed': str(speed),
                    'emo_prompt_text': PROMPT_PREFIX + emo_prompt,
                },
                files={
                    'emo_prompt_wav': emo_handle,
                    'prompt_wav': ref_handle,
                },
                timeout=SYNTH_TIMEOUT)
        response.raise_for_status()
        return response.content
