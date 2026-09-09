@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m unittest CHECK_V4262_CANDIDATE_WORKFLOW_RECOVERY -v
) else (
  python -m unittest CHECK_V4262_CANDIDATE_WORKFLOW_RECOVERY -v
)
exit /b %errorlevel%
