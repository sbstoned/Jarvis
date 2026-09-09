"""Offline regression checks for checkpoint/dashboard compatibility in V42.46."""

from pathlib import Path
import json
import importlib.util
import socket
import sys
import tempfile
import types
import zipfile


ROOT = Path(__file__).resolve().parent
checks = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    checks.append(name)
    print(f"PASS: {name}")


# The release test is intentionally runnable on a clean build machine. Jarvis's
# Windows environment supplies these packages; the stubs prevent an offline
# source-level regression test from trying to use HTTP or load a .env file.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    class _RequestError(Exception):
        pass
    requests_stub.Timeout = _RequestError
    requests_stub.RequestException = _RequestError
    requests_stub.exceptions = types.SimpleNamespace(ReadTimeout=_RequestError)
    requests_stub.get = lambda *args, **kwargs: (_ for _ in ()).throw(_RequestError("offline test"))
    requests_stub.post = requests_stub.get
    sys.modules["requests"] = requests_stub

try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: False
    sys.modules["dotenv"] = dotenv_stub


import jarvis_v4240_repair as repair
import multi_provider as providers
import local_qwen_project as project


identity = project._v36_release_identity()
check("active release identity", identity.get("version") == "V42.50.0", identity)
check("active engine identity", identity.get("engine") == project.V4241_ENGINE, identity)
check("engine marker", (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")
check("engine disk guard", project._v4240_engine_disk_guard()[0] is True)
check("universal language support retained", identity.get("language_framework_toolchain_agnostic") is True)
check("persistent repair memory advertised", identity.get("full_pass_project_repair_memory") is True)
check("accepted stop checkpoint advertised", identity.get("accepted_workspace_checkpoint_on_stop") is True)


candidate, error = project._v36_apply_search_replace(
    "let stale = 1;\nlet stale = 1;\n",
    [{"search": "let stale = 1;", "replace": "let fixed = 2;"}],
)
check("repeated exact patch accepted", not error, error)
check("repeated exact patch changes every occurrence", candidate.count("let fixed = 2;") == 2, candidate)
candidate, error = project._v36_apply_search_replace(
    "x\n" * 65, [{"search": "x\n", "replace": "y\n"}]
)
check("repeated exact patch remains bounded", not candidate and "limit is 64" in error, error)


rust = "query.fetch_all(&mut tx).await?;\nquery.execute(&mut tx).await?;\n"
fixed, reasons = repair._rust_compiler_candidate(
    rust, "Transaction does not implement Executor for &mut Transaction", "src/tools.rs"
)
check("compiler-evidence SQLx repair", "&mut *tx" in fixed and len(reasons) == 1, fixed)


class FakeStream:
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True


stream = FakeStream()
providers._ACTIVE_QWEN_STREAM = stream
check("active model stream cancellation", providers.cancel_active_qwen_stream() is True)
check("active model stream closed", stream.closed is True)
check("cancel is idempotent", providers.cancel_active_qwen_stream() is False)


with tempfile.TemporaryDirectory(prefix="jarvis_v4240_stop_") as temp_name:
    g = {"GENERATED_DIR": Path(temp_name), "_utc_stamp": lambda: "2026-09-05T00:00:00Z"}
    repair.begin_project_run(g, 77, "build fixture", "fixture.zip")
    outcome = repair.request_project_stop(g, "regression stop")
    control = json.loads((Path(temp_name) / repair.CONTROL_FILE).read_text())
    check("stop request accepted", outcome.get("ok") is True, outcome)
    check("stop request persisted immediately", control.get("stop_requested") is True, control)
    check("stop request preserves job identity", control.get("job_id") == 77, control)
    stop_events = (Path(temp_name) / repair.STOP_LOG_FILE).read_text(encoding="utf-8")
    check("early stop event survives shutdown", '"event": "stop_requested"' in stop_events, stop_events)
    repair.finish_project_run(g, 77, {"status": "tested"})
    control = json.loads((Path(temp_name) / repair.CONTROL_FILE).read_text())
    check("finish clears active stop", control.get("stop_requested") is False and control.get("job_id") is None, control)


original_generated_dir = project.GENERATED_DIR
with tempfile.TemporaryDirectory(prefix="jarvis_v4240_package_") as temp_name:
    try:
        project.GENERATED_DIR = Path(temp_name)
        project.begin_project_run(78, "finish checkpoint fixture", "")
        work = Path(temp_name) / "fixture_work"
        (work / "src").mkdir(parents=True)
        (work / "src" / "app.py").write_text('print("checkpoint")\n', encoding="utf-8")
        (work / project.PROJECT_STATE_FILE).write_text(json.dumps({
            "manifest": {"project_name": "fixture", "files": [{"path": "src/app.py"}]},
            "original_request": "finish checkpoint fixture",
            "latest_instruction": "finish checkpoint fixture",
            "unresolved_requirements": ["final validation not run"],
        }), encoding="utf-8")
        ok, detail, checkpoint_path = project.checkpoint_stopped_project(78, "regression stop")
        check("stopped project is not labeled complete", ok is False and "not falsely labeled complete" in detail, detail)
        check("resumable checkpoint ZIP created", checkpoint_path and Path(checkpoint_path).is_file(), checkpoint_path)
        with zipfile.ZipFile(checkpoint_path) as archive:
            names = set(archive.namelist())
        check("checkpoint contains accepted source", "src/app.py" in names, sorted(names))
        check("checkpoint contains stop metadata", repair.MANUAL_CHECKPOINT_FILE in names, sorted(names))
    finally:
        project.finish_project_run(78)
        project.GENERATED_DIR = original_generated_dir


html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
dashboard = (ROOT / "ui" / "dashboard.py").read_text(encoding="utf-8")
jarvis = (ROOT / "jarvis.py").read_text(encoding="utf-8")

check("stable conversation panel id", 'id="conversation-panel"' in html)
check("visible chat resize handle", 'class="panel-resize-handle"' in html and "cursor:nwse-resize" in css)
check("chat input remains addressable", 'id="chat-input"' in html and "pointer-events:auto!important" in css)
check("chat reset control", 'id="chat-panel-reset"' in html and "clearPanelGeometry(chat)" in js)
check("stop checkpoint control", 'id="stop-project-btn"' in html and "stopProjectAndCheckpoint" in js)
check("chat uses shared adjustable-panel system", "initializeAdjustablePanels" in js and "boundedPanelSize(panel" in js)
check("layout persistence schema bumped", "PANEL_LAYOUT_VERSION=2" in js and "jarvis.dashboard.layout.v2" in js)
check("legacy panel layouts rejected", "Number(value.version)===PANEL_LAYOUT_VERSION" in js)
check("chat size kept usable", "const minWidth=chat?260:180" in js and "const minHeight=chat?260:100" in js)
check("chat kept inside viewport", "if(panel.id==='conversation-panel')" in js and "keepPanelReachable" in js)
check("dashboard auto-open defaults on", "JARVIS_DASHBOARD_AUTO_OPEN', '1'" in dashboard)
check("dashboard standalone app launch", "f'--app={launch_url}'" in dashboard and "threading.Timer(0.35" in dashboard)
check("dashboard verifies Jarvis before opening", "health.get('service') == 'jarvis-dashboard'" in dashboard)
check("dashboard uses isolated browser profile", "BrowserProfileV2" in dashboard and "--user-data-dir=" in dashboard)
check("dashboard excludes Qwen port", "candidate == _QWEN_SERVER_PORT" in dashboard)

dashboard_spec = importlib.util.spec_from_file_location("jarvis_dashboard_regression", ROOT / "ui" / "dashboard.py")
dashboard_module = importlib.util.module_from_spec(dashboard_spec)
dashboard_spec.loader.exec_module(dashboard_module)
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = occupied.getsockname()[1]
    original_candidates = dashboard_module._dashboard_port_candidates
    try:
        dashboard_module._dashboard_port_candidates = lambda: [occupied_port, 0]
        fallback_server = dashboard_module._create_dashboard_server()
        fallback_port = fallback_server.server_address[1]
        fallback_server.server_close()
    finally:
        dashboard_module._dashboard_port_candidates = original_candidates
check("dashboard falls back from an occupied port", fallback_port != occupied_port, fallback_port)
check("backend stop command route", "__jarvis_stop_project_and_checkpoint__" in jarvis.lower())
check("worker begins persistent run", "begin_project_run(job_id, request, source_zip)" in jarvis)
check("worker catches cooperative stop", "except ProjectStopRequested as exc:" in jarvis)
check("worker creates stopped checkpoint", "checkpoint_stopped_project(job_id, str(exc))" in jarvis)


# Automatic exhaustion should replace stale preflight/testing heartbeat text with
# the terminal checkpoint state in the durable dashboard control file.
original_generated_dir = project.GENERATED_DIR
with tempfile.TemporaryDirectory(prefix="jarvis_v4245_terminal_ui_") as temp_name:
    try:
        project.GENERATED_DIR = Path(temp_name)
        project.begin_project_run(79, "terminal ui fixture", "")
        work = Path(temp_name) / "terminal_work"
        work.mkdir(parents=True)
        project.register_project_work(work)
        (work / project.V4242_TERMINAL_FILE).write_text(json.dumps({
            "diagnostic_count": 7,
            "repository_token": "terminal-token",
        }), encoding="utf-8")
        project._progress(None, "stale runtime preflight text", stage="testing", percent=82)
        project.finish_project_run(79, {
            "ok": False,
            "automatic_exhausted": True,
            "zip_path": str(Path(temp_name) / "checkpoint.zip"),
        })
        active_state = dict(repair._ACTIVE)
        check("automatic finish replaces stale activity", "checkpoint saved" in str(active_state.get("activity") or "").lower(), active_state)
        check("automatic finish exposes terminal stage", active_state.get("stage") == "checkpoint" and active_state.get("percent") == 100, active_state)
        check("automatic finish retains terminal diagnostics", active_state.get("diagnostic_count") == 7 and active_state.get("repository_token") == "terminal-token", active_state)
    finally:
        project.GENERATED_DIR = original_generated_dir


caps = json.loads((ROOT / "JARVIS_V42_CAPABILITIES.json").read_text())
policy = json.loads((ROOT / "V42_RUNTIME_POLICY.json").read_text())
check("capability manifest version", caps.get("version") == "42.50.0")
check("runtime policy version", policy.get("version") == "42.50.0")
check("checkpoint capability manifest", caps.get("checkpoint_control_v4240", {}).get("dashboard_stop_and_checkpoint") is True)
check("layout recovery policy", policy.get("convergence_v4240", {}).get("legacy_unreachable_chat_layouts_invalidated") is True)


print(f"V42.46 checkpoint compatibility regression: {len(checks)}/{len(checks)} PASS")
