from pathlib import Path
import ast
j=Path("jarvis.py").read_text(encoding="utf-8")
r=Path("restart_supervisor.py").read_text(encoding="utf-8")
p=Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
ast.parse(j); ast.parse(r)
block=j[j.index("def _schedule_jarvis_stack_restart"):j.index("def _announce_agent_completion_if_needed")]
assert "restart_supervisor.py" in block
assert "sys.executable" in block
assert "supervisor-ready" in block
assert "powershell.exe" not in block
assert "os._exit" not in block
assert "_resolve_tts_output_device" in j
assert "device=tts_device" in j
assert "TTS first PCM audio received" in j
assert "monitor_started=False" in j
assert "BARGE_IN_GRACE_SECONDS = 1.25" in j
assert "JarvisFullRestart_v245" in p
print("v2.45 restart + speech regression passed.")
