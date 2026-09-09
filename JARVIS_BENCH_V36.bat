@echo off
cd /d "%~dp0"
echo Jarvis-Bench can take a long time because each case uses the real local Qwen pipeline.
echo Running one benchmark case by default. Edit the command or run the Python file with --list/--ids.
python JARVIS_BENCH_V36.py --limit 1
pause
