from pathlib import Path
import json
import tempfile

import local_qwen_project as m


checks = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    checks.append(name)


identity = m._v36_release_identity()
check("release identity is V42.36 or newer", tuple(map(int, identity.get("version", "V0")[1:].split("."))) >= (42, 36, 0), identity)
check("engine identity", identity.get("engine") == m.V4240_ENGINE, identity)
check("fresh component authority advertised", identity.get("fresh_component_result_owns_current_blocker") is True)
check("native delta gate advertised", identity.get("native_candidate_requires_strict_error_count_delta") is True)
check("universal mode preserved", identity.get("language_framework_toolchain_agnostic") is True)
check("edit mode preserved", identity.get("new_project_and_existing_project_edit_modes") is True)
check("engine marker matches", m._v4240_engine_disk_guard()[0] is True)


with tempfile.TemporaryDirectory(prefix="v4236_candidate_parity_") as temp_name:
    root = Path(temp_name) / "accepted"
    (root / "node_modules" / "fixture-package").mkdir(parents=True)
    (root / "node_modules" / "fixture-package" / "marker.txt").write_text("ready\n", encoding="utf-8")
    (root / "package.json").write_text('{"scripts":{"build":"node -e \\\"process.exit(0)\\\"}}\n', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.js").write_text("export default 1;\n", encoding="utf-8")
    transaction, clone = m._copy_project_for_candidate_validation(root)
    try:
        marker = clone / "node_modules" / "fixture-package" / "marker.txt"
        check("generic candidate receives dependency parity", marker.read_text(encoding="utf-8").strip() == "ready")
        check("generic candidate remains isolated", clone.resolve() != root.resolve())
    finally:
        transaction.cleanup()


RUST_FAILURE = r'''V36 COMPONENT FAILED [rust | rust | src-tauri]:
Command failed (101): C:\Users\fixture\.cargo\bin\cargo.EXE build
error[E0277]: the trait bound `for<'r> Tool: FromRow<'r, _>` is not satisfied
  --> src\tools.rs:53:38
   |
  ::: src\models\tool.rs:2:1
   |
 2 | pub struct Tool {
   | --------------- doesn't satisfy `Tool: FromRow<'r, _>`
error[E0308]: mismatched types
  --> src\tools.rs:68:9
error[E0308]: mismatched types
  --> src\tools.rs:86:68
Some errors have detailed explanations: E0255, E0277, E0308, E0432, E0433, E0599.
error: could not compile `geartrack` (lib) due to 75 previous errors; 8 warnings emitted'''

GREEN_REACT = "vite v5 build\n43 modules transformed\n1 test passed"


def fixture(root):
    (root / "src" / "components").mkdir(parents=True)
    (root / "src-tauri" / "src" / "models").mkdir(parents=True)
    (root / "src" / "components" / "InventoryView.tsx").write_text(
        "export function InventoryView(){return <div/>}\n", encoding="utf-8"
    )
    (root / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    (root / "src-tauri" / "src" / "tools.rs").write_text("pub fn tools() {}\n", encoding="utf-8")
    (root / "src-tauri" / "src" / "models" / "tool.rs").write_text(
        "pub struct Tool {}\n", encoding="utf-8"
    )
    manifest = {
        "components": [
            {"id": "react", "root": ".", "toolchain_adapter": "react"},
            {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"},
        ],
        "files": [
            {"path": "src/components/InventoryView.tsx"},
            {"path": "vite.config.ts"},
            {"path": "src-tauri/src/tools.rs"},
            {"path": "src-tauri/src/models/tool.rs"},
        ],
    }
    (root / m.V33_ARCHITECTURE_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


with tempfile.TemporaryDirectory(prefix="v4236_paths_") as temp_name:
    root = Path(temp_name)
    manifest = fixture(root)
    rows = m._v4236_native_diagnostics(root, manifest, RUST_FAILURE)
    files = {row["file"] for row in rows}
    check("cargo cwd path mapped to project tools", "src-tauri/src/tools.rs" in files, rows)
    check("cargo cwd path mapped to project model", "src-tauri/src/models/tool.rs" in files, rows)
    ranked = m._v4236_rank_native_targets(rows, RUST_FAILURE)
    check("definition evidence outranks cascade consumer", ranked[0] == "src-tauri/src/models/tool.rs", ranked)
    check("Rust failure recognized as native compiler evidence", m._v4236_is_native_compiler_failure(root, manifest, RUST_FAILURE))


with tempfile.TemporaryDirectory(prefix="v4236_other_compilers_") as temp_name:
    root = Path(temp_name)
    (root / "backend" / "src").mkdir(parents=True)
    (root / "backend" / "src" / "service.go").write_text("package src\n", encoding="utf-8")
    go_manifest = {"components": [{"id": "go-core", "root": "backend", "toolchain_adapter": "go"}]}
    go_failure = "V36 COMPONENT FAILED [go-core | go | backend]:\nsrc/service.go:12:4: undefined: Thing\nCommand failed (1): go build ./..."
    go_rows = m._v4236_native_diagnostics(root, go_manifest, go_failure)
    check("Go component-relative path resolved", go_rows[0]["file"] == "backend/src/service.go", go_rows)

    (root / "desktop").mkdir()
    (root / "desktop" / "Program.cs").write_text("class Program {}\n", encoding="utf-8")
    cs_manifest = {"components": [{"id": "desktop", "root": "desktop", "toolchain_adapter": "dotnet"}]}
    cs_failure = "V36 COMPONENT FAILED [desktop | dotnet | desktop]:\nProgram.cs(10,5): error CS0103: The name X does not exist\nCommand failed (1): dotnet build"
    cs_rows = m._v4236_native_diagnostics(root, cs_manifest, cs_failure)
    check("dotnet component-relative path resolved", cs_rows[0]["file"] == "desktop/Program.cs", cs_rows)


with tempfile.TemporaryDirectory(prefix="v4236_projection_") as temp_name:
    root = Path(temp_name)
    manifest = fixture(root)
    projection = root / m.V4225_PROJECTION_FILE
    projection.write_text(json.dumps({
        "version": "V42.35.0",
        "current_blocker": {
            "file": ".", "component": "react", "kind": "component_validation",
            "problem": "stale Vite alias failure",
        },
    }), encoding="utf-8")
    m._append_project_event(
        root, "fixture_repair_committed", "frontend config repaired", file="vite.config.ts"
    )
    data = json.loads(projection.read_text(encoding="utf-8"))
    check("component-level dot blocker invalidated by owned file", "current_blocker" not in data, data)
    check("component invalidation requires fresh validation", data.get("fresh_validation_required") is True, data)

    # A fresh green result clears any remaining blocker for that component. The
    # immediately following Rust result must then replace it with live Cargo paths.
    projection.write_text(json.dumps({
        "current_blocker": {"file": ".", "component": "react", "problem": "old"}
    }), encoding="utf-8")
    m._v4236_record_component_result(root, manifest, manifest["components"][0], True, GREEN_REACT)
    data = json.loads(projection.read_text(encoding="utf-8"))
    check("fresh green component clears its stale blocker", "current_blocker" not in data, data)
    m._v4236_record_component_result(root, manifest, manifest["components"][1], False, RUST_FAILURE)
    data = json.loads(projection.read_text(encoding="utf-8"))
    blocker = data.get("current_blocker") or {}
    check("fresh Rust failure becomes current blocker", blocker.get("component") == "rust", blocker)
    check("fresh Rust provider path becomes blocker file", blocker.get("file") == "src-tauri/src/models/tool.rs", blocker)
    check("stale React problem is absent", "vite" not in str(blocker.get("problem") or "").lower(), blocker)
    controller_blocker = (m._v4218_state(root).get("current_blocker") or {})
    check("convergence controller receives same Rust blocker", controller_blocker.get("component") == "rust", controller_blocker)


with tempfile.TemporaryDirectory(prefix="v4236_router_") as temp_name:
    root = Path(temp_name)
    manifest = fixture(root)
    called = []
    old_repair = m._repair_file_for_issues
    old_fast = m._v4221_fast_static_recovery
    try:
        def fake_repair(_request, _manifest, work, rel, _problems, _callback=None, validation_failure=None):
            called.append(rel)
            path = Path(work) / rel
            path.write_text(path.read_text(encoding="utf-8") + "// repaired\n", encoding="utf-8")
            m._v413_mark_accepted(work, rel, "fixture")
            return True

        m._repair_file_for_issues = fake_repair
        m._v4221_fast_static_recovery = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("global frontend fast recovery must not run for Rust")
        )
        repaired = m._v4236_repair_native_compiler_failure(
            "finish project", manifest, root, RUST_FAILURE, None
        )
    finally:
        m._repair_file_for_issues = old_repair
        m._v4221_fast_static_recovery = old_fast
    check("native router accepted source-changing target", repaired is True, called)
    check("native router selected compiler provider", called == ["src-tauri/src/models/tool.rs"], called)
    check("native router never selected green frontend", not any("InventoryView" in rel for rel in called), called)


with tempfile.TemporaryDirectory(prefix="v4236_budget_") as temp_name:
    root = Path(temp_name)
    manifest = fixture(root)
    called = []
    old_repair = m._repair_file_for_issues
    try:
        def no_delta(_request, _manifest, _work, rel, _problems, _callback=None, validation_failure=None):
            called.append(rel)
            return False
        m._repair_file_for_issues = no_delta
        results = [
            m._v4236_repair_native_compiler_failure("finish", manifest, root, RUST_FAILURE, None)
            for _ in range(5)
        ]
    finally:
        m._repair_file_for_issues = old_repair
    check("no-delta native attempts return false", not any(results), results)
    check("same-revision targets are distinct", len(called) == len(set(called)), called)
    check("same-revision budget stops", len(called) == 2, called)
    check("budget never spills into frontend", not any("InventoryView" in rel for rel in called), called)


before = RUST_FAILURE
after_less = RUST_FAILURE.replace("75 previous errors", "12 previous errors")
after_same_moved = RUST_FAILURE.replace("src\\tools.rs:68:9", "src\\tools.rs:99:2")
check("strict native count accepts reduction", m._runtime_failure_still_present(before, after_less) is False)
check("line movement alone is not progress", m._runtime_failure_still_present(before, after_same_moved) is True)

print(f"V42.36 compatibility regression: {len(checks)}/{len(checks)} PASS")

