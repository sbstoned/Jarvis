@echo off
setlocal
title JARVIS Desktop Automation Setup
cd /d "%~dp0"
echo ============================================================
echo JARVIS - DESKTOP AUTOMATION SETUP
echo ============================================================
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: Jarvis virtual environment was not found.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pyautogui pygetwindow pillow
echo.
echo Setup complete. Move the mouse to the upper-left corner to abort PyAutoGUI automation.
pause
