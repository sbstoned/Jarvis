from pathlib import Path
import shutil
import tempfile

import jarvis_v4242_repair as active

passed = 0

def check(name, condition, detail=None):
    global passed
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    passed += 1
    print(f"PASS: {name}")

check("active V42.46 version", active.VERSION == "42.50.0", active.VERSION)
check("warm-cache strategy generation", active.STRATEGY_GENERATION == "functional-acceptance-v8-regression-safe-component-proof", active.STRATEGY_GENERATION)
check("warm-cache engine", active.ENGINE == "REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY", active.ENGINE)

component = {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"}

with tempfile.TemporaryDirectory(prefix="jarvis_v4245_warm_gate_") as td:
    base = Path(td)
    accepted = base / "accepted"
    clone = base / "clone"
    (accepted / "src-tauri").mkdir(parents=True)
    (clone / "src-tauri").mkdir(parents=True)
    (accepted / "src-tauri/Cargo.toml").write_text('[package]\nname="x"\nversion="0.1.0"\n', encoding="utf-8")
    (clone / "src-tauri/Cargo.toml").write_text('[package]\nname="x"\nversion="0.1.0"\n', encoding="utf-8")
    calls = []
    progress = []
    def runner(args, cwd, timeout):
        calls.append((list(args), Path(cwd), timeout))
        if len(calls) == 1:
            return False, "Command timed out after 300s: cargo build\nCompiling x v0.1.0"
        return True, "Finished dev profile"
    old_which = active.shutil.which
    active.shutil.which = lambda name: "/fake/cargo" if name == "cargo" else old_which(name)
    try:
        g = {
            "_run_command": runner,
            "_progress": lambda *args, **kwargs: progress.append((args, kwargs)),
        }
        result = active._warm_rust_compile_gate(g, accepted, clone, component, ["src-tauri/src/tools.rs"])
    finally:
        active.shutil.which = old_which
    expected_target = str((accepted / "src-tauri/target").resolve())
    check("timeout gets one bounded warmed continuation", result.get("ok") is True and result.get("attempts") == 2, result)
    check("compiler proof uses shared accepted target dir", all("--target-dir" in args and expected_target in args for args, _, _ in calls), calls)
    check("candidate source cwd remains disposable clone", all(cwd == (clone / "src-tauri").resolve() for _, cwd, _ in calls), calls)
    check("warm proof reports dedicated proof kind", result.get("kind") == "cargo_build_shared_target", result)
    check("retry emits progress heartbeat", len(progress) == 1, progress)

with tempfile.TemporaryDirectory(prefix="jarvis_v4245_warm_gate_fail_") as td:
    base = Path(td)
    accepted = base / "accepted"
    clone = base / "clone"
    (accepted / "src-tauri").mkdir(parents=True)
    (clone / "src-tauri").mkdir(parents=True)
    (clone / "src-tauri/Cargo.toml").write_text('[package]\nname="x"\nversion="0.1.0"\n', encoding="utf-8")
    old_which = active.shutil.which
    active.shutil.which = lambda name: "/fake/cargo" if name == "cargo" else old_which(name)
    try:
        g = {"_run_command": lambda args, cwd, timeout: (False, "error[E0277]: still broken"), "_progress": lambda *a, **k: None}
        result = active._warm_rust_compile_gate(g, accepted, clone, component, ["src-tauri/src/tools.rs"])
    finally:
        active.shutil.which = old_which
    check("real compiler failure stays fail-closed", result.get("ok") is False and result.get("timed_out") is False, result)

print(f"V42.46 warm-cache compiler gate regression: {passed}/{passed} PASS")
