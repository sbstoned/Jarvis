"""Jarvis V42.50 regression-safe functional convergence.

V42.49 correctly dependency-ordered functional repairs, but its patch-only path
still promoted a changed source file before proving that the affected component
remained compiler/build green.  A functional/persistence finding could therefore
improve while a previously-green Rust/TypeScript/etc. component regressed.

V42.50 makes candidate acceptance lexicographic and stack-agnostic:
  1. compiler/build/component health may never regress;
  2. the targeted functional contract family must strictly improve;
  3. only then may the candidate become authoritative;
  4. the normal whole-project build/test/runtime/functional audit still reruns
     after promotion and remains final acceptance authority.

The candidate stays in a disposable project clone until these proofs pass.  Rust
uses the accepted workspace's warm Cargo target cache; other stacks use their
registered component validator/build adapter.  Stack adapters are optional -- the
policy itself is universal.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import jarvis_v4237_repair as v4237
import jarvis_v4242_repair as v4242
import jarvis_v4249_repair as v4249

VERSION = "42.50.0"
ENGINE = "REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY"
STRATEGY_GENERATION = "functional-acceptance-v8-regression-safe-component-proof"

_COMPONENT_BLOCKER_TOKENS = (
    "component_validation", "compiler", "compile", "build_failure", "build",
    "language_syntax", "syntax_error", "typecheck", "type_check",
)


def _norm(value: object) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def _is_component_blocker(row: dict) -> bool:
    kind = str((row or {}).get("kind") or "").strip().lower()
    if kind == "component_validation":
        return True
    return any(token == kind or kind.startswith(token + "_") for token in _COMPONENT_BLOCKER_TOKENS)


def _resolve_component(g: dict, root: Path, manifest: dict, rel: str) -> dict:
    component = v4237._component_for_rel(manifest or {}, rel)
    if isinstance(component, dict) and component:
        return component
    discover = g.get("_v35_discover_components")
    if callable(discover):
        try:
            tmp = dict(manifest or {})
            tmp["components"] = list(discover(root, manifest or {}) or [])
            component = v4237._component_for_rel(tmp, rel)
            if isinstance(component, dict):
                return component
        except Exception:
            pass
    return {}


def _component_cwd(root: Path, component: dict) -> Path:
    _cid, rel_root, _adapter = v4237._component_identity(component)
    return root if rel_root in {"", "."} else root / rel_root


def _link_dir(source: Path, destination: Path) -> bool:
    """Best-effort read-only-ish dependency-cache bridge for disposable clones."""
    if not source.is_dir() or destination.exists():
        return destination.exists()
    try:
        if os.name == "nt":
            # Directory junctions do not require Developer Mode/admin on normal NTFS.
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(destination), str(source)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                timeout=20, check=False,
            )
            return result.returncode == 0 and destination.exists()
        os.symlink(source, destination, target_is_directory=True)
        return destination.exists()
    except Exception:
        return False


def _hydrate_candidate_dependencies(root: Path, clone: Path, component: dict) -> None:
    accepted = _component_cwd(root, component)
    candidate = _component_cwd(clone, component)
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    # These are dependency/tool caches only; authored source never comes from them.
    for name in ("node_modules", ".dart_tool", ".gradle"):
        _link_dir(accepted / name, candidate / name)


def _run_rust_candidate_tests(g: dict, root: Path, clone: Path, component: dict, changed: List[str], progress_callback=None) -> dict:
    build = v4242._warm_rust_compile_gate(g, root, clone, component, changed, progress_callback)
    if not build.get("available") or not build.get("ok"):
        return build
    cargo = shutil.which("cargo")
    runner = g.get("_run_command")
    if not cargo or not callable(runner):
        return {"available": False, "ok": False, "kind": "cargo_test_unavailable", "output": "cargo/test runner unavailable"}
    _cid, rel_root, _adapter = v4237._component_identity(component)
    candidate_cwd = clone if rel_root in {"", "."} else clone / rel_root
    accepted_cwd = root if rel_root in {"", "."} else root / rel_root
    target = accepted_cwd / "target"
    try:
        timeout = max(60, min(900, int(os.getenv("JARVIS_V4250_CANDIDATE_TEST_TIMEOUT", "300"))))
    except Exception:
        timeout = 300
    try:
        ok, output = runner([cargo, "test", "--target-dir", str(target)], candidate_cwd, timeout)
    except Exception as exc:
        ok, output = False, str(exc)
    return {
        "available": True,
        "ok": bool(ok),
        "kind": "cargo_build_and_test_shared_target",
        "output": str(build.get("output") or "")[-5000:] + "\n" + str(output or "")[-7000:],
        "target_dir": str(target),
    }


def _component_candidate_proof(g: dict, root: Path, clone: Path, manifest: dict, rel: str, progress_callback=None) -> dict:
    """Prove the affected component stays green before functional promotion."""
    component = _resolve_component(g, root, manifest or {}, rel)
    if not component:
        # Interpreted/uncomponentized projects still get language syntax + functional
        # delta gates; the normal whole-project audit remains authoritative.
        return {"available": False, "ok": True, "kind": "no_declared_component", "output": ""}

    cid, _component_root, adapter = v4237._component_identity(component)
    if adapter == "rust":
        return _run_rust_candidate_tests(g, root, clone, component, [rel], progress_callback)

    _hydrate_candidate_dependencies(root, clone, component)
    validator = g.get("_v35_validate_component")
    if callable(validator):
        try:
            ok, output = validator(clone, manifest or {}, component, "V42.50 candidate regression proof")
            return {
                "available": True,
                "ok": bool(ok),
                "kind": "declared_component_validator",
                "component": cid,
                "adapter": adapter,
                "output": str(output or ""),
            }
        except Exception as exc:
            return {
                "available": True, "ok": False, "kind": "component_validator_exception",
                "component": cid, "adapter": adapter, "output": str(exc),
            }

    quick = g.get("_v4216_validate_production_component")
    if callable(quick):
        try:
            result = quick(clone, manifest or {}, rel)
            if result is not None:
                return {
                    "available": True, "ok": bool(result[0]), "kind": "production_component_validator",
                    "component": cid, "adapter": adapter, "output": str(result[1] or ""),
                }
        except Exception as exc:
            return {"available": True, "ok": False, "kind": "production_validator_exception", "output": str(exc)}

    # A declared compiled component with no proof is fail-closed.  That is safer than
    # silently turning a functional improvement into a compiler regression.
    return {
        "available": False, "ok": False, "kind": "component_proof_unavailable",
        "component": cid, "adapter": adapter,
        "output": "No registered candidate component validator was available.",
    }


def _syntax_candidate_error(g: dict, root: Path, manifest: dict, rel: str, content: str) -> str:
    syntax = g.get("_v4216_language_syntax_error")
    if callable(syntax):
        try:
            return str(syntax(root, manifest or {}, rel, content) or "")
        except Exception as exc:
            return "candidate syntax validator failed: " + str(exc)
    content_gate = g.get("_content_validation_error")
    if callable(content_gate):
        try:
            return str(content_gate(rel, content) or "")
        except Exception as exc:
            return "candidate content validator failed: " + str(exc)
    return ""


def _matching_issue_count(rows: Iterable[dict], rel: str, kinds: Iterable[str]) -> int:
    rel = _norm(rel)
    wanted = set(str(x or "") for x in kinds)
    return sum(
        1 for row in rows
        if isinstance(row, dict) and _norm(row.get("file")) == rel and str(row.get("kind") or "") in wanted
    )


def _functional_delta(root: Path, clone: Path, user_request: str, manifest: dict, group: dict) -> dict:
    before = list(v4249.functional_acceptance_issues(root, user_request, manifest or {}) or [])
    after = list(v4249.functional_acceptance_issues(clone, user_request, manifest or {}) or [])
    before_group = _matching_issue_count(before, group.get("file"), group.get("kinds") or [])
    after_group = _matching_issue_count(after, group.get("file"), group.get("kinds") or [])
    return {
        "before_total": len(before), "after_total": len(after),
        "before_group": before_group, "after_group": after_group,
        "improved": bool(before_group > 0 and after_group < before_group),
        "before": before, "after": after,
    }


def _commit_validated_candidate(g: dict, root: Path, rel: str, clone: Path, manifest: dict) -> bool:
    source = clone / rel
    destination = root / rel
    if not source.is_file() or not destination.is_file():
        return False
    try:
        before = destination.read_text(encoding="utf-8", errors="replace")
        content = source.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    if before.strip() == content.strip():
        return False
    checkpoint = g.get("_v36_checkpoint_file")
    if callable(checkpoint):
        try: checkpoint(root, rel, before, "before_v4250_regression_safe_functional_patch")
        except Exception: pass
    tmp = destination.with_name(destination.name + ".jarvis_v4250_tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, destination)
        marker = g.get("_v413_mark_accepted")
        if callable(marker):
            try: marker(root, rel, "v4250_regression_safe_functional_patch")
            except Exception: pass
        delete_draft = g.get("_delete_candidate_draft")
        if callable(delete_draft):
            try: delete_draft(root, rel)
            except Exception: pass
        for key in ("_v36_build_repo_graph", "_v36_build_contract_registry"):
            fn = g.get(key)
            if callable(fn):
                try: fn(root, manifest or {}, write=True)
                except TypeError: pass
                except Exception: pass
        return True
    except Exception:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return False


def _patch_only_repair(g: dict, user_request, manifest, root: Path, group: dict, progress_callback=None) -> Tuple[bool, List[str]]:
    patcher = g.get("_v36_patch_repair_candidate")
    copier = g.get("_copy_project_for_candidate_validation")
    if not callable(patcher) or not callable(copier):
        return False, ["candidate patch/sandbox primitive unavailable"]

    rel = str(group.get("file") or "")
    problems = v4249._functional_patch_problems(root, group)
    request = (
        str(user_request or "")
        + "\n\nV42.50 REGRESSION-SAFE FUNCTIONAL AUTHORITY: the patch remains disposable until the affected component still builds/tests and the targeted functional issue family strictly decreases. Do not trade compiler/build health for a functional score."
    )
    errors: List[str] = []

    for attempt in range(1, v4249.MAX_PATCH_ATTEMPTS_PER_GROUP + 1):
        try:
            candidate, err = patcher(
                request, manifest, root, rel, problems,
                "\n".join(problems), attempt, progress_callback,
            )
        except Exception as exc:
            candidate, err = None, str(exc)
        if not candidate:
            if err: errors.append(str(err)[-1800:])
            continue
        content = str((candidate or {}).get("content") or "")
        if not content:
            errors.append("candidate returned no source content")
            continue
        syntax_error = _syntax_candidate_error(g, root, manifest or {}, rel, content)
        if syntax_error:
            errors.append("syntax gate rejected candidate: " + syntax_error[-1600:])
            continue

        handle = None
        try:
            handle, clone = copier(root)
            clone = Path(clone).resolve()
            target = clone / rel
            if not target.is_file():
                errors.append("candidate sandbox missing target file")
                continue
            target.write_text(content, encoding="utf-8")

            proof = _component_candidate_proof(g, root, clone, manifest or {}, rel, progress_callback)
            if not proof.get("ok"):
                tail = str(proof.get("output") or "")[-2600:]
                errors.append(f"component regression gate rejected candidate ({proof.get('kind')}): {tail}")
                try:
                    g["_append_project_event"](
                        root, "v4250_functional_candidate_compile_rejected",
                        f"V42.50 rejected a functional patch in {rel} because the affected component did not remain build/test green.",
                        file=rel, kinds=list(group.get("kinds") or []), proof_kind=proof.get("kind"),
                        proof_tail=tail, final_acceptance=False,
                    )
                except Exception: pass
                continue

            delta = _functional_delta(root, clone, str(user_request or ""), manifest or {}, group)
            if not delta.get("improved"):
                errors.append(
                    f"functional delta gate rejected candidate: target issue family {delta.get('before_group')} -> {delta.get('after_group')} (whole audit {delta.get('before_total')} -> {delta.get('after_total')})"
                )
                try:
                    g["_append_project_event"](
                        root, "v4250_functional_candidate_no_contract_delta",
                        f"V42.50 rejected a build-green patch in {rel} because it did not reduce the targeted functional contract family.",
                        file=rel, kinds=list(group.get("kinds") or []),
                        before_group=delta.get("before_group"), after_group=delta.get("after_group"),
                        before_total=delta.get("before_total"), after_total=delta.get("after_total"),
                    )
                except Exception: pass
                continue

            if _commit_validated_candidate(g, root, rel, clone, manifest or {}):
                try:
                    g["_append_project_event"](
                        root, "v4250_regression_safe_functional_patch_committed",
                        f"V42.50 promoted {rel} only after the affected component remained green and the targeted functional contract improved {delta.get('before_group')} -> {delta.get('after_group')}.",
                        file=rel, kinds=list(group.get("kinds") or []), proof_kind=proof.get("kind"),
                        before_group=delta.get("before_group"), after_group=delta.get("after_group"),
                        before_total=delta.get("before_total"), after_total=delta.get("after_total"),
                        final_acceptance=False,
                    )
                except Exception: pass
                return True, errors
            errors.append("validated candidate could not be atomically promoted")
        finally:
            if handle is not None:
                try: handle.cleanup()
                except Exception: pass

    return False, errors


def install(g: dict) -> None:
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_append = g["_append_project_event"]
    previous_qwen = g["_qwen_call"]
    previous_generate = g["generate_project_zip"]
    previous_edit = g["analyze_and_edit_project_zip"]

    # Keep the V42.49 planner but replace its candidate promotion primitive.
    v4249.VERSION = VERSION
    v4249.ENGINE = ENGINE
    v4249.STRATEGY_GENERATION = STRATEGY_GENERATION
    v4249._patch_only_repair = lambda gg, req, manifest, root, group, progress_callback=None: _patch_only_repair(
        gg, req, manifest, root, group, progress_callback
    )
    g["JARVIS_REPAIR_STRATEGY_GENERATION"] = STRATEGY_GENERATION

    # Propagate identity into older convergence ledgers so exhausted old strategies
    # can reopen once under this genuinely stronger candidate proof policy.
    try:
        import jarvis_v4240_repair as v4240
        v4240.VERSION = VERSION; v4240.ENGINE = ENGINE
        g["V4240_VERSION"] = VERSION; g["V4240_ENGINE"] = ENGINE
    except Exception: pass
    try:
        import jarvis_v4241_repair as v4241
        v4241.VERSION = VERSION; v4241.ENGINE = ENGINE
        g["V4241_VERSION"] = VERSION; g["V4241_ENGINE"] = ENGINE
    except Exception: pass
    try:
        import jarvis_v4248_repair as v4248
        v4248.VERSION = VERSION; v4248.ENGINE = ENGINE; v4248.STRATEGY_GENERATION = STRATEGY_GENERATION
    except Exception: pass
    try:
        import jarvis_v4247_repair as v4247
        v4247.VERSION = VERSION; v4247.ENGINE = ENGINE; v4247.STRATEGY_GENERATION = STRATEGY_GENERATION
    except Exception: pass
    try:
        import jarvis_v4242_repair as old42
        old42.VERSION = VERSION; old42.ENGINE = ENGINE; old42.STRATEGY_GENERATION = STRATEGY_GENERATION
    except Exception: pass

    def append_event(work, event_type, message, **fields):
        values = dict(fields); values["engine_version"] = "V" + VERSION
        rendered = re.sub(r"\bV42\.49(?:\.0)?\b", "V42.50", str(message or ""))
        return previous_append(work, event_type, rendered, **values)

    def progress(callback, text=None, **fields):
        rendered = re.sub(r"\bV42\.49(?:\.0)?\b", "V42.50", str(text or ""))
        values = dict(fields); values["engine_version"] = "V" + VERSION
        return previous_progress(callback, rendered, **values)

    def repair_round(user_request, manifest, work, audit_payload, progress_callback=None, round_no=1):
        root = Path(work).resolve()
        rows = [x for x in (audit_payload or {}).get("issues") or [] if isinstance(x, dict)]
        blockers = [x for x in rows if _is_component_blocker(x)]
        if blockers:
            # Compiler/build health is lexicographically prior to functional debt.
            # Route the exact authoritative failure to the mature component repair
            # controller and do not spend functional patch budget until it is green.
            controller = g.get("_v4237_repair_component_failure")
            for row in blockers[:4]:
                failure = str(row.get("problem") or "")
                if not failure:
                    continue
                progress(
                    progress_callback,
                    f"V42.50 compiler/build regression first: {row.get('file') or row.get('component') or 'component'}",
                    stage="V42.50 regression-safe component recovery", percent=84,
                    current_file=str(row.get("file") or ""),
                )
                try:
                    if callable(controller) and controller(user_request, manifest or {}, root, failure, progress_callback):
                        append_event(
                            root, "v4250_component_regression_repaired",
                            "V42.50 repaired an authoritative compiler/build regression before resuming functional convergence.",
                            file=row.get("file"), kind=row.get("kind"), final_acceptance=False,
                        )
                        return True
                except Exception as exc:
                    append_event(
                        root, "v4250_component_regression_repair_failed",
                        "V42.50 could not repair the authoritative compiler/build regression in this bounded attempt; functional promotion remains blocked.",
                        file=row.get("file"), kind=row.get("kind"), error=str(exc)[-1800:],
                    )
            return False
        return bool(previous_repair_round(user_request, manifest, root, audit_payload, progress_callback, round_no))

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = """

