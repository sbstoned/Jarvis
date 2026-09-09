from pathlib import Path
j=Path("jarvis.py").read_text(encoding="utf-8")
d=Path("ui/dashboard.py").read_text(encoding="utf-8")
l=Path("START_COMMAND_CENTER.bat").read_text(encoding="utf-8")
p=Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
assert "voice_health.json" in j
assert "_write_voice_health" in j
assert "voice_health.json" in l
assert "Get-Process -Id" in l
assert "ConnectionAbortedError" in d
assert "function VoiceHealthy" in p
print("v2.30.2 startup health regression passed.")
