"""统一异常处理：把领域异常转成 {"detail", "code"}。"""

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from voicesculptor.errors import VoiceSculptorError


def install_handlers(app: FastAPI) -> None:
    """给应用注册领域异常处理器。"""

    @app.exception_handler(VoiceSculptorError)
    async def _handle(request: Request, exc: VoiceSculptorError):
        del request
        return JSONResponse(status_code=exc.status_code,
                            content={
                                'detail': exc.message,
                                'code': type(exc).__name__,
                            })
