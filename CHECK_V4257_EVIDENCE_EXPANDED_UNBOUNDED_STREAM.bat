@echo off
setlocal
cd /d "%~dp0"
python CHECK_V4257_EVIDENCE_EXPANDED_UNBOUNDED_STREAM.py
set RC=%ERRORLEVEL%
echo.
if %RC%==0 (
  echo V42.57 evidence-expanded/unbounded-stream checks PASSED.
) else (
  echo V42.57 checks FAILED with exit code %RC%.
)
exit /b %RC%
