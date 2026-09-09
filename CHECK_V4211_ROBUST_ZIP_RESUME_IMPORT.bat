@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py CHECK_V4211_ROBUST_ZIP_RESUME_IMPORT.py
) else (
  python CHECK_V4211_ROBUST_ZIP_RESUME_IMPORT.py
)
pause
