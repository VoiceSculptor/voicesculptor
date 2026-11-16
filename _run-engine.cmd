@echo off
rem Keep batch files ASCII-only; user-facing text here intentionally uses ASCII.
setlocal
title VoiceSculptor Engine (uv)
set "ROOT=%~dp0"
set "ENG=%ROOT%engine\CosyVoice"
set "MODEL=%ENG%\pretrained_models\Fun-CosyVoice3-0.5B"
if defined COSYVOICE_MODEL_DIR set "MODEL=%COSYVOICE_MODEL_DIR:"=%"
if "%MODEL:~-1%"=="\" set "MODEL=%MODEL:~0,-1%"
if "%MODEL:~-1%"=="/" set "MODEL=%MODEL:~0,-1%"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"

set "PYTHONUTF8=1"
set "PYTHONPATH=%ENG%"
set "PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128"
set "FP16_ARG="
if "%COSYVOICE_FP16%"=="1" set "FP16_ARG=--fp16"

if exist "%LOG%\engine.failed" del /q "%LOG%\engine.failed"
echo ==== Engine starting (uv) ====>> "%LOG%\engine.log"
cd /d "%ENG%" 2>nul || (
  echo [ERROR] Engine directory not found: "%ENG%"
  pause
  exit /b 1
)
echo ---- uv sync ---->> "%LOG%\engine.log"
uv sync>> "%LOG%\engine.log" 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency installation failed. See "%LOG%\engine.log".
  echo ==== Engine dependency installation failed ====>> "%LOG%\engine.log"
  > "%LOG%\engine.failed" echo sync-failed
  pause
  exit /b 1
)
echo ---- uv run server.py ---->> "%LOG%\engine.log"
uv run python -u -X faulthandler runtime\python\fastapi\server.py --port 50000 --model_dir "%MODEL%" %FP16_ARG%>> "%LOG%\engine.log" 2>&1
set "CODE=%errorlevel%"
if not "%CODE%"=="0" > "%LOG%\engine.failed" echo exit-%CODE%
echo.>> "%LOG%\engine.log"
echo ==== Engine exited with code %CODE% ====>> "%LOG%\engine.log"
echo.
echo [Engine exited] Exit code: %CODE%
echo Log: "%LOG%\engine.log"
pause
