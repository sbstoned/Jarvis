from pathlib import Path

dash = Path("ui/dashboard.py").read_text(encoding="utf-8")
launcher = Path("START_COMMAND_CENTER.bat").read_text(encoding="utf-8")
jarvis = Path("jarvis.py").read_text(encoding="utf-8")

assert "import jarvis as jarvis_core" not in dash
assert "Never import jarvis.py inside the dashboard process" in dash
assert 'jarvis_core.process_command' not in dash
assert 'win32_client.Dispatch("Outlook.Application")' in dash

assert "Waiting for voice and dashboard" in launcher
assert "voiceCount -eq 1" in launcher
assert "v2.30.1" in launcher

# Voice singleton must remain in the actual voice process.
assert "_acquire_jarvis_single_instance" in jarvis
assert "WakeWordModel" in jarvis
assert "WhisperModel" in jarvis

print("v2.30.1 startup isolation regression passed.")
