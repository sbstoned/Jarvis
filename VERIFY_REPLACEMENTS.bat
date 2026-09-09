@echo off
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%USERPROFILE%\Jarvis"
pushd "%TARGET%" || exit /b 1
python -m py_compile jarvis.py local_qwen_project.py TEST_COMMAND_ROUTING.py TEST_COMPOSITE_EDIT_RESTART_ROUTING.py TEST_RESUME_CHECKPOINT.py TEST_SENSITIVE_QWEN_CONTEXT.py TEST_CHECKPOINT_ROUTING.py || (popd & exit /b 1)
python TEST_COMMAND_ROUTING.py || (popd & exit /b 1)
python TEST_COMPOSITE_EDIT_RESTART_ROUTING.py || (popd & exit /b 1)
python TEST_RESUME_CHECKPOINT.py || (popd & exit /b 1)
python TEST_SENSITIVE_QWEN_CONTEXT.py || (popd & exit /b 1)
python TEST_CHECKPOINT_ROUTING.py || (popd & exit /b 1)
popd
echo All V28 routing/resume checks passed.
endlocal
