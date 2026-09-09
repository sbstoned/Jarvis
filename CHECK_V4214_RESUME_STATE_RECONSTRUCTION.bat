@echo off
setlocal
cd /d "%~dp0"
python CHECK_V4214_RESUME_STATE_RECONSTRUCTION.py
exit /b %ERRORLEVEL%
