@echo off
rem Keep batch files ASCII-only; user-facing text here intentionally uses ASCII.
setlocal
title VoiceSculptor Emotion Service (uv)
set "ROOT=%~dp0"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"
set "PYTHONUTF8=1"
echo ==== Emotion service starting (uv) ====>> "%LOG%\emotion.log"
cd /d "%ROOT%emotion" 2>nul || (
  echo [ERROR] Emotion service directory not found: "%ROOT%emotion"
  pause
  exit /b 1
)
echo ---- uv sync ---->> "%LOG%\emotion.log"
uv sync>> "%LOG%\emotion.log" 2>&1
if errorlevel 1 (
  echo [ERROR] Dependency installation failed. See "%LOG%\emotion.log".
  pause
  exit /b 1
)
echo ---- uv run server.py ---->> "%LOG%\emotion.log"
uv run python -u server.py --port 50001>> "%LOG%\emotion.log" 2>&1
echo [Emotion service exited] Exit code: %errorlevel%. Log: "%LOG%\emotion.log"
pause
