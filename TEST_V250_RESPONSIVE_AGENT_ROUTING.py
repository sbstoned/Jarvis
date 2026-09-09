from pathlib import Path
import ast
j=Path("jarvis.py").read_text(encoding="utf-8")
a=Path("ui/app.js").read_text(encoding="utf-8")
ast.parse(j)

block=j[j.index("def process_command"):j.index("# ============================================================\n# VOICE ENGINE HEALTH")]
status_pos=block.index("_active_agent_status_request(command)")
coding_pos=block.index("_looks_like_coding_request(command)")
lock_pos=block.index("with foreground_command_lock:")
assert status_pos < lock_pos
assert coding_pos < lock_pos
assert "handle_direct_coding_request," not in block[lock_pos:]
assert "JarvisFastReplySpeech" in j
assert "Turn {turn} of {max_turns or '?'}" in j
assert "providerChoiceNow.startsWith('nvidia::')" in a
print("v2.50 responsive coding/status routing regression passed.")
