"""Offline production-path regression for Jarvis V42.46."""

from pathlib import Path
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import types


ROOT = Path(__file__).resolve().parent
checks = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    checks.append(name)
    print(f"PASS: {name}")


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


import jarvis_v4242_memory as memory
import jarvis_v4242_mcp_registry as mcp
import jarvis_v4242_repair as repair
import jarvis_v4240_repair as compat40
import jarvis_v4241_repair as compat41
import local_qwen_project as project


identity = project._v36_release_identity()
check("active V42.46 identity", identity.get("version") == "V42.50.0", identity)
check("revision convergence engine active", identity.get("engine") == repair.ENGINE, identity)
check("active engine marker", (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")
check("V42.46 disk guard", project._v4242_engine_disk_guard()[0] is True)
check("automatic checkpoint advertised", identity.get("automatic_exhausted_checkpoint") is True)
check("shared WAL memory advertised", identity.get("shared_sqlite_wal_worker_memory") is True)
check("structured worker handoff advertised", identity.get("worker_structured_handoff_contract") is True)
check("universal adapter boundary retained", identity.get("language_framework_toolchain_agnostic") is True)

# Reproduce the real public call chain: V42.46 -> retained V42.41 guard ->
# registered base generator/editor. Every compatibility guard must validate the
# final installed identity rather than rejecting its historical version.
layered = dict(vars(project))
base_calls = []
base_generate = lambda *_args, **_kwargs: base_calls.append("generate") or (True, "BASE_REACHED", "fixture.zip")
base_edit = lambda *_args, **_kwargs: base_calls.append("edit") or (True, "BASE_EDIT_REACHED", "fixture.zip")
layered["generate_project_zip"] = base_generate
layered["analyze_and_edit_project_zip"] = base_edit
layered["_v4235_previous_generate_project_zip"] = base_generate
layered["_v4235_previous_analyze_project_zip"] = base_edit
compat40.install(layered)
compat41.install(layered)
repair.install(layered)
generate_result = layered["generate_project_zip"]("fixture")
edit_result = layered["analyze_and_edit_project_zip"]("fixture", "fixture.zip")
check("nested legacy generation guards reach current base generator", generate_result[0] is True and generate_result[1] == "BASE_REACHED", generate_result)
check("nested legacy edit guards reach current base editor", edit_result[0] is True and edit_result[1] == "BASE_EDIT_REACHED", edit_result)
check("both guarded public entrypoints reach their registered implementation", base_calls == ["generate", "edit"], base_calls)
stale_identity = {"_v36_release_identity": lambda: {"version": "V42.41.0"}}
check("genuinely stale process identity still differs from disk release", compat40.active_process_version(stale_identity, "42.41.0") != "V42.50.0")

numbered_search = "36: pub struct Tool {\n37:     pub id: i64,\n38: }"
numbered_replace = "36: pub struct Tool {\n37:     pub id: i64,\n38:     pub name: String,\n39: }"
patched, patch_error = project._v36_apply_search_replace(
    "pub struct Tool {\n    pub id: i64,\n}\n",
    [{"search": numbered_search, "replace": numbered_replace}],
)
check("repeated-patch wrapper preserves numbered transport recovery", not patch_error, patch_error)
check("normalized replacement is applied without viewer prefixes", "pub name: String" in patched and "36:" not in patched, patched)


failure_a = """V36 COMPONENT FAILED [rust | rust | src-tauri]:
Compiling fixture v0.1.0 (C:\\work\\trial_01\\src-tauri)
error[E0255]: the name `init_db` is defined multiple times
 --> src\\categories.rs:79:1
error[E0432]: unresolved import `crate::db::Pool`
 --> src\\tools.rs:1:26
error[E0433]: cannot find module or crate `chrono` in this scope
 --> src\\checkout.rs:36:15
error: could not compile `fixture` (lib) due to 3 previous errors
"""
failure_b = """V36 COMPONENT FAILED [rust | rust | src-tauri]:
Finished in 18.3s
error[E0433]: cannot find module or crate `chrono` in this scope
 --> src/checkout.rs:999:4
error[E0432]: unresolved import `crate::db::Pool`
 --> src/tools.rs:44:8
error[E0255]: the name `init_db` is defined multiple times
 --> src/categories.rs:101:7
error: could not compile `fixture` (lib) due to 3 previous errors
"""
norm_a = repair.normalized_diagnostics(failure_a)
norm_b = repair.normalized_diagnostics(failure_b)
check("diagnostic normalization ignores order and line churn", norm_a["signature"] == norm_b["signature"], (norm_a, norm_b))
component = {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"}
check("revision key excludes volatile diagnostic text", repair.revision_key(component, "repo-1") == repair.revision_key(component, "repo-1"))
check("fresh repository revision resets breaker key", repair.revision_key(component, "repo-1") != repair.revision_key(component, "repo-2"))

large_failure = failure_a + "\n" + "\n".join(
    f"error[E0599]: repeated downstream symptom {index}\n --> src/tools.rs:{index + 20}:1"
    for index in range(160)
) + "\nerror: could not compile `fixture` (lib) due to 163 previous errors\n"
compacted = repair.compact_component_failure(large_failure)
check("full-stream compaction stays below legacy audit boundary", len(compacted) <= 11200, len(compacted))
check("full-stream compaction retains first root-cause codes", "E0255" in compacted and "E0432" in compacted and "E0433" in compacted, compacted[:1200])
check("full-stream compaction retains compiler total", "163 previous errors" in compacted, compacted[-800:])

with tempfile.TemporaryDirectory(prefix="jarvis_v4242_release_reopen_") as temp_name:
    root = Path(temp_name)
    (root / "main.go").write_text("package main\n", encoding="utf-8")
    reopen_component = {"id": "go", "root": ".", "toolchain_adapter": "go"}
    reopen_key = repair.revision_key(reopen_component, "same-source")
    (root / repair.LEDGER_FILE).write_text(json.dumps({
        "version": "V42.46.1", "revisions": {reopen_key: {
            "id": reopen_key, "repository_token": "same-source", "component": "go",
            "component_root": ".", "adapter": "go", "diagnostic_signatures": [],
            "attempts": [], "model_cycles": 1, "exhausted": True, "terminal": True,
        }},
    }), encoding="utf-8")
    reopen_g = {
        "_v429_progress_token": lambda _work: "same-source",
        "_utc_stamp": lambda: "2026-09-05T04:01:00Z",
    }
    _, reopened, _ = repair._revision_record(reopen_g, root, reopen_component, "main.go:1:1: error: fixture")
    check("new repair release reopens older terminal revision", reopened.get("exhausted") is False and reopened.get("terminal") is False, reopened)
    current_ledger = json.loads((root / repair.LEDGER_FILE).read_text(encoding="utf-8"))
    current_ledger["revisions"][reopen_key]["exhausted"] = True
    current_ledger["revisions"][reopen_key]["terminal"] = True
    (root / repair.LEDGER_FILE).write_text(json.dumps(current_ledger), encoding="utf-8")
    _, retained, _ = repair._revision_record(reopen_g, root, reopen_component, "main.go:2:1: error: same fixture")
    check("same release does not repeatedly reset revision state", retained.get("exhausted") is True and retained.get("terminal") is True, retained)


with tempfile.TemporaryDirectory(prefix="jarvis_v4242_checkpoint_recovery_") as temp_name:
    generated = Path(temp_name) / "generated_projects"
    nested = generated / "resume_job" / "trial_01"
    nested.mkdir(parents=True)
    (nested / "main.go").write_text("package main\n", encoding="utf-8")
    (nested / "JARVIS_PROJECT_STATE.json").write_text(json.dumps({
        "manifest": {"project_name": "fixture", "acceptance_criteria": ["build passes"]},
        "original_request": "finish fixture", "latest_instruction": "repair fixture",
        "unresolved_requirements": ["compiler error"],
    }), encoding="utf-8")
    checkpoint_path = generated / "fixture_checkpoint.zip"
    control_events = []
    control_g = {
        "GENERATED_DIR": generated,
        "PROJECT_STATE_FILE": "JARVIS_PROJECT_STATE.json",
        "V4242_RUN_STATE_FILE": repair.RUN_STATE_FILE,
        "_utc_stamp": lambda: "2026-09-05T04:00:00Z",
        "_existing_real_source_files": lambda work: ["main.go"] if (Path(work) / "main.go").is_file() else [],
        "_append_project_event": lambda *args, **kwargs: control_events.append((args, kwargs)),
        "_package_resume_checkpoint_zip": lambda *_args, **_kwargs: (checkpoint_path, 2),
    }
    old_active = dict(repair.v4240._ACTIVE)
    try:
        repair.v4240.begin_project_run(control_g, 42422, "finish fixture", "fixture.zip")
        repair.v4240.register_project_work(control_g, nested)
        check("nested workspace registered during active job", repair.v4240._find_active_work(control_g) == nested.resolve())
        stopped = repair.v4240.checkpoint_stopped_project(
            control_g, 42422, "V42.46 automatically stopped after bounded repair exhaustion."
        )
        check("automatic exhaustion checkpoints registered nested source", stopped[2] == checkpoint_path and "CHECKPOINT ZIP" in stopped[1], stopped)
        repair.v4240.finish_project_run(control_g, 42422, {"zip_path": str(checkpoint_path), "ok": False})
        check("worker finish retains last workspace", repair.v4240._ACTIVE.get("last_work") == str(nested.resolve()), repair.v4240._ACTIVE)
        check("worker finish retains structured result", repair.v4240._ACTIVE.get("last_result", {}).get("zip_path") == str(checkpoint_path), repair.v4240._ACTIVE)
        check("late recovery still resolves finished workspace", repair.v4240._find_active_work(control_g) == nested.resolve())
    finally:
        repair.v4240._ACTIVE.clear()
        repair.v4240._ACTIVE.update(old_active)
        repair.v4240._STOP_EVENT.clear()


full_failure = """V36 COMPONENT FAILED [rust | rust | src-tauri]:
error[E0255]: the name `init_db` is defined multiple times
 --> src/categories.rs:8:1
error[E0432]: unresolved import `crate::db::init_persons_table`
 --> src/persons.rs:1:26
error[E0432]: unresolved import `crate::db::Pool`
 --> src/tools.rs:1:26
error[E0433]: cannot find module or crate `chrono` in this scope
 --> src/checkout.rs:4:15
error[E0433]: cannot find `Error` in `thiserror`
 --> src/checkout.rs:5:31
error[E0599]: no method named `join` found for reference `&PathResolver<Runtime>` in the current scope
 --> src/app.rs:6:37
error[E0308]: mismatched types
 --> src/app.rs:10:13
 expected reference `&Pool<_>`
 found struct `Pool<_>`
error[E0733]: recursion in an async fn requires boxing
 --> src/persons.rs:4:1
error: could not compile `fixture` (lib) due to 8 previous errors
"""
app_source = """use crate::db::init_db;
use sqlx::SqlitePool;
use tauri::{AppHandle, Manager};
pub async fn init_app(app_handle: AppHandle) -> Result<SqlitePool, Box<dyn std::error::Error>> {
    let db_path = app_handle.path().join("data.sqlite").unwrap();
    let pool = SqlitePool::connect("file:data.sqlite").await?;
    init_db(pool).await?;
    Ok(pool)
}
"""
category_source = """use crate::db::init_db;
use sqlx::{Pool, Sqlite};
pub async fn init_db(pool: &Pool<Sqlite>) -> Result<(), sqlx::Error> { Ok(()) }
"""
persons_source = """use crate::db::{init_db, init_persons_table};
use sqlx::SqlitePool;
use std::error::Error;
pub async fn init_persons_table(pool: &SqlitePool) -> Result<(), Box<dyn Error + Send + Sync>> {
    init_db(pool).await?;
    init_persons_table(pool).await
}
"""
tools_source = """use crate::db::{init_db, Pool};
pub async fn init_tools_table(pool: &Pool) { let _ = pool; }
"""
checkout_source = """pub async fn checkout() -> Result<(), sqlx::Error> {
    let now = chrono::Utc::now();
    return Err(thiserror::Error::Msg(format!("already checked out")));
}
"""

app_fixed, app_reasons = repair.rust_compiler_candidate(app_source, full_failure, "src-tauri/src/app.rs")
category_fixed, _ = repair.rust_compiler_candidate(category_source, full_failure, "src-tauri/src/categories.rs")
persons_fixed, _ = repair.rust_compiler_candidate(persons_source, full_failure, "src-tauri/src/persons.rs")
tools_fixed, _ = repair.rust_compiler_candidate(tools_source, full_failure, "src-tauri/src/tools.rs")
checkout_fixed, _ = repair.rust_compiler_candidate(checkout_source, full_failure, "src-tauri/src/checkout.rs")
check("Tauri path API repaired", ".path().app_data_dir()?.join(" in app_fixed, app_fixed)
check("owned SQLx pool borrowed", "init_db(&pool).await?" in app_fixed, app_fixed)
check("valid imports in unrelated files preserved", "use crate::db::init_db;" in app_fixed, app_fixed)
check("duplicate local definition import removed", "use crate::db::init_db;" not in category_fixed, category_fixed)
check("unresolved self import removed", "init_persons_table};" not in persons_fixed, persons_fixed)
check("direct recursive async forwarder closed", "Ok(())" in persons_fixed, persons_fixed)
check("SQLx pool imported directly", "use sqlx::SqlitePool as Pool;" in tools_fixed, tools_fixed)
check("invalid thiserror value replaced by declared error", "sqlx::Error::Protocol" in checkout_fixed, checkout_fixed)
check("Tauri repair reason retained", any("Tauri 2" in reason for reason in app_reasons), app_reasons)
cargo_fixed, cargo_reasons = repair._cargo_candidate("[dependencies]\nsqlx = \"0.8\"\n", full_failure)
check("missing direct crate added to Cargo", 'chrono = { version = "0.4"' in cargo_fixed, cargo_fixed)
check("dependency repair records evidence", any("chrono" in reason for reason in cargo_reasons), cargo_reasons)


def copy_candidate(root):
    handle = tempfile.TemporaryDirectory(prefix="jarvis_v4242_candidate_")
    clone = Path(handle.name) / "candidate"
    shutil.copytree(root, clone)
    return handle, clone


events = []
with tempfile.TemporaryDirectory(prefix="jarvis_v4242_cluster_") as temp_name:
    root = Path(temp_name)
    source_root = root / "src-tauri" / "src"
    source_root.mkdir(parents=True)
    (source_root / "app.rs").write_text(app_source, encoding="utf-8")
    (source_root / "categories.rs").write_text(category_source, encoding="utf-8")
    (source_root / "persons.rs").write_text(persons_source, encoding="utf-8")
    (source_root / "tools.rs").write_text(tools_source, encoding="utf-8")
    (source_root / "checkout.rs").write_text(checkout_source, encoding="utf-8")
    (root / "src-tauri" / "Cargo.toml").write_text("[dependencies]\nsqlx = \"0.8\"\n", encoding="utf-8")

    def validator(clone, *_args):
        check("cluster candidate repairs every compiler-owned source", all([
            ".app_data_dir()?" in (clone / "src-tauri/src/app.rs").read_text(),
            "use crate::db::init_db;" not in (clone / "src-tauri/src/categories.rs").read_text(),
            "Ok(())" in (clone / "src-tauri/src/persons.rs").read_text(),
            "SqlitePool as Pool" in (clone / "src-tauri/src/tools.rs").read_text(),
            "sqlx::Error::Protocol" in (clone / "src-tauri/src/checkout.rs").read_text(),
            "chrono =" in (clone / "src-tauri/Cargo.toml").read_text(),
        ]))
        return False, "error: could not compile due to 2 previous errors"

    fake_g = {
        "_v4236_native_diagnostics": lambda *_args: [],
        "_v4236_rank_native_targets": lambda *_args: [],
        "_copy_project_for_candidate_validation": copy_candidate,
        "_v35_validate_component": validator,
        "_progress": lambda *_args, **_kwargs: None,
        "_v36_checkpoint_file": lambda *_args, **_kwargs: None,
        "_v413_mark_accepted": lambda *_args, **_kwargs: None,
        "_append_project_event": lambda *args, **kwargs: events.append((args, kwargs)),
    }
    accepted, outcome = repair.deterministic_component_transaction(
        fake_g, "finish fixture", {"components": [component]}, root, full_failure, component,
    )
    check("multi-file compiler transaction accepted strict decrease", accepted and outcome.get("after") == 2, outcome)
    check("connected source files promoted atomically", "SqlitePool as Pool" in (source_root / "tools.rs").read_text())
    check("dependency manifest promoted atomically", "chrono =" in (root / "src-tauri/Cargo.toml").read_text())


with tempfile.TemporaryDirectory(prefix="jarvis_v4242_memory_") as temp_name:
    root = Path(temp_name)
    database = root / "shared.sqlite3"
    store = memory.SharedMemoryStore(database)
    project_dir = root / "project"
    project_dir.mkdir()
    store.append_event("conversation_user", {"text": "password=hunter2"}, scope="personal")
    store.append_event("worker_started", {"task": "inspect"}, scope="worker", project=project_dir, worker_id="1")
    store.append_event("worker_completed", {"result": "validated"}, scope="worker", project=project_dir, worker_id="2", status="completed")
    store.upsert_fact("accepted_revision", "abc123", scope="project", project=project_dir)
    context = store.context_packet(project=project_dir)
    check("shared worker events visible across worker identities", "worker_started" in context and "worker_completed" in context, context)
    check("raw personal transcript excluded from project worker context", "hunter2" not in context and "conversation_user" not in context, context)
    snapshot = store.export_project_snapshot(project_dir, extra={"status": "testing"})
    snapshot_text = snapshot.read_text(encoding="utf-8")
    check("project snapshot excludes personal transcript", "hunter2" not in snapshot_text and "conversation_user" not in snapshot_text, snapshot_text)
    with sqlite3.connect(database) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    check("shared memory uses WAL", str(journal_mode).lower() == "wal", journal_mode)


with tempfile.TemporaryDirectory(prefix="jarvis_v4242_mcp_") as temp_name:
    root = Path(temp_name)
    shutil.copy2(ROOT / mcp.CATALOG_FILE, root / mcp.CATALOG_FILE)
    config = root / "mcp_servers.json"
    config.write_text(json.dumps({"mcpServers": {"local-python": {"command": sys.executable, "args": ["--token=secret"]}}}), encoding="utf-8")
    report = mcp.configured_servers(root)
    check("MCP configuration discovered", report.get("config_found") is True, report)
    check("configured local MCP command preflighted", report.get("available_count") == 1, report)
    check("MCP report does not expose arguments or token", "secret" not in json.dumps(report), report)
    context = mcp.capability_context(root)
    check("MCP context includes prioritized development capabilities", "github" in context and "playwright" in context, context)


with tempfile.TemporaryDirectory(prefix="jarvis_v4242_breaker_") as temp_name:
    root = Path(temp_name)
    (root / "main.go").write_text("package main\n", encoding="utf-8")
    legacy = {
        "version": "V42.41.0", "issues": {
            "volatile-a": {"id": "volatile-a", "repository_token": "same-revision", "component": "go", "strategy_generation": repair.STRATEGY_GENERATION, "exhausted": True, "attempts": [{"strategy": "bounded_model_component_transaction"}, {"strategy": "bounded_model_component_transaction"}]},
            "volatile-b": {"id": "volatile-b", "repository_token": "same-revision", "component": "go", "strategy_generation": repair.STRATEGY_GENERATION, "exhausted": False, "attempts": []},
        },
    }
    (root / "JARVIS_V4241_REPAIR_LEDGER.json").write_text(json.dumps(legacy), encoding="utf-8")
    model_calls = []
    recorded_events = []
    old_memory_db = os.environ.get("JARVIS_SHARED_MEMORY_DB")
    os.environ["JARVIS_SHARED_MEMORY_DB"] = str(root / "memory.sqlite3")
    fake = {
        "Path": Path, "__file__": str(ROOT / "local_qwen_project.py"),
        "_utc_stamp": lambda: "2026-09-05T01:00:00Z",
        "_v429_progress_token": lambda _work: "same-revision",
        "_v4237_repair_component_failure": lambda *_args, **_kwargs: model_calls.append(1) or False,
        "_v36_release_identity": lambda: {}, "_v36_stack_skill_names": lambda _manifest: [],
        "generate_project_zip": lambda *_args, **_kwargs: (False, "fixture", None),
        "analyze_and_edit_project_zip": lambda *_args, **_kwargs: (False, "fixture", None),
        "checkpoint_stopped_project": lambda *_args, **_kwargs: (False, "checkpoint", None),
        "_append_project_event": lambda *args, **kwargs: recorded_events.append((args, kwargs)),
        "_v4235_durable_append_project_event": lambda *args, **kwargs: recorded_events.append((args, kwargs)) or {},
        "_progress": lambda *_args, **_kwargs: None,
        "_v4235_base_progress": lambda *_args, **_kwargs: None,
        "_qwen_call": lambda *_args, **_kwargs: (False, "offline"),
        "_v4235_previous_qwen_call": lambda *_args, **_kwargs: (False, "offline"),
        "_v35_validate_component": lambda *_args, **_kwargs: (False, large_failure),
    }
    repair.install(fake)
    validator_ok, validator_output = fake["_v35_validate_component"](
        root, {}, {"id": "go", "root": ".", "toolchain_adapter": "go"}, "finish"
    )
    check("failed validator returns compact full-stream evidence", validator_ok is False and len(validator_output) <= 11200, len(validator_output))
    check("full validator output is retained in project", (root / repair.VALIDATOR_OUTPUT_FILE).read_text(encoding="utf-8") == large_failure, root)
    validator_record = json.loads((root / repair.VALIDATOR_EVIDENCE_FILE).read_text(encoding="utf-8"))
    check("structured validator evidence records provenance", validator_record.get("full_output_sha256") and validator_record.get("diagnostic_count") == 163, validator_record)
    go_manifest = {"components": [{"id": "go", "root": ".", "toolchain_adapter": "go"}]}
    go_failure = "V36 COMPONENT FAILED [go | go | .]:\nmain.go:1:1: error: fixture\ngo build failed due to 1 previous error"
    old_active = dict(repair.v4240._ACTIVE)
    repair.v4240._ACTIVE.update({"job_id": 4242, "work": "", "last_work": ""})
    try:
        fake["_append_project_event"](root, "fixture_event", "register accepted workspace")
        check("V42.46 event wrapper registers accepted workspace", repair.v4240._ACTIVE.get("work") == str(root.resolve()), repair.v4240._ACTIVE)
        fake["_v4237_repair_component_failure"]("finish", go_manifest, root, go_failure)
        raised = False
    except repair.AutomaticRepairExhausted:
        raised = True
    finally:
        repair.v4240._ACTIVE.clear()
        repair.v4240._ACTIVE.update(old_active)
        if old_memory_db is None:
            os.environ.pop("JARVIS_SHARED_MEMORY_DB", None)
        else:
            os.environ["JARVIS_SHARED_MEMORY_DB"] = old_memory_db
    ledger = json.loads((root / repair.LEDGER_FILE).read_text())
    revision = next(iter(ledger["revisions"].values()))
    check("legacy issue-hash churn merged into one revision record", set(revision.get("legacy_issue_ids") or []) == {"volatile-a", "volatile-b"}, revision)
    check("exhausted revision stops before another model call", raised and not model_calls, model_calls)
    check("automatic terminal state persisted", (root / repair.TERMINAL_FILE).is_file())
    check("project run state requests checkpoint", json.loads((root / repair.RUN_STATE_FILE).read_text()).get("final_action") == "checkpoint")
    check("terminal event emitted", any(args[1] == "v4242_revision_exhausted_checkpoint" for args, _ in recorded_events if len(args) > 1), recorded_events)


with tempfile.TemporaryDirectory(prefix="jarvis_v4242_state_reducer_") as temp_name:
    root = Path(temp_name)
    (root / "JARVIS_PROJECT_STATE.json").write_text(json.dumps({
        "unresolved_requirements": ["stale React error"],
        "current_blocker": {"problem": "stale React error"},
    }), encoding="utf-8")
    (root / "JARVIS_V429_WHOLE_PROJECT_AUDIT.json").write_text(json.dumps({
        "updated_at": "2026-09-05T01:02:00Z", "accepted_token": "current-revision",
        "clean": False,
        "issues": [{"file": "src-tauri/src/tools.rs", "kind": "component_validation", "problem": "current Rust error"}],
        "components": [{"id": "react", "root": ".", "adapter": "react", "ok": True}, {"id": "rust", "root": "src-tauri", "adapter": "rust", "ok": False}],
    }), encoding="utf-8")
    reduced = project._v4242_reconcile_project_state(root, "v429_whole_project_audit")
    check("project state reducer removes stale historical blocker", "stale React error" not in json.dumps(reduced), reduced)
    check("project state reducer records current audit blocker", "current Rust error" in json.dumps(reduced), reduced)
    check("project state reducer records component validation truth", reduced.get("last_audit", {}).get("components", [])[0].get("ok") is True, reduced)
    reduced = project._v4242_reconcile_project_state(root, "whole_project_green")
    check("green acceptance clears current unresolved state", reduced.get("stage") == "complete" and not reduced.get("unresolved_requirements") and reduced.get("current_blocker") is None, reduced)


jarvis_source = (ROOT / "jarvis.py").read_text(encoding="utf-8")
check("project worker distinguishes automatic exhaustion", "except AutomaticRepairExhausted as exc:" in jarvis_source)
check("automatic exhaustion creates checkpoint", "checkpoint_stopped_project(job_id, str(exc))" in jarvis_source)
check("project progress updates durable heartbeat", "record_project_heartbeat(info)" in jarvis_source)
check("background workers receive shared contract", "worker_context_contract(user_task, project_path, job_id)" in jarvis_source)
check("worker results written to shared memory", '"worker_completed" if success else "worker_failed"' in jarvis_source)
check("self-improvement requires reversible checkpoint", "create a reversible checkpoint" in jarvis_source)
check("self-improvement requires full release validation", "complete current-release validation suite" in jarvis_source)
check("worker finish persists structured result", "finish_project_run(job_id, {" in jarvis_source)


caps = json.loads((ROOT / "JARVIS_V42_CAPABILITIES.json").read_text())
policy = json.loads((ROOT / "V42_RUNTIME_POLICY.json").read_text())
check("capability manifest identifies V42.46", caps.get("version") == "42.50.0", caps.get("version"))
check("runtime policy identifies V42.46", policy.get("version") == "42.50.0", policy.get("version"))
check("revision breaker policy recorded", policy.get("convergence_v4242", {}).get("global_audit_after_terminal_exhaustion") is False)
check("MCP least privilege policy recorded", caps.get("revision_scoped_convergence_v4242", {}).get("mcp_registry", {}).get("least_privilege_routing") is True)
check("active identity launch guard policy recorded", policy.get("convergence_v4242", {}).get("legacy_wrapper_guard_uses_final_installed_identity") is True)
check("durable nested workspace policy recorded", policy.get("convergence_v4242", {}).get("nested_workspace_registered_durably") is True)
check("full compiler stream evidence policy recorded", caps.get("revision_scoped_convergence_v4242", {}).get("full_validator_stream_compaction") is True)
check("bounded two-cycle retry policy recorded", policy.get("convergence_v4242", {}).get("default_model_cycles_per_revision_component") == 2)


print(f"V42.46 revision/memory convergence regression: {len(checks)}/{len(checks)} PASS")
