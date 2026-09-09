@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%JARVIS_QWEN_SERVER_EXE%"=="" set "JARVIS_QWEN_SERVER_EXE=C:\llama.cpp\llama-server.exe"
if "%JARVIS_QWEN_PORT%"=="" set "JARVIS_QWEN_PORT=8081"

if "%JARVIS_QWEN_MODEL_PATH%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_QWEN_LOCAL.ps1" -ServerExe "%JARVIS_QWEN_SERVER_EXE%" -Port %JARVIS_QWEN_PORT%
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_QWEN_LOCAL.ps1" -ServerExe "%JARVIS_QWEN_SERVER_EXE%" -ModelPath "%JARVIS_QWEN_MODEL_PATH%" -Port %JARVIS_QWEN_PORT%
)
exit /b %ERRORLEVEL%
