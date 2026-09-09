@echo off
setlocal
cd /d "%~dp0"
call "%~dp0START_COMMAND_CENTER.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
timeout /t 3 /nobreak >nul

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "EDGE64=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"

if exist "%CHROME%" (
  start "" "%CHROME%" --kiosk http://127.0.0.1:8080
  exit /b
)
if exist "%EDGE64%" (
  start "" "%EDGE64%" --kiosk http://127.0.0.1:8080
  exit /b
)
if exist "%EDGE%" (
  start "" "%EDGE%" --kiosk http://127.0.0.1:8080
  exit /b
)
