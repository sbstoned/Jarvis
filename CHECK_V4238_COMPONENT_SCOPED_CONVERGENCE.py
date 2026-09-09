from pathlib import Path
import json
import os
import shutil
import tempfile

import local_qwen_project as M


checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL") + ": " + name + ((" -- " + str(detail)) if detail and not condition else ""))


identity = M._v36_release_identity()
check("release identity", tuple(map(int, identity.get("version", "V0")[1:].split("."))) >= (42, 38, 0), identity)
check("engine identity", identity.get("engine") == getattr(M, "V4240_ENGINE", getattr(M, "V4239_ENGINE", M.V4238_ENGINE)), identity)
check("component revision state advertised", identity.get("component_source_revision_transport_state") is True)
check("journal reconstruction advertised", identity.get("journal_transport_state_reconstruction") is True)
check("time cannot reset transport budget", identity.get("elapsed_time_cannot_reset_transport_budget") is True)
check("explicit tests reject linkage smoke", identity.get("explicit_tests_reject_linkage_only_smoke") is True)
check("engine marker", M._v4238_engine_disk_guard()[0] is True)


with tempfile.TemporaryDirectory(prefix="v4238_tokens_") as temp_name:
    root = Path(temp_name)
    (root / "src").mkdir()
    (root / "src-tauri" / "src").mkdir(parents=True)
    app = root / "src" / "App.tsx"
    native = root / "src-tauri" / "src" / "lib.rs"
    app.write_text("export default function App() { return null; }\n", encoding="utf-8")
    native.write_text("pub fn value() -> i32 { 1 }\n", encoding="utf-8")
    manifest = {"components": [
        {"id": "react", "root": ".", "toolchain_adapter": "react"},
        {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"},
    ]}
    react = manifest["components"][0]
    rust = manifest["components"][1]
    rust_before = M._v4238_component_source_token(root, manifest, rust)
    react_before = M._v4238_component_source_token(root, manifest, react)
    app.write_text("export default function App() { return <main />; }\n", encoding="utf-8")
    rust_after_frontend = M._v4238_component_source_token(root, manifest, rust)
    react_after_frontend = M._v4238_component_source_token(root, manifest, react)
    native.write_text("pub fn value() -> i32 { 2 }\n", encoding="utf-8")
    rust_after_native = M._v4238_component_source_token(root, manifest, rust)
    react_after_native = M._v4238_component_source_token(root, manifest, react)
    check("frontend edit does not reset Rust token", rust_before == rust_after_frontend)
    check("Rust edit changes Rust token", rust_after_native != rust_after_frontend)
    check("frontend edit changes React token", react_before != react_after_frontend)
    check("nested Rust edit is excluded from root React token", react_after_native == react_after_frontend)


with tempfile.TemporaryDirectory(prefix="v4238_journal_") as temp_name:
    root = Path(temp_name)
    manifest = {"components": [
        {"id": "react", "root": ".", "toolchain_adapter": "react"},
        {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"},
    ]}
    rust = manifest["components"][1]
    events = [
        {"type": "v4237_model_transport_failed", "component": "rust", "file": "src-tauri/src/models/tool.rs"},
        {"type": "file_accepted", "file": "tests/application.integration.test.ts"},
        {"type": "v4237_model_transport_failed", "component": "rust", "file": "src-tauri/src/models/tool.rs"},
        {"type": "v4237_model_transport_failed", "component": "rust", "file": "src-tauri/src/tools.rs"},
    ]
    (root / "JARVIS_PROJECT_JOURNAL.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in events), encoding="utf-8"
    )
    counts = M._v4238_journal_transport_counts(root, manifest, rust)
    check("journal reconstructs lost target counts", counts == {
        "src-tauri/src/models/tool.rs": 2, "src-tauri/src/tools.rs": 1,
    }, counts)
    with (root / "JARVIS_PROJECT_JOURNAL.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "v4238_component_transaction_committed", "component": "rust", "files": ["src-tauri/src/models/tool.rs"]}) + "\n")
        handle.write(json.dumps({"type": "v4238_model_transport_failed", "component": "rust", "file": "src-tauri/src/tools.rs"}) + "\n")
    reset_counts = M._v4238_journal_transport_counts(root, manifest, rust)
    check("accepted Rust revision resets earlier Rust transport history", reset_counts == {"src-tauri/src/tools.rs": 1}, reset_counts)


RUST_FAILURE = """V36 COMPONENT FAILED [native | rust | native]:
error[E0277]: bad
 --> src/model.rs:1:1
error: could not compile due to 2 previous errors
"""


with tempfile.TemporaryDirectory(prefix="v4238_transport_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    model = root / "native" / "src" / "model.rs"
    model.write_text("pub struct Item;\n", encoding="utf-8")
    (root / "src").mkdir()
    app = root / "src" / "App.tsx"
    app.write_text("export default 1;\n", encoding="utf-8")
    manifest = {"components": [
        {"id": "react", "root": ".", "toolchain_adapter": "react"},
        {"id": "native", "root": "native", "toolchain_adapter": "rust"},
    ], "files": [{"path": "native/src/model.rs"}]}
    old = {
        "copy": M._copy_project_for_candidate_validation,
        "base": M._v36_base_qwen_call,
        "mode": M._v426_mode,
        "switch": M._v426_switch_for_call,
        "diagnostics": M._v4236_native_diagnostics,
        "rank": M._v4236_rank_native_targets,
    }
    old_limit = os.environ.get("JARVIS_V4238_TRANSPORT_ATTEMPTS_PER_COMPONENT_REVISION")
    cleanups = []
    calls = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4238_transport_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            cleanups.append(handle)
            return handle, clone
        def timeout(*args, **kwargs):
            calls.append(kwargs.get("hard_timeout"))
            return False, "model exceeded configured hard watchdog"
        M._copy_project_for_candidate_validation = fake_copy
        M._v36_base_qwen_call = timeout
        M._v426_mode = lambda: "auto"
        M._v426_switch_for_call = lambda *args, **kwargs: (True, "ready")
        M._v4236_native_diagnostics = lambda *args, **kwargs: [{"file": "native/src/model.rs", "code": "E0277"}]
        M._v4236_rank_native_targets = lambda *args, **kwargs: ["native/src/model.rs"]
        os.environ["JARVIS_V4238_TRANSPORT_ATTEMPTS_PER_COMPONENT_REVISION"] = "1"
        first = M._v4238_repair_component_failure("finish", manifest, root, RUST_FAILURE, None)
        first_calls = len(calls)
        app.write_text("export default 2;\n", encoding="utf-8")
        second = M._v4238_repair_component_failure("finish", manifest, root, RUST_FAILURE, None)
    finally:
        for key, value in old.items():
            if key == "copy": M._copy_project_for_candidate_validation = value
            elif key == "base": M._v36_base_qwen_call = value
            elif key == "mode": M._v426_mode = value
            elif key == "switch": M._v426_switch_for_call = value
            elif key == "diagnostics": M._v4236_native_diagnostics = value
            elif key == "rank": M._v4236_rank_native_targets = value
        if old_limit is None:
            os.environ.pop("JARVIS_V4238_TRANSPORT_ATTEMPTS_PER_COMPONENT_REVISION", None)
        else:
            os.environ["JARVIS_V4238_TRANSPORT_ATTEMPTS_PER_COMPONENT_REVISION"] = old_limit
        for handle in cleanups:
            try: handle.cleanup()
            except Exception: pass
    state = json.loads((root / M.V4238_STATE_FILE).read_text(encoding="utf-8"))
    entry = next(iter(state["failures"].values()))
    event_types = [json.loads(line).get("type") for line in (root / "JARVIS_PROJECT_JOURNAL.jsonl").read_text(encoding="utf-8").splitlines()]
    check("transport-only repair never mutates source", first is False and second is False and model.read_text(encoding="utf-8") == "pub struct Item;\n")
    check("bounded routes run once", calls == [90, 150], calls)
    check("unrelated source change cannot re-enter exhausted target", len(calls) == first_calls, calls)
    check("transport does not consume semantic no-delta", entry.get("semantic_no_delta") == [], entry)
    check("transport state blocks until component changes", entry.get("blocked_until_component_source_changes") is True, entry)
    check("transport-only event is honest", "v4238_component_transport_deferred" in event_types and "v4238_component_transaction_no_delta" not in event_types, event_types)


suggestion_failure = """error[E0308]: mismatched types
 --> native/src/tool.rs:2:1
  |
2 -     pub active: String,
2 +     pub active: bool,
"""
source = "pub struct Tool {\n    pub active: String,\n}\n"
candidate, reasons = M._v4238_deterministic_candidate(source, suggestion_failure, "native/src/tool.rs")
check("compiler exact replacement parsed", "pub active: bool" in candidate and "compiler_exact_replacement" in reasons, (candidate, reasons))


with tempfile.TemporaryDirectory(prefix="v4238_fromrow_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    model = root / "native" / "src" / "model.rs"
    model.write_text("#[derive(Debug, Clone)]\npub struct Tool {\n    pub id: String,\n}\n", encoding="utf-8")
    manifest = {"components": [{"id": "native", "root": "native", "toolchain_adapter": "rust"}], "files": [{"path": "native/src/model.rs"}]}
    failure = """V36 COMPONENT FAILED [native | rust | native]:
error[E0277]: the trait bound `for<'r> Tool: FromRow<'r, _>` is not satisfied
 --> src/model.rs:2:1
error: could not compile due to 3 previous errors
"""
    old = {
        "copy": M._copy_project_for_candidate_validation,
        "validate": M._v35_validate_component,
        "base": M._v36_base_qwen_call,
        "diagnostics": M._v4236_native_diagnostics,
        "rank": M._v4236_rank_native_targets,
        "gate": M._candidate_transaction_error,
        "mark": M._v413_mark_accepted,
    }
    cleanups = []
    model_calls = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4238_fromrow_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            cleanups.append(handle)
            return handle, clone
        def fake_validate(work, passed_manifest, component, user_request=""):
            text = (Path(work) / "native/src/model.rs").read_text(encoding="utf-8")
            return (True, "cargo check passed") if "sqlx::FromRow" in text else (False, failure)
        def should_not_call(*args, **kwargs):
            model_calls.append(True)
            return False, "unexpected"
        M._copy_project_for_candidate_validation = fake_copy
        M._v35_validate_component = fake_validate
        M._v36_base_qwen_call = should_not_call
        M._v4236_native_diagnostics = lambda *args, **kwargs: [{"file": "native/src/model.rs", "code": "E0277"}]
        M._v4236_rank_native_targets = lambda *args, **kwargs: ["native/src/model.rs"]
        M._candidate_transaction_error = lambda *args, **kwargs: ""
        M._v413_mark_accepted = lambda *args, **kwargs: None
        changed = M._v4238_repair_component_failure("finish", manifest, root, failure, None)
    finally:
        M._copy_project_for_candidate_validation = old["copy"]
        M._v35_validate_component = old["validate"]
        M._v36_base_qwen_call = old["base"]
        M._v4236_native_diagnostics = old["diagnostics"]
        M._v4236_rank_native_targets = old["rank"]
        M._candidate_transaction_error = old["gate"]
        M._v413_mark_accepted = old["mark"]
        for handle in cleanups:
            try: handle.cleanup()
            except Exception: pass
    check("compiler-proven FromRow repair commits", changed is True and "sqlx::FromRow" in model.read_text(encoding="utf-8"))
    check("deterministic improvement avoids model call", model_calls == [], model_calls)


with tempfile.TemporaryDirectory(prefix="v4238_tests_") as temp_name:
    root = Path(temp_name)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "App.tsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
    smoke = (
        "import { describe, expect, it } from 'vitest';\n"
        "import App from '../src/App';\n"
        "describe('application integration smoke', () => {\n"
        "  it('links the real application entry component', () => {\n"
        "    expect(typeof App).toBe('function');\n"
        "  });\n"
        "});\n"
    )
    (root / "tests" / "application.integration.test.ts").write_text(smoke, encoding="utf-8")
    manifest = {
        "_original_user_request": "Build this application and include real unit tests",
        "components": [{"id": "react", "root": ".", "toolchain_adapter": "react", "test_command": "npm test"}],
        "files": [
            {"path": "src/App.tsx", "phase": "implementation"},
            {"path": "tests/application.integration.test.ts", "phase": "test"},
        ],
    }
    issues = M._deterministic_acceptance_issues(root, manifest)
    check("explicit test requirement remains open for linkage smoke", any("V42.38 explicit-test gate" in str(row.get("problem")) for row in issues), issues)
    manifest["_original_user_request"] = "Build this application"
    soft_issues = M._deterministic_acceptance_issues(root, manifest)
    check("runner bootstrap is allowed when tests were not requested", not any("V42.38 explicit-test gate" in str(row.get("problem")) for row in soft_issues), soft_issues)


passed = sum(1 for _name, ok, _detail in checks if ok)
print(f"V42.38 regression: {passed}/{len(checks)} PASS")
raise SystemExit(0 if passed == len(checks) else 1)
