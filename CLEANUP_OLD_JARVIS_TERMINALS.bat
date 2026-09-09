@echo off
cd /d "%~dp0"
echo Cleaning old Jarvis terminal shells from previous /k launchers...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=[regex]::Escape('%CD%'); Get-CimInstance Win32_Process | Where-Object {($_.Name -in @('cmd.exe','powershell.exe','pwsh.exe')) -and ($_.CommandLine -match $root) -and (($_.CommandLine -match 'jarvis\.py') -or ($_.CommandLine -match 'ui[\\/]dashboard\.py')) -and ($_.CommandLine -notmatch 'CLEANUP_OLD_JARVIS_TERMINALS')} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done.
timeout /t 2 /nobreak >nul
