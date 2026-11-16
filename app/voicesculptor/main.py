"""应用装配与启动入口。

create_app() 组装依赖与路由；main() 负责日志、种子音色、启动自检和
uvicorn 启动。两者分离是为了测试能直接拿 create_app() 的实例。
"""

import argparse
import logging
import mimetypes
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from voicesculptor import config
from voicesculptor.api import context as api_context
from voicesculptor.api import errors as api_errors
from voicesculptor.api import routes_audit
from voicesculptor.api import routes_emotion
from voicesculptor.api import routes_env
from voicesculptor.api import routes_health
from voicesculptor.api import routes_pages
from voicesculptor.api import routes_tts
from voicesculptor.api import routes_voices
from voicesculptor.envcheck import checks as env_checks

LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
ROUTERS = (routes_pages, routes_health, routes_env, routes_voices, routes_tts,
           routes_emotion, routes_audit)
LOG = logging.getLogger(__name__)


def create_app(settings: config.Settings | None = None) -> FastAPI:
    """按配置创建 FastAPI 应用；不启动服务，不联网。"""
    # Windows 注册表可能把 .js 映射成 text/plain，导致 ES Module 拒绝加载
    mimetypes.add_type('text/javascript', '.js')
    mimetypes.add_type('text/css', '.css')
    chosen = settings or config.Settings.from_env()
    app = FastAPI(title='声刻 Studio', version='2.0.0')
    app.state.ctx = api_context.build_context(chosen)
    api_errors.install_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router)
    app.mount('/static',
              StaticFiles(directory=config.STATIC_DIR),
              name='static')
    return app


def _log_report(report) -> None:
    """逐条打印环境检测结果，FAIL/WARN 用警告级别。"""
    for item in report.checks:
        if item.level is env_checks.Level.OK:
            level = logging.INFO
        elif item.level is env_checks.Level.WARN:
            level = logging.WARNING
        else:
            level = logging.ERROR
        LOG.log(level, '[%s] %s %s', item.level.value, item.id, item.message)


def main(argv: list[str] | None = None) -> int:
    """命令行入口：python app.py --port 8091。"""
    parser = argparse.ArgumentParser(prog='app.py')
    parser.add_argument('--host', default=config.DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=config.DEFAULT_PORT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    app = create_app()
    ctx = app.state.ctx
    ctx.store.seed_defaults()
    _log_report(ctx.env_cache.get(ctx, refresh=True))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == '__main__':
    sys.exit(main())
