"""V42.67: owner-local repair transactions with compact edit transport.

This layer sits on top of V42.66. It fixes the remaining live-run bottleneck:
V42.66 narrowed the *owner label* after the connected cluster evidence had already
been collected, so a nominal one-owner repair could still prefill a multi-owner
prompt. V42.67 narrows before evidence collection, uses a compact target-only
SEARCH/REPLACE transport, and applies an explicit per-call repair class/budget.

All existing disposable-candidate, syntax/build, functional-delta, component-proof,
rollback, and protected-regression gates remain authoritative.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import jarvis_v4251_repair as transactions
import jarvis_v4259_repair as adaptive_io
import jarvis_v4265_repair as endgame

VERSION = "42.67.0"
ENGINE = "OWNER_LOCAL_COMPACT_REPAIR_FACTORY"
STRATEGY = "functional-acceptance-v24-owner-local-compact-repair"

OWNER_EVIDENCE_CHARS = max(
    24000, min(64000, int(os.getenv("JARVIS_V4267_OWNER_EVIDENCE_CHARS", "42000")))
)
RELATED_FILE_LIMIT = max(
    1, min(4, int(os.getenv("JARVIS_V4267_RELATED_FILES", "2")))
)
PROD_27B_BUDGETS = (3072, 4096, 5120, 6144)
PROD_9B_BUDGETS = (4096, 5120, 6144, 8192)
PROD_OTHER_BUDGETS = (3072, 4096, 5120, 6144)
TEST_BUDGETS = (4096, 6144, 8192, 8192, 8192, 8192)

_CALL = threading.local()

_COMPACT_SCHEMA = {
    "type": "object",
    "properties": {
        "replacements": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "replace": {"type": "string"},
                },
                "required": ["search", "replace"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["replacements"],
    "additionalProperties": False,
}


def _rows(group):
    return [row for row in ((group or {}).get("rows") or []) if isinstance(row, dict)]


def _repair_class(group) -> str:
    if any(str(row.get("kind") or "") == "functional_test_coverage" for row in _rows(group)):
        return "workflow_test"
    rel = str((group or {}).get("file") or "")
    try:
        if transactions.is_test(rel):
            return "workflow_test"
    except Exception:
        pass
    kinds = {str(x or "") for x in ((group or {}).get("kinds") or [])}
    if "functional_bridge" in kinds or "functional_runtime_state" in kinds:
        return "integration"
    return "production"


def _owner_groups(group):
    try:
        return list(transactions._owner_groups(group) or [])
    except Exception:
        return [group] if isinstance(group, dict) and group.get("file") else []


def _focus_group(group, prior_errors=None):
    """Choose one issue owner before V42.58 builds related-source evidence."""
    owners = _owner_groups(group)
    if len(owners) <= 1:
        return group
    rotate = 1 if prior_errors else 0
    owner = owners[rotate % len(owners)]
    focused = dict(owner)
    focused["file"] = str(owner.get("file") or "")
    focused["files"] = [focused["file"]]
    focused["owner_groups"] = [owner]
    focused["rows"] = list(owner.get("rows") or [])
    focused["kinds"] = list(owner.get("kinds") or [])
    focused["problems"] = list(owner.get("problems") or [])
    focused["phase"] = owner.get("phase", group.get("phase", 2))
    focused["cluster"] = False
    focused["parent_cluster_key"] = group.get("key")
    focused["key"] = str(owner.get("key") or (str(group.get("key") or "") + ":" + focused["file"]))
    return focused


def _select_evidence(evidence: dict, target: str) -> dict:
    """Target + a few highest-ranked related files, with a hard char ceiling."""
    evidence = dict(evidence or {})
    if target not in evidence:
        return evidence
    selected = {target: evidence[target]}
    total = len(str(evidence[target]))
    for rel, text in evidence.items():
        if rel == target:
            continue
        if len(selected) - 1 >= RELATED_FILE_LIMIT:
            break
        text = str(text)
        if total + len(text) > OWNER_EVIDENCE_CHARS:
            continue
        selected[rel] = text
        total += len(text)
    return selected


def _budget_for(target: str, repair_class: str, attempt: int) -> int:
    idx = max(0, min(int(attempt or 1) - 1, 5))
    if repair_class == "workflow_test":
        return TEST_BUDGETS[idx]
    low = str(target or "").lower()
    if low.startswith("27b") or "27b38" in low:
        seq = PROD_27B_BUDGETS
    elif low.startswith("9b") or "9b35" in low:
        seq = PROD_9B_BUDGETS
    else:
        seq = PROD_OTHER_BUDGETS
    return seq[min(idx, len(seq) - 1)]


def _strip_fence(raw) -> str:
    text = str(raw or "").strip().lstrip("\ufeff")
    fenced = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", text, re.I)
    return fenced.group(1).strip() if fenced else text


def _parse_compact_replacements(raw):
    """Parse compact JSON; salvage only fully decoded leading replacement objects."""
    text = _strip_fence(raw)
    try:
        obj = json.loads(text)
        if set(obj) != {"replacements"} or not isinstance(obj.get("replacements"), list):
            raise ValueError("Compact repair JSON must contain only replacements.")
        return obj
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.match(r'\s*\{\s*"replacements"\s*:\s*\[', text)
    if not match:
        raise ValueError("Invalid compact repair JSON.")
    decoder = json.JSONDecoder()
    pos, n = match.end(), len(text)
    rows = []
    while pos < n and len(rows) < 2:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos < n and text[pos] == ",":
            pos += 1
            continue
        if pos >= n or text[pos] == "]":
            break
        try:
            value, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        if not isinstance(value, dict) or set(value) != {"search", "replace"}:
            break
        rows.append(value)
        pos = end
        while pos < n and text[pos].isspace():
            pos += 1
        if pos < n and text[pos] == ",":
            pos += 1
            continue
        if pos < n and text[pos] == "]":
            break
        break
    if not rows:
        raise ValueError("Invalid compact repair JSON.")
    return {"replacements": rows}


def _compact_manifest(manifest, target: str):
    value = {}
    for key in ("build_command", "test_command", "acceptance_criteria", "requirements"):
        item = (manifest or {}).get(key)
        if item:
            value[key] = item
    comps = []
    for comp in (manifest or {}).get("components") or []:
        if not isinstance(comp, dict):
            continue
        root = str(comp.get("root") or ".").replace("\\", "/").strip("/")
        if root in {"", "."} or target.replace("\\", "/").startswith(root + "/"):
            comps.append({
                k: comp.get(k)
                for k in ("id", "root", "toolchain_adapter", "build_command", "test_command")
                if comp.get(k)
            })
    if comps:
        value["components"] = comps[:2]
    return value


def _compact_model_candidate(g, request, manifest, root, group, evidence, errors, attempt, callback):
    root = Path(root).resolve()
    target = str(group.get("file") or "")
    evidence = _select_evidence(evidence, target)
    if target not in evidence:
        raise ValueError("Focused issue owner has no complete source evidence.")
    current = str(evidence[target] or "")
    repair_class = _repair_class(group)
    raw_test = repair_class == "workflow_test" and (not (root / target).exists() or not current.strip())

    rejection = "\n".join(str(x) for x in (errors or [])[-2:])[-2400:] or "(first attempt)"
    findings = json.dumps(group.get("rows") or group.get("problems") or [], ensure_ascii=False, default=str)
    manifest_note = json.dumps(_compact_manifest(manifest or {}, target), ensure_ascii=False, default=str)

    if raw_test:
        header = "<<<JARVIS_FILE path=" + json.dumps(target, ensure_ascii=False) + ">>>"
        format_rule = (
            "Return one complete executable test only, with no Markdown or prose, between:\n"
            + header + "\n<complete source>\n<<<JARVIS_END_FILE>>>"
        )
        response_schema = None
    else:
        format_rule = (
            'Return exactly one JSON object: {"replacements":[{"search":"exact current source",'
            '"replace":"replacement"}]}. Edit ONLY the issue-owner file. Use 1-3 small disjoint '
            "SEARCH/REPLACE blocks. SEARCH must be copied exactly from CURRENT TARGET SOURCE. "
            "Do not return an edits array, file path, whole-file content, Markdown, or prose."
        )
        response_schema = _COMPACT_SCHEMA

    preamble = (
        f"V{VERSION} OWNER-LOCAL REPAIR.\n"
        + format_rule
        + "\nRepair the validator finding using the real APIs/providers/persistence visible in evidence. "
        "Preserve public APIs and unrelated behavior. Do not weaken tests, suppress diagnostics, add mocks, "
        "invent helper modules, or change production semantics merely to satisfy a test. "
        "Related files are READ-ONLY evidence in this call; a later audit will repair their own findings. "
        "A candidate is promoted only if the existing compiler/build/component and functional-delta gates prove it.\n"
        "USER REQUEST:\n" + str(request)
        + "\nREPAIR CLASS: " + repair_class
        + "\nCURRENT OWNER FINDINGS:\n" + findings
        + "\nRELEVANT BUILD/TEST CONTRACT:\n" + manifest_note
        + "\nPREVIOUS REJECTION EVIDENCE:\n" + rejection
    )

    supplied = dict(evidence)

    def build_prompt(budget):
        rendered, chosen = transactions.fit_source_prompt(
            preamble, evidence, target, max(8000, int(budget))
        )
        supplied.clear()
        supplied.update(chosen)
        return rendered

    initial = build_prompt(max(12000, OWNER_EVIDENCE_CHARS + len(preamble) + 4000))
    try:
        target_model = adaptive_io._route_target(g, f"V{VERSION} functional transaction {attempt}: {target}", "repair", initial)
    except Exception:
        target_model = ""
    requested = _budget_for(target_model, repair_class, attempt)

    _CALL.repair_class = repair_class
    _CALL.attempt = int(attempt or 1)
    _CALL.target = target
    try:
        ok, raw = g["_qwen_call"](
            initial,
            callback,
            f"V{VERSION} functional transaction {attempt}: {target}",
            profile="repair",
            max_tokens=requested,
            thinking=False,
            response_schema=response_schema,
            schema_name="v4267_compact_replacements" if response_schema else None,
            strict_output=bool(response_schema),
            prompt_builder=build_prompt,
        )
    finally:
        _CALL.repair_class = ""
        _CALL.attempt = 0
        _CALL.target = ""

    try:
        receipt = transactions.save_response(
            root, target, attempt, raw, supplied, status="received" if ok else "transport_failed"
        )
        event = g.get("_append_project_event")
        if callable(event):
            event(
                root,
                "v4267_model_response",
                "Saved owner-local compact model response.",
                file=target,
                attempt=attempt,
                repair_class=repair_class,
                evidence_files=list(supplied),
                evidence_chars=sum(len(str(v)) for v in supplied.values()),
                diagnostic=str(receipt.relative_to(root)),
                transport=getattr(raw, "metadata", {}),
            )
    except OSError:
        pass

    if not ok:
        raise ValueError("Model call failed: " + str(raw)[-1800:])

    if raw_test:
        content = transactions.parse_source_file(raw, target)
        if not content.strip():
            raise ValueError("Generated workflow test was empty.")
        return {target: content}

    obj = _parse_compact_replacements(raw)
    replacements = obj.get("replacements")
    replacements = transactions._scoped_replacements(group, current, replacements)
    replacements = transactions._applicable_replacements(current, replacements)
    if not replacements:
        raise ValueError(
            "All compact owner hunks were stale or outside validator-owned scope; use current-source locators."
        )
    content = transactions._apply(current, replacements)
    if content == current:
        raise ValueError("Compact repair made no source change.")
    return {target: content}


def install(g: dict[str, Any]):
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_repair_transaction = transactions.repair_transaction
    previous_model_candidate = transactions._model_candidate
    previous_adaptive_output = adaptive_io._adaptive_functional_output

    transactions.MAX_CHARS = min(int(getattr(transactions, "MAX_CHARS", OWNER_EVIDENCE_CHARS)), OWNER_EVIDENCE_CHARS)

    def repair_transaction(g2, request, manifest, root, group, callback=None, prior_errors=None):
        focused = _focus_group(group, prior_errors)
        try:
            g2["_progress"](
                callback,
                f"V{VERSION} owner-local repair: {focused.get('file')} "
                f"(evidence cap {transactions.MAX_CHARS:,} chars)",
                stage=f"V{VERSION} owner-local compact repair",
                percent=92,
                issue_owner_focus=1,
                original_connected_owners=len(_owner_groups(group)),
                repair_class=_repair_class(focused),
            )
        except Exception:
            pass
        return previous_repair_transaction(
            g2, request, manifest, root, focused, callback, prior_errors
        )

    def adaptive_output(g2, prompt, stage, profile, requested=None):
        budget, target, owners, findings = previous_adaptive_output(
            g2, prompt, stage, profile, requested
        )
        repair_class = str(getattr(_CALL, "repair_class", "") or "production")
        attempt = int(getattr(_CALL, "attempt", 1) or 1)
        cap = _budget_for(target, repair_class, attempt)
        try:
            explicit = int(requested or 0)
        except Exception:
            explicit = 0
        if explicit > 0:
            cap = min(cap, explicit)
        return max(1024, min(int(budget), int(cap))), target, 1, min(int(findings or 1), 1)

    def model_candidate(g2, request, manifest, root, group, evidence, errors, attempt, callback):
        text = "\n".join(str(x) for x in (errors or [])[-3:]).lower()
        cross_file_needed = any(token in text for token in (
            "did not strictly improve",
            "scope_expansion_required",
            "out-of-scope",
            "component proof",
            "introduced new functional debt",
        ))
        if int(attempt or 1) >= 3 and cross_file_needed:
            _CALL.repair_class = _repair_class(group)
            _CALL.attempt = int(attempt or 1)
            _CALL.target = str(group.get("file") or "")
            try:
                return previous_model_candidate(
                    g2, request, manifest, root, group, evidence, errors, attempt, callback
                )
            finally:
                _CALL.repair_class = ""
                _CALL.attempt = 0
                _CALL.target = ""
        return _compact_model_candidate(
            g2, request, manifest, root, group, evidence, errors, attempt, callback
        )

    transactions._model_candidate = model_candidate
    transactions.repair_transaction = repair_transaction
    adaptive_io._adaptive_functional_output = adaptive_output

    if callable(g.get("_copy_resume_workspace")):
        def copy_project_for_candidate_validation(work):
            source = Path(work).resolve()
            temp = tempfile.TemporaryDirectory(prefix="jarvis_candidate_")
            clone = Path(temp.name) / "project"
            try:
                g["_copy_resume_workspace"](source, clone)
            except Exception:
                temp.cleanup()
                raise
            return temp, clone
        g["_copy_project_for_candidate_validation"] = copy_project_for_candidate_validation

    previous_audit = g.get("_v429_whole_project_audit")
    if callable(previous_audit):
        def audit(root, request, manifest, run_components=True, progress_callback=None):
            try:
                endgame._sync_test_commands(g, root, manifest)
            except Exception:
                pass
            value = previous_audit(
                root, request, manifest,
                run_components=run_components,
                progress_callback=progress_callback,
            )
            required = {
                str(row.get("component") or "")
                for row in (value or {}).get("issues") or []
                if isinstance(row, dict)
                and str(row.get("kind") or "") == "functional_test_coverage"
                and str(row.get("component") or "")
            }
            try:
                restored = endgame._sync_test_commands(g, root, manifest, required)
            except Exception:
                restored = []
            if restored:
                value = previous_audit(
                    root, request, manifest,
                    run_components=run_components,
                    progress_callback=progress_callback,
                )
            return value
        g["_v429_whole_project_audit"] = audit

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r"jarvis_v42(?:4[0-9]|5[0-9]|6[0-6])_repair", name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass
            if hasattr(module, "STRATEGY"):
                module.STRATEGY = STRATEGY
            if hasattr(module, "STRATEGY_GENERATION"):
                module.STRATEGY_GENERATION = STRATEGY

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r"V42\.\d+(?:\.\d+)?(?!\d)", "V" + VERSION, str(text))
        fields = dict(fields)
        fields["engine_version"] = "V" + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version="V" + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode="owner-local-compact-repair-v42.67",
            v4261_connected_scheduler_preserved=True,
            owner_focus_happens_before_evidence_collection=True,
            model_issue_owner_focus=1,
            owner_evidence_char_cap=transactions.MAX_CHARS,
            related_file_limit=RELATED_FILE_LIMIT,
            compact_target_only_search_replace_transport=True,
            explicit_repair_class=True,
            production_27b_first_budget=PROD_27B_BUDGETS[0],
            production_27b_max_budget=PROD_27B_BUDGETS[-1],
            workflow_test_budget_max=max(TEST_BUDGETS),
            malformed_compact_prefix_salvage=True,
            bounded_cross_file_fallback=True,
            v4265_source_only_candidate_clone=True,
            v4265_test_command_recovery=True,
            candidate_validation_gate_preserved=True,
            compiler_and_functional_gates_preserved=True,
            protected_regression_gate_preserved=True,
            rejected_candidate_source_never_promoted=True,
            manual_model_selection_strict_lock=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4267_VERSION=VERSION,
        V4267_ENGINE=ENGINE,
    )
    try:
        Path(
            g.get("JARVIS_DIR") or Path(__file__).resolve().parent,
            "JARVIS_ACTIVE_ENGINE.txt",
        ).write_text("V" + VERSION + "\n", encoding="utf-8")
    except OSError:
        pass
