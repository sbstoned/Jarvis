@echo off
setlocal
cd /d "%~dp0"
set "JARVIS_DASHBOARD_AUTO_OPEN=1"
set "JARVIS_DASHBOARD_PORT=8080"

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0ui\dashboard.py"
  goto :done
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0ui\dashboard.py"
  goto :done
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python "%~dp0ui\dashboard.py"
  goto :done
)

echo Python was not found. Start Jarvis with your normal launcher after restoring its Python environment.
pause

:done
endlocal
