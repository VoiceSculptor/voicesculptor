"""页面路由。"""

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from voicesculptor import config

router = APIRouter()


@router.get('/')
def index() -> FileResponse:
    """返回前端首页。"""
    return FileResponse(os.path.join(config.STATIC_DIR, 'index.html'))


@router.get('/legacy')
def legacy() -> FileResponse:
    """返回旧版页面，仅供前端重绘期间对照回滚。"""
    return FileResponse(os.path.join(config.STATIC_DIR, 'legacy.html'))
