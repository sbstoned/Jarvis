@echo off
cd /d "%~dp0"
echo ============================================================
echo JARVIS PROCESS DIAGNOSTICS
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$root=[regex]::Escape('%CD%'); Get-CimInstance Win32_Process | Where-Object {($_.Name -in @('python.exe','pythonw.exe','cmd.exe')) -and ($_.CommandLine -match $root)} | Select-Object ProcessId,Name,CommandLine | Format-List"
echo.
echo Port 8080:
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Format-Table -AutoSize"
echo.
echo Voice health:
if exist "%CD%\voice_health.json" type "%CD%\voice_health.json"
echo.
pause
