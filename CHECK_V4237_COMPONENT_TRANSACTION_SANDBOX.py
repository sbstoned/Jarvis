from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

import jarvis_v42_runtime as R
import local_qwen_project as M


checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL") + ": " + name + ((" -- " + str(detail)) if detail and not ok else ""))


identity = M._v36_release_identity()
check("release identity", tuple(map(int, identity.get("version", "V0")[1:].split("."))) >= (42, 37, 0), identity)
check("engine marker", M._v4240_engine_disk_guard()[0] is True)
check("exact component replay advertised", identity.get("exact_component_candidate_replay") is True)
check("transport budget separation advertised", identity.get("model_transport_failure_not_semantic_budget") is True)


VITE_FAILURE = """V36 COMPONENT FAILED [react | react | .]:
Command failed (1): npm run build
[vite:load-fallback] Could not load /src-tauri/src-tauri/tauri.conf.json/core (imported by src/hooks/useTauriCommands.ts): ENOENT
"""
SPAWN_FAILURE = "Command failed: spawn cargo ENOENT; could not find executable"
check("bundler import ENOENT is project evidence", M._v4220_infrastructure_failure(VITE_FAILURE) is False)
check("spawn ENOENT remains infrastructure", M._v4220_infrastructure_failure(SPAWN_FAILURE) is True)


with tempfile.TemporaryDirectory(prefix="v4237_replay_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    (root / "native" / "src" / "lib.rs").write_text("pub fn value() {}\n", encoding="utf-8")
    manifest = {"components": [
        {"id": "react", "root": ".", "toolchain_adapter": "react"},
        {"id": "native", "root": "native", "toolchain_adapter": "rust"},
    ]}
    rust_failure = "V36 COMPONENT FAILED [native | rust | native]:\nerror[E0308]: mismatch\n --> src/lib.rs:1:1\nerror: could not compile due to 1 previous error"
    calls = []
    old_validate = M._v35_validate_component
    try:
        def fake_validate(work, passed_manifest, component, user_request=""):
            calls.append(component.get("id"))
            return False, rust_failure
        M._v35_validate_component = fake_validate
        replay_ok, replay_output = M._replay_validation_for_failure(root, "finish", manifest, rust_failure)
    finally:
        M._v35_validate_component = old_validate
    check("replay executes only named failing component", calls == ["native"], calls)
    check("replay preserves component result", replay_ok is False and "E0308" in replay_output)


with tempfile.TemporaryDirectory(prefix="v4237_alias_") as temp_name:
    root = Path(temp_name)
    (root / "src" / "hooks").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({
        "dependencies": {"@tauri-apps/api": "^2.0.0", "react": "^18.0.0"},
        "devDependencies": {"vite": "^5.0.0"},
    }), encoding="utf-8")
    (root / "src" / "hooks" / "useTauriCommands.ts").write_text(
        "import { invoke } from '@tauri-apps/api/core';\n", encoding="utf-8"
    )
    (root / "vite.config.ts").write_text(
        "import { defineConfig } from 'vite';\n"
        "export default defineConfig({ resolve: { alias: {\n"
        "  '@tauri-apps/api': '/src-tauri/src-tauri/tauri.conf.json',\n"
        "} } });\n",
        encoding="utf-8",
    )
    manifest = {"components": [{"id": "react", "root": ".", "toolchain_adapter": "react"}], "files": [
        {"path": "vite.config.ts", "purpose": "Vite build configuration"},
        {"path": "src/hooks/useTauriCommands.ts", "purpose": "Tauri command client"},
    ]}
    old_copy = M._copy_project_for_candidate_validation
    old_validate = M._v35_validate_component
    old_mark = M._v413_mark_accepted
    created = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4237_alias_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            created.append(handle)
            return handle, clone
        M._copy_project_for_candidate_validation = fake_copy
        M._v35_validate_component = lambda work, passed_manifest, component, user_request="": (
            ("@tauri-apps/api': '/src-tauri" not in (Path(work) / "vite.config.ts").read_text(encoding="utf-8")),
            "vite build passed",
        )
        M._v413_mark_accepted = lambda *args, **kwargs: None
        changed = M._v4237_repair_dependency_alias(root, manifest, VITE_FAILURE, None)
    finally:
        M._copy_project_for_candidate_validation = old_copy
        M._v35_validate_component = old_validate
        M._v413_mark_accepted = old_mark
        for handle in created:
            try: handle.cleanup()
            except Exception: pass
    repaired = (root / "vite.config.ts").read_text(encoding="utf-8")
    check("validated package-shadow alias repaired", changed is True, repaired)
    check("bad package alias removed", "src-tauri/src-tauri" not in repaired, repaired)
    check("unrelated Vite configuration preserved", "defineConfig" in repaired, repaired)


