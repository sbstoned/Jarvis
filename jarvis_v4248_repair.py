"""Jarvis V42.48 bounded functional convergence.

V42.47 correctly made functional behavior a publication requirement, but a real
all-day GearTrack resume exposed two convergence bugs:

1. the functional auditor walked Jarvis-owned backup/checkpoint trees and treated
   historical source snapshots as live application source; and
2. one functional repair round could walk every reported issue, allowing dozens
   of expensive model transactions before the normal no-progress breaker regained
   control.

V42.48 keeps the universal functional-contract gate, but makes its source view and
repair budget revision-scoped.  Only live authored source is audited; related
issues are repaired coherently per live file; failed model attempts are bounded by
an authored-source fingerprint; and build-tool timeouts are treated as validation
infrastructure until concrete compiler/test diagnostics prove a source defect.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List

import jarvis_v4247_repair as v4247
import jarvis_v4242_repair as v4242

VERSION = "42.48.0"
ENGINE = "BOUNDED_FUNCTIONAL_CONVERGENCE_FACTORY"
STRATEGY_GENERATION = "functional-acceptance-v6-live-source-bounded-repair"
LEDGER_FILE = "JARVIS_V4248_FUNCTIONAL_REPAIR_LEDGER.json"

# Every name is lowercase because V42.47's iterator lowercases path parts.
_INTERNAL_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "target", "dist", "build", "coverage",
    ".next", ".nuxt", ".gradle", ".dart_tool", "pods", "deriveddata",
    ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache", ".cache",
    ".jarvis_runtime", ".jarvis_build", ".jarvis_candidates", ".jarvis_backups",
    ".jarvis_failures", ".jarvis_checkpoints",
}

MAX_GROUPS_PER_ROUND = max(1, min(3, int(os.getenv("JARVIS_V4248_FUNCTIONAL_GROUPS_PER_ROUND", "2"))))
MAX_ATTEMPTS_PER_GROUP = max(1, min(3, int(os.getenv("JARVIS_V4248_FUNCTIONAL_ATTEMPTS_PER_GROUP", "2"))))
MAX_ATTEMPTS_PER_REVISION = max(2, min(12, int(os.getenv("JARVIS_V4248_FUNCTIONAL_ATTEMPTS_PER_REVISION", "6"))))
CARGO_BUILD_TIMEOUT = max(240, min(1200, int(os.getenv("JARVIS_V4248_CARGO_BUILD_TIMEOUT", "600"))))
CARGO_FETCH_TIMEOUT = max(180, min(900, int(os.getenv("JARVIS_V4248_CARGO_FETCH_TIMEOUT", "300"))))

# Fix the V42.47 source iterator itself. Its installed audit closure resolves this
# module-global set at call time, so the correction applies to the real publication path.
v4247._SKIP_DIRS.update(_INTERNAL_DIRS)
_PREVIOUS_FUNCTIONAL_ACCEPTANCE = v4247.functional_acceptance_issues


def _norm(rel: object) -> str:
    return str(rel or "").replace("\\", "/").strip("/")


def _is_internal_rel(rel: object) -> bool:
    parts = [p.lower() for p in _norm(rel).split("/") if p]
    return any(p in _INTERNAL_DIRS for p in parts)


def functional_acceptance_issues(work, user_request="", manifest=None) -> List[dict]:
    """Return only live-source functional debt.

    The underlying V42.47 detectors remain adapter-based and universal.  This
    wrapper removes Jarvis-owned evidence/checkpoint trees both before scanning
    (via _SKIP_DIRS above) and after scanning as a fail-safe.
    """
    rows = _PREVIOUS_FUNCTIONAL_ACCEPTANCE(work, user_request, manifest)
    out = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rel = _norm(row.get("file"))
        if not rel or _is_internal_rel(rel):
            continue
        kind = str(row.get("kind") or "functional_contract")
        problem = re.sub(r"\s+", " ", str(row.get("problem") or "")).strip()
        key = (rel, kind, problem)
        if not problem or key in seen:
            continue
        seen.add(key)
        out.append({**row, "file": rel, "kind": kind, "problem": problem})
    return out[:48]


# The V42.47 installed audit function performs a module-global lookup, so replace
# the global detector after preserving the original above.
v4247.functional_acceptance_issues = functional_acceptance_issues


def _live_source_token(work: Path) -> str:
    """Fingerprint authored source only; backup creation cannot reset repair budgets."""
    root = Path(work).resolve()
    rows = []
    for rel, path, _text in v4247._source_files(root):
        if _is_internal_rel(rel):
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:24]
        except Exception:
            continue
        rows.append((rel, digest))
    raw = json.dumps(sorted(rows), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]


def _load_json(path: Path, default=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def _ledger(root: Path, token: str) -> tuple[dict, dict, Path]:
    path = root / LEDGER_FILE
    data = _load_json(path, {})
    if not isinstance(data, dict) or data.get("strategy_generation") != STRATEGY_GENERATION:
        data = {
            "version": "V" + VERSION,
            "engine": ENGINE,
            "strategy_generation": STRATEGY_GENERATION,
            "revisions": {},
        }
    revisions = data.setdefault("revisions", {})
    record = revisions.setdefault(token, {
        "source_token": token,
        "attempts_total": 0,
        "groups": {},
    })
    return data, record, path


def _group_signature(rel: str, rows: Iterable[dict]) -> str:
    payload = {
        "file": rel,
        "issues": sorted((str(x.get("kind") or ""), re.sub(r"\s+", " ", str(x.get("problem") or "")).strip()) for x in rows),
        "strategy": STRATEGY_GENERATION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def _group_functional_rows(rows: Iterable[dict]) -> List[dict]:
    by_file: Dict[str, List[dict]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        if not kind.startswith(("functional_", "persistence_")):
            continue
        rel = _norm(row.get("file"))
        if not rel or _is_internal_rel(rel):
            continue
        by_file.setdefault(rel, []).append(row)

    groups = []
    for rel, items in by_file.items():
        kinds = sorted(set(str(x.get("kind") or "") for x in items))
        problems = []
        for x in items:
            p = re.sub(r"\s+", " ", str(x.get("problem") or "")).strip()
            if p and p not in problems:
                problems.append(p)
        low = "/" + rel.lower()
        is_test = "/tests/" in low or ".test." in low or ".spec." in low
        if any(k in {"functional_bridge", "functional_runtime_state"} for k in kinds):
            tier = 0
        elif any(k.startswith("persistence_") for k in kinds):
            tier = 1
        elif any(k == "functional_mock" for k in kinds):
            tier = 2
        elif is_test or any(k == "functional_test_coverage" for k in kinds):
            tier = 5
        else:
            tier = 3
        groups.append({
            "file": rel,
            "rows": items,
            "kinds": kinds,
            "problems": problems,
            "is_test": is_test,
            "tier": tier,
            "signature": _group_signature(rel, items),
        })
    # Production implementation must become real before tests are rewritten.
    if any(not g["is_test"] for g in groups):
        groups = [g for g in groups if not g["is_test"]]
    return sorted(groups, key=lambda g: (g["tier"], g["file"]))


def _is_validation_timeout_without_source_diagnostic(failure: object) -> bool:
    text = str(failure or "")
    low = text.lower()
    if "timed out after" not in low and "validation timed out" not in low:
        return False
    # Do not suppress a timeout transcript that already contains concrete source evidence.
    concrete = (
        re.search(r"error\[e\d+\]", text, re.I)
        or re.search(r"\bTS\d{4}\b", text)
        or "traceback (most recent call last)" in low
        or "assertionerror" in low
        or "test failures" in low
        or "tests failed" in low
        or re.search(r"\berror:\s+(?!could not compile due to signal)", low)
    )
    return not bool(concrete)


def _cargo_action(cmd) -> str:
    if isinstance(cmd, str):
        parts = re.findall(r'"[^"]*"|\S+', cmd)
    else:
        try:
            parts = [str(x) for x in cmd]
        except Exception:
            return ""
    if not parts:
        return ""
    exe = Path(parts[0].strip('"')).name.lower()
    if exe not in {"cargo", "cargo.exe"}:
        return ""
    for token in parts[1:]:
        token = token.strip().lower()
        if token and not token.startswith("-"):
            return token
    return ""


def install(g: dict) -> None:
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_run_command = g["_run_command"]
    previous_runtime_repair = g.get("_repair_real_validation_failure")
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_append = g["_append_project_event"]
    previous_generate = g["generate_project_zip"]
    previous_edit = g["analyze_and_edit_project_zip"]

    # Make the previously installed V42.46/V42.47 closures see the new strategy
    # generation.  This legitimately reopens an exhausted unchanged revision once.
    v4247.VERSION = VERSION
    v4247.ENGINE = ENGINE
    v4247.STRATEGY_GENERATION = STRATEGY_GENERATION
    v4242.VERSION = VERSION
    v4242.ENGINE = ENGINE
    v4242.STRATEGY_GENERATION = STRATEGY_GENERATION
    try:
        import jarvis_v4240_repair as v4240
        v4240.VERSION = VERSION
        v4240.ENGINE = ENGINE
    except Exception:
        pass
    g["JARVIS_REPAIR_STRATEGY_GENERATION"] = STRATEGY_GENERATION

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        rendered = re.sub(r"\bV42\.47(?:\.0)?\b", "V42.48", str(message or ""))
        return previous_append(work, event_type, rendered, **values)

    def progress(callback, text=None, **fields):
        rendered = re.sub(r"\bV42\.47(?:\.0)?\b", "V42.48", str(text or ""))
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return previous_progress(callback, rendered, **values)

    def run_command(cmd, cwd, timeout, env=None):
        action = _cargo_action(cmd)
        effective = int(timeout or 0)
        if action in {"build", "test"}:
            effective = max(effective, CARGO_BUILD_TIMEOUT)
        elif action in {"fetch", "check"}:
            effective = max(effective, CARGO_FETCH_TIMEOUT)
        return previous_run_command(cmd, cwd, effective, env=env)

    def runtime_repair(user_request, manifest, work, failure, progress_callback=None):
        if _is_validation_timeout_without_source_diagnostic(failure):
            append_event(
                work,
                "v4248_validation_timeout_not_source_repair",
                "V42.48 classified a build/test timeout without concrete compiler/test diagnostics as validation infrastructure, so Qwen will not rewrite source merely to cure elapsed time.",
                failure_tail=str(failure or "")[-2400:],
            )
            return False
        if previous_runtime_repair is None:
            return False
        return previous_runtime_repair(user_request, manifest, work, failure, progress_callback)

    def repair_round(user_request, manifest, work, audit_payload, progress_callback=None, round_no=1):
        root = Path(work).resolve()
        rows = [x for x in (audit_payload or {}).get("issues") or [] if isinstance(x, dict)]
        groups = _group_functional_rows(rows)
        if not groups:
            return bool(previous_repair_round(user_request, manifest, work, audit_payload, progress_callback, round_no))

        token = _live_source_token(root)
        data, revision, ledger_path = _ledger(root, token)
        eligible = []
        for group in groups:
            state = revision.setdefault("groups", {}).setdefault(group["signature"], {
                "file": group["file"], "kinds": group["kinds"], "attempts": 0,
            })
            if int(state.get("attempts") or 0) >= MAX_ATTEMPTS_PER_GROUP:
                continue
            eligible.append((group, state))

        remaining_total = MAX_ATTEMPTS_PER_REVISION - int(revision.get("attempts_total") or 0)
        if remaining_total <= 0 or not eligible:
            revision["exhausted"] = True
            revision["last_result"] = "bounded_no_progress"
            _save_json(ledger_path, data)
            append_event(
                root,
                "v4248_functional_revision_budget_exhausted",
                "V42.48 stopped model-backed functional edits for this unchanged live-source revision. The outer convergence controller can now checkpoint instead of spending hours retrying the same source.",
                repository_token=token,
                attempts_total=revision.get("attempts_total"),
                groups=[{"file": g["file"], "kinds": g["kinds"]} for g in groups[:12]],
            )
            return False

        attempts_this_round = 0
        for group, state in eligible:
            if attempts_this_round >= MAX_GROUPS_PER_ROUND or remaining_total <= 0:
                break
            rel = group["file"]
            target = root / rel
            if not target.is_file() or _is_internal_rel(rel):
                continue
            state["attempts"] = int(state.get("attempts") or 0) + 1
            revision["attempts_total"] = int(revision.get("attempts_total") or 0) + 1
            revision["last_file"] = rel
            revision["last_round"] = int(round_no or 0)
            attempts_this_round += 1
            remaining_total -= 1
            _save_json(ledger_path, data)

            progress(
                progress_callback,
                f"V42.48 bounded functional repair {attempts_this_round}/{MAX_GROUPS_PER_ROUND}: {rel}",
                stage="V42.48 functional convergence",
                percent=91,
                current_file=rel,
            )
            append_event(
                root,
                "v4248_functional_group_attempt",
                f"V42.48 is repairing all related functional contracts in {rel} as one coherent transaction.",
                file=rel,
                kinds=group["kinds"],
                group_attempt=state["attempts"],
                revision_attempts=revision["attempts_total"],
                repository_token=token,
            )
            try:
                changed = bool(g["_repair_file_for_issues"](
                    user_request,
                    manifest,
                    work,
                    rel,
                    group["problems"],
                    progress_callback,
                    validation_failure="\n".join(group["problems"]),
                ))
            except Exception as exc:
                changed = False
                state["last_error"] = str(exc)[:1200]
            state["last_changed"] = bool(changed)
            _save_json(ledger_path, data)
            if changed:
                state["accepted"] = True
                revision["last_result"] = "accepted_source_change"
                _save_json(ledger_path, data)
                after_token = _live_source_token(root)
                append_event(
                    root,
                    "v4248_functional_repair_accepted",
                    f"V42.48 accepted one coherent functional-contract repair in {rel}; rebuild/test/audit is required before another edit.",
                    file=rel,
                    kinds=group["kinds"],
                    before_repository_token=token,
                    after_repository_token=after_token,
                    round=round_no,
                )
                return True

        revision["last_result"] = "bounded_round_no_change"
        _save_json(ledger_path, data)
        append_event(
            root,
            "v4248_functional_round_no_change",
            "V42.48 finished the bounded functional attempts for this round with no accepted live-source change. It will not fall through into an unbounded legacy per-issue model sweep.",
            repository_token=token,
            attempts_this_round=attempts_this_round,
            attempts_total=revision.get("attempts_total"),
        )
        # Critical V42.48 behavior: while concrete functional debt exists, do not
        # invoke the inherited per-issue fallback, which was the all-day loop.
        return False

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "bounded-live-source-functional-convergence-v42.48",
            "repair_strategy_generation": STRATEGY_GENERATION,
            "functional_acceptance_gate": True,
            "compile_success_is_not_project_completion": True,
            "jarvis_internal_trees_excluded_from_functional_audit": True,
            "functional_issue_grouping_by_live_file": True,
            "functional_model_attempts_revision_scoped": True,
            "functional_groups_per_round": MAX_GROUPS_PER_ROUND,
            "functional_attempts_per_group": MAX_ATTEMPTS_PER_GROUP,
            "functional_attempts_per_revision": MAX_ATTEMPTS_PER_REVISION,
            "functional_no_progress_returns_to_outer_circuit_breaker": True,
            "build_timeout_without_diagnostics_is_not_source_repair": True,
            "cargo_build_timeout_seconds": CARGO_BUILD_TIMEOUT,
            "cargo_fetch_timeout_seconds": CARGO_FETCH_TIMEOUT,
            "language_framework_toolchain_agnostic": True,
        })
        return data

    def guard():
        marker = Path(g["__file__"]).resolve().with_name("JARVIS_ACTIVE_ENGINE.txt")
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
        expected = "V" + VERSION
        return (not disk or disk == expected, "" if (not disk or disk == expected) else f"Jarvis engine files identify {disk}, but this running process is {expected}. Fully close and restart Jarvis.")

    def generate(user_request, max_files=None, max_audit_passes=None, progress_callback=None):
        ok, msg = guard()
        if not ok:
            return False, msg, None
        return previous_generate(user_request, max_files=max_files, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    def edit(user_request, source_zip, max_audit_passes=None, progress_callback=None):
        ok, msg = guard()
        if not ok:
            return False, msg, None
        return previous_edit(user_request, source_zip, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    g.update({
        "V4248_VERSION": VERSION,
        "V4248_ENGINE": ENGINE,
        "V4248_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "_v4247_functional_acceptance_issues": functional_acceptance_issues,
        "_v4248_functional_acceptance_issues": functional_acceptance_issues,
        "_v4248_live_source_token": _live_source_token,
        "_v429_repair_audit_round": repair_round,
        "_run_command": run_command,
        "_v36_release_identity": identity,
        "_progress": progress,
        "_append_project_event": append_event,
        "_v4248_engine_disk_guard": guard,
        "generate_project_zip": generate,
        "analyze_and_edit_project_zip": edit,
    })
    if previous_runtime_repair is not None:
        g["_repair_real_validation_failure"] = runtime_repair
