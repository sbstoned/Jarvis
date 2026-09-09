@echo off
cd /d "%~dp0"
python CHECK_V4251_FUNCTIONAL_TRANSACTIONS.py
if errorlevel 1 exit /b 1
python CHECK_V4250_REGRESSION_SAFE_FUNCTIONAL_PROMOTION.py
exit /b %errorlevel%
