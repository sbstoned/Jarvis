@echo off
cd /d "%~dp0"
title JARVIS Full Restart Test
echo ============================================================
echo JARVIS - FULL RESTART TEST
echo ============================================================
echo.
echo This will intentionally close Jarvis, the dashboard, and this UI.
echo A fresh Jarvis stack should reopen automatically.
echo.
choice /C YN /M "Run the full restart test now"
if errorlevel 2 exit /b 0
start "" /min "%~dp0HARD_RESTART_ALL_SYSTEMS.bat" 0
exit /b 0
