@echo off
setlocal
cd /d "%~dp0"
echo === JARVIS KOKORO ONNX LOCAL TTS SETUP ===
".venv\Scripts\python.exe" -m pip install -U kokoro-onnx soundfile piper-tts
if not exist "tools\kokoro" mkdir "tools\kokoro"
if not exist "tools\kokoro\kokoro-v1.0.onnx" powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile 'tools\kokoro\kokoro-v1.0.onnx'"
if not exist "tools\kokoro\voices-v1.0.bin" powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile 'tools\kokoro\voices-v1.0.bin'"
".venv\Scripts\python.exe" -c "import kokoro_onnx; print('KOKORO ONNX RUNTIME: OK')"
echo Setup complete. Start Jarvis and open VOICE LAB.
pause
