"""Jarvis V42.41 authoritative repair-controller layer.

V42.40 supplied deterministic repair and durable memory, but V42.37's live
audit closures called a captured local function instead of the registered
controller.  V42.41 establishes one call-time dispatch point, records every
strategy against compiler evidence plus the accepted repository revision, and
applies conservative compiler-directed Rust corrections in a disposable
component workspace before asking a model.

The controller remains language/framework agnostic: existing adapters own
component discovery and validation.  Language-specific deterministic rules are
small optional strategies, never acceptance authorities.  Only the component's
real validator can promote a candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import jarvis_v4236_repair as v4236
import jarvis_v4237_repair as v4237
import jarvis_v4240_repair as v4240


VERSION = "42.41.0"
ENGINE = "AUTHORITATIVE_REPAIR_CONTROLLER_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
LEDGER_FILE = "JARVIS_V4241_REPAIR_LEDGER.json"
TRACE_FILE = "JARVIS_V4241_REPAIR_TRACE.jsonl"
REPORT_FILE = "JARVIS_V4241_REPAIR_STATUS.md"


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {} if default is None else default


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _strip_ansi(value: object) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(value or ""))


def _failure_key(component: dict | None, failure: object, repository_token: str) -> str:
    text = _strip_ansi(failure)
    stable = re.sub(r":\d+(?::\d+)?", ":#", text)
    stable = re.sub(r"\b(?:elapsed|duration|finished in)\s+[^\n]+", "", stable, flags=re.I)
    codes = sorted(set(re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", stable, re.I)))
    cid, root, adapter = v4237._component_identity(component or {})
    material = {
        "component": cid,
        "root": root,
        "adapter": adapter,
        "repository_token": repository_token,
        "codes": codes,
        "failure": hashlib.sha256(stable.encode("utf-8", errors="replace")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _append_trace(g: dict, root: Path, event: str, **fields) -> None:
    row = {"at": g["_utc_stamp"](), "event": event, "version": "V" + VERSION, "engine": ENGINE}
    row.update(fields)
    try:
        with (root / TRACE_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _ledger_issue(g: dict, root: Path, component: dict | None, failure: object) -> tuple[dict, dict, Path]:
    token = str(v4237._repo_token(g, root))
    key = _failure_key(component, failure, token)
    path = root / LEDGER_FILE
    strategy_generation = str(g.get("JARVIS_REPAIR_STRATEGY_GENERATION") or "legacy")
    ledger = _load(path, {"version": "V" + VERSION, "engine": ENGINE, "issues": {}})
    ledger.update({
        "version": "V" + VERSION, "engine": ENGINE,
        "strategy_generation": strategy_generation, "updated_at": g["_utc_stamp"](),
    })
    issue = ledger.setdefault("issues", {}).setdefault(key, {
        "id": key,
        "repository_token": token,
        "component": v4237._component_identity(component or {})[0],
        "adapter": v4237._component_identity(component or {})[2],
        "diagnostic_count": v4237.diagnostic_count(failure),
        "attempts": [],
        "model_cycles": 0,
        "exhausted": False,
        "strategy_generation": strategy_generation,
    })
    prior_generation = str(issue.get("strategy_generation") or "legacy")
    if prior_generation != strategy_generation:
        history = list(issue.get("prior_strategy_generations") or [])
        history.append({
            "strategy_generation": prior_generation,
            "model_cycles": int(issue.get("model_cycles") or 0),
            "exhausted": bool(issue.get("exhausted")),
            "attempts": list(issue.get("attempts") or [])[-12:],
        })
        issue["prior_strategy_generations"] = history[-8:]
        issue["strategy_generation"] = strategy_generation
        issue["attempts"] = []
        issue["model_cycles"] = 0
        issue["exhausted"] = False
        issue["reopened_for_new_strategy_at"] = g["_utc_stamp"]()
    issue["last_seen"] = g["_utc_stamp"]()
    issue["seen_count"] = int(issue.get("seen_count") or 0) + 1
    _save(path, ledger)
    return ledger, issue, path


def _record_attempt(g: dict, root: Path, ledger: dict, issue: dict, path: Path,
                    strategy: str, result: str, **fields) -> None:
    row = {"at": g["_utc_stamp"](), "strategy": strategy, "result": result}
    row.update(fields)
    issue.setdefault("attempts", []).append(row)
    issue["last_result"] = result
    issue["last_strategy"] = strategy
    ledger["updated_at"] = g["_utc_stamp"]()
    _save(path, ledger)
    _append_trace(g, root, "strategy_result", issue=issue.get("id"), **row)


def _rustc_line_replacements(source: str, failure: str) -> tuple[str, list[str]]:
    """Apply exact old/new source lines printed by rustc help diagnostics.

    Suggestions are accepted here only when the old line occurs exactly once in
    the candidate file.  The result still has to reduce the real Cargo
    diagnostic count before it can leave the disposable workspace.
    """
    updated = source
    reasons = []
    pattern = re.compile(
        r"(?m)^\s*\d+\s+-\s?(?P<old>[^\r\n]+)\r?\n\s*\d+\s+\+\s?(?P<new>[^\r\n]+)$"
    )
    for match in pattern.finditer(failure):
        old = match.group("old").rstrip()
        new = match.group("new").rstrip()
        if old and old != new and updated.count(old) == 1:
            updated = updated.replace(old, new, 1)
            reasons.append("exact rustc old/new suggestion")
    return updated, reasons


def _add_from_row_derives(source: str, failure: str) -> tuple[str, list[str]]:
    updated = source
    reasons = []
    names = sorted(set(re.findall(
        r"\b([A-Z][A-Za-z0-9_]*)\s*:\s*(?:for\s*<[^>]+>\s*)?(?:sqlx::)?FromRow\b",
        failure,
    )))
    for name in names:
        struct = re.search(rf"(?m)^(?P<indent>\s*)(?:pub(?:\([^)]*\))?\s+)?struct\s+{re.escape(name)}\b", updated)
        if not struct:
            continue
        direct = re.search(r"(?m)(?P<whole>^[ \t]*#\[derive\((?P<body>[^\n]*)\)\][ \t]*\r?\n)(?=[ \t]*(?:pub(?:\([^)]*\))?\s+)?struct\s+" + re.escape(name) + r"\b)", updated)
        if direct:
            body = direct.group("body")
            if "FromRow" not in body:
                replacement = direct.group("whole").replace(body, body.rstrip() + ", sqlx::FromRow")
                updated = updated[:direct.start("whole")] + replacement + updated[direct.end("whole"):]
                reasons.append(f"compiler-required sqlx::FromRow derive for {name}")
        else:
            struct = re.search(rf"(?m)^(?P<indent>\s*)(?:pub(?:\([^)]*\))?\s+)?struct\s+{re.escape(name)}\b", updated)
            if struct:
                updated = updated[:struct.start()] + struct.group("indent") + "#[derive(sqlx::FromRow)]\n" + updated[struct.start():]
                reasons.append(f"compiler-required sqlx::FromRow derive for {name}")
    return updated, reasons


def _replace_string_enum_matches(source: str, failure: str) -> tuple[str, list[str]]:
    if not (
        "this expression has type `std::string::String`" in failure
        and re.search(r"expected\s+`?String`?,\s*found\s+`?[A-Za-z_]", failure)
    ):
        return source, []
    pattern = re.compile(
        r"(?P<indent>^[ \t]*)let\s+(?P<name>[A-Za-z_]\w*)\s*=\s*match\s+"
        r"(?P<expr>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\{\s*\n"
        r"(?P<arms>(?:[ \t]*[A-Za-z_]\w*::[A-Za-z_]\w*\s*=>\s*(?:Some\(\s*)?\"[^\"]*\"(?:\s*\))?\s*,?\s*\n){2,})"
        r"[ \t]*\};",
        re.M,
    )
    updated, count = pattern.subn(
        lambda m: f"{m.group('indent')}let {m.group('name')} = {m.group('expr')}.as_str();",
        source,
    )
    return updated, ([f"String field replaced invalid enum match ({count})"] if count else [])


def _replace_nullable_string_binds(source: str, failure: str) -> tuple[str, list[str]]:
    if not any(token in failure for token in ("expected `&str`, found `String`", "returns a value referencing function parameter")):
        return source, []
    updated = source
    reasons = []
    mapped = re.compile(
        r"\.bind\(\s*(?P<expr>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)"
        r"\.map\(\|(?P<arg>[A-Za-z_]\w*)\|\s*(?P=arg)\.as_str\(\)\)"
        r"\.unwrap_or\(\"null\"(?:\.to_string\(\))?\)\s*\)"
    )
    updated, count = mapped.subn(lambda m: f".bind({m.group('expr')}.as_deref())", updated)
    if count:
        reasons.append(f"nullable String SQL bind corrected ({count})")
    matched = re.compile(
        r"\.bind\(\s*match\s+(?P<expr>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\{\s*"
        r"Some\([A-Za-z_]\w*\)\s*=>\s*[A-Za-z_]\w*\.as_str\(\)\s*,\s*"
        r"None\s*=>\s*\"null\"\s*\}\s*\)"
    )
    updated, count = matched.subn(lambda m: f".bind({m.group('expr')}.as_deref())", updated)
    if count:
        reasons.append(f"borrow-safe optional SQL bind corrected ({count})")
    return updated, reasons


def rust_compiler_candidate(source: str, failure: object, rel: object) -> tuple[str, list[str]]:
    if not str(rel or "").lower().endswith(".rs"):
        return source, []
    text = _strip_ansi(failure)
    updated = source
    reasons = []
    for strategy in (
        _rustc_line_replacements,
        _add_from_row_derives,
        _replace_string_enum_matches,
        _replace_nullable_string_binds,
    ):
        updated, found = strategy(updated, text)
        reasons.extend(found)
    # Retain V42.40's SQLx transaction dereference correction.
    updated, found = v4240._rust_compiler_candidate(updated, text, rel)
    reasons.extend(found)
    return updated, list(dict.fromkeys(reasons))


def _ensure_sqlx_derive_feature(source: str) -> tuple[str, list[str]]:
    line_pattern = re.compile(r"(?m)^(?P<prefix>\s*sqlx\s*=\s*\{[^\n]*features\s*=\s*\[)(?P<body>[^\]]*)(?P<suffix>\][^\n]*\}\s*)$")
    match = line_pattern.search(source)
    if not match or re.search(r"[\"']derive[\"']", match.group("body")):
        return source, []
    body = match.group("body").rstrip()
    if body and not body.rstrip().endswith(","):
        body += ","
    body += ' "derive"'
    replacement = match.group("prefix") + body + match.group("suffix")
    return source[:match.start()] + replacement + source[match.end():], ["enable SQLx derive support required by FromRow"]


def _deterministic_component_transaction(g: dict, request: object, manifest: dict,
                                         root: Path, failure: object, component: dict,
                                         progress_callback=None) -> tuple[bool, dict]:
    cid, component_root, adapter = v4237._component_identity(component)
    before = v4237.diagnostic_count(failure)
    try:
        rows = list(g["_v4236_native_diagnostics"](root, manifest, failure) or [])
        targets = list(g["_v4236_rank_native_targets"](rows, failure) or [])
    except Exception:
        rows, targets = [], []
    targets = [rel for rel in targets if v4237._component_identity(v4237._component_for_rel(manifest, rel))[0] == cid]
    if adapter != "rust" or not targets or before <= 0:
        return False, {"result": "not_applicable", "before": before, "after": before, "files": []}

    handle = None
    try:
        handle, clone = g["_copy_project_for_candidate_validation"](root)
        clone = Path(clone).resolve()
        changed = []
        reasons = []
        for rel in targets[:6]:
            path = clone / rel
            if not path.is_file():
                continue
            original = path.read_text(encoding="utf-8", errors="replace")
            candidate, found = rust_compiler_candidate(original, failure, rel)
            if candidate != original:
                path.write_text(candidate, encoding="utf-8")
                changed.append(rel)
                reasons.extend(found)

        if any("FromRow" in reason for reason in reasons):
            cargo_rel = str(Path(component_root) / "Cargo.toml").replace("\\", "/")
            cargo = clone / cargo_rel
            if cargo.is_file():
                original = cargo.read_text(encoding="utf-8", errors="replace")
                candidate, found = _ensure_sqlx_derive_feature(original)
                if candidate != original:
                    cargo.write_text(candidate, encoding="utf-8")
                    changed.append(cargo_rel)
                    reasons.extend(found)

        changed = list(dict.fromkeys(changed))
        if not changed:
            return False, {"result": "no_candidate", "before": before, "after": before, "files": []}

        g["_progress"](
            progress_callback,
            f"V42.41 validating deterministic {cid} root-cause transaction",
            stage="V42.41 compiler-directed repair",
            percent=84,
            component=cid,
            files=changed,
            diagnostic_count=before,
        )
        ok, output = g["_v35_validate_component"](clone, manifest, component, str(request or ""))
        output = str(output or "")
        after = 0 if ok else v4237.diagnostic_count(output)
        # A failed validator with zero parseable diagnostics is commonly an
        # infrastructure/tool-launch failure.  It is never proof that source
        # improved.  Zero is accepted only when the validator itself succeeds.
        improved = bool(ok or (before > 0 and 0 < after < before))
        if not improved:
            return False, {
                "result": "no_delta", "before": before, "after": after,
                "files": changed, "reasons": reasons, "validator_tail": output[-2400:],
            }
        committed, reason = v4237._commit_component_transaction(
            g, root, clone, changed, before, after, component
        )
        return bool(committed), {
            "result": "committed" if committed else "commit_failed",
            "before": before, "after": after, "files": changed,
            "reasons": reasons, "commit_detail": str(reason or "")[-1200:],
        }
    except v4240.ProjectStopRequested:
        raise
    except Exception as exc:
        return False, {"result": "sandbox_failure", "before": before, "after": before, "files": [], "error": str(exc)[-1800:]}
    finally:
        v4237._cleanup_temp(handle)


def _write_status(g: dict, root: Path, issue: dict) -> None:
    attempts = list(issue.get("attempts") or [])
    last = attempts[-1] if attempts else {}
    lines = [
        "# Jarvis V42.41 repair status", "",
        f"Updated: {g['_utc_stamp']()}",
        f"Component: {issue.get('component') or 'unknown'} ({issue.get('adapter') or 'unknown'})",
        f"Compiler diagnostics: {issue.get('diagnostic_count') or 0}",
        f"Repository revision token: {issue.get('repository_token') or 'unknown'}",
        f"Last strategy: {last.get('strategy') or 'none'}",
        f"Last result: {last.get('result') or 'pending'}",
        f"Model cycles on this exact revision: {issue.get('model_cycles') or 0}",
        f"Exhausted at this revision: {bool(issue.get('exhausted'))}", "",
        "Jarvis only promotes a candidate when the failing component's real validator passes or its diagnostic count decreases.",
    ]
    (root / REPORT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_component_repair = g["_v4237_repair_component_failure"]
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_real_repair = g["_repair_real_validation_failure"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_qwen = g["_qwen_call"]
    durable_append = g.get("_v4235_durable_append_project_event", g["_append_project_event"])
    base_progress = g.get("_v4235_base_progress", g["_progress"])
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])

    # Keep V42.40's stop/checkpoint files and public functions while ensuring
    # their durable control records identify the active release.
    v4240.VERSION = VERSION
    v4240.ENGINE = ENGINE

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        rendered = re.sub(
            r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)",
            "V42.41",
            str(message or ""),
        )
        event = durable_append(work, event_type, rendered, **values)
        try:
            # Accepted edits invalidate only their affected blocker.  A later
            # fresh green validation must run after that invalidation and clear
            # the pending flag authoritatively.
            v4236._component_aware_invalidate(g, work, event_type, values)
            projection = Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            data = _load(projection, {})
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
                        "type": event_key,
                        "at": g["_utc_stamp"](),
                    }
                _save(projection, data)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested from the Jarvis dashboard.")
        rendered = re.sub(
            r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)",
            "V42.41",
            str(text or ""),
        )
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return base_progress(callback, rendered, **values)

    def component_repair(request, manifest, work, failure, callback=None):
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested before repair transaction.")
        root = Path(work).resolve()
        manifest = manifest if isinstance(manifest, dict) else {}
        component = v4237.component_from_failure(manifest, failure)
        if not component:
            return bool(previous_component_repair(request, manifest, root, failure, callback))
        ledger, issue, ledger_path = _ledger_issue(g, root, component, failure)
        _write_status(g, root, issue)

        deterministic_done = any(
            row.get("strategy") == "compiler_directed_transaction"
            for row in issue.get("attempts") or []
        )
        allow_deterministic_retry = os.getenv(
            "JARVIS_V4241_RETRY_DETERMINISTIC_SAME_REVISION", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        if deterministic_done and not allow_deterministic_retry:
            changed = False
            result = {
                "result": "same_revision_suppressed",
                "before": issue.get("diagnostic_count"),
                "after": issue.get("diagnostic_count"),
                "files": [],
                "reasons": ["compiler strategy already evaluated against this exact revision and evidence"],
            }
            _record_attempt(
                g, root, ledger, issue, ledger_path,
                "same_revision_deterministic_circuit_breaker", result["result"],
                before=result.get("before"), after=result.get("after"),
            )
        else:
            changed, result = _deterministic_component_transaction(
                g, request, manifest, root, failure, component, callback
            )
            _record_attempt(
                g, root, ledger, issue, ledger_path,
                "compiler_directed_transaction", result.get("result", "unknown"),
                before=result.get("before"), after=result.get("after"),
                files=result.get("files") or [], reasons=result.get("reasons") or [],
                validator_ok=result.get("validator_ok"),
                phase_progress=result.get("phase_progress"),
                proof_kind=result.get("proof_kind"),
                validator_tail=str(result.get("validator_tail") or "")[-1800:],
                proof_tail=str(result.get("proof_tail") or "")[-1800:],
            )
        _write_status(g, root, issue)
        if changed:
            g["_append_project_event"](
                root, "v4241_deterministic_repair_committed",
                f"V42.41 accepted a compiler-directed {issue.get('component')} repair: "
                f"{result.get('before')} -> {result.get('after')} diagnostics.",
                component=issue.get("component"), diagnostic_count=result.get("after"),
                error_delta=int(result.get("after") or 0) - int(result.get("before") or 0),
                files=result.get("files") or [],
            )
            return True

        max_cycles = max(0, min(3, int(os.getenv("JARVIS_V4241_MODEL_CYCLES_PER_REVISION", "2"))))
        cycles = int(issue.get("model_cycles") or 0)
        if cycles >= max_cycles:
            issue["exhausted"] = True
            _record_attempt(
                g, root, ledger, issue, ledger_path,
                "same_revision_circuit_breaker", "model_retry_suppressed",
                model_cycles=cycles, maximum=max_cycles,
            )
            _write_status(g, root, issue)
            g["_append_project_event"](
                root, "v4241_same_revision_exhausted",
                "V42.41 stopped repeating an unchanged repair strategy; fresh source or compiler evidence is required.",
                component=issue.get("component"), diagnostic_count=issue.get("diagnostic_count"),
                repository_token=issue.get("repository_token"), model_cycles=cycles,
            )
            return False

        issue["model_cycles"] = cycles + 1
        _save(ledger_path, ledger)
        before_token = str(v4237._repo_token(g, root))
        repaired = bool(previous_component_repair(request, manifest, root, failure, callback))
        after_token = str(v4237._repo_token(g, root))
        _record_attempt(
            g, root, ledger, issue, ledger_path,
            "bounded_model_component_transaction",
            "committed" if repaired else "no_accepted_change",
            source_changed=after_token != before_token,
        )
        if not repaired:
            issue["exhausted"] = True
            _save(ledger_path, ledger)
        _write_status(g, root, issue)
        # The prior component engine returns True only after its exact validator
        # and atomic commit gate pass.  A separate progress token can lag while
        # an accepted-revision ledger is written, so it remains logging evidence
        # and must not negate a validated commit.
        return repaired

    def repair_round(user_request, manifest, work, audit, progress_callback=None, round_no=1):
        issues = [row for row in (audit or {}).get("issues") or [] if isinstance(row, dict)]
        for row in issues:
            failure = str(row.get("problem") or "")
            try:
                native = bool(g["_v4236_is_native_compiler_failure"](work, manifest, failure))
            except Exception:
                native = False
            if native:
                controller = g.get("_v4237_repair_component_failure")
                if callable(controller):
                    return bool(controller(user_request, manifest, work, failure, progress_callback))
                return component_repair(user_request, manifest, work, failure, progress_callback)
        return bool(previous_repair_round(user_request, manifest, work, audit, progress_callback, round_no))

    def real_repair(user_request, manifest, work, failure, progress_callback=None):
        try:
            if g["_v4236_is_native_compiler_failure"](work, manifest, failure):
                controller = g.get("_v4237_repair_component_failure")
                if callable(controller):
                    return bool(controller(user_request, manifest, work, failure, progress_callback))
                return component_repair(user_request, manifest, work, failure, progress_callback)
        except v4240.ProjectStopRequested:
            raise
        except Exception:
            pass
        return bool(previous_real_repair(user_request, manifest, work, failure, progress_callback))

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested before the next model call.")
        authority = (
            "\n\nV42.41 FINAL AUTHORITY: one current repair controller owns every compiler failure. "
            "Use the current source revision and exact component validator evidence. Prefer the smallest root-cause transaction, "
            "never repeat a failed strategy against unchanged evidence, and never claim completion until all build, test, runtime, integration, and original-requirement gates pass."
        )
        return previous_qwen(
            str(prompt or "") + authority,
            progress_callback,
            re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.41", str(stage or "Generating")),
            profile=profile,
            **kwargs,
        )

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "authoritative-repair-controller-v42.41",
            "call_time_repair_dispatch": True,
            "compiler_directed_root_cause_transaction": True,
            "same_revision_strategy_circuit_breaker": True,
            "progress_aware_local_model_watchdog": True,
            "repair_strategy_ledger": LEDGER_FILE,
            "repair_trace": TRACE_FILE,
            "repair_status_report": REPORT_FILE,
            "language_framework_toolchain_agnostic": True,
        })
        return data

    def stack_skills(manifest):
        names = list(previous_skills(manifest) or [])
        for name in ("authoritative-repair-controller", "compiler-diagnostic-strategies", "same-revision-circuit-breaker"):
            if name not in names:
                names.append(name)
        return names[:24]

    def engine_guard():
        marker = PathType(g["__file__"]).resolve().with_name(ENGINE_MARKER)
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
        # This V42.41 wrapper remains in the V42.43+ call chain. Validate the
        # final installed process identity, not this module's historical
        # version, while still rejecting a genuinely stale running process.
        expected = v4240.active_process_version(g, VERSION)
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
        "V4241_VERSION": VERSION,
        "V4241_ENGINE": ENGINE,
        # Compatibility aliases used by existing launch checks.  They represent
        # the active installed release after V42.41 is loaded.
        "V4240_VERSION": VERSION,
        "V4240_ENGINE": ENGINE,
        "V4241_LEDGER_FILE": LEDGER_FILE,
        "V4241_TRACE_FILE": TRACE_FILE,
        "V4241_REPORT_FILE": REPORT_FILE,
        "_v4241_rust_compiler_candidate": rust_compiler_candidate,
        "_v4241_deterministic_component_transaction": lambda request, manifest, work, failure, component, callback=None: _deterministic_component_transaction(
            g, request, manifest, Path(work).resolve(), failure, component, callback
        ),
        "_v4237_repair_component_failure": component_repair,
        "_v429_repair_audit_round": repair_round,
        "_repair_real_validation_failure": real_repair,
        "_append_project_event": append_event,
        "_progress": progress,
        "_qwen_call": qwen_call,
        "_v36_release_identity": identity,
        "_v36_stack_skill_names": stack_skills,
        "_v4241_engine_disk_guard": engine_guard,
        # Older regression callers use this public name; it must validate the
        # active release rather than an obsolete marker.
        "_v4240_engine_disk_guard": engine_guard,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
