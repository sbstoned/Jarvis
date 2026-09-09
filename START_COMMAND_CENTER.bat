@echo off
setlocal EnableExtensions
title JARVIS Command Center Launcher
cd /d "%~dp0"
call "%~dp0START_QWEN_LOCAL.bat"
if errorlevel 1 (
  echo.
  echo ERROR: Local Qwen failed to start with the required Jarvis runtime profile.
  echo Check qwen_server_stderr.log and qwen_server_stdout.log in %~dp0
  exit /b 1
)
timeout /t 2 /nobreak >nul

echo ============================================================
echo JARVIS COMMAND CENTER - RELIABLE START v2.57
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found.
  pause
  exit /b 1
)

if /I not "%~1"=="--supervised-restart" del /q "restart_in_progress.flag" >nul 2>nul

REM Air Touch is optional. Install free MediaPipe assets on first launch if missing.
if not exist "%CD%\ui\airtouch\vendor\vision_bundle.mjs" (
  echo [AIR TOUCH] First-run local MediaPipe setup...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\SETUP_AIR_TOUCH.ps1"
  if errorlevel 1 echo [AIR TOUCH] Setup unavailable. Jarvis will continue with Air Touch off.
)

echo [PRECHECK] Checking for an existing Jarvis stack...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\JARVIS_START_PREFLIGHT.ps1" -Root "%CD%"
set "PREFLIGHT=%ERRORLEVEL%"

if "%PREFLIGHT%"=="0" (
  echo Existing Jarvis voice engine and dashboard are healthy.
  goto open_ui
)

echo [1/5] Starting Hermes...
where hermes >nul 2>nul
if %errorlevel%==0 hermes gateway restart >nul 2>&1

echo [2/5] Starting exactly one Jarvis voice engine...
start "JARVIS Voice Engine" cmd.exe /c ""%CD%\START_VOICE_ENGINE.bat""

echo [3/5] Starting dashboard...
start "JARVIS Dashboard Server" /min cmd.exe /c ""%CD%\.venv\Scripts\python.exe" "%CD%\ui\dashboard.py""

echo [4/5] Waiting for voice and dashboard...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$health=Join-Path '%CD%' 'voice_health.json';$deadline=(Get-Date).AddSeconds(75);$last='';while((Get-Date)-lt $deadline){$dash=$false;$voice=$false;$state='none';try{$r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8080/api/health' -TimeoutSec 5;if($r.StatusCode -eq 200){$d=$r.Content|ConvertFrom-Json;if($d.ok -eq $true -and [string]$d.build_id -eq 'v2.60-project-attachments'){$dash=$true}}}catch{};try{if(Test-Path $health){$h=Get-Content $health -Raw|ConvertFrom-Json;$state=[string]$h.state;$updated=[datetime]$h.updated_at;$age=((Get-Date)-$updated).TotalSeconds;$pidAlive=$false;try{Get-Process -Id ([int]$h.pid) -ErrorAction Stop|Out-Null;$pidAlive=$true}catch{};if($pidAlive -and $age -lt 30 -and $state -in @('online','ready','listening','wake_detected')){$voice=$true}}}catch{};$cur=('dashboard='+$dash+' voice='+$voice+' state='+$state);if($cur -ne $last){Write-Host ('    '+$cur);$last=$cur};if($dash -and $voice){exit 0};Start-Sleep -Milliseconds 500};exit 1"

if errorlevel 1 (
  echo.
  echo ERROR: Jarvis startup health check timed out.
  echo Dashboard and voice health did not both become ready.
  echo Run CHECK_JARVIS_PROCESSES.bat for diagnostics.
  pause
  exit /b 2
)

:open_ui
if /I "%~1"=="--supervised-restart" (
  echo [5/5] Fresh stack is healthy. Restart supervisor owns the browser reopen.
  exit /b 0
)
echo [5/5] Opening fresh Command Center...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "Get-Process chrome,msedge -ErrorAction SilentlyContinue ^| Where-Object {$_.MainWindowTitle -match 'JARVIS|Jarvis Command Center|J\.A\.R\.V\.I\.S'} ^| ForEach-Object {try{$_.CloseMainWindow() ^| Out-Null}catch{}}" >nul 2>nul
timeout /t 1 /nobreak >nul

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "CHROME86=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set "EDGE64=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%CHROME%" (
 start "" "%CHROME%" --user-data-dir="%TEMP%\JarvisCommandCenterChrome_v260" --disable-application-cache --disk-cache-size=1 --app=http://127.0.0.1:8080/?build=v2.60 --start-maximized
 goto done
)
if exist "%CHROME86%" (
 start "" "%CHROME86%" --user-data-dir="%TEMP%\JarvisCommandCenterChrome_v260" --disable-application-cache --disk-cache-size=1 --app=http://127.0.0.1:8080/?build=v2.60 --start-maximized
 goto done
)
if exist "%EDGE64%" (
 start "" "%EDGE64%" --user-data-dir="%TEMP%\JarvisCommandCenterChrome_v260" --disable-application-cache --disk-cache-size=1 --app=http://127.0.0.1:8080/?build=v2.60 --start-maximized
 goto done
)
if exist "%EDGE%" (
 start "" "%EDGE%" --user-data-dir="%TEMP%\JarvisCommandCenterChrome_v260" --disable-application-cache --disk-cache-size=1 --app=http://127.0.0.1:8080/?build=v2.60 --start-maximized
 goto done
)
start "" "http://127.0.0.1:8080/?build=v2.60"

:done
echo JARVIS ONLINE.
timeout /t 2 /nobreak >nul
exit /b 0
