@echo off
cd /d "%~dp0"
git --version
where gh
if not errorlevel 1 gh auth status
echo.
git -C "%~dp0" status --short --branch
git -C "%~dp0" remote -v
pause
