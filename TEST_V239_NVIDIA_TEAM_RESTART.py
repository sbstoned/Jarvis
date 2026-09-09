from pathlib import Path
import ast

m=Path("multi_provider.py").read_text(encoding="utf-8")
d=Path("ui/dashboard.py").read_text(encoding="utf-8")
a=Path("ui/app.js").read_text(encoding="utf-8")
h=Path("ui/index.html").read_text(encoding="utf-8")
j=Path("jarvis.py").read_text(encoding="utf-8")
p=Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
l=Path("START_COMMAND_CENTER.bat").read_text(encoding="utf-8")

ast.parse(m); ast.parse(d); ast.parse(j)
assert "get_nvidia_models" in m
assert "choose_nvidia_model" in m
assert "nvidia_model_team_status" in m
assert "NVIDIA_MODEL_SELECTION_FILE" in m
assert "/api/nvidia/models" in d
assert "/api/nvidia/model" in d
assert "nvidia-model-select" in h
assert "AUTO BEST" in h
assert "loadNvidiaModels" in a
assert "CREATE_BREAKAWAY_FROM_JOB" in j

# Restart regression: wrapper ancestors must NEVER be tree-killed.
stop_block=p[p.index("function StopOldStack"):p.index("function DownSnapshot")]
assert "WrapperProcs | ForEach-Object {StopOnly" in stop_block
assert "WrapperProcs | ForEach-Object {KillTree" not in stop_block
assert "offline-confirmed" in p
assert "FULL RESTART SUCCESS" in p
assert "VoiceHealthy $launchStarted" in p
assert "--supervised-restart" in p
assert 'if /I not "%~1"=="--supervised-restart"' in l
print("v2.39 NVIDIA model-team + restart-supervisor regression passed.")
