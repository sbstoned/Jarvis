@echo off
setlocal
cd /d "%~dp0"
py -3 CHECK_V429_WHOLE_PROJECT_AUDIT.py
if errorlevel 1 python CHECK_V429_WHOLE_PROJECT_AUDIT.py
pause
