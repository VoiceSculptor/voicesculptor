"""健康检查路由。"""

from fastapi import APIRouter
from fastapi import Request

from voicesculptor.api.context import get_context

router = APIRouter()


@router.get('/api/health')
def health(request: Request) -> dict:
    """引擎、模型、情绪服务与能力开关。"""
    ctx = get_context(request)
    engines = {
        'cosyvoice': ctx.cosyvoice.health() is not None,
        'model': ctx.encoder.is_available(),
    }
    report = ctx.env_cache.get(ctx)
    return {
        'ok': all(engines.values()),
        'engines': engines,
        'emotion': ctx.emotion.health() is not None,
        'voices': len(ctx.store.list_voices()),
        'broken_voices': ctx.store.broken_voices(),
        'capabilities': report.capabilities,
    }
