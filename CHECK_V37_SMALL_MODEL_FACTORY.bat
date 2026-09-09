@echo off
setlocal
cd /d "%~dp0"
python CHECK_V37_SMALL_MODEL_FACTORY.py
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo V37 regression checks FAILED.
if "%RC%"=="0" echo V37 regression checks PASSED.
pause
exit /b %RC%
