"""领域异常层级。

每个异常自带 HTTP 状态码，API 层统一转成 ``{"detail": message}``，
业务代码不需要再关心 FastAPI 的 HTTPException。
"""


class VoiceSculptorError(Exception):
    """所有业务异常的基类。"""

    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(VoiceSculptorError):
    """请求参数不合法。"""

    status_code = 422


class PayloadTooLargeError(VoiceSculptorError):
    """上传内容超过大小上限。"""

    status_code = 413


class VoiceNotFoundError(VoiceSculptorError):
    """音色不存在或参考音频缺失。"""

    status_code = 404


class BusyError(VoiceSculptorError):
    """并发闸门排队超时。"""

    status_code = 429


class EngineUnavailableError(VoiceSculptorError):
    """合成引擎不可用。"""

    status_code = 503


class EngineEmptyError(VoiceSculptorError):
    """引擎返回空音频。"""

    status_code = 502


class ModelUnavailableError(VoiceSculptorError):
    """本地评测模型缺失或加载失败。"""

    status_code = 503


class EmotionServiceError(VoiceSculptorError):
    """情绪服务不可用。"""

    status_code = 503


class EmotionTimeoutError(VoiceSculptorError):
    """情绪服务响应超时。"""

    status_code = 504


class StorageError(VoiceSculptorError):
    """音色文件写入失败。"""

    status_code = 500
