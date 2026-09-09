@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo JARVIS V37 SMALL-MODEL SOFTWARE FACTORY - FULL REGRESSION
echo ============================================================
python -m py_compile local_qwen_project.py || exit /b 1
python CHECK_V37_CORE_COMPAT.py || exit /b 1
python CHECK_V37_REAL_RUN_COMPAT.py || exit /b 1
python CHECK_V37_PLANNER_COMPAT.py || exit /b 1
python CHECK_V37_SMALL_MODEL_FACTORY.py || exit /b 1
echo.
echo ALL V37 REGRESSIONS PASSED.
endlocal
