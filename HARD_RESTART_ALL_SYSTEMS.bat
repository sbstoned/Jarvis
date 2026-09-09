@echo off
setlocal
cd /d "%~dp0"

set "OLD_JARVIS_PID=%~1"
if "%OLD_JARVIS_PID%"=="" set "OLD_JARVIS_PID=0"

REM Spawn the actual supervisor as a new independent PowerShell process.
start "JARVIS HARD RESTART" /min powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0HARD_RESTART_ALL_SYSTEMS.ps1" -OldJarvisPid %OLD_JARVIS_PID%

exit /b 0
