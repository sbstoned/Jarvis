"""Jarvis V42.40.2 convergence, persistence, and safe stop/checkpoint layer.

This focused install layer preserves the stack-agnostic V42.37 component
transaction engine while adding deterministic compiler preflight, durable
failure memory, repeated exact-patch support, and a cooperative user stop that
packages only the accepted workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

import jarvis_v4237_repair as v4237


VERSION = "42.40.2"
ENGINE = "CHECKPOINT_CONTROL_COMPILER_EVIDENCE_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
CONTROL_FILE = "JARVIS_V4240_ACTIVE_PROJECT.json"
STOP_LOG_FILE = "JARVIS_V4240_STOP_EVENTS.jsonl"
MANUAL_CHECKPOINT_FILE = "JARVIS_MANUAL_CHECKPOINT.json"
MEMORY_FILE = "JARVIS_V4239_PROJECT_REPAIR_MEMORY.json"
TRACE_FILE = "JARVIS_V4239_FULL_PASS_TRACE.jsonl"
REPORT_FILE = "JARVIS_V4239_FAILURE_REPORT.md"


class ProjectStopRequested(RuntimeError):
    pass


_CONTROL_LOCK = threading.RLock()
_STOP_EVENT = threading.Event()
_ACTIVE = {
    "job_id": None,
    "work": "",
    "last_job_id": None,
    "last_work": "",
    "last_user_request": "",
    "last_source_zip": "",
    "last_finished_epoch": 0.0,
    "user_request": "",
    "source_zip": "",
    "created_epoch": 0.0,
    "last_checkpoint": "",
    "last_result": {},
    "stop_reason": "",
}


def active_process_version(g: dict, fallback: object = "") -> str:
    """Return the final installed runtime identity, not this wrapper's release.

    Generation entry points are intentionally wrapped by later compatibility
    layers.  An older wrapper must therefore validate the fully installed
    process at call time.  Reading its own module VERSION creates a false stale
    process error whenever a newer layer correctly calls through it.
    """
    identity = g.get("_v36_release_identity")
    if callable(identity):
        try:
            value = str((identity() or {}).get("version") or "").strip()
            if re.fullmatch(r"V?\d+(?:\.\d+){1,3}", value, re.I):
                return value if value.upper().startswith("V") else "V" + value
        except Exception:
            pass

    candidates = []
    for key, raw in g.items():
        if not re.fullmatch(r"V\d+_VERSION", str(key or "")):
            continue
        value = str(raw or "").strip().lstrip("Vv")
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}", value):
            continue
        parts = tuple(int(item) for item in value.split("."))
        candidates.append((parts + (0,) * (4 - len(parts)), value))
    if candidates:
        return "V" + max(candidates)[1]
    value = str(fallback or VERSION).strip()
    return value if value.upper().startswith("V") else "V" + value


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _json(path: Path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value
    except Exception:
        return {} if default is None else default


def _control_snapshot(g: dict) -> dict:
    with _CONTROL_LOCK:
        data = dict(_ACTIVE)
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "stop_requested": _STOP_EVENT.is_set(),
            "updated_at": g["_utc_stamp"](),
        })
        return data


def _save_control(g: dict) -> None:
    try:
        _atomic_json(Path(g["GENERATED_DIR"]) / CONTROL_FILE, _control_snapshot(g))
    except Exception:
        pass


def _append_stop_event(g: dict, event: str, **fields) -> None:
    """Persist control events immediately, including stops before a workspace exists."""
    try:
        root = Path(g["GENERATED_DIR"])
        root.mkdir(parents=True, exist_ok=True)
        row = {"at": g["_utc_stamp"](), "event": str(event), "version": "V" + VERSION}
        row.update(fields)
        with (root / STOP_LOG_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def begin_project_run(g: dict, job_id=None, user_request="", source_zip="") -> None:
    with _CONTROL_LOCK:
        _STOP_EVENT.clear()
        _ACTIVE.update({
            "job_id": job_id,
            "work": "",
            "user_request": str(user_request or ""),
            "source_zip": str(source_zip or ""),
            "created_epoch": time.time(),
            "last_checkpoint": "",
            "last_result": {},
            "stop_reason": "",
        })
    _save_control(g)
    _append_stop_event(g, "project_run_started", job_id=job_id, source_zip=Path(str(source_zip or "")).name)


def register_project_work(g: dict, work) -> Path | None:
    """Durably bind the current job to its accepted project workspace.

    Later release wrappers may bypass this module's event wrapper, so workspace
    registration is a public control operation rather than an append-event side
    effect. The last valid path survives worker shutdown so a late checkpoint
    can recover source instead of incorrectly claiming that none exists.
    """
    try:
        path = Path(work).resolve()
    except Exception:
        return None
    if not path.is_dir():
        return None
    with _CONTROL_LOCK:
        rendered = str(path)
        if _ACTIVE.get("job_id") is not None:
            _ACTIVE["work"] = rendered
            _ACTIVE["last_job_id"] = _ACTIVE.get("job_id")
            _ACTIVE["last_user_request"] = str(_ACTIVE.get("user_request") or "")
            _ACTIVE["last_source_zip"] = str(_ACTIVE.get("source_zip") or "")
        _ACTIVE["last_work"] = rendered
    _save_control(g)
    return path


def finish_project_run(g: dict, job_id=None, result=None) -> None:
    with _CONTROL_LOCK:
        if job_id is not None and _ACTIVE.get("job_id") not in (None, job_id):
            return
        if _ACTIVE.get("work"):
            _ACTIVE["last_work"] = str(_ACTIVE.get("work"))
        _ACTIVE["last_job_id"] = job_id if job_id is not None else _ACTIVE.get("job_id")
        _ACTIVE["last_user_request"] = str(_ACTIVE.get("user_request") or _ACTIVE.get("last_user_request") or "")
        _ACTIVE["last_source_zip"] = str(_ACTIVE.get("source_zip") or _ACTIVE.get("last_source_zip") or "")
        _ACTIVE["last_finished_epoch"] = time.time()
        if result is not None:
            _ACTIVE["last_result"] = dict(result or {})
            result_row = dict(result or {})
            if result_row.get("automatic_exhausted"):
                _ACTIVE["activity"] = "Automatic repair budget exhausted; resumable checkpoint saved."
                _ACTIVE["stage"] = "checkpoint"
                _ACTIVE["percent"] = 100
                try:
                    current_work = Path(str(_ACTIVE.get("work") or _ACTIVE.get("last_work") or ""))
                    terminal = _json(current_work / g.get("V4242_TERMINAL_FILE", "JARVIS_V4242_TERMINAL_STATE.json"), {})
                    if terminal.get("diagnostic_count") is not None:
                        _ACTIVE["diagnostic_count"] = terminal.get("diagnostic_count")
                    if terminal.get("repository_token"):
                        _ACTIVE["repository_token"] = terminal.get("repository_token")
                except Exception:
                    pass
            elif result_row.get("ok"):
                _ACTIVE["activity"] = "Project run finished successfully."
                _ACTIVE["stage"] = "complete"
                _ACTIVE["percent"] = 100
                _ACTIVE["diagnostic_count"] = 0
            else:
                _ACTIVE["activity"] = "Project run finished."
                _ACTIVE["stage"] = "finished"
        _ACTIVE["job_id"] = None
        _ACTIVE["work"] = ""
        _ACTIVE["user_request"] = ""
        _ACTIVE["source_zip"] = ""
        _STOP_EVENT.clear()
    _save_control(g)
    _append_stop_event(g, "project_run_finished", job_id=job_id, result=dict(result or {}))


def request_project_stop(g: dict, reason="User requested STOP + CHECKPOINT.") -> dict:
    with _CONTROL_LOCK:
        active = dict(_ACTIVE)
        if active.get("job_id") is None:
            return {"ok": False, "message": "No Qwen project job is currently running."}
        _STOP_EVENT.set()
        _ACTIVE["stop_reason"] = str(reason)
    cancelled = False
    try:
        from multi_provider import cancel_active_qwen_stream
        cancelled = bool(cancel_active_qwen_stream())
    except Exception:
        pass
    _save_control(g)
    _append_stop_event(
        g, "stop_requested", job_id=active.get("job_id"), reason=str(reason),
        active_stream_cancelled=cancelled,
    )
    return {
        "ok": True,
        "job_id": active.get("job_id"),
        "stream_cancelled": cancelled,
        "message": "Stop accepted. Jarvis is unwinding to a safe boundary and saving the best accepted workspace.",
    }


def _find_active_work(g: dict) -> Path | None:
    with _CONTROL_LOCK:
        job_id = _ACTIVE.get("job_id")
        raw_values = [str(_ACTIVE.get("work") or "")]
        if job_id is None or _ACTIVE.get("last_job_id") in (None, job_id):
            raw_values.append(str(_ACTIVE.get("last_work") or ""))
        started = float(_ACTIVE.get("created_epoch") or 0.0)
    persisted = _json(Path(g["GENERATED_DIR"]) / CONTROL_FILE, {})
    if isinstance(persisted, dict):
        persisted_job = persisted.get("job_id")
        persisted_last_job = persisted.get("last_job_id")
        if job_id is None or persisted_job in (None, job_id):
            raw_values.append(str(persisted.get("work") or ""))
        if job_id is None or persisted_last_job in (None, job_id):
            raw_values.append(str(persisted.get("last_work") or ""))
    for raw in dict.fromkeys(value for value in raw_values if value):
        path = Path(raw)
        if path.is_dir():
            return path
    root = Path(g["GENERATED_DIR"])
    candidates = []
    try:
        state_names = {
            g.get("PROJECT_STATE_FILE", "JARVIS_PROJECT_STATE.json"),
            g.get("V4242_RUN_STATE_FILE", "JARVIS_V4242_RUN_STATE.json"),
        }
        for state_path in root.rglob("*.json"):
            if state_path.name not in state_names:
                continue
            try:
                if started and state_path.stat().st_mtime + 5 < started:
                    continue
                path = state_path.parent.resolve()
                if path not in candidates:
                    candidates.append(path)
            except Exception:
                continue
    except Exception:
        pass
    return max(
        candidates,
        key=lambda p: max(
            (p / name).stat().st_mtime for name in state_names if (p / name).is_file()
        ),
    ) if candidates else None


def checkpoint_stopped_project(g: dict, job_id=None, reason="User requested a checkpoint."):
    work = _find_active_work(g)
    if work is None:
        return False, "Stop completed before Jarvis created a project workspace; there was no source to checkpoint.", None
    try:
        real_sources = list(g["_existing_real_source_files"](work) or [])
    except Exception:
        real_sources = []
    if not real_sources:
        return False, f"Stop completed before any real source files existed. Diagnostic workspace: {work}", None

    state = _json(work / g.get("PROJECT_STATE_FILE", "JARVIS_PROJECT_STATE.json"), {})
    manifest = state.get("manifest") if isinstance(state.get("manifest"), dict) else {}
    if not manifest:
        manifest = {"project_name": work.name, "acceptance_criteria": list(state.get("acceptance_criteria") or [])}
    with _CONTROL_LOCK:
        active = dict(_ACTIVE)
    active_request = str(active.get("user_request") or active.get("last_user_request") or "")
    original_request = str(state.get("original_request") or state.get("user_request") or active_request)
    latest_instruction = str(state.get("latest_instruction") or active_request or original_request)
    unresolved = list(state.get("unresolved_requirements") or [])
    source_zip = Path(str(active.get("source_zip") or active.get("last_source_zip") or "")).name
    created_at = g["_utc_stamp"]()
    reason_text = str(reason or "")
    automatic_exhaustion = bool(re.match(r"V42\.\d+(?:\.\d+)* automatically stopped", reason_text)) or "exhausted the bounded" in reason_text
    manual = {
        "version": "V" + VERSION,
        "engine": ENGINE,
        "status": "automatic_exhausted_checkpoint" if automatic_exhaustion else "stopped_checkpoint",
        "created_at": created_at,
        "reason": str(reason),
        "job_id": active.get("job_id"),
        "workspace": str(work),
        "source_zip_name": source_zip,
        "real_source_files": len(real_sources),
        "resume_instruction": "Attach this ZIP to Jarvis and ask to finish this project.",
    }
    _atomic_json(work / MANUAL_CHECKPOINT_FILE, manual)
    try:
        g["_append_project_event"](
            work, "v4242_automatic_exhausted_checkpoint" if automatic_exhaustion else "v4240_user_stop_checkpoint",
            (
                f"V{VERSION} automatically checkpointed the best accepted workspace after the current revision exhausted its bounded repair strategies."
                if automatic_exhaustion else
                f"V{VERSION} accepted the user's stop request and preserved the best accepted workspace."
            ),
            status="AUTOMATIC_EXHAUSTED_CHECKPOINT" if automatic_exhaustion else "STOPPED_CHECKPOINT",
            job_id=active.get("job_id"), source_files=len(real_sources),
        )
    except Exception:
        pass
    out, count = g["_package_resume_checkpoint_zip"](
        work, manifest, original_request, latest_instruction, unresolved,
        source_zip_name=source_zip, resume_count=int(state.get("resume_count") or 1), snapshot=None,
    )
    with _CONTROL_LOCK:
        _ACTIVE["last_checkpoint"] = str(out)
    _save_control(g)
    _append_stop_event(
        g, "checkpoint_saved", job_id=active.get("job_id"), path=str(out),
        source_files=len(real_sources), reason=str(reason),
    )
    prefix = (
        "Qwen reached a bounded repair limit and stopped automatically at a safe boundary."
        if automatic_exhaustion else
        "Qwen stopped at a safe boundary."
    )
    return False, (
        f"{prefix} A RESUMABLE CHECKPOINT ZIP was saved with {count} files. "
        "It contains the best accepted workspace and is not falsely labeled complete."
    ), out


def apply_repeated_search_replace(previous_apply, current, replacements):
    candidate = str(current)
    changed = 0
    for index, replacement in enumerate(replacements or [], start=1):
        search = str(replacement.get("search") or "")
        replace = str(replacement.get("replace") or "")
        if not search:
            return "", f"SEARCH/REPLACE block {index} has an empty SEARCH section."
        count = candidate.count(search)
        if count == 0:
            # Give the inherited exact-patch parser first refusal.  It owns
            # safe transport recovery such as stripping copied source-viewer
            # line numbers; rejecting before that call silently disabled the
            # V41.3 normalization contract.
            one, error = previous_apply(candidate, [replacement])
            if error:
                return "", error
            candidate = one
            changed += 1
            continue
        if count == 1:
            one, error = previous_apply(candidate, [replacement])
            if error:
                return "", error
            candidate = one
            changed += 1
            continue
        if count > 64:
            return "", f"SEARCH/REPLACE block {index} matched {count} locations; bounded repeated repair limit is 64."
        if search in replace:
            return "", f"SEARCH/REPLACE block {index} is self-containing and cannot be safely repeated."
        candidate = candidate.replace(search, replace)
        changed += count
    if not changed or candidate == current:
        return "", "Patch made no change; do not repeat it."
    return candidate, ""


def _rust_compiler_candidate(source: str, failure: object, rel: object):
    text = str(failure or "")
    if not str(rel or "").lower().endswith(".rs"):
        return source, []
    updated = source
    reasons = []
    if "Transaction" in text and "Executor" in text and "&mut" in text:
        pattern = re.compile(r"\.(execute|fetch|fetch_one|fetch_all|fetch_optional)\(\s*&mut\s+(?!\*)([A-Za-z_]\w*)\s*\)")
        updated, count = pattern.subn(lambda m: f".{m.group(1)}(&mut *{m.group(2)})", updated)
        if count:
            reasons.append(f"compiler-proven SQLx transaction dereference ({count})")
    return updated, reasons


def _issue_snapshot(failure: object, component: dict | None = None) -> dict:
    raw = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(failure or ""))
    stable = re.sub(r":\d+(?::\d+)?", ":#", raw)
    files = sorted(set(re.findall(r"(?im)(?:-->|\bat\s+)(?:\s*)([^\s:]+\.[A-Za-z0-9]+)", raw)))
    codes = sorted(set(x.upper() for x in re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", raw, re.I)))
    identity = v4237._component_identity(component or {})
    digest = hashlib.sha256(stable.encode("utf-8", errors="replace")).hexdigest()[:24]
    return {"id": digest, "component": identity[0], "root": identity[1], "adapter": identity[2],
            "codes": codes, "files": files, "diagnostic_count": v4237.diagnostic_count(raw),
            "evidence": raw[-6000:]}


def _record_failure_memory(g: dict, work: Path, failure: object, manifest: dict, decision="pending") -> dict:
    component = v4237.component_from_failure(manifest, failure)
    issue = _issue_snapshot(failure, component)
    path = work / MEMORY_FILE
    memory = _json(path, {"version": "V" + VERSION, "issues": {}, "resolved": []})
    memory["version"] = "V" + VERSION
    memory["engine"] = ENGINE
    memory["updated_at"] = g["_utc_stamp"]()
    record = dict(memory.setdefault("issues", {}).get(issue["id"]) or {})
    record.update(issue)
    record["decision"] = decision
    record["seen_count"] = int(record.get("seen_count") or 0) + 1
    record["last_seen"] = memory["updated_at"]
    memory["issues"][issue["id"]] = record
    _atomic_json(path, memory)
    trace = {"at": memory["updated_at"], "issue": issue["id"], "component": issue["component"],
             "codes": issue["codes"], "files": issue["files"], "count": issue["diagnostic_count"], "decision": decision}
    with (work / TRACE_FILE).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trace, ensure_ascii=False) + "\n")
    report = ["# Jarvis project repair status", "", f"Updated: {memory['updated_at']}", "",
              f"Current component: {issue['component']} ({issue['adapter']} at {issue['root']})",
              f"Diagnostic count: {issue['diagnostic_count']}", f"Codes: {', '.join(issue['codes']) or 'unclassified'}",
              f"Files: {', '.join(issue['files']) or 'not localized'}", f"Decision: {decision}", "",
              "## Next action", "Run the exact component validator after a bounded candidate repair; publish only after all acceptance gates pass."]
    (work / REPORT_FILE).write_text("\n".join(report) + "\n", encoding="utf-8")
    return issue


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_qwen = g["_qwen_call"]
    previous_apply = g["_v36_apply_search_replace"]
    previous_repair = g["_v4237_repair_component_failure"]
    previous_append = g["_append_project_event"]
    base_progress = g.get("_v4235_base_progress", g["_progress"])
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])

    def append_event(work, event_type, message, **fields):
        register_project_work(g, work)
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        # Keep the V42.36/V42.37 component-aware stale-blocker invalidation;
        # then project the current release identity back onto its durable view.
        event = previous_append(work, event_type, message, **values)
        try:
            projection = Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            data = _json(projection, {})
            if isinstance(data, dict):
                data.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
                _atomic_json(projection, data)
        except Exception:
            pass
        _save_control(g)
        return event

    def progress(callback, text=None, **fields):
        if _STOP_EVENT.is_set():
            raise ProjectStopRequested("Stop requested from the Jarvis dashboard.")
        value = re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.40.2", str(text or ""))
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return base_progress(callback, value, **values)

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        if _STOP_EVENT.is_set():
            raise ProjectStopRequested("Stop requested before the next model call.")
        authority = (
            "\n\nV42.40.2 FINAL AUTHORITY: use the latest exact component validator evidence. "
            "Apply deterministic compiler-proven corrections before model repair. Keep candidates disposable until the same component passes or diagnostic count strictly decreases. "
            "Persist issue identity and resolved history across resume; never repeat an unchanged failed strategy or publish without full build, test, runtime, integration, and original-requirement acceptance."
        )
        result = previous_qwen(str(prompt or "") + authority, progress_callback,
                               re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.40.2", str(stage or "Generating")),
                               profile=profile, **kwargs)
        if _STOP_EVENT.is_set():
            raise ProjectStopRequested("Stop requested after the active model stream closed.")
        return result

    def repair_component(request, manifest, work, failure, callback=None):
        root = Path(work).resolve()
        manifest = manifest if isinstance(manifest, dict) else {}
        issue = _record_failure_memory(g, root, failure, manifest, "deterministic compiler preflight")
        component = v4237.component_from_failure(manifest, failure)
        rows = list(g.get("_v4236_native_diagnostics", lambda *_: [])(root, manifest, str(failure)) or [])
        targets = list(g.get("_v4236_rank_native_targets", lambda *_: [])(rows, str(failure)) or [])
        before = v4237.diagnostic_count(failure)
        handle = None
        try:
            handle, clone = g["_copy_project_for_candidate_validation"](root)
            clone = Path(clone).resolve()
            changed = []
            for rel in targets[:4]:
                path = clone / rel
                if not path.is_file():
                    continue
                original = path.read_text(encoding="utf-8", errors="replace")
                candidate, reasons = _rust_compiler_candidate(original, failure, rel)
                if candidate != original:
                    path.write_text(candidate, encoding="utf-8")
                    changed.append(rel)
            if changed and component:
                ok, output = g["_v35_validate_component"](clone, manifest, component, str(request or ""))
                after = 0 if ok else v4237.diagnostic_count(output)
                if ok or (before > 0 and 0 < after < before):
                    committed, _reason = v4237._commit_component_transaction(g, root, clone, changed, before, after, component)
                    if committed:
                        _record_failure_memory(g, root, failure, manifest, f"deterministic transaction committed {before}->{after}")
                        return True
        except ProjectStopRequested:
            raise
        except Exception:
            pass
        finally:
            v4237._cleanup_temp(handle)
        _record_failure_memory(g, root, failure, manifest, "bounded model component transaction")
        return bool(previous_repair(request, manifest, root, failure, callback))

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION, "engine": ENGINE,
            "planner_mode": "checkpoint-control-compiler-evidence-convergence-v42.40.2",
            "deterministic_repairs_ignore_model_transport_exhaustion": True,
            "full_pass_project_repair_memory": True,
            "stable_issue_fingerprints_across_resume": True,
            "failure_report_includes_command_cwd_evidence_and_next_action": True,
            "user_stop_checkpoint_control": True, "active_qwen_stream_cancellation": True,
            "accepted_workspace_checkpoint_on_stop": True,
            "repeated_exact_patch_staged_in_sandbox": True,
            "repeated_patch_promotion_requires_component_diagnostic_decrease": True,
            "compiler_evidence_rust_transaction_repair": True,
            "dashboard_auto_launch": True, "dashboard_standalone_window": True,
            "dashboard_layout_schema": 2, "legacy_dashboard_layout_invalidated": True,
            "chat_panel_resize_handle": True, "chat_input_reachable_during_stop": True,
            "chat_panel_reset_control": True, "language_framework_toolchain_agnostic": True,
        })
        return data

    def stack_skills(manifest):
        names = list(previous_skills(manifest) or [])
        for name in ("deterministic-first-repair", "persistent-repair-memory", "safe-stop-checkpoint"):
            if name not in names:
                names.append(name)
        return names[:24]

    def engine_guard():
        marker = PathType(g["__file__"]).resolve().with_name(ENGINE_MARKER)
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
        expected = active_process_version(g, VERSION)
        if disk and disk != expected:
            return False, f"Jarvis engine files identify {disk}, but this running process is {expected}. Fully close and restart Jarvis."
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
        "V4240_VERSION": VERSION, "V4240_ENGINE": ENGINE,
        "_v4240_active_process_version": lambda: active_process_version(g, VERSION),
        "ProjectStopRequested": ProjectStopRequested,
        "begin_project_run": lambda job_id=None, user_request="", source_zip="": begin_project_run(g, job_id, user_request, source_zip),
        "finish_project_run": lambda job_id=None, result=None: finish_project_run(g, job_id, result),
        "register_project_work": lambda work: register_project_work(g, work),
        "request_project_stop": lambda reason="User requested STOP + CHECKPOINT.": request_project_stop(g, reason),
        "checkpoint_stopped_project": lambda job_id=None, reason="": checkpoint_stopped_project(g, job_id, reason),
        "_v36_apply_search_replace": lambda current, replacements: apply_repeated_search_replace(previous_apply, current, replacements),
        "_v4237_repair_component_failure": repair_component,
        "_append_project_event": append_event, "_progress": progress, "_qwen_call": qwen_call,
        "_v36_release_identity": identity, "_v36_stack_skill_names": stack_skills,
        "_v4240_engine_disk_guard": engine_guard,
        "generate_project_zip": generate_project_zip, "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
