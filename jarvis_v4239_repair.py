"""V42.39 deterministic-first native convergence and terminal transport halt.

V42.38 correctly reconstructed component-scoped model transport history, but it
filtered exhausted targets before its deterministic compiler repair stage.  A
resumed component with useful rustc suggestions was therefore blocked without
ever trying those zero-model edits.  The enclosing whole-project loop could
then continue into a specialist audit even though the component was explicitly
transport-blocked.

This install layer makes deterministic evidence independent of model budgets,
validates combined and isolated compiler-derived candidates transactionally,
and makes an unchanged transport block terminal when it is the only remaining
audit problem.  Generic component metadata and validator output remain the
authority; Rust is one narrow evidence adapter, not a project-specific patch.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import jarvis_v4236_repair as v4236
import jarvis_v4237_repair as v4237
import jarvis_v4238_repair as v4238


VERSION = "42.39.0"
ENGINE = "DETERMINISTIC_FIRST_TERMINAL_CONVERGENCE_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
STATE_FILE = "JARVIS_V4239_DETERMINISTIC_STATE.json"
HALT_FILE = "JARVIS_V4239_CONVERGENCE_HALT.json"
BUNDLE_FILE = "JARVIS_V4239_DETERMINISTIC_BUNDLE.json"
MEMORY_FILE = "JARVIS_V4239_PROJECT_REPAIR_MEMORY.json"
TRACE_FILE = "JARVIS_V4239_FULL_PASS_TRACE.jsonl"
REPORT_FILE = "JARVIS_V4239_FAILURE_REPORT.md"

_BASE_V4238_MODEL_PROMPT = v4238._model_patch_prompt


def _context(g: dict, manifest: dict, work: Path, failure: str):
    component = v4237.component_from_failure(manifest, failure)
    if not component:
        return None
    cid, component_root, adapter = v4237._component_identity(component)
    if adapter in v4237._NODE_ADAPTERS:
        return None
    try:
        rows = list(g["_v4236_native_diagnostics"](work, manifest, failure) or [])
        targets = list(g["_v4236_rank_native_targets"](rows, failure) or [])
    except Exception:
        rows, targets = [], []
    targets = [
        rel for rel in targets
        if v4237._component_identity(v4237._component_for_rel(manifest, rel))[0] == cid
    ]
    if not targets:
        return None
    before = v4237.diagnostic_count(failure)
    if before <= 0:
        try:
            before = int(g.get("_v4236_native_error_count", lambda value: 0)(failure) or 0)
        except Exception:
            before = 0
    signature = v4237._failure_signature(component, rows, failure)
    token = v4238._component_source_token(work, manifest, component)
    return component, cid, component_root, adapter, rows, targets, before, signature, token


def _error_count(g: dict, output: str) -> int:
    count = v4237.diagnostic_count(output)
    if count <= 0:
        try:
            count = int(g.get("_v4236_native_error_count", lambda value: 0)(output) or 0)
        except Exception:
            count = 0
    return count


def _state_key(cid: str, token: str, signature: str) -> str:
    return hashlib.sha256(f"{cid}|{token}|{signature}".encode("utf-8")).hexdigest()[:24]


def _commit(g: dict, work: Path, clone: Path, files: list[str], before: int, after: int, component: dict, reasons: list[str]) -> tuple[bool, str]:
    originals: dict[str, bytes] = {}
    temporaries: list[Path] = []
    try:
        for rel in files:
            source = clone / rel
            destination = work / rel
            if not source.is_file() or source.suffix.lower() not in v4237._SOURCE_SUFFIXES:
                return False, f"unsafe deterministic transaction member: {rel}"
            if not destination.resolve(strict=False).is_relative_to(work.resolve()):
                return False, f"deterministic transaction escapes project: {rel}"
            originals[rel] = destination.read_bytes()
            try:
                g["_v36_checkpoint_file"](
                    work, rel, originals[rel].decode("utf-8", errors="replace"),
                    "before_v4239_deterministic_transaction",
                )
            except Exception:
                pass
            temporary = destination.with_name(destination.name + ".v4239.tmp")
            temporary.write_bytes(source.read_bytes())
            temporaries.append(temporary)
        for rel, temporary in zip(files, temporaries):
            os.replace(temporary, work / rel)
        for rel in files:
            try:
                g["_v413_mark_accepted"](work, rel, "v4239_deterministic_compiler_delta")
            except Exception:
                pass
        cid, component_root, adapter = v4237._component_identity(component)
        g["_append_project_event"](
            work, "v4239_deterministic_component_committed",
            f"V42.39 promoted {len(files)} compiler-derived {cid} edit(s); isolated diagnostics decreased {before} -> {after} before any model-budget decision.",
            component=cid, component_root=component_root, adapter=adapter,
            files=files, before=before, after=after, reasons=sorted(set(reasons)),
        )
        return True, ""
    except Exception as exc:
        for rel, content in originals.items():
            try:
                (work / rel).write_bytes(content)
            except Exception:
                pass
        return False, str(exc)
    finally:
        for temporary in temporaries:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass


def _source_candidates(work: Path, targets: list[str], failure: str):
    changed: dict[str, tuple[str, list[str]]] = {}
    for rel in targets:
        try:
            source = (work / rel).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        candidate, reasons = v4238._deterministic_candidate(source, failure, rel)
        if candidate != source and reasons:
            changed[rel] = (candidate, reasons)
    return changed


def deterministic_preflight(g: dict, user_request: object, manifest: dict | None, work: Path | str, failure: object, progress_callback=None) -> bool:
    """Try compiler-derived edits even when every model target is exhausted."""
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    text = str(failure or "")
    context = _context(g, manifest, root, text)
    if not context:
        return False
    component, cid, component_root, adapter, _rows, targets, before, signature, token = context
    changes = _source_candidates(root, targets, text)
    if not changes:
        return False

    state_path = root / STATE_FILE
    state = v4237._load(state_path, {"attempts": {}})
    attempts = state.setdefault("attempts", {})
    key = _state_key(cid, token, signature)
    prior = attempts.get(key) if isinstance(attempts.get(key), dict) else {}
    candidate_fingerprint = hashlib.sha256(json.dumps(
        {rel: hashlib.sha256(value[0].encode("utf-8")).hexdigest() for rel, value in changes.items()},
        sort_keys=True,
    ).encode("utf-8")).hexdigest()[:24]
    if prior.get("candidate_fingerprint") == candidate_fingerprint and prior.get("result") in {
        "bounded_no_delta", "safety_rejected", "commit_failed",
    }:
        return False

    variants = [list(changes)]
    if len(changes) > 1:
        variants.extend([[rel] for rel in changes])
    v4237._save(root / BUNDLE_FILE, {
        "version": "V" + VERSION, "engine": ENGINE,
        "component": {"id": cid, "root": component_root, "adapter": adapter},
        "component_source_token": token, "failure_signature": signature,
        "diagnostic_count": before, "diagnostic_targets": targets,
        "deterministic_targets": list(changes), "candidate_fingerprint": candidate_fingerprint,
        "policy": "compiler-derived candidates execute before model budgets; promote only on exact-component strict diagnostic decrease",
    })
    g["_append_project_event"](
        root, "v4239_deterministic_preflight_started",
        f"V42.39 found compiler-derived edits for {cid} and is validating them before consulting model transport state.",
        component=cid, component_root=component_root, files=list(changes),
        component_token=token, diagnostic_count=before,
    )
    g["_progress"](
        progress_callback,
        f"V42.39 deterministic-first repair: validating {len(changes)} compiler-proven {cid} target(s) before model eligibility.",
        stage="V42.39 deterministic compiler transaction", percent=82,
        component=cid, current_file=next(iter(changes)),
    )

    results = []
    for variant in variants:
        temp_handle = None
        try:
            temp_handle, clone = g["_copy_project_for_candidate_validation"](root)
            clone = Path(clone).resolve()
            staged = []
            reasons = []
            for rel in variant:
                candidate, why = changes[rel]
                safety = v4237._candidate_safety(g, clone, manifest, rel, candidate, text)
                if safety:
                    results.append({"files": variant, "result": "safety_rejected", "detail": safety[-1000:]})
                    staged = []
                    break
                (clone / rel).write_text(candidate, encoding="utf-8")
                staged.append(rel)
                reasons.extend(why)
            if not staged:
                continue
            valid, replay = g["_v35_validate_component"](clone, manifest, component, str(user_request or ""))
            replay = str(replay or "")
            after = 0 if valid else _error_count(g, replay)
            improved = bool(valid or (before > 0 and after > 0 and after < before))
            results.append({
                "files": list(staged), "result": "improved" if improved else "no_delta",
                "validator_ok": bool(valid), "before": before, "after": after,
                "reasons": sorted(set(reasons)), "output": replay[-2500:],
            })
            if not improved:
                continue
            changed = v4237._diff_selected(root, clone, staged)
            committed, reason = _commit(g, root, clone, changed, before, after, component, reasons)
            attempts[key] = {
                "component": cid, "component_token": token, "failure_signature": signature,
                "candidate_fingerprint": candidate_fingerprint,
                "result": "committed" if committed else "commit_failed",
                "files": changed, "before": before, "after": after,
                "last_error": reason[-1200:], "at": g["_utc_stamp"](), "trials": results,
            }
            v4237._save(state_path, state)
            return bool(committed)
        except Exception as exc:
            results.append({"files": variant, "result": "sandbox_failure", "detail": str(exc)[-1200:]})
        finally:
            v4237._cleanup_temp(temp_handle)

    attempts[key] = {
        "component": cid, "component_token": token, "failure_signature": signature,
        "candidate_fingerprint": candidate_fingerprint, "result": "bounded_no_delta",
        "at": g["_utc_stamp"](), "trials": results,
    }
    v4237._save(state_path, state)
    g["_append_project_event"](
        root, "v4239_deterministic_preflight_no_delta",
        f"V42.39 tested compiler-derived {cid} candidates before model eligibility, but none reduced exact-component diagnostics.",
        component=cid, files=list(changes), diagnostic_count=before,
    )
    return False


def repair_component_failure(g: dict, user_request: object, manifest: dict | None, work: Path | str, failure: object, progress_callback=None) -> bool:
    if deterministic_preflight(g, user_request, manifest, work, failure, progress_callback):
        return True
    return bool(v4238.repair_component_failure(g, user_request, manifest, work, failure, progress_callback))


def _manifest_component(manifest: dict, cid: str, component_root: str):
    for row in manifest.get("components") or []:
        if not isinstance(row, dict):
            continue
        rid, rroot, _adapter = v4237._component_identity(row)
        if rid == cid or rroot == component_root:
            return row
    return None


def active_transport_block(work: Path | str, manifest: dict | None):
    """Return only a block that still matches the component's current source."""
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    state = v4237._load(root / v4238.STATE_FILE, {})
    for entry in (state.get("failures") or {}).values():
        if not isinstance(entry, dict):
            continue
        if not entry.get("blocked_until_component_source_changes") and entry.get("result") != "transport_exhausted":
            continue
        cid = str(entry.get("component") or "")
        component_root = v4237._norm(entry.get("component_root") or ".")
        component = _manifest_component(manifest, cid, component_root)
        if not component:
            continue
        current = v4238._component_source_token(root, manifest, component)
        blocked = str(entry.get("blocked_component_token") or entry.get("component_token") or "")
        if current == blocked:
            return {
                "component": cid, "component_root": component_root,
                "component_token": current, "entry": entry,
            }
    return None


