@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS Qwen Live Performance Check
python CHECK_QWEN_PERFORMANCE.py
pause
