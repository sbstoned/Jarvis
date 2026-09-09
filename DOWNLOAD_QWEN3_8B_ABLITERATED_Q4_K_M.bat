@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Download Qwen3-8B Abliterated Q4_K_M
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0DOWNLOAD_QWEN3_8B_ABLITERATED_Q4_K_M.ps1"
echo.
pause