def _audit_is_only_blocked_component(audit: dict, block: dict, manifest: dict) -> bool:
    issues = [row for row in (audit or {}).get("issues") or [] if isinstance(row, dict)]
    if not issues:
        return False
    wanted = str(block.get("component") or "")
    for row in issues:
        if str(row.get("kind") or "") != "component_validation":
            return False
        cid = str(row.get("component") or "")
        if not cid:
            component = v4237.component_from_failure(manifest, row.get("problem"))
            cid = v4237._component_identity(component)[0] if component else ""
        if cid != wanted:
            return False
    return True


def _record_terminal_halt(g: dict, work: Path, audit: dict, block: dict, progress_callback=None) -> None:
    path = work / HALT_FILE
    old = v4237._load(path, {})
    token = str(block.get("component_token") or "")
    payload = {
        "version": "V" + VERSION, "engine": ENGINE, "status": "MODEL_TRANSPORT_BLOCKED",
        "component": block.get("component"), "component_root": block.get("component_root"),
        "component_source_token": token,
        "message": "Deterministic compiler candidates are exhausted or unavailable, and model transport is exhausted for this unchanged component revision.",
        "action": "Preserve the checkpoint. Restore model responsiveness or make a real source/config change in this component before resuming.",
        "issues": (audit.get("issues") or [])[:20], "updated_at": g["_utc_stamp"](),
    }
    v4237._save(path, payload)
    if old.get("component_source_token") != token or old.get("status") != payload["status"]:
        g["_append_project_event"](
            work, "v4239_transport_terminal_stop",
            f"V42.39 ended convergence because {block.get('component')} is transport-blocked at an unchanged component revision and no deterministic compiler transaction advanced it.",
            component=block.get("component"), component_root=block.get("component_root"),
            component_token=token, status="MODEL_TRANSPORT_BLOCKED",
        )
    g["_progress"](
        progress_callback,
        f"V42.39 stopped cleanly: {block.get('component')} is MODEL_TRANSPORT_BLOCKED at an unchanged source revision. The checkpoint is preserved.",
        stage="V42.39 terminal transport halt", percent=94,
        component=block.get("component"), status="MODEL_TRANSPORT_BLOCKED",
    )


