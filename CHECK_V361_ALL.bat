@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo JARVIS V36.1 COMPLETE REGRESSION SUITE
echo ============================================================
echo.
python CHECK_V36_SOFTWARE_FACTORY.py
if errorlevel 1 (
  echo.
  echo V36 inherited regression suite FAILED.
  exit /b 1
)
echo.
python CHECK_V361_REAL_RUN.py
if errorlevel 1 (
  echo.
  echo V36.1 real-run regression suite FAILED.
  exit /b 1
)
echo.
echo ============================================================
echo PASS: 82 / 82 regression checks
 echo ============================================================
pause
endlocal
