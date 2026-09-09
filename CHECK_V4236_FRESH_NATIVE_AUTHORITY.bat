@echo off
setlocal
cd /d "%~dp0"
python CHECK_V4236_FRESH_NATIVE_AUTHORITY.py
if errorlevel 1 exit /b 1
exit /b 0
