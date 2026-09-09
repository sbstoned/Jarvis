@echo off
cd /d "%~dp0"
python CHECK_V4252_DURABLE_FUNCTIONAL_PROGRESS.py
if errorlevel 1 exit /b 1
call CHECK_V4251_FUNCTIONAL_TRANSACTIONS.bat
exit /b %errorlevel%
