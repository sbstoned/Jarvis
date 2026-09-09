@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo JARVIS v2.19.4 - HARD RESTART TEST
echo ============================================================
echo.
echo This should visibly close the Jarvis HUD, stop Jarvis/dashboard/Hermes,
echo and then reopen a completely fresh Command Center.
echo.
choice /C YN /M "Run hard restart test"
if errorlevel 2 exit /b 0

call "%~dp0HARD_RESTART_ALL_SYSTEMS.bat" 0
exit /b 0
