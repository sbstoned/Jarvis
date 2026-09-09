from pathlib import Path
import ast, re

source=Path("jarvis.py").read_text(encoding="utf-8")
tree=ast.parse(source)
wanted={"_restart_explicitly_forbidden","_is_pure_restart_intent","_restart_after_success_authorized","_looks_like_coding_request"}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
mod=ast.Module(body=nodes,type_ignores=[])
env={"re":re, "clean_transcription":lambda x:(x or "").strip()}
exec(compile(mod,"<routing-tests>","exec"),env)

cmd=r"Inspect your own live codebase at C:\\Users\\gunsh\\Jarvis. Find one small, safe improvement you can make. Make the change directly, test it, tell me exactly which files you changed and what the tests showed. Do not restart yet."
assert env["_looks_like_coding_request"](cmd) is True
assert env["_restart_explicitly_forbidden"](cmd) is True
assert env["_is_pure_restart_intent"](cmd) is False
assert env["_restart_after_success_authorized"](cmd) is False

assert env["_is_pure_restart_intent"]("shutdown and restart all systems") is True
assert env["_is_pure_restart_intent"]("restart Jarvis") is True

combo="Make one small safe UI improvement, test it, and when you're done shutdown and restart all systems."
assert env["_looks_like_coding_request"](combo) is True
assert env["_restart_after_success_authorized"](combo) is True
assert env["_is_pure_restart_intent"](combo) is False

assert "desktop_automation.open_web(query)" not in source
assert "generic_failure_followup" in source
assert "_latest_failed_agent" in source

dash=Path("ui/dashboard.py").read_text(encoding="utf-8")
assert "pythoncom.CoInitialize()" in dash
assert "pythoncom.CoUninitialize()" in dash
assert "for attempt in range(2)" in dash
print("Jarvis v2.31 routing/research/restart/calendar regression passed.")
