from pathlib import Path
import json
import shutil
import tempfile

import jarvis_v4237_repair as V37
import jarvis_v4239_repair as V39
import local_qwen_project as M


checks = []


def check(name, condition, detail=""):
    checks.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL") + ": " + name + ((" -- " + str(detail)) if detail and not condition else ""))


identity = M._v36_release_identity()
check("release identity", tuple(map(int, identity.get("version", "V0")[1:].split("."))) >= (42, 39, 0), identity)
check("deterministic-first engine", identity.get("engine") == getattr(M, "V4240_ENGINE", M.V4239_ENGINE), identity)
check("model exhaustion cannot block deterministic repair", identity.get("deterministic_repairs_ignore_model_transport_exhaustion") is True)
check("terminal transport halt advertised", identity.get("transport_block_terminal_when_only_issue") is True)
check("durable project repair memory advertised", identity.get("full_pass_project_repair_memory") is True)
check("engine marker", M._v4239_engine_disk_guard()[0] is True)


with tempfile.TemporaryDirectory(prefix="v4239_deterministic_first_") as temp_name:
    root = Path(temp_name)
    native = root / "src-tauri" / "src"
    native.mkdir(parents=True)
    model = native / "models" / "tool.rs"
    model.parent.mkdir()
    tools = native / "tools.rs"
    model.write_text("#[derive(Debug, Clone)]\npub struct Tool {\n    pub id: String,\n}\n", encoding="utf-8")
    tools.write_text(
        "pub fn value(option: Option<String>) -> &'static str {\n"
        "    let value = option.map(|s| s.as_str()).unwrap_or(\"null\".to_string());\n"
        "    \"fixture\"\n}\n",
        encoding="utf-8",
    )
    manifest = {
        "_original_user_request": "finish this project",
        "components": [{"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust", "build_command": "cargo check"}],
        "files": [{"path": "src-tauri/src/models/tool.rs"}, {"path": "src-tauri/src/tools.rs"}],
    }
    failure = """V36 COMPONENT FAILED [rust | rust | src-tauri]:
error[E0277]: the trait bound `for<'r> Tool: FromRow<'r, _>` is not satisfied
 --> src/models/tool.rs:2:1
error[E0308]: mismatched types
 --> src/tools.rs:2:1
  |
2 -     let value = option.map(|s| s.as_str()).unwrap_or("null".to_string());
2 +     let value = option.as_deref().unwrap_or("null");
error: could not compile `geartrack` due to 75 previous errors
"""
    component = manifest["components"][0]
    token = M._v4238_component_source_token(root, manifest, component)
    blocked_state = {
        "failures": {
            "old-block": {
                "component": "rust", "component_root": "src-tauri", "adapter": "rust",
                "component_token": token, "blocked_component_token": token,
                "blocked_until_component_source_changes": True, "result": "transport_exhausted",
                "transport_failures": {"src-tauri/src/models/tool.rs": 4, "src-tauri/src/tools.rs": 4},
                "semantic_no_delta": [],
            }
        }
    }
    (root / M.V4238_STATE_FILE).write_text(json.dumps(blocked_state), encoding="utf-8")
    old = {
        "copy": M._copy_project_for_candidate_validation,
        "validate": M._v35_validate_component,
        "base": M._v36_base_qwen_call,
        "diagnostics": M._v4236_native_diagnostics,
        "rank": M._v4236_rank_native_targets,
        "gate": M._candidate_transaction_error,
        "mark": M._v413_mark_accepted,
    }
    model_calls = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4239_candidate_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            return handle, clone

        def fake_validate(work, passed_manifest, passed_component, user_request=""):
            first = (Path(work) / "src-tauri/src/models/tool.rs").read_text(encoding="utf-8")
            second = (Path(work) / "src-tauri/src/tools.rs").read_text(encoding="utf-8")
            if "sqlx::FromRow" in first and "option.as_deref().unwrap_or(\"null\")" in second:
                return True, "cargo check passed"
            return False, failure

        def should_not_call(*args, **kwargs):
            model_calls.append(True)
            return False, "unexpected model call"

        M._copy_project_for_candidate_validation = fake_copy
        M._v35_validate_component = fake_validate
        M._v36_base_qwen_call = should_not_call
        M._v4236_native_diagnostics = lambda *args, **kwargs: [
            {"file": "src-tauri/src/models/tool.rs", "code": "E0277"},
            {"file": "src-tauri/src/tools.rs", "code": "E0308"},
        ]
        M._v4236_rank_native_targets = lambda *args, **kwargs: [
            "src-tauri/src/models/tool.rs", "src-tauri/src/tools.rs"
        ]
        M._candidate_transaction_error = lambda *args, **kwargs: ""
        M._v413_mark_accepted = lambda *args, **kwargs: None
        changed = M._v4239_repair_component_failure("finish", manifest, root, failure, None)
    finally:
        M._copy_project_for_candidate_validation = old["copy"]
        M._v35_validate_component = old["validate"]
        M._v36_base_qwen_call = old["base"]
        M._v4236_native_diagnostics = old["diagnostics"]
        M._v4236_rank_native_targets = old["rank"]
        M._candidate_transaction_error = old["gate"]
        M._v413_mark_accepted = old["mark"]
    check("exhausted transport state cannot block deterministic compiler edits", changed is True)
    check("FromRow compiler repair committed", "sqlx::FromRow" in model.read_text(encoding="utf-8"))
    check("exact rustc replacement committed", "option.as_deref().unwrap_or(\"null\")" in tools.read_text(encoding="utf-8"))
    check("deterministic success made no model call", model_calls == [], model_calls)
    check("accepted source revision invalidates old transport block", M._v4239_active_transport_block(root, manifest) is None)
    journal = (root / "JARVIS_PROJECT_JOURNAL.jsonl").read_text(encoding="utf-8")
    check("transaction is journaled with current engine", "v4239_deterministic_component_committed" in journal and identity.get("version") in journal)


