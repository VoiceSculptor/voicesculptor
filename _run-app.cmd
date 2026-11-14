@echo off
rem ============================================================
rem 应用包装器：用 uv 启动 app.py（声刻 Studio 后端），输出写进 logs\app.log
rem   · 端口 8091；前端页面由 app.py 自己托管
rem   · 依赖由 app\pyproject.toml 管理，uv sync 自动安装
rem   · 退出后打印退出码并 pause，便于看报错
rem ============================================================
chcp 65001 >nul
setlocal
title 声刻 Studio 应用（uv）
set "ROOT=%~dp0"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"
set "PYTHONUTF8=1"

echo ==== %date% %time% 应用启动（uv）==== >> "%LOG%\app.log"
cd /d "%ROOT%app"
echo ---- uv sync ---- >> "%LOG%\app.log"
uv sync >> "%LOG%\app.log" 2>&1
if errorlevel 1 (
  echo.
  echo [错误] 依赖安装失败（uv sync），详见 %LOG%\app.log
  pause
  exit /b 1
)
echo ---- uv run app.py ---- >> "%LOG%\app.log"
uv run python -u app.py --port 8091 >> "%LOG%\app.log" 2>&1
set "CODE=%errorlevel%"
echo. >> "%LOG%\app.log"
echo ==== %date% %time% 应用退出，退出码 %CODE% ==== >> "%LOG%\app.log"
echo.
echo [应用已退出] 退出码 %CODE%
echo 日志: %LOG%\app.log
pause
