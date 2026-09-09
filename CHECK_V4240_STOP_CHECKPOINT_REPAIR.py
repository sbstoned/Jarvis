import json
import inspect
import tempfile
import zipfile
from pathlib import Path

import local_qwen_project as project
import multi_provider


checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL") + ": " + name)


identity = project._v36_release_identity()
check("release identity", identity.get("version") == "V42.40.0", identity)
check("stop checkpoint advertised", identity.get("user_stop_checkpoint_control") is True)
check("repeated patch validation advertised", identity.get("repeated_exact_patch_staged_in_sandbox") is True)
builder_closure = inspect.getclosurevars(project.generate_project_zip).nonlocals
check("active builder bypasses stale historical marker guards", builder_closure.get("previous_generate") is project._v4235_previous_generate_project_zip, builder_closure)

current = ".execute(&mut transaction)\n.execute(&mut transaction)\n"
candidate, error = project._v36_apply_search_replace(current, [{
    "search": ".execute(&mut transaction)",
    "replace": ".execute(&mut *transaction)",
}])
check("repeated exact repair is staged", not error and candidate.count("&mut *transaction") == 2, error)

rust_source = """pub async fn init(pool: &Pool) {
    let mut tx = pool.begin().await.unwrap();
    query().execute(&mut tx).await.unwrap();
    query().execute(&mut tx).await.unwrap();
}
pub fn update(tool: Tool) {
    let condition_str = match tool.condition {
        ToolCondition::New => \"New\",
        ToolCondition::Good => \"Good\",
    };
    use_value(condition_str);
}
"""
rust_failure = """error[E0277]: the trait bound `&mut Transaction<'_, Sqlite>: Executor<'_>` is not satisfied
error[E0308]: mismatched types
this expression has type `std::string::String`
expected `String`, found `ToolCondition`
"""
fixed, reasons = project._v4240_rust_compiler_candidate(rust_source, rust_failure, "src/db.rs")
check("compiler evidence dereferences every transaction use", fixed.count("execute(&mut *tx)") == 2, fixed)
check("compiler evidence collapses invalid String enum match", "let condition_str = tool.condition.as_str();" in fixed, fixed)
check("compiler repair reasons recorded", len(reasons) == 2, reasons)


class DummyResponse:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


dummy = DummyResponse()
with multi_provider._ACTIVE_QWEN_RESPONSE_LOCK:
    multi_provider._ACTIVE_QWEN_RESPONSES.add(dummy)
try:
    count = multi_provider.cancel_active_qwen_requests()
finally:
    with multi_provider._ACTIVE_QWEN_RESPONSE_LOCK:
        multi_provider._ACTIVE_QWEN_RESPONSES.discard(dummy)
check("active Qwen stream can be cancelled", count >= 1 and dummy.closed)

old_generated = project.GENERATED_DIR
with tempfile.TemporaryDirectory(prefix="jarvis_v4240_check_") as td:
    root = Path(td)
    project.GENERATED_DIR = root / "generated"
    project.GENERATED_DIR.mkdir()
    work = root / "working"
    work.mkdir()
    (work / "main.py").write_text("print('preserved')\n", encoding="utf-8")
    project._save_project_state(work, {
        "manifest": {"project_name": "checkpoint-fixture", "files": [{"path": "main.py", "purpose": "entrypoint"}]},
        "original_request": "make a fixture",
        "latest_instruction": "finish it",
        "unresolved_requirements": ["validation not finished"],
    })
    project.begin_project_run(77)
    project._v4240_register_active_workspace(work, user_request="finish it", source_zip="fixture.zip")
    requested = project.request_project_stop(77, "regression test")
    check("stop request waits for worker-safe boundary", requested.get("pending") is True and not requested.get("zip_path"), requested)
    outcome = project.checkpoint_stopped_project(77, "regression test")
    checkpoint = Path(outcome.get("zip_path") or "")
    names = []
    if checkpoint.is_file():
        with zipfile.ZipFile(checkpoint) as archive:
            names = archive.namelist()
    check("manual stop creates checkpoint", outcome.get("ok") is True and checkpoint.is_file(), outcome)
    check("checkpoint preserves source", "main.py" in names, names)
    check("checkpoint is resumable", ".jarvis_resume.json" in names, names)
    check("checkpoint records manual stop", project.MANUAL_CHECKPOINT_FILE in names, names)
    projection = json.loads((work / project.V4225_PROJECTION_FILE).read_text(encoding="utf-8"))
    check("checkpoint event records current engine", projection.get("version") == "V42.40.0" and projection.get("engine") == project.V4240_ENGINE, projection)
    project.finish_project_run(77)
project.GENERATED_DIR = old_generated

ui_root = Path(__file__).resolve().parent / "ui"
index = (ui_root / "index.html").read_text(encoding="utf-8")
app = (ui_root / "app.js").read_text(encoding="utf-8")
dashboard = (ui_root / "dashboard.py").read_text(encoding="utf-8")
jarvis = (Path(__file__).resolve().parent / "jarvis.py").read_text(encoding="utf-8")
check("chat has stop button", 'id="stop-project-btn"' in index)
check("button invokes checkpoint command", "__JARVIS_STOP_PROJECT_AND_CHECKPOINT__" in app)
check("browser and server build identities match", app.count("v2.61-stop-checkpoint") >= 2 and "v2.61-stop-checkpoint" in dashboard)
check("Jarvis handles checkpoint command before normal routing", "__jarvis_stop_project_and_checkpoint__" in jarvis)
check("worker packages only after cooperative unwind", "outcome = checkpoint_stopped_project(job_id" in jarvis)

failed = [name for name, ok, _ in checks if not ok]
if failed:
    raise SystemExit("V42.40 regression failed: " + ", ".join(failed))
print(f"V42.40 regression: {len(checks)}/{len(checks)} PASS")
