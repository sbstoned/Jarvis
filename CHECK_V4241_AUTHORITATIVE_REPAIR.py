"""Offline compatibility regression for the V42.41 controller under V42.46."""

from pathlib import Path
import json
import shutil
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


import jarvis_v4241_repair as repair
import jarvis_v4242_repair as active_repair
import local_qwen_project as project
import multi_provider as providers


identity = project._v36_release_identity()
check("active V42.46 identity", identity.get("version") == "V42.50.0", identity)
check("authoritative controller identity", identity.get("engine") == active_repair.ENGINE, identity)
check("active engine marker", (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")
check("V42.46 disk guard through compatibility alias", project._v4241_engine_disk_guard()[0] is True)
check("V42.40 guard aliases active release", project._v4240_engine_disk_guard()[0] is True)
check("call-time dispatch advertised", identity.get("call_time_repair_dispatch") is True)
check("same-revision breaker advertised", identity.get("same_revision_strategy_circuit_breaker") is True)


# This is the production regression for the bug observed in job 56: both
# high-level repair entrypoints must resolve the currently registered controller
# at call time instead of retaining V42.37's local implementation.
original_controller = project._v4237_repair_component_failure
original_native = project._v4236_is_native_compiler_failure
dispatches = []


def sentinel_controller(request, manifest, work, failure, callback=None):
    dispatches.append((request, str(failure)))
    return True


try:
    project._v4237_repair_component_failure = sentinel_controller
    project._v4236_is_native_compiler_failure = lambda *args, **kwargs: True
    audit_ok = project._v429_repair_audit_round(
        "finish fixture", {"components": []}, ROOT,
        {"issues": [{"problem": "native compiler fixture"}]}, None, 1,
    )
    real_ok = project._repair_real_validation_failure(
        "finish fixture", {"components": []}, ROOT, "native compiler fixture", None,
    )
finally:
    project._v4237_repair_component_failure = original_controller
    project._v4236_is_native_compiler_failure = original_native

check("audit path dynamically dispatches current repair controller", audit_ok is True and len(dispatches) >= 1, dispatches)
check("real-repair path dynamically dispatches current repair controller", real_ok is True and len(dispatches) == 2, dispatches)


failure = """V36 COMPONENT FAILED [rust | rust | src-tauri]:
error[E0277]: the trait bound `for<'r> Tool: FromRow<'r, _>` is not satisfied
  --> src/models/tool.rs:2:1
error[E0308]: mismatched types
  --> src/tools.rs:4:25
this expression has type `std::string::String`
expected `String`, found `ToolCondition`
error[E0308]: mismatched types
  --> src/tools.rs:10:68
expected `&str`, found `String`
  10 -     query.bind(tool.current_holder_id.map(|s| s.as_str()).unwrap_or("null".to_string()));
  10 +     query.bind(tool.current_holder_id.map(|s| s.as_str()).unwrap_or("null"));
error: could not compile due to 10 previous errors
"""
model_source = """#[derive(Debug, Clone)]
pub struct Tool {
    pub condition: String,
    pub current_holder_id: Option<String>,
}
"""
consumer_source = """fn save(tool: Tool) {
    let condition_str = match tool.condition {
        ToolCondition::New => "New",
        ToolCondition::Good => "Good",
    };
    query.bind(tool.current_holder_id.map(|s| s.as_str()).unwrap_or("null".to_string()));
}
"""

candidate, reasons = repair.rust_compiler_candidate(model_source, failure, "src-tauri/src/models/tool.rs")
check("compiler trait evidence adds FromRow", "sqlx::FromRow" in candidate, candidate)
check("trait correction records reason", any("FromRow" in item for item in reasons), reasons)
candidate, reasons = repair.rust_compiler_candidate(consumer_source, failure, "src-tauri/src/tools.rs")
check("String field avoids invalid enum match", "tool.condition.as_str()" in candidate, candidate)
check("nullable SQL bind uses a borrow-safe Option", "tool.current_holder_id.as_deref()" in candidate, candidate)
cargo, reasons = repair._ensure_sqlx_derive_feature('sqlx = { version = "0.8", features = ["sqlite"] }\n')
check("SQLx derive feature is enabled transactionally", '"derive"' in cargo, cargo)


manifest = {"components": [{"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"}]}


def create_fixture(root):
    (root / "src-tauri" / "src" / "models").mkdir(parents=True)
    (root / "src-tauri" / "src" / "models" / "tool.rs").write_text(model_source, encoding="utf-8")
    (root / "src-tauri" / "src" / "tools.rs").write_text(consumer_source, encoding="utf-8")
    (root / "src-tauri" / "Cargo.toml").write_text(
        'sqlx = { version = "0.8", features = ["sqlite"] }\n', encoding="utf-8"
    )


def copy_candidate(root):
    handle = tempfile.TemporaryDirectory(prefix="jarvis_v4241_candidate_")
    clone = Path(handle.name) / "candidate"
    shutil.copytree(root, clone)
    return handle, clone


events = []


def fake_g(validate):
    return {
        "_v4236_native_diagnostics": project._v4236_native_diagnostics,
        "_v4236_rank_native_targets": project._v4236_rank_native_targets,
        "_copy_project_for_candidate_validation": copy_candidate,
        "_v35_validate_component": validate,
        "_progress": lambda *args, **kwargs: None,
        "_v36_checkpoint_file": lambda *args, **kwargs: None,
        "_v413_mark_accepted": lambda *args, **kwargs: None,
        "_append_project_event": lambda *args, **kwargs: events.append((args, kwargs)),
    }


with tempfile.TemporaryDirectory(prefix="jarvis_v4241_improve_") as temp_name:
    root = Path(temp_name)
    create_fixture(root)

    def improving_validator(clone, _manifest, _component, _request):
        check("candidate contains FromRow before validation", "sqlx::FromRow" in (clone / "src-tauri/src/models/tool.rs").read_text())
        check("candidate contains consumer root fix before validation", ".as_str()" in (clone / "src-tauri/src/tools.rs").read_text())
        check("candidate contains dependency feature before validation", '"derive"' in (clone / "src-tauri/Cargo.toml").read_text())
        return False, "error: could not compile due to 2 previous errors"

    accepted, result = repair._deterministic_component_transaction(
        fake_g(improving_validator), "finish fixture", manifest, root, failure, manifest["components"][0]
    )
    check("real component diagnostic decrease commits transaction", accepted is True and result.get("after") == 2, result)
    check("accepted source promoted atomically", "sqlx::FromRow" in (root / "src-tauri/src/models/tool.rs").read_text())
    check("accepted Cargo configuration promoted atomically", '"derive"' in (root / "src-tauri/Cargo.toml").read_text())


with tempfile.TemporaryDirectory(prefix="jarvis_v4241_infra_") as temp_name:
    root = Path(temp_name)
    create_fixture(root)
    original = (root / "src-tauri/src/models/tool.rs").read_text()
    rejected, result = repair._deterministic_component_transaction(
        fake_g(lambda *args, **kwargs: (False, "cargo executable unavailable")),
        "finish fixture", manifest, root, failure, manifest["components"][0],
    )
    check("zero parsed diagnostics on failed validator is not improvement", rejected is False and result.get("result") == "compile_gate_failed_unclassified" and result.get("phase_progress") is False, result)
    check("infrastructure failure cannot promote candidate", (root / "src-tauri/src/models/tool.rs").read_text() == original)


# The newest event writer bypasses old version-overwriting wrappers while still
# maintaining the durable projection.
with tempfile.TemporaryDirectory(prefix="jarvis_v4241_event_") as temp_name:
    root = Path(temp_name)
    project._append_project_event(root, "fixture", "V42.37 old label", diagnostic_count=5)
    event = json.loads((root / "JARVIS_PROJECT_JOURNAL.jsonl").read_text().splitlines()[-1])
    projection = json.loads((root / "JARVIS_V4225_EVENT_PROJECTION.json").read_text())
    check("journal event stamped V42.46", event.get("engine_version") == "V42.50.0", event)
    check("old progress label replaced", event.get("message", "").startswith("V42.46"), event)
    check("event projection stamped active engine", projection.get("engine") == active_repair.ENGINE, projection)


# Validate the circuit breaker independently from compiler strategies: one
# bounded model cycle is allowed for an exact repository revision; the second
# identical entry is suppressed.
with tempfile.TemporaryDirectory(prefix="jarvis_v4241_breaker_") as temp_name:
    root = Path(temp_name)
    (root / "main.go").write_text("package main\n", encoding="utf-8")
    model_calls = []
    fake = {
        "Path": Path,
        "__file__": str(ROOT / "local_qwen_project.py"),
        "_utc_stamp": lambda: "2026-09-05T00:00:00Z",
        "_v4237_repair_component_failure": lambda *args, **kwargs: model_calls.append(1) or False,
        "_v429_repair_audit_round": lambda *args, **kwargs: False,
        "_repair_real_validation_failure": lambda *args, **kwargs: False,
        "_v36_release_identity": lambda: {},
        "_v36_stack_skill_names": lambda manifest: [],
        "_qwen_call": lambda *args, **kwargs: (False, "offline"),
        "_v4235_durable_append_project_event": lambda *args, **kwargs: {},
        "_append_project_event": lambda *args, **kwargs: {},
        "_v4235_base_progress": lambda *args, **kwargs: None,
        "_progress": lambda *args, **kwargs: None,
        "_v4235_previous_generate_project_zip": lambda *args, **kwargs: (False, "fixture", None),
        "_v4235_previous_analyze_project_zip": lambda *args, **kwargs: (False, "fixture", None),
        "generate_project_zip": lambda *args, **kwargs: (False, "fixture", None),
        "analyze_and_edit_project_zip": lambda *args, **kwargs: (False, "fixture", None),
        "_v429_progress_token": lambda work: "unchanged-revision",
    }
    repair.install(fake)
    go_manifest = {"components": [{"id": "go", "root": ".", "toolchain_adapter": "go"}]}
    go_failure = "V36 COMPONENT FAILED [go | go | .]:\nmain.go:1:1: error fixture\ngo build failed due to 1 previous error"
    first = fake["_v4237_repair_component_failure"]("finish", go_manifest, root, go_failure)
    calls_after_first = len(model_calls)
    second = fake["_v4237_repair_component_failure"]("finish", go_manifest, root, go_failure)
    calls_after_second = len(model_calls)
    third = fake["_v4237_repair_component_failure"]("finish", go_manifest, root, go_failure)
    ledger = json.loads((root / repair.LEDGER_FILE).read_text())
    check("first exact revision receives one model cycle", first is False and calls_after_first == 1, model_calls)
    check("second exact revision receives bounded evidence retry", second is False and calls_after_second == 2, model_calls)
    check("third unchanged model strategy is suppressed", third is False and len(model_calls) == 2, model_calls)
    check("circuit-breaker decision is durable", any(row.get("strategy") == "same_revision_circuit_breaker" for issue in ledger["issues"].values() for row in issue.get("attempts", [])), ledger)
    check("deterministic strategy is not rerun on unchanged evidence", sum(row.get("strategy") == "compiler_directed_transaction" for issue in ledger["issues"].values() for row in issue.get("attempts", [])) == 1, ledger)


# A slow local stream that is producing real tokens may cross the initial
# watchdog, but it remains bounded by the absolute multiplier.
class FakeResponse:
    status_code = 200
    text = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass

    def iter_lines(self, decode_unicode=True):
        yield 'data: {"choices":[{"delta":{"content":"A"}}]}'
        yield 'data: {"choices":[{"delta":{"content":"B"}}]}'
        yield "data: [DONE]"


original_post = providers.requests.post
original_family = providers.qwen_runtime_model_family
original_monotonic = providers.time.monotonic
timeline = iter([0.0, 50.0, 50.0, 100.0, 100.0, 110.0])
try:
    providers.requests.post = lambda *args, **kwargs: FakeResponse()
    providers.qwen_runtime_model_family = lambda: "qwen35"
    providers.time.monotonic = lambda: next(timeline)
    stream_ok, stream_text = providers.ask_qwen("fixture", hard_timeout=60, max_tokens=64, enable_thinking=False)
finally:
    providers.requests.post = original_post
    providers.qwen_runtime_model_family = original_family
    providers.time.monotonic = original_monotonic
check("useful streaming progress extends initial watchdog", stream_ok is True and stream_text == "AB", stream_text)


caps = json.loads((ROOT / "JARVIS_V42_CAPABILITIES.json").read_text())
policy = json.loads((ROOT / "V42_RUNTIME_POLICY.json").read_text())
check("capability manifest identifies V42.46", caps.get("version") == "42.50.0", caps.get("version"))
check("runtime policy identifies V42.46", policy.get("version") == "42.50.0", policy.get("version"))
check("authoritative controller capability recorded", caps.get("authoritative_repair_controller_v4241", {}).get("call_time_dispatch_from_audit_and_real_repair") is True)
check("unchanged strategy policy recorded", policy.get("convergence_v4241", {}).get("unchanged_strategy_reentry") is False)


print(f"V42.41 controller compatibility under V42.46: {len(checks)}/{len(checks)} PASS")