with tempfile.TemporaryDirectory(prefix="v4237_transaction_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    model = root / "native" / "src" / "model.rs"
    service = root / "native" / "src" / "service.rs"
    model.write_text("pub struct Item {\n    pub id: String,\n}\n", encoding="utf-8")
    service.write_text("use crate::model::Item;\n", encoding="utf-8")
    manifest = {
        "_original_user_request": "finish project",
        "components": [{"id": "native", "root": "native", "toolchain_adapter": "rust", "build_command": "cargo check"}],
        "files": [
            {"path": "native/src/model.rs", "purpose": "Canonical Item model", "exports": ["Item"]},
            {"path": "native/src/service.rs", "purpose": "Item service", "depends_on": ["native/src/model.rs"]},
        ],
    }
    rust_failure = """V36 COMPONENT FAILED [native | rust | native]:
error[E0277]: Item does not implement Clone
 --> src/service.rs:1:1
 ::: src/model.rs:1:1
error: could not compile due to 3 previous errors
"""
    old = {
        "copy": M._copy_project_for_candidate_validation,
        "validate": M._v35_validate_component,
        "base": M._v36_base_qwen_call,
        "mode": M._v426_mode,
        "switch": M._v426_switch_for_call,
        "mark": M._v413_mark_accepted,
        "gate": M._candidate_transaction_error,
    }
    cleanups = []
    marked = []
    patch_timeouts = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4237_component_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            cleanups.append(handle)
            return handle, clone
        def fake_validate(work, passed_manifest, component, user_request=""):
            source = (Path(work) / "native/src/model.rs").read_text(encoding="utf-8")
            return (True, "cargo check passed") if "#[derive(Clone)]" in source else (False, rust_failure)
        def fake_qwen(prompt, progress_callback=None, stage="", profile="repair", **kwargs):
            assert "FAILING COMPONENT: id=native" in prompt
            assert "EXACT CURRENT TARGET SOURCE" in prompt
            patch_timeouts.append(kwargs.get("hard_timeout"))
            return True, """<<<<<<< SEARCH
pub struct Item {
=======
#[derive(Clone)]
pub struct Item {
>>>>>>> REPLACE"""
        M._copy_project_for_candidate_validation = fake_copy
        M._v35_validate_component = fake_validate
        M._v36_base_qwen_call = fake_qwen
        M._v426_mode = lambda: "auto"
        M._v426_switch_for_call = lambda *args, **kwargs: (True, "ready")
        M._v413_mark_accepted = lambda work, rel, reason: marked.append((rel, reason))
        M._candidate_transaction_error = lambda *args, **kwargs: ""
        changed = M._v4237_repair_component_failure("finish", manifest, root, rust_failure, None)
    finally:
        M._copy_project_for_candidate_validation = old["copy"]
        M._v35_validate_component = old["validate"]
        M._v36_base_qwen_call = old["base"]
        M._v426_mode = old["mode"]
        M._v426_switch_for_call = old["switch"]
        M._v413_mark_accepted = old["mark"]
        M._candidate_transaction_error = old["gate"]
        for handle in cleanups:
            try: handle.cleanup()
            except Exception: pass
    check("component transaction accepted strict compiler improvement", changed is True)
    check("component transaction promoted source", "#[derive(Clone)]" in model.read_text(encoding="utf-8"))
    check("accepted ledger marked changed target", any(row[0] == "native/src/model.rs" for row in marked), marked)
    check("compact patch uses per-call watchdog", bool(patch_timeouts) and set(patch_timeouts) == {240}, patch_timeouts)
    bundle = json.loads((root / M.V4237_BUNDLE_FILE).read_text(encoding="utf-8"))
    check("repair bundle records exact component", bundle.get("component", {}).get("id") == "native", bundle)
    check("repair bundle records validator cwd", bundle.get("validator", {}).get("cwd") == "native", bundle)


with tempfile.TemporaryDirectory(prefix="v4237_reject_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    model = root / "native" / "src" / "model.rs"
    model.write_text("pub struct Item;\n", encoding="utf-8")
    manifest = {"components": [{"id": "native", "root": "native", "toolchain_adapter": "rust"}], "files": [{"path": "native/src/model.rs"}]}
    failure = "V36 COMPONENT FAILED [native | rust | native]:\nerror[E0277]: bad\n --> src/model.rs:1:1\nerror: could not compile due to 2 previous errors"
    old_copy = M._copy_project_for_candidate_validation
    old_validate = M._v35_validate_component
    old_base = M._v36_base_qwen_call
    old_mode = M._v426_mode
    old_switch = M._v426_switch_for_call
    old_gate = M._candidate_transaction_error
    cleanups = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4237_reject_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            cleanups.append(handle)
            return handle, clone
        M._copy_project_for_candidate_validation = fake_copy
        M._v35_validate_component = lambda *args, **kwargs: (False, failure)
        M._v36_base_qwen_call = lambda *args, **kwargs: (True, "<<<<<<< SEARCH\npub struct Item;\n=======\npub struct Item { value: i32 }\n>>>>>>> REPLACE")
        M._v426_mode = lambda: "auto"
        M._v426_switch_for_call = lambda *args, **kwargs: (True, "ready")
        M._candidate_transaction_error = lambda *args, **kwargs: ""
        changed = M._v4237_repair_component_failure("finish", manifest, root, failure, None)
    finally:
        M._copy_project_for_candidate_validation = old_copy
        M._v35_validate_component = old_validate
        M._v36_base_qwen_call = old_base
        M._v426_mode = old_mode
        M._v426_switch_for_call = old_switch
        M._candidate_transaction_error = old_gate
        for handle in cleanups:
            try: handle.cleanup()
            except Exception: pass
    check("no-delta candidate rejected", changed is False)
    check("rejected candidate cannot mutate authoritative source", model.read_text(encoding="utf-8") == "pub struct Item;\n")


with tempfile.TemporaryDirectory(prefix="v4237_transport_") as temp_name:
    root = Path(temp_name)
    (root / "native" / "src").mkdir(parents=True)
    model = root / "native" / "src" / "model.rs"
    model.write_text("pub struct Item;\n", encoding="utf-8")
    manifest = {"components": [{"id": "native", "root": "native", "toolchain_adapter": "rust"}], "files": [{"path": "native/src/model.rs"}]}
    failure = "V36 COMPONENT FAILED [native | rust | native]:\nerror[E0277]: bad\n --> src/model.rs:1:1\nerror: could not compile due to 2 previous errors"
    old_copy = M._copy_project_for_candidate_validation
    old_base = M._v36_base_qwen_call
    old_mode = M._v426_mode
    old_switch = M._v426_switch_for_call
    old_retry = os.environ.get("JARVIS_V4237_TRANSPORT_RETRIES_PER_STATE")
    old_cooldown = os.environ.get("JARVIS_V4237_TRANSPORT_RETRY_COOLDOWN_SECONDS")
    cleanups = []
    transport_calls = []
    try:
        def fake_copy(work):
            handle = tempfile.TemporaryDirectory(prefix="v4237_transport_clone_")
            clone = Path(handle.name) / "project"
            shutil.copytree(work, clone)
            cleanups.append(handle)
            return handle, clone
        def timed_out(*args, **kwargs):
            transport_calls.append(kwargs.get("hard_timeout"))
            return False, "model exceeded configured hard watchdog"
        M._copy_project_for_candidate_validation = fake_copy
        M._v36_base_qwen_call = timed_out
        M._v426_mode = lambda: "auto"
        M._v426_switch_for_call = lambda *args, **kwargs: (True, "ready")
        os.environ["JARVIS_V4237_TRANSPORT_RETRIES_PER_STATE"] = "1"
        os.environ["JARVIS_V4237_TRANSPORT_RETRY_COOLDOWN_SECONDS"] = "600"
        first = M._v4237_repair_component_failure("finish", manifest, root, failure, None)
        calls_after_first = len(transport_calls)
        second = M._v4237_repair_component_failure("finish", manifest, root, failure, None)
    finally:
        M._copy_project_for_candidate_validation = old_copy
        M._v36_base_qwen_call = old_base
        M._v426_mode = old_mode
        M._v426_switch_for_call = old_switch
        for name, value in (
            ("JARVIS_V4237_TRANSPORT_RETRIES_PER_STATE", old_retry),
            ("JARVIS_V4237_TRANSPORT_RETRY_COOLDOWN_SECONDS", old_cooldown),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        for handle in cleanups:
            try: handle.cleanup()
            except Exception: pass
    transport_state = json.loads((root / M.V4237_STATE_FILE).read_text(encoding="utf-8"))
    transport_entry = next(iter(transport_state.get("failures", {}).values()))
    check("transport failure produces no authoritative edit", first is False and second is False and model.read_text(encoding="utf-8") == "pub struct Item;\n")
    check("transport retry cooldown prevents tight model loop", calls_after_first == 2 and len(transport_calls) == calls_after_first, transport_calls)
    check("transport failure does not consume semantic budget", transport_entry.get("semantic_no_delta") == [], transport_entry)
    check("transport watchdogs are bounded by route", transport_calls == [240, 480], transport_calls)


with tempfile.TemporaryDirectory(prefix="v4237_env_") as temp_name:
    old_values = {name: os.environ.get(name) for name in ("CUSTOM_API_KEY", "DATABASE_PASSWORD", "HARMLESS_SETTING", "GITHUB_TOKEN", "JARVIS_SANDBOX_PASSTHROUGH_ENV")}
    try:
        os.environ["CUSTOM_API_KEY"] = "secret-a"
        os.environ["DATABASE_PASSWORD"] = "secret-b"
        os.environ["HARMLESS_SETTING"] = "keep"
        os.environ["GITHUB_TOKEN"] = "allowed-private-dependency-token"
        os.environ["JARVIS_SANDBOX_PASSTHROUGH_ENV"] = "GITHUB_TOKEN"
        broker = R.CommandBroker(Path(temp_name))
        environment = broker._prepare_env()
    finally:
        for name, value in old_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    check("unknown API-key environment scrubbed", "CUSTOM_API_KEY" not in environment)
    check("unknown password environment scrubbed", "DATABASE_PASSWORD" not in environment)
    check("ordinary environment preserved", environment.get("HARMLESS_SETTING") == "keep")
    check("explicit private-dependency token passthrough works", environment.get("GITHUB_TOKEN") == "allowed-private-dependency-token")
    check("additional package-manager caches isolated", all(environment.get(name) for name in ("YARN_CACHE_FOLDER", "COREPACK_HOME", "BUN_INSTALL_CACHE_DIR")))


passed = sum(1 for _name, ok, _detail in checks if ok)
print(f"V42.37 regression: {passed}/{len(checks)} PASS")
raise SystemExit(0 if passed == len(checks) else 1)
