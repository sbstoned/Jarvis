@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m unittest CHECK_V4263_MODEL_STARTUP -v
) else (
  python -m unittest CHECK_V4263_MODEL_STARTUP -v
)
exit /b %errorlevel%
