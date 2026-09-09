import ast
from pathlib import Path

source = Path(__file__).with_name("jarvis.py").read_text(encoding="utf-8")
tree = ast.parse(source)

# Direct coding is intentionally dispatched BEFORE the foreground handler list.
direct_dispatch = source.index("handled, response = handle_direct_coding_request(command)")
handler_list = source.index("handlers = [", direct_dispatch)
restart_in_list = source.index("handle_restart_command,", handler_list)
assert direct_dispatch < handler_list < restart_in_list

# Calendar routing guards and UI/coding recognition remain present.
assert 'normalized.startswith(("add ", "create ", "make ", "put ", "leave "))' in source
assert "and has_calendar_noun" in source
assert "and has_calendar_time" in source
assert '"make all the panels"' in source

# Composite edit + restart authorization is persisted on the background coding job.
assert "_restart_after_success_authorized" in source
assert 'job["restart_after_success"] = True' in source
assert "restart_after_success=auto_restart" in source

failed_command = (
    "make all the panels in the ui adjustable so i can change their size or "
    "move them around dont add anything visually to them when your done editing "
    "the code shutdown and restart all systems do it now"
)
lower = failed_command.lower()
assert "make all the panels" in lower
assert "shutdown and restart all systems" in lower
assert "when your done" in lower

# Current background-agent signature includes restart_after_success.
assert "def _start_background_agent(task, safety_text=None, restart_after_success=False):" in source
assert "safety_subject = task if safety_text is None else safety_text" in source
assert "safety_text=command" in source

# The user's UI request itself contains no destructive action; guardrail prose may.
dangerous = (
    "force push", "force-push", "push --force", "git reset --hard",
    "clean -fd", "delete the repo", "delete repository", "delete the project",
    "delete branch", "remove branch", "rotate credential", "change api key",
    "change the api key", "change secret", "update secret",
    "overwrite remote history", "delete remote",
)
assert not any(p in lower for p in dangerous)

print("Command-routing regression checks passed.")
