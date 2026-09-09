@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Download Qwen3.5-9B HauhauCS Aggressive Q4_K_M
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0DOWNLOAD_QWEN35_9B_AGGRESSIVE_Q4_K_M.ps1"
echo.
pause
