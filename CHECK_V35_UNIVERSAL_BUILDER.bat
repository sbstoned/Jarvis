@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py CHECK_V35_UNIVERSAL_BUILDER.py
) else (
  python CHECK_V35_UNIVERSAL_BUILDER.py
)
echo.
pause
