"""情绪识别服务的 HTTP 客户端。"""

import logging

import requests

from voicesculptor.errors import EmotionServiceError
from voicesculptor.errors import EmotionTimeoutError
from voicesculptor.errors import PayloadTooLargeError
from voicesculptor.errors import ValidationError
from voicesculptor.errors import VoiceSculptorError

LOG = logging.getLogger(__name__)

HEALTH_TIMEOUT = 5
EMOTION_TIMEOUT = 60
UNPROCESSABLE_ENTITY = 422
PAYLOAD_TOO_LARGE = 413
FILENAME = 'a.wav'


class EmotionClient:
    """调用本机情绪分类服务。

    Args:
        base_url: 情绪服务地址，例如 http://127.0.0.1:50001。
        session: 已配置好的 requests 会话。
    """

    def __init__(self, base_url: str, session: requests.Session) -> None:
        self._base_url = base_url.rstrip('/')
        self._session = session
        self._session.trust_env = False

    def health(self) -> dict | None:
        """返回情绪服务 /health 的 JSON，不可用时返回 None。"""
        try:
            response = self._session.get(self._base_url + '/health',
                                         timeout=HEALTH_TIMEOUT)
            if not response.ok:
                return None
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def classify(self, wav_bytes: bytes, filename: str = FILENAME) -> dict:
        """上传一段音频，返回情绪服务的原始 JSON。

        Args:
            wav_bytes: WAV 文件字节。
            filename: 上传时使用的文件名，服务端据此判断格式。

        Returns:
            形如 {'label': 'happy', 'cn': '开心', 'cn_scores': {...}} 的字典。

        Raises:
            ValidationError: 音频为空或服务端无法识别（422）。
            PayloadTooLargeError: 音频过大（413）。
            EmotionServiceError: 连接失败、超时以外的请求错误或响应损坏。
            EmotionTimeoutError: 请求超时。
        """
        if not wav_bytes:
            raise ValidationError('参考音频为空')
        try:
            response = self._session.post(
                self._base_url + '/emotion',
                files={'file': (filename, wav_bytes, 'audio/wav')},
                timeout=EMOTION_TIMEOUT)
        except requests.Timeout as exc:
            raise EmotionTimeoutError('情绪服务超时') from exc
        except requests.RequestException as exc:
            raise EmotionServiceError('情绪服务不可用') from exc
        if response.status_code == UNPROCESSABLE_ENTITY:
            raise ValidationError(self._detail(response) or '情绪服务无法识别音频')
        if response.status_code == PAYLOAD_TOO_LARGE:
            raise PayloadTooLargeError(self._detail(response) or '音频过大')
        if not response.ok:
            raise EmotionServiceError('情绪服务不可用')
        try:
            payload = response.json()
        except ValueError as exc:
            raise EmotionServiceError('情绪服务不可用') from exc
        if not isinstance(payload, dict):
            raise EmotionServiceError('情绪服务不可用')
        return payload

    def detect_label(self, wav_bytes: bytes) -> str | None:
        """识别中文情绪标签；任何失败都返回 None 并记 info 日志。"""
        try:
            payload = self.classify(wav_bytes)
        except VoiceSculptorError as exc:
            LOG.info('情绪服务不可用: %s', exc)
            return None
        label = payload.get('cn')
        return str(label) if label else None

    @staticmethod
    def _detail(response: requests.Response) -> str:
        """从响应体里取出 detail 文本。"""
        try:
            payload = response.json()
        except ValueError:
            return ''
        if isinstance(payload, dict):
            detail = payload.get('detail')
        else:
            detail = payload
        return str(detail) if detail else ''
