@echo off
rem ============================================================
rem 一键诊断：把系统/显卡/驱动/Python/CUDA/文件完整性/端口/日志尾部
rem 全部写进 logs\诊断报告.txt，用户直接把这个文件发回即可定位问题
rem   · 依赖已改用 uv，Python 自检通过引擎项目的 uv 环境运行
rem ============================================================
chcp 65001 >nul
setlocal
title 声刻 诊断
set "ROOT=%~dp0"
set "ENG=%ROOT%engine\CosyVoice"
set "MODEL=%ENG%\pretrained_models\Fun-CosyVoice3-0.5B"
set "REPORT=%ROOT%logs\诊断报告.txt"
if not exist "%ROOT%logs" mkdir "%ROOT%logs"

echo.正在收集环境信息，请稍候（首次含 uv sync，较久）...
> "%REPORT%" echo ======== 声刻 环境诊断报告 ========
>> "%REPORT%" echo 时间: %date% %time%
>> "%REPORT%" echo 目录: %ROOT%
>> "%REPORT%" echo.

>> "%REPORT%" echo ---- 系统 ----
ver >> "%REPORT%" 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory | Format-List" >> "%REPORT%" 2>&1

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- 显卡 / 驱动 ----
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  >> "%REPORT%" echo [无] 未找到 nvidia-smi，可能没有 NVIDIA 显卡或驱动未安装
) else (
  powershell -NoProfile -Command "nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv" >> "%REPORT%" 2>&1
  powershell -NoProfile -Command "nvidia-smi | Select-String 'CUDA Version'" >> "%REPORT%" 2>&1
)

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- 磁盘 ----
powershell -NoProfile -Command "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,@{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,1)}},@{n='TotalGB';e={[math]::Round($_.Size/1GB,1)}} | Format-Table" >> "%REPORT%" 2>&1

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- 工具 / 文件完整性 ----
where uv >nul 2>nul
if errorlevel 1 ( >> "%REPORT%" echo [缺失] uv 未安装（winget install astral-sh.uv） ) else ( >> "%REPORT%" echo [OK] uv )
for %%F in ("%ENG%\runtime\python\fastapi\server.py" "%MODEL%\llm.pt" "%MODEL%\flow.pt" "%MODEL%\hift.pt" "%MODEL%\campplus.onnx" "%ROOT%app\app.py") do (
  if exist %%F ( >> "%REPORT%" echo [OK]   %%~fF ) else ( >> "%REPORT%" echo [缺失] %%~fF )
)

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- Python / CUDA 自检（引擎 uv 环境）----
cd /d "%ENG%"
uv run python "%ROOT%_selfcheck.py" >> "%REPORT%" 2>&1

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- 端口占用 ----
powershell -NoProfile -Command "netstat -ano | Select-String ':50000 |:8091 '" >> "%REPORT%" 2>&1

>> "%REPORT%" echo.
>> "%REPORT%" echo ---- 引擎日志（最后 40 行）----
if exist "%ROOT%logs\engine.log" (
  powershell -NoProfile -Command "Get-Content '%ROOT%logs\engine.log' -Tail 40" >> "%REPORT%" 2>&1
) else (
  >> "%REPORT%" echo [无] 还没有 engine.log（可能从未成功启动过引擎）
)

echo.
echo.诊断完成：%REPORT%
echo.
echo.请把这个文件发回：%REPORT%
echo.
pause
