@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHECK_QWEN_MAX_CONTEXT.ps1"
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
