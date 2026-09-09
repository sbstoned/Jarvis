@echo off
setlocal
cd /d "%~dp0"
python CHECK_V4237_COMPONENT_TRANSACTION_SANDBOX.py
exit /b %errorlevel%
