@echo off
rem ============================================================
rem 引擎包装器：用 uv 启动 CosyVoice 并把它所有输出写进 logs\engine.log
rem   · 依赖由 engine\CosyVoice\pyproject.toml 管理，uv sync 自动安装
rem   · PYTHONPATH 指向 engine\CosyVoice，否则 import cosyvoice 失败
rem   · -u 关闭缓冲，保证日志实时写入
rem   · 退出后打印退出码并 pause，防止窗口一闪而过
rem ============================================================
chcp 65001 >nul
setlocal
title 声刻 引擎（uv）
set "ROOT=%~dp0"
set "ENG=%ROOT%engine\CosyVoice"
set "MODEL=%ENG%\pretrained_models\Fun-CosyVoice3-0.5B"
if defined COSYVOICE_MODEL_DIR set "MODEL=%COSYVOICE_MODEL_DIR%"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"

set "PYTHONUTF8=1"
set "PYTHONPATH=%ENG%"
set "PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128"
set "FP16_ARG="
if "%COSYVOICE_FP16%"=="1" set "FP16_ARG=--fp16"

if exist "%LOG%\engine.failed" del /q "%LOG%\engine.failed"
echo.==== %date% %time% 引擎启动（uv）==== >> "%LOG%\engine.log"
cd /d "%ENG%" 2>nul || (
  echo [错误] 找不到引擎目录: %ENG%
  pause & exit /b 1
)
echo ---- uv sync ---- >> "%LOG%\engine.log"
uv sync >> "%LOG%\engine.log" 2>&1
if errorlevel 1 (
  echo.
  echo [错误] 依赖安装失败（uv sync），详见 %LOG%\engine.log
  echo.==== %date% %time% 依赖安装失败 ==== >> "%LOG%\engine.log"
  > "%LOG%\engine.failed" echo sync-failed
  pause
  exit /b 1
)
echo ---- uv run server.py ---- >> "%LOG%\engine.log"
uv run python -u -X faulthandler runtime\python\fastapi\server.py --port 50000 --model_dir "%MODEL%" %FP16_ARG% >> "%LOG%\engine.log" 2>&1
set "CODE=%errorlevel%"
if not "%CODE%"=="0" > "%LOG%\engine.failed" echo exit-%CODE%
echo. >> "%LOG%\engine.log"
echo.==== %date% %time% 引擎退出，退出码 %CODE% ==== >> "%LOG%\engine.log"
echo.
echo.[引擎已退出] 退出码 %CODE%
echo.日志: %LOG%\engine.log
pause
