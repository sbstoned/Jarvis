@echo off
cd /d "%~dp0"
echo ============================================================
echo JARVIS V36.2 COMPLETE REGRESSION SUITE
echo ============================================================
python CHECK_V36_SOFTWARE_FACTORY.py || exit /b 1
python CHECK_V361_REAL_RUN.py || exit /b 1
python CHECK_V362_PLANNER.py || exit /b 1
echo.
echo ALL V36.2 REGRESSION SUITES PASSED
pause
