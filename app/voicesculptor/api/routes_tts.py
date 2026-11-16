"""合成路由。"""

from fastapi import APIRouter
from fastapi import Form
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from voicesculptor.api.context import get_context
from voicesculptor.emotions import DEFAULT_EMOTION
from voicesculptor.synthesis.request import validate

router = APIRouter()


@router.post('/api/tts')
async def tts(
    request: Request,
    voice_id: str = Form(...),
    text: str = Form(...),
    emotion: str = Form(DEFAULT_EMOTION),
    mode: str = Form('auto'),
    speed: float = Form(1.0),
    quality: str = Form('balanced'),
    best_n: int = Form(2),
    verify: bool = Form(True),
    instruct_text: str = Form(''),
    emo_voice_id: str = Form('')
) -> dict:
    """合成语音；表单字段与旧接口保持一致。"""
    ctx = get_context(request)
    form = {
        'voice_id': voice_id,
        'text': text,
        'emotion': emotion,
        'mode': mode,
        'speed': speed,
        'quality': quality,
        'best_n': best_n,
        'verify': verify,
        'instruct_text': instruct_text,
        'emo_voice_id': emo_voice_id,
    }
    parsed = validate(form, ctx.settings)
    return await run_in_threadpool(ctx.pipeline.run, parsed)
