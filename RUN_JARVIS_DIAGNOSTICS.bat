@echo off
setlocal
cd /d "%~dp0"
echo JARVIS v2.19 FULL DIAGNOSTICS
".venv\Scripts\python.exe" -m py_compile jarvis.py multi_provider.py desktop_automation.py web_research.py ui\dashboard.py
if errorlevel 1 goto :fail
git status --short --branch
git remote -v
hermes status
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/api/status -TimeoutSec 3).Content}catch{Write-Host 'Dashboard not reachable.'}"
if exist "tools\JarvisHardwareSensors\JarvisHardwareSensors.exe" "tools\JarvisHardwareSensors\JarvisHardwareSensors.exe"
pause
exit /b 0
:fail
echo Diagnostics FAILED.
pause
exit /b 1