with tempfile.TemporaryDirectory(prefix="v4239_terminal_halt_") as temp_name:
    root = Path(temp_name)
    native = root / "src-tauri" / "src"
    native.mkdir(parents=True)
    (native / "lib.rs").write_text("pub fn fixture() -> bool { true }\n", encoding="utf-8")
    manifest = {"components": [{"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"}]}
    token = M._v4238_component_source_token(root, manifest, manifest["components"][0])
    (root / M.V4238_STATE_FILE).write_text(json.dumps({"failures": {"blocked": {
        "component": "rust", "component_root": "src-tauri", "component_token": token,
        "blocked_component_token": token, "blocked_until_component_source_changes": True,
        "result": "transport_exhausted", "transport_failures": {"src-tauri/src/lib.rs": 2},
    }}}), encoding="utf-8")
    failure = "V36 COMPONENT FAILED [rust | rust | src-tauri]:\nerror[E0999]: fixture unresolved\nerror: could not compile due to 1 previous error"
    audit = {"clean": False, "issues": [{"kind": "component_validation", "component": "rust", "problem": failure}]}
    old = {
        "audit": M._v429_whole_project_audit,
        "native": M._v4236_is_native_compiler_failure,
        "diagnostics": M._v4236_native_diagnostics,
        "rank": M._v4236_rank_native_targets,
    }
    try:
        M._v429_whole_project_audit = lambda *args, **kwargs: audit
        M._v4236_is_native_compiler_failure = lambda *args, **kwargs: True
        M._v4236_native_diagnostics = lambda *args, **kwargs: []
        M._v4236_rank_native_targets = lambda *args, **kwargs: []
        result, issues = M._v429_whole_project_convergence("finish", manifest, root, None)
    finally:
        M._v429_whole_project_audit = old["audit"]
        M._v4236_is_native_compiler_failure = old["native"]
        M._v4236_native_diagnostics = old["diagnostics"]
        M._v4236_rank_native_targets = old["rank"]
    halt = json.loads((root / M.V4239_HALT_FILE).read_text(encoding="utf-8"))
    check("only blocked component stops convergence", result is False and len(issues) == 1)
    check("terminal checkpoint status is explicit", halt.get("status") == "MODEL_TRANSPORT_BLOCKED", halt)
    check("terminal stop is durable", "v4239_transport_terminal_stop" in (root / "JARVIS_PROJECT_JOURNAL.jsonl").read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory(prefix="v4239_memory_") as temp_name:
    root = Path(temp_name)
    source = root / "src-tauri" / "src" / "lib.rs"
    source.parent.mkdir(parents=True)
    source.write_text("pub fn fixture() -> bool { true }\n", encoding="utf-8")
    manifest = {
        "_original_user_request": "create a reliable project",
        "components": [{"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust", "build_command": "cargo check"}],
        "files": [{"path": "src-tauri/src/lib.rs", "purpose": "native entry"}],
    }
    first_problem = "V36 COMPONENT FAILED [rust | rust | src-tauri]: error[E0308] --> src/lib.rs:10:4 mismatched types"
    moved_problem = "V36 COMPONENT FAILED [rust | rust | src-tauri]: error[E0308] --> src/lib.rs:88:9 mismatched types"
    first = {"clean": False, "issues": [{"kind": "component_validation", "component": "rust", "file": "src-tauri/src/lib.rs", "problem": first_problem}]}
    moved = {"clean": False, "issues": [{"kind": "component_validation", "component": "rust", "file": "src-tauri/src/lib.rs", "problem": moved_problem}]}
    memory1 = M._v4239_update_project_repair_memory(root, "create", manifest, first)
    memory2 = M._v4239_update_project_repair_memory(root, "create", manifest, moved)
    active = [row for row in memory2["issues"] if row.get("status") == "active"]
    check("line movement preserves issue identity", len(active) == 1 and active[0].get("occurrences") == 2, active)
    check("component repair state persists", memory2["components"][0].get("status") == "failing", memory2["components"])
    prompt = V39._memory_aware_model_prompt(M.__dict__, root, manifest, manifest["components"][0], "src-tauri/src/lib.rs", ["src-tauri/src/lib.rs"], moved_problem)
    check("model prompt receives compact project memory", "DURABLE PROJECT REPAIR MEMORY" in prompt and "CURRENT SOURCE:" in prompt and len(prompt) <= 10000)
    trace = M._v4239_write_failure_observability(root, manifest, moved, memory2)
    report = (root / M.V4239_REPORT_FILE).read_text(encoding="utf-8")
    trace_line = json.loads((root / M.V4239_TRACE_FILE).read_text(encoding="utf-8").splitlines()[-1])
    check("full pass machine trace contains actionable evidence", trace.get("failures") and trace_line.get("failures")[0].get("codes") == ["E0308"], trace_line)
    check("human report explains cause and next action", "Why it is failing:" in report and "What is needed next:" in report and "cargo check" in report)
    secret_audit = {"clean": False, "issues": [{"kind": "component_validation", "component": "rust", "problem": "error: api_key=do-not-log-this"}]}
    M._v4239_write_failure_observability(root, manifest, secret_audit, memory2)
    last_trace = (root / M.V4239_TRACE_FILE).read_text(encoding="utf-8").splitlines()[-1]
    check("recognized credentials are redacted from generated logs", "do-not-log-this" not in last_trace and "[REDACTED]" in last_trace)
    memory3 = M._v4239_update_project_repair_memory(root, "create", manifest, {"clean": True, "issues": []})
    resolved = [row for row in memory3["issues"] if row.get("status") == "resolved"]
    check("resolved issue history is retained", len(resolved) == 1 and resolved[0].get("resolved_at"), resolved)


failed = [name for name, ok, _detail in checks if not ok]
if failed:
    raise SystemExit("V42.39 regression failed: " + ", ".join(failed))
print(f"V42.39 regression: {len(checks)}/{len(checks)} PASS")
