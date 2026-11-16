@echo off
chcp 936 >nul
rem ============================================================
rem 把 logs 目录打包成 日志包.zip，方便发给开发者
rem ============================================================
setlocal
title 声刻 收集日志
set "ROOT=%~dp0"
set "OUT=%ROOT%日志包.zip"
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
if exist "%OUT%" del /f /q "%OUT%"

echo.正在收集环境信息...
> "%ROOT%logs\环境.txt" echo 时间: %date% %time%
>> "%ROOT%logs\环境.txt" echo 目录: %ROOT%
uv --version >> "%ROOT%logs\环境.txt" 2>&1
git -C "%ROOT%." rev-parse --short HEAD >> "%ROOT%logs\环境.txt" 2>&1
git -C "%ROOT%engine\CosyVoice" rev-parse --short HEAD >> "%ROOT%logs\环境.txt" 2>&1

echo.正在打包日志...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%ROOT%logs') { Compress-Archive -Path '%ROOT%logs\*' -DestinationPath '%OUT%' -Force }"
if errorlevel 1 (
  echo.
  echo.[警告] 日志打包失败（可能有文件正被占用）。请先关闭「声刻」窗口，再运行本脚本。
)

if exist "%OUT%" (
  echo.
  echo.已生成：%OUT%
  echo.请把这个文件发回给开发者。
) else (
  echo.
  echo.[提示] 没有找到 logs 目录或里面没有文件。
  echo.       请先运行一次「启动-声刻.cmd」，再运行本脚本。
)
echo.
pause
