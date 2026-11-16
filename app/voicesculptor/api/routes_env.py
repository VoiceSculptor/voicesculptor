"""环境检测路由。"""

from fastapi import APIRouter
from fastapi import Request

from voicesculptor.api.context import get_context

router = APIRouter()


@router.get('/api/env')
def env(request: Request, refresh: int = 0) -> dict:
    """完整环境检测；任何情况都返回 200。"""
    ctx = get_context(request)
    report = ctx.env_cache.get(ctx, refresh=bool(refresh))
    return report.to_dict()
