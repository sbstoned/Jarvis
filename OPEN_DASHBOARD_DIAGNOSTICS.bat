@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
start "" notepad "%~dp0logs\dashboard_frontend.log"
start "" notepad "%~dp0logs\dashboard_http.log"
start "" http://127.0.0.1:8080/api/diagnostics/logs
endlocal
