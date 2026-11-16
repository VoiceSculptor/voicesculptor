@echo off
rem Keep batch files ASCII-only; user-facing text here intentionally uses ASCII.
setlocal
title VoiceSculptor Studio App (uv)
set "ROOT=%~dp0"
set "LOG=%ROOT%logs"
if not exist "%LOG%" mkdir "%LOG%"
set "PYTHONUTF8=1"

if exist "%LOG%\app.failed" del /q "%LOG%\app.failed"
echo ==== App starting (uv) ====>> "%LOG%\app.log"
cd /d "%ROOT%app" 2>nul || (
  echo [ERROR] App directory not found: "%ROOT%app"
  pause
  exit /b 1
)
echo ---- uv sync ---->> "%LOG%\app.log"
uv sync>> "%LOG%\app.log" 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency installation failed. See "%LOG%\app.log".
  > "%LOG%\app.failed" echo sync-failed
  pause
  exit /b 1
)
echo ---- uv run app.py ---->> "%LOG%\app.log"
uv run python -u app.py --port 8091>> "%LOG%\app.log" 2>&1
set "CODE=%errorlevel%"
if not "%CODE%"=="0" > "%LOG%\app.failed" echo exit-%CODE%
echo.>> "%LOG%\app.log"
echo ==== App exited with code %CODE% ====>> "%LOG%\app.log"
echo.
echo [App exited] Exit code: %CODE%
echo Log: "%LOG%\app.log"
pause
