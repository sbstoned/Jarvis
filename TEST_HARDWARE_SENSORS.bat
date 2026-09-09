@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo JARVIS - HARDWARE SENSOR TEST
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0READ_HARDWARE_SENSORS.ps1"
echo.
echo If the JSON above lists temperature sensors, restart Jarvis/dashboard.
echo RAM temp only appears if the DIMMs or motherboard expose it.
pause
