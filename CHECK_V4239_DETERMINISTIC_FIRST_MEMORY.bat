@echo off
setlocal
cd /d "%~dp0"
python CHECK_V4239_DETERMINISTIC_FIRST_MEMORY.py
if errorlevel 1 exit /b %errorlevel%
endlocal
