@echo off
cd /d "%~dp0"
call "%~dp0START_QWEN_LOCAL.bat"
if errorlevel 1 (
  echo.
  echo ERROR: Local Qwen failed to start with the required Jarvis runtime profile.
  echo Check qwen_server_stderr.log and qwen_server_stdout.log in %~dp0
  exit /b 1
)
timeout /t 2 /nobreak >nul
call .venv\Scripts\activate.bat
python jarvis.py
pause
