@echo off
setlocal
set "DEST=D:\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF"
set "FILE=Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf"
set "URL=https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/resolve/main/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf?download=true"
if not exist "%DEST%" mkdir "%DEST%"
echo.
echo Downloading %FILE%
echo Destination: %DEST%
echo This file is approximately 10.68 GB.
echo.
where curl.exe >nul 2>nul
if %errorlevel%==0 (
  curl.exe -L --fail --retry 5 --retry-delay 3 -C - -o "%DEST%\%FILE%" "%URL%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Start-BitsTransfer -Source '%URL%' -Destination '%DEST%\%FILE%'"
)
if errorlevel 1 (
  echo.
  echo Download failed. You can download the same GGUF manually from Hugging Face.
  exit /b 1
)
echo.
echo Download complete: %DEST%\%FILE%
echo Jarvis can now select the model from the provider dropdown.
endlocal
