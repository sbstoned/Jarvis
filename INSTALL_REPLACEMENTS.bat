@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%USERPROFILE%\Jarvis"

if not exist "%TARGET%\jarvis.py" (
  echo.
  echo ERROR: Jarvis folder not found at:
  echo   %TARGET%
  echo.
  echo Run with your Jarvis folder as the first argument, for example:
  echo   INSTALL_REPLACEMENTS.bat "C:\Users\<USER>\Jarvis"
  exit /b 1
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "BACKUP=%TARGET%\backup_qwen35_v37_%STAMP%"
mkdir "%BACKUP%" >nul 2>&1
mkdir "%BACKUP%\ui" >nul 2>&1

set "CORE=jarvis.py local_qwen_project.py multi_provider.py qwen_model_manager.py START_QWEN_LOCAL.ps1 START_QWEN_LOCAL.bat START_ALL.bat START_COMMAND_CENTER.bat START_JARVIS.bat START_JARVIS_SERVICES.bat START_VOICE_ENGINE.bat qwen_selected_profile.json"
set "UIFILES=app.js index.html dashboard.py"

echo Backing up current Jarvis files to:
echo   %BACKUP%
for %%F in (%CORE%) do (
  if exist "%TARGET%\%%F" copy /y "%TARGET%\%%F" "%BACKUP%\%%F" >nul
)
for %%F in (%UIFILES%) do (
  if exist "%TARGET%\ui\%%F" copy /y "%TARGET%\ui\%%F" "%BACKUP%\ui\%%F" >nul
)

echo.
echo Installing Qwen3.5-9B JARVIS V37 SMALL-MODEL SOFTWARE FACTORY...
for %%F in (%CORE%) do (
  if not exist "%~dp0%%F" (
    echo ERROR: Replacement bundle is missing %%F
    exit /b 1
  )
  copy /y "%~dp0%%F" "%TARGET%\%%F" >nul || exit /b 1
)

if not exist "%TARGET%\ui" mkdir "%TARGET%\ui" >nul 2>&1
for %%F in (%UIFILES%) do (
  if not exist "%~dp0ui\%%F" (
    echo ERROR: Replacement bundle is missing ui\%%F
    exit /b 1
  )
  copy /y "%~dp0ui\%%F" "%TARGET%\ui\%%F" >nul || exit /b 1
)

rem V36/V36.2 stack-specific skills are required by the dynamic prompt/context layer.
if exist "%~dp0project_builder_skills" (
  if not exist "%TARGET%\project_builder_skills" mkdir "%TARGET%\project_builder_skills" >nul 2>&1
  xcopy /e /i /y "%~dp0project_builder_skills\*" "%TARGET%\project_builder_skills\" >nul || exit /b 1
)

for %%F in (CHECK_V37_SMALL_MODEL_FACTORY.py CHECK_V37_SMALL_MODEL_FACTORY.bat CHECK_V37_CORE_COMPAT.py CHECK_V37_REAL_RUN_COMPAT.py CHECK_V37_PLANNER_COMPAT.py CHECK_V37_ALL.bat JARVIS_BENCH_V37.py JARVIS_BENCH_V37.bat V37_SMALL_MODEL_FACTORY_README.txt V37_VALIDATION_REPORT.txt V37_RESEARCH_NOTES.txt V37_TASKFORGE_FAILURE_REPLAY.txt VERSION_V37.txt CHECK_QWEN_MAX_CONTEXT.ps1 CHECK_QWEN_MAX_CONTEXT.bat QWEN_MAX_CONTEXT_README.txt QWEN35_MODEL_README.txt) do (
  if exist "%~dp0%%F" copy /y "%~dp0%%F" "%TARGET%\%%F" >nul
)

echo.
echo Verifying Python syntax...
python -m py_compile "%TARGET%\jarvis.py" "%TARGET%\local_qwen_project.py" "%TARGET%\multi_provider.py" "%TARGET%\qwen_model_manager.py" "%TARGET%\ui\dashboard.py"
if errorlevel 1 (
  echo ERROR: Python syntax verification failed. Your backup is at %BACKUP%
  exit /b 1
)

echo.
echo SUCCESS. JARVIS V37 SMALL-MODEL SOFTWARE FACTORY is installed.
echo Backup: %BACKUP%
echo.
echo V37 adds semantic dependency normalization, flattening-tolerant frozen requirements, bounded 32K working turns,
echo focused repo-map context, read-before-edit patching, large-file rewrite guards, repair loop memory,
echo failure-only bounded deliberation, immediate syntax/foundation gates, and actionable architecture failures.
echo.
echo Recommended verification:
echo   CHECK_V37_ALL.bat
 echo.
echo Qwen3.5 keeps native ctx=262144 as a ceiling; V37 defaults ordinary plan/generate/repair/audit turns to 32768 tokens for small-model reliability.
echo Restart Jarvis with START_COMMAND_CENTER.bat after installation.
echo.
endlocal

