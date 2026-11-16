@echo off
rem Keep batch files ASCII-only; user-facing text here intentionally uses ASCII.
setlocal
title VoiceSculptor Studio (uv)
set "ROOT=%~dp0"
set "ENG=%ROOT%engine\CosyVoice"
set "MODEL=%ENG%\pretrained_models\Fun-CosyVoice3-0.5B"
if defined COSYVOICE_MODEL_DIR set "MODEL=%COSYVOICE_MODEL_DIR:"=%"
if "%MODEL:~-1%"=="\" set "MODEL=%MODEL:~0,-1%"
if "%MODEL:~-1%"=="/" set "MODEL=%MODEL:~0,-1%"
set "PORT=8091"
set "EPORT=50000"
set "LOG=%ROOT%logs"
cd /d "%ROOT%"
if not exist "%LOG%" mkdir "%LOG%"

echo ============================================
echo   VoiceSculptor Studio
echo   Root: "%ROOT%"
echo   Logs: "%LOG%"
echo ============================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] uv was not found. Install it with: winget install astral-sh.uv
  pause
  exit /b 1
)
for %%F in ("llm.pt" "flow.pt" "hift.pt" "campplus.onnx" "speech_tokenizer_v3.onnx" "CosyVoice-BlankEN\model.safetensors") do (
  if not exist "%MODEL%\%%~F" (
    echo [ERROR] Missing model file: "%MODEL%\%%~F"
    echo Download the model files from the GitHub release.
    pause
    exit /b 1
  )
)

set "VS_URL=http://127.0.0.1:%EPORT%/health"
set "VS_KEY=sample_rate"
set "VS_TMO=3"
netstat -ano | findstr /C:":%EPORT% " | findstr LISTENING >nul
if errorlevel 1 goto engine_start
call :probe
if not errorlevel 1 goto engine_reuse
call :port_owner %EPORT%
echo [ERROR] Port %EPORT% is in use by another program, PID %VS_OWNER%. It is not the VoiceSculptor engine.
tasklist /FI "PID eq %VS_OWNER%" /NH
echo Close that program or free the port, then run this launcher again.
pause
exit /b 1

:engine_reuse
echo [1/3] Reusing the VoiceSculptor engine already running on port %EPORT%.
goto engine_ready

:engine_start
if exist "%LOG%\engine.failed" del /q "%LOG%\engine.failed"
echo [1/3] Starting engine...
echo       First install downloads about 4 GB of packages and may take 10 minutes or more.
start "VoiceSculptor Engine" /min /D "%ROOT%." cmd /c _run-engine.cmd
set /a _w=0
:wait_engine
ping -n 6 127.0.0.1 >nul
set /a _w+=5
call :probe
if not errorlevel 1 goto engine_up
if exist "%LOG%\engine.failed" goto engine_failed
if %_w% GEQ 900 goto engine_timeout
goto wait_engine

:engine_up
echo       Engine ready after %_w% seconds.
goto engine_ready

:engine_failed
echo.
echo [ERROR] Engine startup failed. Last 20 log lines:
goto engine_print_log

:engine_timeout
echo.
echo [ERROR] Engine did not start within 15 minutes. Last 20 log lines:
:engine_print_log
echo --------------------------------------------
set "VS_TAIL=%LOG%\engine.log"
powershell -NoProfile -Command "$p=$env:VS_TAIL; if (Test-Path -LiteralPath $p) { Get-Content -LiteralPath $p -Encoding UTF8 -Tail 20 } else { 'engine.log not found' }"
echo --------------------------------------------
echo Run the Diagnostics launcher and inspect logs\diagnostic-report.txt.
pause
exit /b 1

:engine_ready
echo [1/3] Engine is listening on port %EPORT%.
rem The emotion service is optional; synthesis still works without it.
if defined VS_NO_EMOTION goto emotion_done
set "VS_URL=http://127.0.0.1:50001/health"
set "VS_KEY=loaded"
set "VS_TMO=3"
netstat -ano | findstr ":50001 " | findstr LISTENING >nul
if errorlevel 1 goto emotion_start
call :probe
if not errorlevel 1 goto emotion_done
echo [WARN] Port 50001 is used by another program. Emotion detection will be unavailable.
goto emotion_done

:emotion_start
echo       Starting optional emotion service on port 50001...
start "VoiceSculptor Emotion" /min /D "%ROOT%." cmd /c _run-emotion.cmd

:emotion_done
set "VS_URL=http://127.0.0.1:%PORT%/api/health"
set "VS_KEY=engines"
set "VS_TMO=8"
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if errorlevel 1 goto app_start
call :probe
if not errorlevel 1 goto app_reuse
call :port_owner %PORT%
echo [ERROR] Port %PORT% is in use by another program, PID %VS_OWNER%. It is not the VoiceSculptor app.
tasklist /FI "PID eq %VS_OWNER%" /NH
echo Close that program or free the port, then run this launcher again.
pause
exit /b 1

:app_reuse
echo [2/3] Reusing the VoiceSculptor app already running on port %PORT%.
goto app_ready

:app_start
if exist "%LOG%\app.failed" del /q "%LOG%\app.failed"
echo [2/3] Starting Studio app...
start "VoiceSculptor App" /min /D "%ROOT%." cmd /c _run-app.cmd
set /a _a=0
:wait_app
ping -n 4 127.0.0.1 >nul
set /a _a+=3
call :probe
if not errorlevel 1 goto app_up
if exist "%LOG%\app.failed" goto app_failed
if %_a% GEQ 600 goto app_timeout
goto wait_app

:app_up
echo       App ready after %_a% seconds.
goto app_ready

:app_failed
echo.
echo [ERROR] App startup failed. Last 20 log lines:
goto app_print_log

:app_timeout
echo.
echo [ERROR] App did not start within 10 minutes. Last 20 log lines:
:app_print_log
echo --------------------------------------------
set "VS_TAIL=%LOG%\app.log"
powershell -NoProfile -Command "$p=$env:VS_TAIL; if (Test-Path -LiteralPath $p) { Get-Content -LiteralPath $p -Encoding UTF8 -Tail 20 } else { 'app.log not found' }"
echo --------------------------------------------
echo Run the Diagnostics launcher and inspect logs\diagnostic-report.txt.
pause
exit /b 1

:app_ready
echo [2/3] Studio app is listening on port %PORT%.
echo.
echo [3/3] Opening the browser...
start "" http://127.0.0.1:%PORT%
echo.
echo ============================================
echo   Studio is ready: http://127.0.0.1:%PORT%
echo   Keep the engine and app windows open while using Studio.
echo ============================================
echo.
pause
exit /b 0

rem ---- :probe  uses VS_URL / VS_KEY / VS_TMO; errorlevel 0 = HTTP 200 and body contains VS_KEY
:probe
powershell -NoProfile -Command "try { [Net.WebRequest]::DefaultWebProxy = $null; $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec ([int]$env:VS_TMO) -Uri $env:VS_URL; if ($r.StatusCode -eq 200 -and $r.Content -like ('*' + $env:VS_KEY + '*')) { exit 0 } else { exit 2 } } catch { exit 1 }" >nul 2>nul
exit /b %errorlevel%

rem ---- :port_owner <port>  sets VS_OWNER to the listening PID
:port_owner
set "VS_OWNER=unknown"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:":%~1 " ^| findstr LISTENING') do set "VS_OWNER=%%P"
exit /b 0
