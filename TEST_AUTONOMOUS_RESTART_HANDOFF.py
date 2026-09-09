import ast
import subprocess
import threading
from datetime import datetime
from pathlib import Path


def function_node(tree, name):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


source = Path("jarvis.py").read_text(encoding="utf-8")
tree = ast.parse(source)
namespace = {
    "agent_jobs": {
        7: {
            "status": "completed",
            "restart_after_success": True,
            "result": "Fixed the autonomous restart handoff without truncating the report.\nValidation: pytest passed (12 tests).",
        }
    },
    "agent_jobs_lock": threading.RLock(),
    "datetime": datetime,
    "re": __import__("re"),
}
events = []
namespace.update({
    "_save_agent_jobs": lambda: events.append("save") or True,
    "update_live_state": lambda state=None, **extra: events.append(("dashboard", state, extra)) or True,
    "speak_elevenlabs": lambda text: events.append(("speak", text)),
    "_spoken_version": lambda text: text,
    "_schedule_jarvis_stack_restart": lambda: events.append("schedule") or (True, "scheduled"),
    "log": lambda text: events.append(("log", text)),
})
for name in (
    "_extract_agent_test_report",
    "_short_agent_change_confirmation",
    "_complete_authorized_edit_restart",
):
    module = ast.Module(body=[function_node(tree, name)], type_ignores=[])
    exec(compile(module, "jarvis.py", "exec"), namespace)

# This only runs the isolated handoff with mocked speech/scheduler. It cannot restart Jarvis.
namespace["_complete_authorized_edit_restart"](7)
job = namespace["agent_jobs"][7]
assert job["full_result"] == job["result"]
assert "pytest passed" in job["test_report"]
assert job["restart_handoff_stage"] == "supervisor_launching"

first_save = events.index("save")
completed_dashboard = next(i for i, event in enumerate(events) if isinstance(event, tuple) and event[:2] == ("dashboard", "COMPLETED"))
speech = next(i for i, event in enumerate(events) if isinstance(event, tuple) and event[0] == "speak")
restarting_dashboard = next(i for i, event in enumerate(events) if isinstance(event, tuple) and event[:2] == ("dashboard", "RESTARTING"))
schedule = events.index("schedule")
assert first_save < completed_dashboard < speech < restarting_dashboard < schedule, events
completion_payload = events[completed_dashboard][2]["agent_completion"]
assert completion_payload["full_result"] == job["full_result"]
assert completion_payload["test_report"] == job["test_report"]

assert 'job["full_result"] = str(result or "")' in source
assert 'job["test_report"] = _extract_agent_test_report(result)' in source
assert "completion_persisted = _save_agent_jobs()" in source
assert 'if success and finished_job.get("restart_after_success") and completion_persisted:' in source
assert 'script = os.path.join(JARVIS_DIR, "HARD_RESTART_ALL_SYSTEMS.ps1")' in source
assert 'getattr(subprocess, "DETACHED_PROCESS", 0)' in source

supervisor = Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
for required in (
    "function IsFullyDown",
    "dashboardProcesses",
    "voiceProcesses",
    "hardwareProcesses",
    "wrapperProcesses",
    "hermesListeners",
    "hermesProcesses",
    "hermesHttp",
    "START_COMMAND_CENTER.bat",
    "--supervised-restart",
    "VoiceHealthy $launchStarted",
    "function OpenCommandCenter",
    "FULL RESTART SUCCESS",
    "FAILURE verify-down",
    "FAILURE verify-up",
):
    assert required in supervisor, required
assert supervisor.index("if(-not (IsFullyDown $down))") < supervisor.index("STAGE launch: starting detached fresh stack")
assert supervisor.index("STAGE verify-up: SUCCESS") < supervisor.index("OpenCommandCenter))")
assert "StopOnly $voicePid" in supervisor

launcher = Path("START_COMMAND_CENTER.bat").read_text(encoding="utf-8")
assert 'if /I "%~1"=="--supervised-restart"' in launcher
assert "Restart supervisor owns the browser reopen" in launcher

ui = Path("ui/app.js").read_text(encoding="utf-8")
assert "a.full_result||a.result" in ui
assert "<b>Test report</b>" in ui
assert ".slice(0,800)" not in ui
assert ".slice(0,650)" not in ui

# Parse the supervisor without executing it.
parse_command = (
    "$errors=$null; "
    "[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'HARD_RESTART_ALL_SYSTEMS.ps1'),"
    "[ref]$null,[ref]$errors) | Out-Null; "
    "if($errors.Count){$errors | ForEach-Object {$_.ToString()}; exit 1}"
)
parsed = subprocess.run(
    ["powershell.exe", "-NoProfile", "-Command", parse_command],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=20,
)
assert parsed.returncode == 0, parsed.stdout + parsed.stderr
javascript = subprocess.run(
    ["node.exe", "--check", "ui/app.js"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=20,
)
assert javascript.returncode == 0, javascript.stdout + javascript.stderr

print("Autonomous completion -> detached restart handoff regression passed (restart mocked; no real restart performed).")
