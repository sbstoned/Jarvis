from pathlib import Path

s = Path(__file__).with_name("jarvis.py").read_text(encoding="utf-8")

# Direct coding now routes before entering the generic handler list. This is stronger than
# the old design where it merely appeared before restart inside handlers=[...].
direct = s.index("handled, response = handle_direct_coding_request(command)")
handlers = s.index("handlers = [", direct)
restart = s.index("handle_restart_command,", handlers)
assert direct < handlers < restart, "coding must dispatch before generic restart routing"

# Composite edit+restart authorization must flow through the coding job and orchestrator.
assert "_restart_after_success_authorized(command)" in s
assert "_mark_latest_agent_restart_after_success()" in s
assert "restart_after_success=auto_restart" in s
assert 'if success and finished_job.get("restart_after_success")' in s

print("Composite edit -> validate -> auto-restart routing regression passed.")
