@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0START_QWEN_LOCAL.bat"
if errorlevel 1 (
  echo.
  echo ERROR: Local Qwen failed to start with the required Jarvis runtime profile.
  echo Check qwen_server_stderr.log and qwen_server_stdout.log in %~dp0
  exit /b 1
)
timeout /t 2 /nobreak >nul
title JARVIS Voice Engine

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Jarvis Python was not found at %PY%
  pause
  exit /b 2
)

:run
echo.
echo ============================================================
echo JARVIS VOICE ENGINE STARTING
echo ============================================================
"%PY%" "%CD%\jarvis.py"
set "RC=%ERRORLEVEL%"

REM Code 23 means the Python singleton guard found an existing voice engine.
REM Never loop/retry in that case.
if "%RC%"=="23" (
  echo Existing Jarvis voice engine detected. Duplicate launcher is closing.
  exit /b 0
)

REM Code 0 is a deliberate clean shutdown.
if "%RC%"=="0" (
  echo Jarvis voice engine exited cleanly.
  exit /b 0
)

REM During a full hard restart, the external supervisor owns the relaunch.
if exist "%CD%\restart_in_progress.flag" (
  exit /b 0
)

echo.
echo Jarvis voice engine crashed with code %RC%.
echo Restarting voice engine in 3 seconds...
timeout /t 3 /nobreak >nul
goto run