V42.50 REGRESSION-SAFE FUNCTIONAL AUTHORITY:
- A functional improvement may NEVER regress a previously-green compiler/build/test component.
- Candidate source remains disposable until component proof passes and the targeted functional contract family strictly improves.
- Compiler/build regressions outrank functional debt and must be repaired first.
- Do not weaken tests, hide diagnostics, suppress types, or trade runtime correctness for a lower static issue count.
- Preserve the dependency-ordered provider -> integration -> runtime bridge -> workflow-test plan from V42.49.
"""
        stage2 = re.sub(r"\bV42\.49(?:\.0)?\b", "V42.50", str(stage or "Generating"))
        return previous_qwen(str(prompt or "") + authority, progress_callback, stage2, profile=profile, **kwargs)

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "dependency-ordered-regression-safe-functional-convergence-v42.50",
            "repair_strategy_generation": STRATEGY_GENERATION,
            "functional_acceptance_gate": True,
            "compile_success_is_not_project_completion": True,
            "functional_candidate_disposable_until_proven": True,
            "previously_green_component_cannot_regress": True,
            "compiler_build_health_precedes_functional_score": True,
            "target_functional_family_requires_strict_delta": True,
            "component_validation_before_functional_promotion": True,
            "rust_candidate_uses_warm_build_and_test_cache": True,
            "dependency_ordered_functional_convergence_preserved": True,
            "language_framework_toolchain_agnostic": True,
            "stack_specific_contract_adapters_are_optional": True,
        })
        return data

    def guard():
        marker = Path(g["__file__"]).resolve().with_name("JARVIS_ACTIVE_ENGINE.txt")
        try: disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception: disk = ""
        expected = "V" + VERSION
        return (not disk or disk == expected, "" if (not disk or disk == expected) else f"Jarvis engine files identify {disk}, but this running process is {expected}. Fully close and restart Jarvis.")

    def generate(user_request, max_files=None, max_audit_passes=None, progress_callback=None):
        ok, msg = guard()
        if not ok: return False, msg, None
        return previous_generate(user_request, max_files=max_files, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    def edit(user_request, source_zip, max_audit_passes=None, progress_callback=None):
        ok, msg = guard()
        if not ok: return False, msg, None
        return previous_edit(user_request, source_zip, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    g.update({
        "V4250_VERSION": VERSION,
        "V4250_ENGINE": ENGINE,
        "V4250_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "_v4250_is_component_blocker": _is_component_blocker,
        "_v4250_component_candidate_proof": lambda root, clone, manifest, rel, callback=None: _component_candidate_proof(g, Path(root), Path(clone), manifest or {}, rel, callback),
        "_v4250_functional_delta": _functional_delta,
        "_v429_repair_audit_round": repair_round,
        "_qwen_call": qwen_call,
        "_v36_release_identity": identity,
        "_progress": progress,
        "_append_project_event": append_event,
        "_v4250_engine_disk_guard": guard,
        "generate_project_zip": generate,
        "analyze_and_edit_project_zip": edit,
    })
