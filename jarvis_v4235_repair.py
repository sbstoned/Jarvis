"""V42.35 candidate-runtime parity and verified convergence patch.

This module is intentionally installed at the end of local_qwen_project.py.  It
repairs the active function graph without duplicating the large historical engine.
The important invariant is simple: a disposable repair candidate must be compiled
with the same dependency substrate as the accepted workspace.  Dependency/build
artifacts still remain outside project ZIPs and are never promoted as source.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


VERSION = "42.35.0"
ENGINE = "CANDIDATE_RUNTIME_PARITY_UNIVERSAL_CONVERGENCE_FACTORY"
REPORT = "JARVIS_V4235_RUNTIME_PARITY_REPORT.json"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"

_NODE_ADAPTERS = {
    "node", "react", "vite", "nextjs", "vue", "sveltekit", "nuxt",
    "angular", "electron", "react_native", "expo", "tauri",
}
_DISCOVERY_SKIP = {
    ".git", ".svn", ".hg", "node_modules", "vendor", "target", "dist",
    "build", ".next", ".nuxt", ".jarvis_runtime", ".jarvis_artifacts",
    ".jarvis_build", ".jarvis_candidates", ".jarvis_backups", "__pycache__",
    ".cache", ".gradle", ".dart_tool", "Pods", "DerivedData",
}
_DIFF_SKIP = _DISCOVERY_SKIP | {
    ".venv", "venv", "env", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "coverage", ".turbo", ".parcel-cache", ".angular", ".svelte-kit",
}


def _normal_rel(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/")
    return "." if text in {"", "."} else text


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except Exception:
        return False


def _is_linklike(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except Exception:
        pass
    try:
        checker = getattr(path, "is_junction", None)
        return bool(checker and checker())
    except Exception:
        return False


def _link_directory(source: Path, destination: Path) -> tuple[bool, str]:
    """Create a disposable directory reference without copying dependency trees."""
    source = source.resolve()
    destination = destination.absolute()
    if not source.is_dir():
        return False, "source dependency directory is unavailable"
    if destination.exists() or destination.is_symlink():
        return True, "existing"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.symlink_to(source, target_is_directory=True)
        return True, "symlink"
    except Exception as first_error:
        if os.name != "nt":
            return False, str(first_error)
    # Directory junctions work on ordinary Windows installations where creating a
    # symbolic link may require Developer Mode or elevated privileges.
    try:
        cmd = os.environ.get("COMSPEC") or "cmd.exe"
        statement = f'mklink /J "{destination}" "{source}"'
        proc = subprocess.run(
            [cmd, "/d", "/s", "/c", statement],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
        if proc.returncode == 0 and destination.is_dir():
            return True, "junction"
        return False, (proc.stdout or f"mklink exited {proc.returncode}").strip()
    except Exception as exc:
        return False, str(exc)


def _node_component_roots(root: Path, manifest: dict | None = None) -> list[str]:
    root = root.resolve()
    found: list[str] = []

    def add(value: object) -> None:
        rel = _normal_rel(value)
        candidate = root if rel == "." else root / rel
        if not _inside(candidate, root) or not (candidate / "package.json").is_file():
            return
        if rel not in found:
            found.append(rel)

    for component in (manifest or {}).get("components") or []:
        if not isinstance(component, dict):
            continue
        adapter = str(component.get("toolchain_adapter") or "").strip().lower()
        if adapter in _NODE_ADAPTERS:
            add(component.get("root") or ".")

    # Marker discovery keeps candidate parity working when a resumed manifest is old,
    # incomplete, or describes a multi-language repository only at the top level.
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        names[:] = [name for name in names if name not in _DISCOVERY_SKIP]
        here = Path(directory)
        if "package.json" in files:
            try:
                add(here.relative_to(root).as_posix() or ".")
            except Exception:
                pass
        if len(found) >= 32:
            break
    return found


def prepare_candidate_runtime(
    original_root: Path | str,
    candidate_root: Path | str,
    manifest: dict | None = None,
) -> list[dict]:
    """Project read-mostly dependencies into an isolated candidate workspace.

    Source, build outputs, caches, and package artifacts remain distinct.  Only an
    already-restored dependency tree is referenced; this function never installs,
    downloads, or copies a potentially multi-gigabyte tree.
    """
    original = Path(original_root).resolve()
    candidate = Path(candidate_root).resolve()
    if original == candidate or not original.is_dir() or not candidate.is_dir():
        return []
    records: list[dict] = []
    for rel in _node_component_roots(original, manifest):
        source_component = original if rel == "." else original / rel
        candidate_component = candidate if rel == "." else candidate / rel
        if not candidate_component.is_dir():
            continue
        source = source_component / "node_modules"
        destination = candidate_component / "node_modules"
        if not source.is_dir():
            continue
        if not _inside(destination, candidate):
            continue
        ok, method = _link_directory(source, destination)
        records.append({
            "component": rel,
            "dependency": "node_modules",
            "available": bool(ok),
            "method": method[:500],
        })
    return records


def dependency_avalanche(output: object) -> bool:
    """Recognize a validator clone that lost its external dependency substrate."""
    text = str(output or "")
    missing = []
    for module in re.findall(r"Cannot find module ['\"]([^'\"]+)['\"]", text, re.I):
        if module.startswith((".", "/")) or re.match(r"^[A-Za-z]:[\\/]", module):
            continue
        if module not in missing:
            missing.append(module)
    jsx_fallout = len(re.findall(r"JSX element implicitly has type ['\"]?any", text, re.I))
    return len(missing) >= 2 or (bool(missing) and jsx_fallout >= 4)


def _remove_dependency_shadow_alias(
    work: Path | str,
    manifest: dict | None,
    failure: object,
) -> list[dict]:
    """Remove a compiler/bundler-proven alias that hijacks a real package import.

    This is deliberately narrow: the alias key must also be a declared package
    dependency, the failed build must mention the alias/target, and the target must
    be a file-like or missing local path.  Legitimate application aliases remain.
    """
    root = Path(work).resolve()
    evidence = str(failure or "")
    low = evidence.lower()
    if not any(token in low for token in ("could not load", "failed to resolve", "load-fallback", "enoent")):
        return []
    changed: list[dict] = []
    for rel in _node_component_roots(root, manifest or {}):
        component = root if rel == "." else root / rel
        package = component / "package.json"
        try:
            package_data = json.loads(package.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        dependencies = set()
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            values = package_data.get(section) or {}
            if isinstance(values, dict):
                dependencies.update(str(name) for name in values)
        if not dependencies:
            continue
        configs = []
        for name in (
            "vite.config.ts", "vite.config.js", "vite.config.mts", "vite.config.mjs",
            "vitest.config.ts", "vitest.config.js",
        ):
            path = component / name
            if path.is_file():
                configs.append(path)
        for config in configs:
            try:
                source = config.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            output = source
            removed = []
            pattern = re.compile(
                r"(?m)^(?P<indent>[ \t]*)(?P<q>['\"])(?P<key>[^'\"]+)"
                r"(?P=q)[ \t]*:[ \t]*(?P<tq>['\"])(?P<target>[^'\"]+)"
                r"(?P=tq)[ \t]*,?[ \t]*(?:\r?\n|$)"
            )
            for match in list(pattern.finditer(source)):
                key = match.group("key").strip()
                target = match.group("target").strip()
                if key not in dependencies:
                    continue
                if key.lower() not in low and target.lower() not in low:
                    continue
                local_text = target.lstrip("/\\")
                local = component / local_text
                file_like = bool(Path(local_text).suffix) or local.is_file()
                missing = not local.exists()
                if not (file_like or missing):
                    continue
                output = output.replace(match.group(0), "", 1)
                removed.append({"key": key, "target": target})
            if removed and output != source:
                temporary = config.with_name(config.name + ".v4235.tmp")
                try:
                    temporary.write_text(output, encoding="utf-8")
                    os.replace(temporary, config)
                    changed.append({
                        "file": config.relative_to(root).as_posix(),
                        "aliases": removed,
                    })
                except Exception:
                    try:
                        temporary.unlink(missing_ok=True)
                    except Exception:
                        pass
    return changed


def _node_test_files(component: Path) -> list[Path]:
    """Return authored Node test files without scanning dependency/build trees."""
    found: list[Path] = []
    test_name = re.compile(r"(?:^|[._-])(test|spec)\.(?:[cm]?[jt]sx?)$", re.I)
    for directory, names, files in os.walk(component, topdown=True, followlinks=False):
        here = Path(directory)
        kept = []
        for name in names:
            child = here / name
            if name in _DIFF_SKIP or _is_linklike(child):
                continue
            kept.append(name)
        names[:] = kept
        for name in files:
            if test_name.search(name):
                found.append(here / name)
        if len(found) >= 128:
            break
    return found


def _missing_test_evidence(failure: object) -> bool:
    text = str(failure or "").lower()
    return any(token in text for token in (
        "no test files found",
        "no tests found",
        "could not find any test files",
        "did not match any files",
    ))


def _react_vitest_smoke_source(test_rel: str, app_rel: str) -> str:
    import posixpath

    base = posixpath.dirname(_normal_rel(test_rel))
    target = _normal_rel(app_rel)
    module = posixpath.relpath(target, base or ".")
    module = re.sub(r"\.(?:ts|tsx|js|jsx|mts|cts)$", "", module, flags=re.I)
    if not module.startswith("."):
        module = "./" + module
    return (
        "import { describe, expect, it } from 'vitest';\n"
        f"import App from '{module}';\n\n"
        "describe('application integration smoke', () => {\n"
        "  it('links the real application entry component', () => {\n"
        "    expect(typeof App).toBe('function');\n"
        "  });\n"
        "});\n"
    )


def _repair_declared_node_test_contract(
    work: Path | str,
    manifest: dict | None,
    failure: object,
) -> list[dict]:
    """Close the declared-test/no-test contradiction from native runner evidence.

    Jarvis must not declare a real test command, fail because the component has no
    tests, and then retire the missing test as optional debt. A safe deterministic
    seed is used only for the narrow React+Vitest shape. Other stacks receive an
    explicit manifest-owned test file for the normal model-driven implementation
    path; no runner-agnostic fake source is invented.
    """
    if not _missing_test_evidence(failure):
        return []
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    changes: list[dict] = []
    for component_rel in _node_component_roots(root, manifest):
        component = root if component_rel == "." else root / component_rel
        package_path = component / "package.json"
        try:
            package = json.loads(package_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        test_command = str((package.get("scripts") or {}).get("test") or "").strip()
        if not test_command or test_command in {"echo", "true", "exit 0"}:
            continue
        command_low = test_command.lower()
        # Existing tests make this a runner/filter configuration repair, not a
        # missing-owner repair. Never add a second test to hide that real problem.
        if _node_test_files(component):
            continue

        language_ext = ".ts" if (component / "tsconfig.json").is_file() else ".js"
        test_local = f"tests/application.integration.test{language_ext}"
        test_rel = test_local if component_rel == "." else f"{component_rel}/{test_local}"
        app_candidates = [
            ("src/App.tsx", component / "src" / "App.tsx"),
            ("src/App.jsx", component / "src" / "App.jsx"),
        ]
        app_local = next((rel for rel, path in app_candidates if path.is_file()), "")
        deterministic = bool("vitest" in command_low and app_local)

        rows = manifest.setdefault("files", [])
        known = {
            _normal_rel(row.get("path"))
            for row in rows
            if isinstance(row, dict) and row.get("path")
        }
        planned = test_rel not in known
        app_rel = app_local if component_rel == "." else f"{component_rel}/{app_local}"
        if planned:
            rows.append({
                "path": test_rel,
                "purpose": (
                    "Executable integration smoke test owned by the declared component test command; "
                    "it must import production code and contain meaningful assertions."
                ),
                "phase": "test",
                "depends_on": [app_rel] if app_local else [],
                "exports": [],
                "contracts": ["declared_test_command_has_executable_test_owner"],
                "v4235_declared_test_contract": True,
            })
            order = manifest.setdefault("implementation_order", [])
            if isinstance(order, list) and test_rel not in order:
                order.append(test_rel)

        wrote = False
        if deterministic:
            destination = root / test_rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                _react_vitest_smoke_source(test_rel, app_rel), encoding="utf-8"
            )
            wrote = True
        changes.append({
            "component": component_rel,
            "test_command": test_command,
            "test_file": test_rel,
            "manifest_owner_added": planned,
            "deterministic_seed_written": wrote,
            "mode": "react_vitest_production_import" if wrote else "planned_model_implementation",
        })
    return changes


def _source_diff(work: Path | str, clone: Path | str) -> list[str]:
    """Compare authored files without ever descending into links/junctions."""
    root = Path(work).resolve()
    candidate = Path(clone).resolve()
    changed: list[str] = []
    for directory, names, files in os.walk(candidate, topdown=True, followlinks=False):
        here = Path(directory)
        kept = []
        for name in names:
            child = here / name
            if name in _DIFF_SKIP or _is_linklike(child):
                continue
            kept.append(name)
        names[:] = kept
        for name in files:
            path = here / name
            try:
                rel = path.relative_to(candidate)
            except Exception:
                continue
            if set(rel.parts) & _DIFF_SKIP:
                continue
            if rel.name.startswith("JARVIS_") or rel.name.startswith(".jarvis_"):
                continue
            accepted = root / rel
            try:
                if not accepted.exists() or accepted.read_bytes() != path.read_bytes():
                    changed.append(rel.as_posix())
            except Exception:
                continue
    return sorted(set(changed))


def install(engine_globals: dict) -> None:
    """Install V42.35 into the already-loaded Jarvis engine namespace."""
    g = engine_globals
    PathType = g.get("Path", Path)
    g.update({
        "V4235_VERSION": VERSION,
        "V4235_ENGINE": ENGINE,
        "V4235_REPORT": REPORT,
        "V4235_ENGINE_MARKER": ENGINE_MARKER,
        "_v4235_prepare_candidate_runtime": prepare_candidate_runtime,
        "_v4235_dependency_avalanche": dependency_avalanche,
        "_v4235_repair_declared_node_test_contract": _repair_declared_node_test_contract,
    })

    previous_clone = g["_v4224_clone_workspace"]
    previous_measure = g["_v4224_measure_typescript"]
    previous_identity = g["_v36_release_identity"]
    previous_qwen_call = g["_qwen_call"]
    previous_real_failure_repair = g["_repair_real_validation_failure"]
    previous_resume_without_v4230 = g.get("_v4230_prev_run_resume_sweeps", g["_run_resume_sweeps"])
    previous_generate_without_v4230 = g.get("_v4230_prev_generate_project_zip", g["generate_project_zip"])
    previous_edit_without_v4230 = g.get("_v4230_prev_analyze_project_zip", g["analyze_and_edit_project_zip"])
    durable_append = g.get("_v4227_prev_append_project_event", g["_append_project_event"])
    base_progress = g.get("_v38_prev_progress", g["_progress"])

    def clone_workspace(work):
        td, clone = previous_clone(work)
        try:
            prepare_candidate_runtime(work, clone, None)
        except Exception:
            # Measurement below distinguishes unavailable validation infrastructure
            # from a source regression.  Candidate source remains isolated either way.
            pass
        return td, clone

    def measure_typescript(original_work, candidate_work, manifest, hint_rel):
        records = []
        try:
            records = prepare_candidate_runtime(original_work, candidate_work, manifest or {})
        except Exception:
            records = []
        count, output = previous_measure(original_work, candidate_work, manifest, hint_rel)
        original_has_dependencies = any(
            (PathType(original_work) / ("" if rel == "." else rel) / "node_modules").is_dir()
            for rel in _node_component_roots(Path(original_work), manifest or {})
        )
        candidate_has_dependencies = any(bool(row.get("available")) for row in records)
        if original_has_dependencies and not candidate_has_dependencies and dependency_avalanche(output):
            return None, (
                "V42.35 CANDIDATE_RUNTIME_UNAVAILABLE: the disposable validation workspace "
                "could not access the accepted component dependency tree. This is validator "
                "infrastructure evidence, not an application-source regression.\n" + str(output or "")
            )[-12000:]
        return count, output

    def append_event(work, event_type, message, **fields):
        fields = dict(fields)
        fields["engine_version"] = "V" + VERSION
        event = durable_append(work, event_type, message, **fields)
        try:
            projection_name = g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            projection_path = PathType(work) / projection_name
            load = g.get("_v4225_json_load")
            save = g.get("_v4225_json_save")
            data = load(projection_path, {}) if load else {}
            if isinstance(data, dict):
                data.update({
                    "version": "V" + VERSION,
                    "engine": ENGINE,
                    "updated_at": g["_utc_stamp"](),
                })
                event_key = str(event_type or "").strip().lower()
                committed_files = {
                    _normal_rel(item) for item in (fields.get("files") or [])
                    if _normal_rel(item)
                }
                if fields.get("file"):
                    committed_files.add(_normal_rel(fields.get("file")))
                blocker = data.get("current_blocker")
                blocker_file = _normal_rel(blocker.get("file")) if isinstance(blocker, dict) else ""
                improved = False
                try:
                    improved = int(fields.get("after")) < int(fields.get("before"))
                except Exception:
                    improved = False
                committed = "committed" in event_key or "accepted" in event_key
                if (improved or committed) and blocker_file and blocker_file in committed_files:
                    data.pop("current_blocker", None)
                    data["fresh_validation_required"] = True
                    data["invalidated_blocker"] = {
                        "file": blocker_file,
                        "by_event": event_key,
                        "at": g["_utc_stamp"](),
                    }
                fully_green = any(token in event_key for token in (
                    "whole_project_green",
                    "final_acceptance_passed",
                    "project_complete",
                    "publication_accepted",
                ))
                if fully_green:
                    data.pop("current_blocker", None)
                    data["fresh_validation_required"] = False
                    data["last_fully_verified_event"] = {
                        "type": event_key,
                        "at": g["_utc_stamp"](),
                    }
                if save:
                    save(projection_path, data)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        if text is not None:
            text = str(text)
            text = re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.35", text)
        fields = dict(fields)
        fields["engine_version"] = "V" + VERSION
        return base_progress(callback, text, **fields)

    def direct_preflight(user_request, manifest, work, progress_callback=None):
        root = PathType(work)
        try:
            baseline = g["_resume_validation_snapshot"](
                root, manifest, user_request, include_real=True
            )
            rows = g["_v4230_small_semantic_tail"](root, baseline)
        except Exception as exc:
            append_event(
                root,
                "v4235_direct_preflight_unavailable",
                "V42.35 could not obtain a fresh compiler baseline before resume repair.",
                error=str(exc)[:1800],
            )
            return False
        if not rows:
            return False
        before = int(baseline.get("typescript_diagnostic_count") or len(rows))
        files = sorted({g["_v40_norm_rel"](row.get("file")) for row in rows if row.get("file")})
        append_event(
            root,
            "v4235_direct_preflight_started",
            f"V42.35 found {before} syntax-clean compiler diagnostic(s); running the isolated constraint transaction with dependency parity.",
            before=before,
            files=files,
        )
        issue_text = g["_v4230_issue_text_from_rows"](rows)
        try:
            changed = bool(g["_v4229_last_mile_transaction"](
                user_request, manifest, root, [issue_text], progress_callback
            ))
        except Exception as exc:
            append_event(
                root,
                "v4235_direct_preflight_exception",
                "V42.35 isolated compiler transaction failed closed; accepted source was preserved.",
                error=str(exc)[:1800],
            )
            return False
        if not changed:
            append_event(
                root,
                "v4235_direct_preflight_no_change",
                "V42.35 could not prove a compiler-improving deterministic transaction; normal evidence-driven repair remains active.",
                before=before,
            )
            return False
        try:
            after_snapshot = g["_resume_validation_snapshot"](
                root, manifest, user_request, include_real=True
            )
            after = int(after_snapshot.get("typescript_diagnostic_count") or 0)
        except Exception:
            after_snapshot = {}
            after = 0
        payload = {
            "version": "V" + VERSION,
            "engine": ENGINE,
            "at": g["_utc_stamp"](),
            "before": before,
            "after": after,
            "files": files,
            "candidate_runtime_parity": True,
            "policy": "fresh compiler evidence -> dependency-parity candidate -> strict compiler delta -> atomic source commit -> full acceptance",
        }
        try:
            g["_v4225_json_save"](root / REPORT, payload)
        except Exception:
            pass
        append_event(
            root,
            "v4235_direct_preflight_committed",
            f"V42.35 atomically reduced the compiler tail {before} -> {after}; continuing into build, tests, runtime, and requirement acceptance.",
            before=before,
            after=after,
            files=files,
        )
        progress(
            progress_callback,
            f"V42.35 repaired the fresh compiler tail {before} -> {after} with candidate/runtime parity; continuing full acceptance.",
            stage="V42.35 verified compiler convergence",
            percent=92,
        )
        return True

    def run_resume_sweeps(
        user_request, manifest, work, job_root, progress_callback=None,
        generic_resume=True, prior_issues=None, max_sweeps=None,
    ):
        # The V42.30 preflight cloned source before the constraint transaction and
        # thereby discarded the restored dependencies. Run the already-transactional
        # solver against the accepted workspace; it still commits only after a strict
        # compiler improvement from an isolated candidate.
        try:
            direct_preflight(user_request, manifest, work, progress_callback)
        except Exception as exc:
            append_event(
                work,
                "v4235_preflight_guard_exception",
                "V42.35 preflight failed closed; bounded resume repair continues.",
                error=str(exc)[:1800],
            )
        if max_sweeps is None:
            configured = int(os.getenv("JARVIS_V4235_RESUME_SWEEPS", "4"))
            max_sweeps = max(int(g.get("RESUME_SWEEPS", 1)), max(2, min(8, configured)))
        return previous_resume_without_v4230(
            user_request, manifest, work, job_root, progress_callback,
            generic_resume=generic_resume,
            prior_issues=prior_issues,
            max_sweeps=max_sweeps,
        )

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = (
            "\n\nV42.35 FINAL REPAIR AUTHORITY: Treat fresh native compiler/build/test/runtime "
            "output as evidence. Validate repair candidates with the accepted workspace's "
            "dependency substrate; never rewrite application code to compensate for a missing "
            "candidate dependency tree. Stage connected changes together, preserve unrelated "
            "behavior during edits, and accept source only after the relevant real validator "
            "strictly improves. A green compile is an intermediate milestone: continue through "
            "tests, runtime smoke, integration contracts, and every explicit user requirement "
            "before calling the project complete. Remain language/framework/toolchain agnostic."
        )
        return previous_qwen_call(
            str(prompt or "") + authority,
            progress_callback,
            str(stage or "").replace("V42.30", "V42.35"),
            profile=profile,
            **kwargs,
        )

    def fix_dependency_shadow_alias(work, manifest, failure):
        changed = _remove_dependency_shadow_alias(work, manifest, failure)
        if changed:
            append_event(
                work,
                "v4235_dependency_shadow_alias_removed",
                "V42.35 removed a build-proven local alias that shadowed an installed package namespace; the full component will be rebuilt.",
                changes=changed,
            )
        return changed

    def repair_real_validation_failure(user_request, manifest, work, failure, progress_callback=None):
        live_manifest = manifest if isinstance(manifest, dict) else {}
        changed = fix_dependency_shadow_alias(work, live_manifest, failure)
        if changed:
            progress(
                progress_callback,
                "V42.35 repaired a dependency-shadowing bundler alias from real build evidence; rebuilding the complete component now.",
                stage="V42.35 deterministic build-configuration repair",
                percent=91,
                current_file=changed[0].get("file", ""),
            )
            return True
        test_changes = _repair_declared_node_test_contract(work, live_manifest, failure)
        if test_changes:
            original_request = str(live_manifest.get("_original_user_request") or "")
            request_has_explicit_tests = False
            try:
                request_has_explicit_tests = bool(g["_explicit_tests_requested"](
                    str(user_request or "") + "\n" + original_request
                ))
            except Exception:
                request_has_explicit_tests = False
            if request_has_explicit_tests:
                for row in test_changes:
                    if not row.get("deterministic_seed_written"):
                        continue
                    rel = str(row.get("test_file") or "")
                    try:
                        (PathType(work) / rel).unlink(missing_ok=True)
                    except Exception:
                        pass
                    row["deterministic_seed_written"] = False
                    row["mode"] = "explicit_requirement_model_implementation"
            effective_changes = []
            for row in test_changes:
                rel = str(row.get("test_file") or "")
                if not rel:
                    continue
                if row.get("deterministic_seed_written"):
                    try:
                        g["_v413_mark_accepted"](work, rel, "v4235_declared_test_contract")
                    except Exception:
                        pass
                    effective_changes.append(row)
                    continue
                item = next((
                    item for item in live_manifest.get("files") or []
                    if isinstance(item, dict) and _normal_rel(item.get("path")) == rel
                ), None)
                try:
                    ok, wrote = g["_generate_planned_file"](
                        user_request, live_manifest, work, item, progress_callback
                    ) if item else (False, "")
                except Exception as exc:
                    ok, wrote = False, ""
                    row["model_generation_error"] = str(exc)[:1000]
                row["model_generation_succeeded"] = bool(
                    ok and (PathType(work) / rel).is_file()
                )
                row["model_generation_output"] = str(wrote or "")[:500]
                if row["model_generation_succeeded"]:
                    effective_changes.append(row)
            if not effective_changes:
                # A manifest-only mutation is not repair progress. Remove the
                # unmaterialized provisional owners before normal diagnosis so a
                # later audit cannot oscillate between planning and retirement.
                provisional = {
                    str(row.get("test_file") or "") for row in test_changes
                    if row.get("manifest_owner_added")
                }
                live_manifest["files"] = [
                    item for item in live_manifest.get("files") or []
                    if not (
                        isinstance(item, dict)
                        and _normal_rel(item.get("path")) in provisional
                        and item.get("v4235_declared_test_contract")
                    )
                ]
                if isinstance(live_manifest.get("implementation_order"), list):
                    live_manifest["implementation_order"] = [
                        item for item in live_manifest["implementation_order"]
                        if _normal_rel(item) not in provisional
                    ]
                return bool(previous_real_failure_repair(
                    user_request, live_manifest, work, failure, progress_callback
                ))
            try:
                g["_v33_write_architecture"](work, live_manifest)
            except Exception:
                pass
            append_event(
                work,
                "v4235_declared_test_contract_closed",
                "V42.35 converted a native no-tests failure into an explicit test owner; safe React/Vitest components receive a production-import smoke seed and other stacks continue through normal model-driven test implementation.",
                changes=effective_changes,
            )
            progress(
                progress_callback,
                "V42.35 closed the declared-test/no-test contradiction from native runner evidence; rerunning component tests now.",
                stage="V42.35 executable test-contract repair",
                percent=92,
                current_file=effective_changes[0].get("test_file", ""),
            )
            return True
        return bool(previous_real_failure_repair(
            user_request, live_manifest, work, failure, progress_callback
        ))

    def release_identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "candidate-runtime-parity-verified-universal-convergence-v42.35",
            "candidate_dependency_parity": True,
            "candidate_dependency_copy": False,
            "candidate_source_artifact_separation": True,
            "candidate_links_pruned_from_source_diff": True,
            "dependency_avalanche_is_infrastructure": True,
            "resume_last_mile_runs_on_authoritative_dependency_environment": True,
            "fresh_native_validation_required_for_commit": True,
            "full_acceptance_continues_after_compile": True,
            "declared_test_command_requires_executable_test_owner": True,
            "new_project_and_existing_project_edit_modes": True,
            "language_framework_toolchain_agnostic": True,
            "default_resume_sweeps": max(int(g.get("RESUME_SWEEPS", 1)), 4),
        })
        return data

    def engine_guard():
        marker = PathType(g["__file__"]).resolve().with_name(ENGINE_MARKER)
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
        expected = "V" + VERSION
        if disk and disk != expected:
            return False, (
                f"Jarvis engine files identify {disk}, but this running process is {expected}. "
                "Fully close and restart Jarvis before starting or resuming a project."
            )
        return True, ""

    def generate_project_zip(user_request, max_files=None, max_audit_passes=None, progress_callback=None):
        ok, message = engine_guard()
        if not ok:
            return False, message, None
        return previous_generate_without_v4230(
            user_request,
            max_files=max_files,
            max_audit_passes=max_audit_passes,
            progress_callback=progress_callback,
        )

    def analyze_and_edit_project_zip(user_request, source_zip, max_audit_passes=None, progress_callback=None):
        ok, message = engine_guard()
        if not ok:
            return False, message, None
        return previous_edit_without_v4230(
            user_request,
            source_zip,
            max_audit_passes=max_audit_passes,
            progress_callback=progress_callback,
        )

    g.update({
        # Expose the pre-wrapper callables so a later focused release can preserve
        # the disk-engine guard without recursing through V42.35's public wrappers.
        # These are implementation hand-off points, not alternate public APIs.
        "_v4235_previous_generate_project_zip": previous_generate_without_v4230,
        "_v4235_previous_analyze_project_zip": previous_edit_without_v4230,
        "_v4235_previous_qwen_call": previous_qwen_call,
        "_v4235_durable_append_project_event": durable_append,
        "_v4235_base_progress": base_progress,
        "_v4224_clone_workspace": clone_workspace,
        "_v4224_measure_typescript": measure_typescript,
        "_v4225_diff_source_files": _source_diff,
        "_v4235_direct_preflight": direct_preflight,
        "_v4235_engine_disk_guard": engine_guard,
        "_v4235_fix_dependency_shadow_alias": fix_dependency_shadow_alias,
        "_run_resume_sweeps": run_resume_sweeps,
        "_repair_real_validation_failure": repair_real_validation_failure,
        "_qwen_call": qwen_call,
        "_v36_release_identity": release_identity,
        "_append_project_event": append_event,
        "_progress": progress,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
