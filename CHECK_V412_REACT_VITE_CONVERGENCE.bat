@echo off
setlocal
cd /d "%~dp0"
python CHECK_V412_REACT_VITE_CONVERGENCE.py
exit /b %ERRORLEVEL%
