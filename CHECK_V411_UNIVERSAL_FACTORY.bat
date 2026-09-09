@echo off
cd /d "%~dp0"
python CHECK_V411_UNIVERSAL_FACTORY.py
if errorlevel 1 pause
