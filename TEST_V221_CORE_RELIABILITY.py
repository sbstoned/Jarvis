from pathlib import Path
j=Path("jarvis.py").read_text(encoding="utf-8")
ps=Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
launcher=Path("START_COMMAND_CENTER.bat").read_text(encoding="utf-8")
voice=Path("START_VOICE_ENGINE.bat").read_text(encoding="utf-8")

assert 'Wake phrase: "Hey Jarvis"' in j
assert 'wake_model.predict' in j
assert '_write_voice_health("listening"' in j
assert '"shut down and restart"' in j
assert 'restart_after_success' in j
assert '_complete_authorized_edit_restart' in j
assert 'daemon=False' in j
assert 'system restart is the priority' in j.lower()
assert 'START_VOICE_ENGINE.bat' in launcher
assert '$dash -and $voice' in launcher
assert 'FULL RESTART SUCCESS dashboard=true voiceEngineCount=1' in ps
assert 'DOWN CHECK' in ps
assert 'jarvis.py' in voice
print("Jarvis v2.21 reliability regression passed.")