def _issue_signature(row: dict) -> str:
    problem = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(row.get("problem") or ""))
    problem = problem.replace("\\", "/")
    # Normalize compiler line/column locations without touching drive-letter
    # prefixes such as C:\\project.  The numeric lookahead is sufficient.
    problem = re.sub(r":\d+(?::\d+)?(?=[\s)\],]|$)", ":#", problem)
    problem = re.sub(r"\(\d+,\d+\)", "(#,#)", problem)
    problem = re.sub(r"\s+", " ", problem).strip().lower()
    codes = sorted(set(re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", problem, re.I)))
    material = {
        "file": v4237._norm(row.get("file")),
        "kind": str(row.get("kind") or ""),
        "component": str(row.get("component") or ""),
        "codes": [code.upper() for code in codes],
        "problem": problem[:1800],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _redact_log_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\b(\s*[:=]\s*)([^\s,;]+)",
        lambda match: match.group(1) + match.group(2) + "[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", "Bearer [REDACTED]", text)
    return text


def _journal_strategy_tail(work: Path) -> list[dict]:
    try:
        lines = (work / "JARVIS_PROJECT_JOURNAL.jsonl").read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-1000:]
    except Exception:
        return []
    output = []
    for line in lines:
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        kind = str(event.get("type") or "").lower()
        if not any(token in kind for token in (
            "repair", "transport", "committed", "accepted", "no_delta",
            "specialist", "blocked", "terminal_stop", "error_delta",
        )):
            continue
        output.append({
            "time": event.get("time"), "type": event.get("type"),
            "component": event.get("component"), "file": event.get("file"),
            "files": event.get("files"), "before": event.get("before"),
            "after": event.get("after"), "result": event.get("result"),
            "message": str(event.get("message") or "")[:700],
        })
    return output[-80:]


def update_project_repair_memory(g: dict, work: Path | str, user_request: object, manifest: dict | None, audit: dict | None) -> dict:
    """Persist a compact, revision-aware dossier after every full project pass."""
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    audit = audit if isinstance(audit, dict) else {}
    path = root / MEMORY_FILE
    old = v4237._load(path, {})
    now = g["_utc_stamp"]()
    prior = {
        str(row.get("fingerprint")): dict(row)
        for row in old.get("issues") or []
        if isinstance(row, dict) and row.get("fingerprint")
    }
    active_fingerprints = set()
    for row in audit.get("issues") or []:
        if not isinstance(row, dict):
            continue
        fingerprint = _issue_signature(row)
        active_fingerprints.add(fingerprint)
        current = prior.get(fingerprint, {})
        problem = _redact_log_text(row.get("problem"))
        component = str(row.get("component") or "")
        if not component and problem:
            resolved = v4237.component_from_failure(manifest, problem)
            component = v4237._component_identity(resolved)[0] if resolved else ""
        files = []
        if row.get("file"):
            files.append(v4237._norm(row.get("file")))
        files.extend(v4237._norm(value) for value in row.get("diagnostic_files") or [] if value)
        current.update({
            "fingerprint": fingerprint, "status": "active",
            "file": v4237._norm(row.get("file")), "kind": str(row.get("kind") or ""),
            "component": component, "files": list(dict.fromkeys(files)),
            "diagnostic_count": v4237.diagnostic_count(problem),
            "codes": sorted(set(re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", problem, re.I))),
            "summary": re.sub(r"\s+", " ", problem).strip()[:1800],
            "first_seen": current.get("first_seen") or now, "last_seen": now,
            "occurrences": int(current.get("occurrences") or 0) + 1,
        })
        current.pop("resolved_at", None)
        prior[fingerprint] = current
    for fingerprint, row in prior.items():
        if fingerprint in active_fingerprints:
            continue
        if row.get("status") == "active":
            row["status"] = "resolved"
            row["resolved_at"] = now

    components = []
    active_rows = [row for row in prior.values() if row.get("status") == "active"]
    for component in manifest.get("components") or []:
        if not isinstance(component, dict):
            continue
        cid, component_root, adapter = v4237._component_identity(component)
        issues = [row for row in active_rows if row.get("component") == cid]
        components.append({
            "id": cid, "root": component_root, "adapter": adapter,
            "source_token": v4238._component_source_token(root, manifest, component),
            "status": "failing" if issues else "green_or_unmeasured",
            "active_issue_count": len(issues),
            "diagnostic_count": max([int(row.get("diagnostic_count") or 0) for row in issues] + [0]),
            "files": list(dict.fromkeys(value for row in issues for value in row.get("files") or []))[:30],
            "build_command": component.get("build_command"),
            "test_command": component.get("test_command"),
        })
    active_signature = hashlib.sha256(json.dumps(sorted(active_fingerprints)).encode("utf-8")).hexdigest()[:24]
    projection = v4237._load(root / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json"), {})
    payload = {
        "version": "V" + VERSION, "engine": ENGINE, "updated_at": now,
        "original_request": str(manifest.get("_original_user_request") or user_request or "")[:4000],
        "full_pass_clean": bool(audit.get("clean")),
        "active_issue_fingerprint": active_signature,
        "active_issue_count": len(active_fingerprints),
        "components": components,
        "issues": sorted(prior.values(), key=lambda row: (row.get("status") != "active", str(row.get("component") or ""), str(row.get("file") or "")))[:500],
        "last_accepted_event": projection.get("last_accepted_event") if isinstance(projection, dict) else None,
        "strategy_history": _journal_strategy_tail(root),
        "transport_state": v4237._load(root / v4238.STATE_FILE, {}),
        "deterministic_state": v4237._load(root / STATE_FILE, {}),
        "policy": "whole-pass evidence -> stable issue memory -> deterministic repair -> isolated transaction -> strict validator delta -> accepted/resolved history",
    }
    v4237._save(path, payload)
    if old.get("active_issue_fingerprint") != active_signature or old.get("full_pass_clean") != payload["full_pass_clean"]:
        g["_append_project_event"](
            root, "v4239_project_repair_memory_updated",
            f"V42.39 persisted a full-pass repair dossier with {len(active_fingerprints)} active issue fingerprint(s) across {len(components)} component(s).",
            active_issue_count=len(active_fingerprints),
            active_issue_fingerprint=active_signature,
            components=[row["id"] for row in components],
        )
    return payload


def _observability_component(manifest: dict, row: dict) -> dict:
    wanted = str(row.get("component") or "")
    problem = str(row.get("problem") or "")
    component = None
    if wanted:
        component = next((value for value in manifest.get("components") or [] if isinstance(value, dict) and v4237._component_identity(value)[0] == wanted), None)
    component = component or v4237.component_from_failure(manifest, problem) or {}
    cid, component_root, adapter = v4237._component_identity(component)
    return {
        "id": cid or wanted or "unknown", "root": component_root,
        "adapter": adapter or "unknown",
        "build_command": component.get("build_command") or manifest.get("build_command"),
        "test_command": component.get("test_command") or manifest.get("test_command"),
    }


def _failure_explanation(problem: str, kind: str, blocked: bool) -> tuple[str, str]:
    low = problem.lower()
    if blocked:
        return (
            "The component still fails at the same authored source revision. Exact compiler-derived candidates could not advance it, and every bounded local-model transport attempt returned no usable response.",
            "Restore the configured local model service, or make a real source/configuration change in this component and resume the saved checkpoint. Jarvis will re-audit the new component revision before spending another model attempt.",
        )
    if "no space left" in low or "enospc" in low or "disk" in low and "full" in low:
        return "The validator could not complete because its build storage is unavailable or full.", "Free build/cache storage, then resume. Source repair must wait for a trustworthy validator result."
    if "not found" in low and any(token in low for token in ("command", "executable", "toolchain", "compiler")):
        return "A required build/test executable is unavailable, so this is an environment blocker rather than proven source damage.", "Install or configure the named tool, restart Jarvis so capability discovery refreshes, and resume the checkpoint."
    if re.search(r"\b(?:e0308|ts2322|ts2345|cs0029)\b", low):
        return "The compiler reports an incompatible value or argument type at the listed source location.", "Apply the smallest type-correct source change supported by the current declaration and rerun this component's validator."
    if re.search(r"\b(?:e0277|trait bound|interface.*not satisfied)\b", low):
        return "A required trait/interface contract is not implemented or derived for the reported type.", "Repair the reported type contract, then rerun the exact component validator; promotion requires fewer diagnostics or a clean pass."
    if re.search(r"\b(?:e0425|e0432|e0433|ts2304|ts2307|cannot find|unresolved import)\b", low):
        return "The compiler cannot resolve a referenced symbol, module, or import from the current component graph.", "Repair the owning declaration/import or dependency manifest, then rerun the exact component validator."
    if "test" in kind.lower() or "test failed" in low:
        return "A real test command failed; the failing assertion/output below is the acceptance evidence.", "Repair production behavior first unless the test itself contradicts the original requirement, then rerun the declared test command."
    if kind == "component_validation":
        return "The component's real build/test validator returned the diagnostics below.", "Use the reported files and codes as the repair targets. Revalidate in this component root and accept only a strict diagnostic reduction or clean pass."
    return "The full-project audit reports an unresolved acceptance or structural issue.", "Resolve the recorded issue against the original request, then repeat the full project audit before publication."


def write_failure_observability(g: dict, work: Path | str, manifest: dict | None, audit: dict | None, memory: dict | None = None) -> dict:
    """Write an exact machine trace plus a concise human recovery report."""
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    audit = audit if isinstance(audit, dict) else {}
    memory = memory if isinstance(memory, dict) else v4237._load(root / MEMORY_FILE, {})
    block = active_transport_block(root, manifest)
    entries = []
    for ordinal, row in enumerate(audit.get("issues") or [], 1):
        if not isinstance(row, dict):
            continue
        problem = _redact_log_text(row.get("problem"))[-12000:]
        component = _observability_component(manifest, row)
        blocked = bool(block and component["id"] == block.get("component"))
        why, action = _failure_explanation(problem, str(row.get("kind") or ""), blocked)
        files = []
        if row.get("file"):
            files.append(v4237._norm(row.get("file")))
        files.extend(v4237._norm(value) for value in row.get("diagnostic_files") or [] if value)
        files.extend(re.findall(r"(?:-->|at)\s+([^\s:]+\.[A-Za-z0-9]+)(?::\d+)?", problem))
        entries.append({
            "ordinal": ordinal, "fingerprint": _issue_signature(row),
            "kind": str(row.get("kind") or "unknown"), "component": component,
            "files": list(dict.fromkeys(files))[:40],
            "codes": sorted(set(code.upper() for code in re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", problem, re.I))),
            "diagnostic_count": v4237.diagnostic_count(problem),
            "repair_state": "MODEL_TRANSPORT_BLOCKED" if blocked else "ACTIONABLE_OR_PENDING_REPAIR",
            "why": why, "next_action": action, "validator_evidence": problem,
        })
    status = "CLEAN" if audit.get("clean") else ("MODEL_TRANSPORT_BLOCKED" if block else "FAILED_REPAIRABLE_OR_UNCLASSIFIED")
    trace = {
        "version": "V" + VERSION, "engine": ENGINE, "time": g["_utc_stamp"](),
        "status": status, "clean": bool(audit.get("clean")),
        "active_issue_fingerprint": memory.get("active_issue_fingerprint"),
        "component_source_tokens": {row.get("id"): row.get("source_token") for row in memory.get("components") or [] if isinstance(row, dict)},
        "terminal_block": block,
        "failures": entries,
        "recent_repair_decisions": _journal_strategy_tail(root)[-40:],
        "artifacts": {
            "human_report": REPORT_FILE, "full_pass_trace": TRACE_FILE,
            "repair_memory": MEMORY_FILE, "event_journal": "JARVIS_PROJECT_JOURNAL.jsonl",
            "whole_project_audit": g.get("V429_AUDIT_FILE", "JARVIS_V429_WHOLE_PROJECT_AUDIT.json"),
        },
        "privacy": "Provider prompts, responses, environment values, and recognized credentials are not recorded here.",
    }
    with (root / TRACE_FILE).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")

    lines = [
        "# Jarvis V42.39 Failure Report", "", f"Updated: {trace['time']}", f"Status: **{status}**", "",
        "This report is regenerated after every complete component audit. The JSONL trace retains the pass-by-pass evidence.", "",
    ]
    if not entries:
        lines.extend(["## Result", "", "All issues reported by the latest full-project audit are clear. Final publication still depends on the normal build, test, runtime, integration, and original-requirement gates.", ""])
    for entry in entries:
        component = entry["component"]
        lines.extend([
            f"## Failure {entry['ordinal']}: {component['id']} / {entry['kind']}", "",
            f"- State: `{entry['repair_state']}`",
            f"- Component root (validator cwd): `{component['root']}`",
            f"- Adapter: `{component['adapter']}`",
            f"- Build command: `{component.get('build_command') or 'not declared'}`",
            f"- Test command: `{component.get('test_command') or 'not declared'}`",
            f"- Diagnostic count: `{entry['diagnostic_count']}`",
            f"- Codes: `{', '.join(entry['codes']) or 'not parsed'}`",
            f"- Files: `{', '.join(entry['files']) or 'not parsed'}`", "",
            "Why it is failing:", "", entry["why"], "",
            "What is needed next:", "", entry["next_action"], "",
            "Validator evidence:", "", "```text", entry["validator_evidence"].replace("```", "` ` `"), "```", "",
        ])
    decisions = trace["recent_repair_decisions"][-12:]
    lines.extend(["## Recent repair decisions", ""])
    if decisions:
        for row in decisions:
            lines.append(f"- `{row.get('time') or '?'}` `{row.get('type') or '?'}` — {_redact_log_text(row.get('message'))}")
    else:
        lines.append("No repair decision events have been recorded yet.")
    lines.extend(["", "## Related evidence files", "", f"- `{TRACE_FILE}` — append-only full-pass evidence", f"- `{MEMORY_FILE}` — active and resolved issue memory", "- `JARVIS_PROJECT_JOURNAL.jsonl` — repair/acceptance event stream", f"- `{trace['artifacts']['whole_project_audit']}` — latest consolidated audit", ""])
    (root / REPORT_FILE).write_text("\n".join(lines), encoding="utf-8")
    return trace


def _repair_memory_context(work: Path, component: dict, target: str) -> str:
    memory = v4237._load(work / MEMORY_FILE, {})
    if not memory:
        return ""
    cid, _component_root, _adapter = v4237._component_identity(component)
    issues = [
        {
            "fingerprint": row.get("fingerprint"), "file": row.get("file"),
            "count": row.get("diagnostic_count"), "codes": row.get("codes"),
            "occurrences": row.get("occurrences"), "summary": str(row.get("summary") or "")[:550],
        }
        for row in memory.get("issues") or []
        if isinstance(row, dict) and row.get("status") == "active"
        and (row.get("component") == cid or target in (row.get("files") or []))
    ][:4]
    transport = []
    for entry in (memory.get("transport_state", {}).get("failures") or {}).values():
        if isinstance(entry, dict) and entry.get("component") == cid:
            transport.append({
                "result": entry.get("result"),
                "counts": entry.get("transport_failures"),
                "semantic_no_delta": entry.get("semantic_no_delta"),
            })
    attempts = []
    for entry in (memory.get("deterministic_state", {}).get("attempts") or {}).values():
        if isinstance(entry, dict) and entry.get("component") == cid:
            attempts.append({
                "result": entry.get("result"), "files": entry.get("files"),
                "before": entry.get("before"), "after": entry.get("after"),
                "candidate_fingerprint": entry.get("candidate_fingerprint"),
            })
    context = {
        "component": cid, "target": target,
        "component_source_token": next((row.get("source_token") for row in memory.get("components") or [] if row.get("id") == cid), None),
        "active_issues": issues, "prior_deterministic_attempts": attempts[-6:],
        "model_transport_history": transport[-3:],
        "last_accepted_event": memory.get("last_accepted_event"),
    }
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:1900]


def _memory_aware_model_prompt(g: dict, work: Path, manifest: dict, component: dict, target: str, connected: list[str], failure: str) -> str:
    base = _BASE_V4238_MODEL_PROMPT(g, work, manifest, component, target, connected, failure)
    memory = _repair_memory_context(Path(work), component, target)
    if not memory:
        return base
    marker = "CURRENT SOURCE:"
    index = base.find(marker)
    if index < 0:
        return (base[:7900] + "\n\nDURABLE PROJECT REPAIR MEMORY:\n" + memory)[:10000]
    head = base[:index][:3400]
    tail = base[index:][:4600]
    instruction = (
        "\n\nDURABLE PROJECT REPAIR MEMORY:\n" + memory +
        "\nUse this only to avoid repeating rejected strategies and to preserve accepted contracts. Current compiler evidence and exact source remain authoritative.\n\n"
    )
    return (head + instruction + tail)[:10000]


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_real_repair = g["_repair_real_validation_failure"]
    previous_convergence = g["_v429_whole_project_convergence"]
    previous_whole_audit = g["_v429_whole_project_audit"]
    previous_specialist = g["_v429_specialist_whole_audit"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_qwen = g["_qwen_call"]
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])
    durable_append = g.get("_v4235_durable_append_project_event", g["_append_project_event"])
    base_progress = g.get("_v4235_base_progress", g["_progress"])

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        event = durable_append(work, event_type, message, **values)
        try:
            projection = Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            data = v4237._load(projection, {})
            if isinstance(data, dict):
                data.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
                event_key = str(event_type or "").strip().lower()
                if any(token in event_key for token in (
                    "whole_project_green", "final_acceptance_passed",
                    "project_complete", "publication_accepted",
                )):
                    data.pop("current_blocker", None)
                    data["fresh_validation_required"] = False
                    data["last_fully_verified_event"] = {
                        "type": event_key, "at": g["_utc_stamp"](),
                    }
                v4237._save(projection, data)
            # Accepted source changes require fresh validation. Fully-green
            # events above must remain authoritative and are never invalidated.
            if not any(token in str(event_type or "").lower() for token in (
                "whole_project_green", "final_acceptance_passed",
                "project_complete", "publication_accepted",
            )):
                v4236._component_aware_invalidate(g, work, event_type, values)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        value = re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.39", str(text or ""))
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return base_progress(callback, value, **values)

    def repair_round(user_request, manifest, work, audit, progress_callback=None, round_no=1):
        issues = [row for row in (audit or {}).get("issues") or [] if isinstance(row, dict)]
        for row in issues:
            if v4237.repair_dependency_alias(g, work, manifest, row.get("problem"), progress_callback):
                return True
        for row in issues:
            failure = str(row.get("problem") or "")
            try:
                native = bool(g["_v4236_is_native_compiler_failure"](work, manifest, failure))
            except Exception:
                native = False
            if native:
                return repair_component_failure(g, user_request, manifest, work, failure, progress_callback)
        return bool(previous_repair_round(user_request, manifest, work, audit, progress_callback, round_no))

    def real_repair(user_request, manifest, work, failure, progress_callback=None):
        if v4237.repair_dependency_alias(g, work, manifest, failure, progress_callback):
            return True
        try:
            if g["_v4236_is_native_compiler_failure"](work, manifest, failure):
                return repair_component_failure(g, user_request, manifest, work, failure, progress_callback)
        except Exception:
            pass
        return bool(previous_real_repair(user_request, manifest, work, failure, progress_callback))

    def whole_audit(work, user_request, manifest, run_components=True, progress_callback=None):
        payload = previous_whole_audit(work, user_request, manifest, run_components, progress_callback)
        if run_components:
            memory = None
            try:
                memory = update_project_repair_memory(g, work, user_request, manifest, payload)
            except Exception as exc:
                append_event(
                    work, "v4239_project_repair_memory_failed",
                    "V42.39 could not refresh the project repair dossier; validation evidence remains authoritative.",
                    error=str(exc)[-1200:],
                )
            try:
                write_failure_observability(g, work, manifest, payload, memory)
            except Exception as exc:
                append_event(
                    work, "v4239_failure_observability_failed",
                    "V42.39 could not refresh its human/JSONL failure explanation; the raw whole-project audit remains authoritative.",
                    error=str(exc)[-1200:],
                )
        return payload

    def specialist(user_request, manifest, work, audit, progress_callback=None, reason=""):
        block = active_transport_block(work, manifest)
        if block and _audit_is_only_blocked_component(audit or {}, block, manifest or {}):
            append_event(
                work, "v4239_specialist_suppressed_after_transport_block",
                "V42.39 suppressed specialist inference because the only remaining component is already transport-blocked at the same source revision.",
                component=block.get("component"), component_token=block.get("component_token"),
            )
            return "MODEL_TRANSPORT_BLOCKED: specialist inference suppressed until component source changes."
        return previous_specialist(user_request, manifest, work, audit, progress_callback, reason)

    def whole_convergence(user_request, manifest, work, progress_callback=None):
        root = Path(work).resolve()
        try:
            audit = g["_v429_whole_project_audit"](
                root, user_request, manifest, run_components=True, progress_callback=progress_callback
            )
        except Exception:
            return previous_convergence(user_request, manifest, work, progress_callback)
        if audit.get("clean"):
            return True, []
        before = g["_v429_progress_token"](root)
        changed = repair_round(user_request, manifest, root, audit, progress_callback, 1)
        after = g["_v429_progress_token"](root)
        if changed and after != before:
            return previous_convergence(user_request, manifest, root, progress_callback)
        block = active_transport_block(root, manifest)
        if block and _audit_is_only_blocked_component(audit, block, manifest or {}):
            _record_terminal_halt(g, root, audit, block, progress_callback)
            try:
                memory = update_project_repair_memory(g, root, user_request, manifest, audit)
                write_failure_observability(g, root, manifest, audit, memory)
            except Exception:
                pass
            return False, list(audit.get("issues") or [])
        return previous_convergence(user_request, manifest, root, progress_callback)

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = (
            "\n\nV42.39 FINAL AUTHORITY: Compiler-derived deterministic candidates run before model transport eligibility and remain subject to exact-component strict diagnostic improvement. "
            "A model transport block never prevents deterministic repair. If the unchanged blocked component is the only remaining issue and deterministic repair cannot advance it, terminate convergence and preserve a MODEL_TRANSPORT_BLOCKED checkpoint; do not launch another specialist or audit loop. "
            "Continue normally after any accepted component revision and require full build, test, runtime, integration, and original-requirement evidence before publication."
        )
        return previous_qwen(
            str(prompt or "") + authority, progress_callback,
            re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.39", str(stage or "Generating")),
            profile=profile, **kwargs,
        )

    def release_identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION, "engine": ENGINE,
            "planner_mode": "deterministic-first-terminal-component-convergence-v42.39",
            "deterministic_repairs_ignore_model_transport_exhaustion": True,
            "combined_then_isolated_compiler_candidate_validation": True,
            "deterministic_candidate_fingerprint_guard": True,
            "model_budget_checked_only_after_deterministic_preflight": True,
            "transport_block_terminal_when_only_issue": True,
            "specialist_suppressed_after_terminal_transport_block": True,
            "terminal_checkpoint_status": "MODEL_TRANSPORT_BLOCKED",
            "current_event_engine_identity": True,
            "full_pass_project_repair_memory": True,
            "stable_issue_fingerprints_across_resume": True,
            "resolved_issue_history_retained": True,
            "memory_aware_compact_component_prompts": True,
            "current_evidence_overrides_memory": True,
            "full_pass_machine_trace": TRACE_FILE,
            "human_failure_report": REPORT_FILE,
            "failure_report_includes_command_cwd_evidence_and_next_action": True,
            "repair_decision_trace_retained": True,
            "provider_prompts_and_environment_excluded_from_failure_logs": True,
            "component_source_revision_transport_state": True,
            "compiler_exact_suggestions_before_model": True,
            "strict_component_diagnostic_delta": True,
            "language_framework_toolchain_agnostic": True,
            "new_project_and_existing_project_edit_modes": True,
        })
        return data

    def stack_skill_names(manifest):
        names = list(previous_skills(manifest) or [])
        for name in ("deterministic-first-repair", "terminal-transport-halt", "failure-observability"):
            if name not in names:
                names.append(name)
        return names[:24]

    def engine_guard():
        marker = PathType(g["__file__"]).resolve().with_name(ENGINE_MARKER)
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
        expected = "V" + VERSION
        if disk and disk != expected:
            return False, f"Jarvis engine files identify {disk}, but this running process is {expected}. Fully close and restart Jarvis before starting or resuming a project."
        return True, ""

    def generate_project_zip(user_request, max_files=None, max_audit_passes=None, progress_callback=None):
        ok, message = engine_guard()
        if not ok:
            return False, message, None
        return previous_generate(user_request, max_files=max_files, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    def analyze_and_edit_project_zip(user_request, source_zip, max_audit_passes=None, progress_callback=None):
        ok, message = engine_guard()
        if not ok:
            return False, message, None
        return previous_edit(user_request, source_zip, max_audit_passes=max_audit_passes, progress_callback=progress_callback)

    g.update({
        "V4239_VERSION": VERSION, "V4239_ENGINE": ENGINE,
        "V4239_STATE_FILE": STATE_FILE, "V4239_HALT_FILE": HALT_FILE,
        "V4239_BUNDLE_FILE": BUNDLE_FILE, "V4239_MEMORY_FILE": MEMORY_FILE,
        "V4239_TRACE_FILE": TRACE_FILE, "V4239_REPORT_FILE": REPORT_FILE,
        "_v4239_deterministic_preflight": lambda request, manifest, work, failure, callback=None: deterministic_preflight(g, request, manifest, work, failure, callback),
        "_v4239_repair_component_failure": lambda request, manifest, work, failure, callback=None: repair_component_failure(g, request, manifest, work, failure, callback),
        "_v4239_active_transport_block": active_transport_block,
        "_v4239_update_project_repair_memory": lambda work, request, manifest, audit: update_project_repair_memory(g, work, request, manifest, audit),
        "_v4239_write_failure_observability": lambda work, manifest, audit, memory=None: write_failure_observability(g, work, manifest, audit, memory),
        "_v429_whole_project_audit": whole_audit,
        "_v429_repair_audit_round": repair_round,
        "_repair_real_validation_failure": real_repair,
        "_v429_whole_project_convergence": whole_convergence,
        "_v429_specialist_whole_audit": specialist,
        "_append_project_event": append_event, "_progress": progress, "_qwen_call": qwen_call,
        "_v36_release_identity": release_identity, "_v36_stack_skill_names": stack_skill_names,
        "_v4239_engine_disk_guard": engine_guard,
        "_v4238_engine_disk_guard": engine_guard, "_v4237_engine_disk_guard": engine_guard,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
    # V42.38's repair function resolves this module global at call time. Replace
    # only its prompt builder so model attempts receive the compact durable
    # dossier without changing its isolated validation/promotion policy.
    v4238._model_patch_prompt = lambda passed_g, work, manifest, component, target, connected, failure: _memory_aware_model_prompt(
        passed_g, Path(work), manifest, component, target, connected, failure
    )
