@echo off
setlocal
cd /d "%~dp0"
call "%~dp0START_QWEN_LOCAL.bat"
if errorlevel 1 (
  echo.
  echo ERROR: Local Qwen failed to start with the required Jarvis runtime profile.
  echo Check qwen_server_stderr.log and qwen_server_stdout.log in %~dp0
  exit /b 1
)
timeout /t 2 /nobreak >nul
if not exist ".venv\Scripts\python.exe" exit /b 1
start "JARVIS Voice Engine" /min "%CD%\.venv\Scripts\python.exe" "%CD%\jarvis.py"
timeout /t 1 /nobreak >nul
start "JARVIS Dashboard Server" /min "%CD%\.venv\Scripts\python.exe" "%CD%\ui\dashboard.py"
exit /b 0
