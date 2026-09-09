@echo off
cd /d "%~dp0"
python CHECK_V4253_PROJECT_UPLOADS.py
if errorlevel 1 exit /b 1
python CHECK_V4253_JOB_LIFECYCLE.py
if errorlevel 1 exit /b 1
call CHECK_V4252_DURABLE_FUNCTIONAL_PROGRESS.bat
exit /b %errorlevel%
