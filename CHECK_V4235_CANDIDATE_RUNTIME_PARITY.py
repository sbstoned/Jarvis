from pathlib import Path
import json
import os
import shutil
import stat
import tempfile

import local_qwen_project as m


checks = []


def check(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    checks.append(name)


identity = m._v36_release_identity()
check("release identity is V42.35 or newer", tuple(map(int, identity.get("version", "V0")[1:].split("."))) >= (42, 35, 0), identity)
check("candidate parity feature preserved", identity.get("candidate_dependency_parity") is True, identity)
check("universal mode retained", identity.get("language_framework_toolchain_agnostic") is True)
check("edit mode retained", identity.get("new_project_and_existing_project_edit_modes") is True)
check("current engine marker matches", m._v4240_engine_disk_guard()[0] is True)


with tempfile.TemporaryDirectory(prefix="v4235_parity_") as temp_name:
    root = Path(temp_name) / "accepted"
    root.mkdir()
    (root / "src").mkdir()
    (root / "node_modules" / ".bin").mkdir(parents=True)
    (root / "node_modules" / "fixture-package").mkdir()
    (root / "node_modules" / "fixture-package" / "marker.txt").write_text("available\n", encoding="utf-8")
    (root / "package.json").write_text('{"scripts":{"build":"tsc -p tsconfig.json"}}\n', encoding="utf-8")
    (root / "tsconfig.json").write_text('{"compilerOptions":{}}\n', encoding="utf-8")
    (root / "src" / "App.tsx").write_text("BROKEN\n", encoding="utf-8")

    if os.name == "nt":
        compiler = root / "node_modules" / ".bin" / "tsc.cmd"
        compiler.write_text(
            "@echo off\r\n"
            "findstr /C:\"BROKEN\" src\\App.tsx >nul\r\n"
            "if not errorlevel 1 (echo src/App.tsx(1,1): error TS2322: fixture & exit /b 2)\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
    else:
        compiler = root / "node_modules" / ".bin" / "tsc"
        compiler.write_text(
            "#!/bin/sh\n"
            "if grep -q BROKEN src/App.tsx; then\n"
            "  echo \"src/App.tsx(1,1): error TS2322: fixture\"\n"
            "  exit 2\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        compiler.chmod(compiler.stat().st_mode | stat.S_IXUSR)

    manifest = {
        "components": [{
            "id": "web",
            "root": ".",
            "toolchain_adapter": "react",
        }]
    }
    transaction_root, clone = m._v4224_clone_workspace(root)
    try:
        check("artifact plane is external", root not in clone.parents, clone)
        marker = clone / "node_modules" / "fixture-package" / "marker.txt"
        check("candidate dependency parity", marker.read_text(encoding="utf-8").strip() == "available")
        (clone / "src" / "App.tsx").write_text("FIXED\n", encoding="utf-8")
        count, output = m._v4224_measure_typescript(root, clone, manifest, "src/App.tsx")
        check("real isolated compiler sees candidate dependencies", count == 0, output)
        changed = m._v4225_diff_source_files(root, clone)
        check("source diff includes repaired source", changed == ["src/App.tsx"], changed)
        check("source diff excludes dependency tree", not any("node_modules" in item for item in changed), changed)
    finally:
        shutil.rmtree(transaction_root, ignore_errors=True)


avalanche = "\n".join([
    "src/App.tsx(1,1): error TS2307: Cannot find module 'react' or its corresponding type declarations.",
    "vite.config.ts(1,1): error TS2307: Cannot find module 'vite' or its corresponding type declarations.",
    "src/App.tsx(2,1): error TS7026: JSX element implicitly has type 'any' because no interface exists.",
] * 4)
check("dependency avalanche classified as infrastructure", m._v4235_dependency_avalanche(avalanche))


with tempfile.TemporaryDirectory(prefix="v4235_projection_") as temp_name:
    root = Path(temp_name)
    projection = root / m.V4225_PROJECTION_FILE
    projection.write_text(json.dumps({
        "version": "V42.34.0",
        "current_blocker": {"file": "src/App.tsx", "problem": "stale"},
    }), encoding="utf-8")
    m._append_project_event(
        root,
        "v4235_direct_preflight_committed",
        "fixture compiler repair",
        before=8,
        after=0,
        files=["src/App.tsx"],
    )
    data = json.loads(projection.read_text(encoding="utf-8"))
    check("accepted edit invalidates matching stale blocker", "current_blocker" not in data, data)
    check("accepted edit requires fresh whole validation", data.get("fresh_validation_required") is True, data)
    check("projection records current engine", data.get("version") == identity.get("version") and data.get("engine") == identity.get("engine"), data)
    m._append_project_event(root, "v4222_whole_project_green", "fixture green audit")
    data = json.loads(projection.read_text(encoding="utf-8"))
    check("full green audit clears validation pending", data.get("fresh_validation_required") is False, data)


with tempfile.TemporaryDirectory(prefix="v4235_alias_") as temp_name:
    root = Path(temp_name)
    (root / "package.json").write_text(
        '{"dependencies":{"real-package":"^1.0.0"}}\n', encoding="utf-8"
    )
    config = root / "vite.config.ts"
    config.write_text(
        "export default { resolve: { alias: {\n"
        "  'real-package': '/local/missing-config.json',\n"
        "  '@app': '/src',\n"
        "} } };\n",
        encoding="utf-8",
    )
    failure = (
        "[vite:load-fallback] Could not load /local/missing-config.json/core "
        "(imported by src/client.ts): ENOENT"
    )
    changes = m._v4235_fix_dependency_shadow_alias(root, {}, failure)
    repaired = config.read_text(encoding="utf-8")
    check("dependency-shadowing alias repaired", bool(changes), changes)
    check("installed package alias removed", "'real-package'" not in repaired, repaired)
    check("unrelated application alias preserved", "'@app': '/src'" in repaired, repaired)


with tempfile.TemporaryDirectory(prefix="v4235_tests_") as temp_name:
    root = Path(temp_name)
    (root / "src").mkdir()
    (root / "src" / "App.tsx").write_text(
        "export default function App() { return null; }\n", encoding="utf-8"
    )
    (root / "package.json").write_text(
        '{"scripts":{"test":"vitest run"},"devDependencies":{"vitest":"^2.1.0"}}\n',
        encoding="utf-8",
    )
    (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "components": [{"id": "web", "root": ".", "toolchain_adapter": "react"}],
        "files": [{"path": "src/App.tsx", "purpose": "application"}],
        "implementation_order": ["src/App.tsx"],
    }
    changes = m._v4235_repair_declared_node_test_contract(
        root, manifest, "No test files found, exiting with code 1"
    )
    test_file = root / "tests" / "application.integration.test.ts"
    check("declared no-test contradiction repaired", bool(changes), changes)
    check("production-import test seed written", test_file.is_file(), changes)
    test_source = test_file.read_text(encoding="utf-8")
    check("test seed imports production app", "../src/App" in test_source, test_source)
    check("test seed contains assertion", "expect(typeof App)" in test_source, test_source)
    check(
        "test owner persisted in manifest",
        any(row.get("path") == "tests/application.integration.test.ts" for row in manifest["files"]),
        manifest,
    )


with tempfile.TemporaryDirectory(prefix="v4235_tests_wrapper_") as temp_name:
    root = Path(temp_name)
    (root / "src").mkdir()
    (root / "src" / "App.tsx").write_text(
        "export default function App() { return null; }\n", encoding="utf-8"
    )
    (root / "package.json").write_text(
        '{"scripts":{"test":"vitest run"},"devDependencies":{"vitest":"^2.1.0"}}\n',
        encoding="utf-8",
    )
    (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "components": [{"id": "web", "root": ".", "toolchain_adapter": "react"}],
        "files": [{"path": "src/App.tsx", "purpose": "application"}],
        "implementation_order": ["src/App.tsx"],
    }
    repaired = m._repair_real_validation_failure(
        "finish the project", manifest, root,
        "No test files found, exiting with code 1", None,
    )
    check("real failure router repairs missing declared test", repaired is True)
    check(
        "real failure router accepts deterministic test revision",
        m._v413_is_accepted(root, "tests/application.integration.test.ts"),
    )
    check("repaired test contract persisted", (root / m.V33_ARCHITECTURE_FILE).is_file())


with tempfile.TemporaryDirectory(prefix="v4235_existing_tests_") as temp_name:
    root = Path(temp_name)
    (root / "tests").mkdir()
    (root / "tests" / "configured.test.js").write_text("test('x', () => {});\n", encoding="utf-8")
    (root / "package.json").write_text(
        '{"scripts":{"test":"vitest run"}}\n', encoding="utf-8"
    )
    manifest = {"components": [{"id": "web", "root": ".", "toolchain_adapter": "node"}]}
    changes = m._v4235_repair_declared_node_test_contract(
        root, manifest, "No test files found, exiting with code 1"
    )
    check("existing tests route to runner configuration repair", changes == [], changes)


with tempfile.TemporaryDirectory(prefix="v4235_explicit_tests_") as temp_name:
    root = Path(temp_name)
    (root / "src").mkdir()
    (root / "src" / "App.tsx").write_text(
        "export default function App() { return null; }\n", encoding="utf-8"
    )
    (root / "package.json").write_text(
        '{"scripts":{"test":"vitest run"},"devDependencies":{"vitest":"^2.1.0"}}\n',
        encoding="utf-8",
    )
    (root / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "components": [{"id": "web", "root": ".", "toolchain_adapter": "react"}],
        "files": [{"path": "src/App.tsx", "purpose": "application"}],
        "implementation_order": ["src/App.tsx"],
    }
    original_generate = m._generate_planned_file
    model_calls = []
    try:
        def fake_generate(_request, _manifest, work, item, _callback=None):
            model_calls.append(item["path"])
            path = Path(work) / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "import { expect, test } from 'vitest';\n"
                "test('requested behavior', () => expect(2 + 2).toBe(4));\n",
                encoding="utf-8",
            )
            m._v413_mark_accepted(work, item["path"], "fixture")
            return True, item["path"]
        m._generate_planned_file = fake_generate
        repaired = m._repair_real_validation_failure(
            "add integration tests and finish the project", manifest, root,
            "No test files found, exiting with code 1", None,
        )
    finally:
        m._generate_planned_file = original_generate
    check("explicit test request uses model-owned test path", repaired is True, model_calls)
    check("explicit test request bypasses generic seed", model_calls == ["tests/application.integration.test.ts"], model_calls)
    source = (root / "tests" / "application.integration.test.ts").read_text(encoding="utf-8")
    check("explicit test implementation retained", "requested behavior" in source, source)


original_snapshot = m._resume_validation_snapshot
original_transaction = m._v4229_last_mile_transaction
original_small_tail = m._v4230_small_semantic_tail
calls = []
try:
    snapshots = iter([
        {
            "typescript_diagnostic_count": 8,
            "typescript_syntax_diagnostic_count": 0,
            "real_output": "src/App.tsx(1,1): error TS2741: Property 'x' is missing in type '{}'.",
        },
        {
            "typescript_diagnostic_count": 0,
            "typescript_syntax_diagnostic_count": 0,
            "real_ok": True,
            "real_output": "",
        },
    ])
    m._resume_validation_snapshot = lambda *args, **kwargs: next(snapshots)
    m._v4230_small_semantic_tail = lambda work, snapshot: [{
        "file": "src/App.tsx", "code": "2741", "line": 1, "col": 1,
        "raw": "src/App.tsx(1,1): error TS2741: Property 'x' is missing in type '{}'.",
    }]
    m._v4229_last_mile_transaction = lambda request, manifest, work, issues, callback=None: calls.append(Path(work)) or True
    with tempfile.TemporaryDirectory(prefix="v4235_direct_") as temp_name:
        work = Path(temp_name) / "working"
        work.mkdir()
        changed = m._v4235_direct_preflight("finish", {}, work)
        check("direct preflight commits through transaction", changed is True)
        check("direct preflight uses authoritative workspace", calls == [work], calls)
        report = json.loads((work / m.V4235_REPORT).read_text(encoding="utf-8"))
        check("direct preflight report records closure", report.get("before") == 8 and report.get("after") == 0, report)
finally:
    m._resume_validation_snapshot = original_snapshot
    m._v4229_last_mile_transaction = original_transaction
    m._v4230_small_semantic_tail = original_small_tail


print(f"V42.35 compatibility regression: {len(checks)}/{len(checks)} PASS")
