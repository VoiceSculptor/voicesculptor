@echo off
chcp 936 >nul
rem ============================================================
rem 声刻 Studio 启动器（一键启动引擎 + 应用 + 打开浏览器）
rem 依赖管理已改为 uv（不再用便携 Python）：
rem   · 需先安装 uv：winget install astral-sh.uv
rem   · 模型权重仍需放在 engine\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B
rem 执行顺序：
rem   1) 检查 uv 与模型是否存在
rem   2) 若 50000 未监听 -> 调 _run-engine.cmd 启动引擎（日志 logs\engine.log）
rem   3) 若 8091 未监听 -> 调 _run-app.cmd  启动应用（日志 logs\app.log）
rem   4) 两个端口都可连后，才打开浏览器 http://127.0.0.1:8091
rem 设计要点（踩过的坑）：
rem   · 计时用 ping -n，不要用 timeout（输入被重定向时 timeout 会立即失败）
rem   · 启动子脚本用  start "标题" /min "脚本" ；
rem     不要写 start "标题" /min cmd /c ""脚本""（双引号嵌套会让脚本根本不执行）
rem   · 本文件必须是 CRLF 换行，LF 会导致变量解析错乱
rem   · 失败时不要直接退出，要打印日志尾部并 pause
rem ============================================================
setlocal
title 声刻 Studio（uv）
set "ROOT=%~dp0"
set "ENG=%ROOT%engine\CosyVoice"
set "MODEL=%ENG%\pretrained_models\Fun-CosyVoice3-0.5B"
if defined COSYVOICE_MODEL_DIR set "MODEL=%COSYVOICE_MODEL_DIR%"
set "PORT=8091"
set "EPORT=50000"
set "LOG=%ROOT%logs"
cd /d "%ROOT%"
if not exist "%LOG%" mkdir "%LOG%"

echo ============================================
echo   声刻 Studio（uv 版）
echo   目录: %ROOT%
echo   日志: %LOG%
echo ============================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 uv。请先安装：winget install astral-sh.uv
  pause & exit /b 1
)
for %%F in ("llm.pt" "flow.pt" "hift.pt" "campplus.onnx" "speech_tokenizer_v3.onnx" "CosyVoice-BlankEN\model.safetensors") do (
  if not exist "%MODEL%\%%~F" (
    echo [错误] 找不到模型文件: %MODEL%\%%~F
    echo        请从 Release 下载权重，放到该目录
    pause & exit /b 1
  )
)

netstat -ano | findstr ":%EPORT% " | findstr LISTENING >nul
if not errorlevel 1 goto engine_ready

if exist "%LOG%\engine.failed" del /q "%LOG%\engine.failed"
echo [1/3] 启动语音引擎 ...
echo       首次运行会下载约 4GB 依赖（含 CUDA 版 torch），可能需要 10 分钟以上，请耐心等待...
start "声刻-引擎" /min "%ROOT%_run-engine.cmd"
set /a _w=0
:wait_engine
ping -n 6 127.0.0.1 >nul
set /a _w+=5
netstat -ano | findstr /C:":%EPORT% " | findstr LISTENING >nul
if not errorlevel 1 goto engine_up
if exist "%LOG%\engine.failed" goto engine_failed
if %_w% GEQ 900 goto engine_timeout
goto wait_engine

:engine_up
echo       引擎就绪（%_w% 秒）
goto engine_ready

:engine_failed
echo.
echo [失败] 引擎启动失败（多半是依赖安装失败，不是启动慢）。日志最后 20 行：
goto engine_print_log

:engine_timeout
echo.
echo [失败] 引擎 15 分钟内没有启动（首次安装依赖较慢）。日志最后 20 行：
:engine_print_log
echo --------------------------------------------
powershell -NoProfile -Command "$p='%LOG%\engine.log'; if (Test-Path -LiteralPath $p) { Get-Content -LiteralPath $p -Encoding UTF8 -Tail 20 } else { '（没有 engine.log）' }"
echo --------------------------------------------
echo 请运行「诊断.cmd」，把 logs\诊断报告.txt 发回。
pause & exit /b 1

:engine_ready
echo [1/3] 引擎已在运行（端口 %EPORT%）
rem 情绪服务（50001）为可选组件：只启动、不等待；设置 VS_NO_EMOTION=1 可跳过
netstat -ano | findstr ":50001 " | findstr LISTENING >nul
if errorlevel 1 if not defined VS_NO_EMOTION (
  echo       启动情绪服务（端口 50001，可选；首次需下载模型）...
  start "声刻-情绪" /min "%ROOT%_run-emotion.cmd"
)

netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul
if not errorlevel 1 goto app_ready

if exist "%LOG%\app.failed" del /q "%LOG%\app.failed"
echo [2/3] 启动声刻 Studio...
start "声刻-应用" /min "%ROOT%_run-app.cmd"
set /a _a=0
:wait_app
ping -n 4 127.0.0.1 >nul
set /a _a+=3
netstat -ano | findstr /C:":%PORT% " | findstr LISTENING >nul
if not errorlevel 1 goto app_up
if exist "%LOG%\app.failed" goto app_failed
if %_a% GEQ 600 goto app_timeout
goto wait_app

:app_up
echo       应用就绪（%_a% 秒）
goto app_ready

:app_failed
echo.
echo [失败] 应用启动失败（多半是依赖安装失败，不是启动慢）。日志最后 20 行：
goto app_print_log

:app_timeout
echo.
echo [失败] 应用 10 分钟内没有启动。日志最后 20 行：
:app_print_log
echo --------------------------------------------
powershell -NoProfile -Command "$p='%LOG%\app.log'; if (Test-Path -LiteralPath $p) { Get-Content -LiteralPath $p -Encoding UTF8 -Tail 20 } else { '（没有 app.log）' }"
echo --------------------------------------------
echo 请运行「诊断.cmd」，把 logs\诊断报告.txt 发回。
pause & exit /b 1

:app_ready
echo [2/3] 应用已在运行（端口 %PORT%）

echo [3/3] 打开浏览器 ...
start "" http://127.0.0.1:%PORT%

echo.
echo ============================================
echo   已启动。浏览器应自动打开:  http://127.0.0.1:%PORT%
echo   若没有自动打开，请手动在浏览器输入上面的地址。
echo.
echo   注意: 最小化的「声刻-引擎」「声刻-应用」两个窗口
echo         是服务本体，关掉它们服务就停了。
echo ============================================
echo.
pause
