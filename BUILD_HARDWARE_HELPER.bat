@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo JARVIS - BUILD v2.19 HARDWARE SENSOR HELPER
echo ============================================================
set "DOTNET=%USERPROFILE%\.dotnet\dotnet.exe"
if not exist "%DOTNET%" for /f "delims=" %%D in ('where dotnet 2^>nul') do set "DOTNET=%%D"
if not exist "%DOTNET%" (echo ERROR: dotnet.exe not found.&pause&exit /b 1)
"%DOTNET%" --list-sdks | findstr /R /C:"^10\." >nul
if errorlevel 1 (echo ERROR: .NET 10 SDK unavailable.&"%DOTNET%" --list-sdks&pause&exit /b 1)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem '%~dp0tools\LibreHardwareMonitor' -Recurse -File | Unblock-File" >nul 2>&1
if exist "%~dp0hardware_helper\bin" rmdir /s /q "%~dp0hardware_helper\bin"
if exist "%~dp0hardware_helper\obj" rmdir /s /q "%~dp0hardware_helper\obj"
if exist "%~dp0tools\JarvisHardwareSensors" rmdir /s /q "%~dp0tools\JarvisHardwareSensors"
"%DOTNET%" build "%~dp0hardware_helper\JarvisHardwareSensors.csproj" -c Release --nologo
if errorlevel 1 (echo BUILD FAILED.&pause&exit /b 1)
if not exist "%~dp0tools\JarvisHardwareSensors\JarvisHardwareSensors.exe" (echo ERROR: helper missing.&pause&exit /b 1)
> "%~dp0tools\JarvisHardwareSensors\helper.version" echo 2.19
echo Hardware helper v2.19 built successfully.
pause
