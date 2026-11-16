"""音色库路由。"""

from fastapi import APIRouter
from fastapi import File
from fastapi import Form
from fastapi import Request
from fastapi import UploadFile

from voicesculptor.api.context import get_context
from voicesculptor.emotions import DEFAULT_EMOTION

router = APIRouter()


@router.get('/api/voices')
def list_voices(request: Request) -> dict:
    """全部音色。"""
    return {'voices': get_context(request).store.list_voices()}


@router.post('/api/voices')
async def create_voice(
    request: Request,
    name: str = Form(...),
    prompt: str = Form(''),
    emoji: str = Form(''),
    emotion: str = Form(DEFAULT_EMOTION),
    group: str = Form(''),
    ref: UploadFile = File(...)
) -> dict:
    """上传参考音频并新建音色。"""
    data = await ref.read()
    meta, warnings = get_context(request).store.create(name=name,
                                                       prompt=prompt,
                                                       emoji=emoji,
                                                       emotion=emotion,
                                                       group=group,
                                                       data=data)
    return dict(meta, warnings=warnings)


@router.delete('/api/voices/{vid}')
def delete_voice(request: Request, vid: str) -> dict:
    """删除音色；不存在时返回 404。"""
    get_context(request).store.delete(vid)
    return {'ok': True}
