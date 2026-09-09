@echo off
cd /d "%~dp0ui"
call ..\.venv\Scripts\activate.bat
python dashboard.py
pause
