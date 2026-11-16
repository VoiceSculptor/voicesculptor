@echo off
chcp 936 >nul
rem ============================================================
rem 情绪识别服务包装器：emotion\server.py（emotion2vec_plus_large），端口 50001
rem   · 可选组件：没起来时 app 照常合成，只是不判情绪
rem   · 依赖由 emotion\pyproject.toml 管理，uv sync 自动安装
rem ============================================================
setlocal
title 声刻 情绪服务（uv）
set "ROOT=%~dp0"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"
set "PYTHONUTF8=1"
echo ==== %date% %time% 情绪服务启动（uv）==== >> "%LOG%\emotion.log"
cd /d "%ROOT%emotion" 2>nul || (
  echo [错误] 找不到目录: %ROOT%emotion
  pause & exit /b 1
)
echo ---- uv sync ---- >> "%LOG%\emotion.log"
uv sync >> "%LOG%\emotion.log" 2>&1
if errorlevel 1 (
  echo [错误] 依赖安装失败（uv sync），详见 %LOG%\emotion.log
  pause
  exit /b 1
)
echo ---- uv run server.py ---- >> "%LOG%\emotion.log"
uv run python -u server.py --port 50001 >> "%LOG%\emotion.log" 2>&1
echo [情绪服务已退出] 退出码 %errorlevel%，日志: %LOG%\emotion.log
pause
