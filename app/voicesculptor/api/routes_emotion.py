"""情绪识别路由：代理到 50001。"""

from fastapi import APIRouter
from fastapi import File
from fastapi import Request
from fastapi import UploadFile

from voicesculptor.api.context import get_context
from voicesculptor.errors import PayloadTooLargeError
from voicesculptor.errors import ValidationError

router = APIRouter()

MAX_AUDIO_BYTES = 20 * 1024 * 1024


@router.post('/api/emotion')
async def detect_emotion(
    request: Request, file: UploadFile = File(...)) -> dict:
    """识别一段音频的情绪；服务不可用时返回 503。"""
    data = await file.read()
    if not data:
        raise ValidationError('参考音频为空')
    if len(data) > MAX_AUDIO_BYTES:
        raise PayloadTooLargeError('参考音频过大（上限 20MB）')
    ctx = get_context(request)
    return ctx.emotion.classify(data, file.filename or 'a.wav')
