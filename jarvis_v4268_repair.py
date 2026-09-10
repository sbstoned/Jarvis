"""V42.68: tool-using repair sessions with durable project memory.

V42.67 fixed prompt size and owner selection. V42.68 changes the repair interaction
itself: the local model works inside one disposable candidate workspace using bounded
read/search/reference/edit/diagnose tools, while Jarvis persists issue history and
compiler feedback across trials. Existing accepted source is still promoted only by
the V42.51+ functional-delta, component-proof and regression gates.

The model never receives arbitrary shell access. All tools are host-controlled and
confined to the candidate project. Existing files are edited with exact SEARCH/REPLACE
hunks; whole-file rewrites are rejected for nontrivial existing files.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any

import jarvis_v4251_repair as transactions
import jarvis_v4250_repair as gates
import jarvis_v4259_repair as adaptive_io
import jarvis_v4267_repair as owner_local
from jarvis_workflow_contracts import is_test

VERSION = "42.68.0"
ENGINE = "TOOL_USING_MEMORY_REPAIR_FACTORY"
STRATEGY = "functional-acceptance-v25-tool-using-memory-repair"

MAX_TOOL_STEPS = max(3, min(10, int(os.getenv("JARVIS_V4268_TOOL_STEPS", "7"))))
MAX_EDIT_ROUNDS = max(2, min(5, int(os.getenv("JARVIS_V4268_EDIT_ROUNDS", "3"))))
MAX_INSPECTION_STEPS = max(1, min(4, int(os.getenv("JARVIS_V4268_INSPECTION_STEPS", "2"))))
MAX_TOOL_RESULT_CHARS = max(2500, min(12000, int(os.getenv("JARVIS_V4268_TOOL_RESULT_CHARS", "6500"))))
MAX_TRANSCRIPT_CHARS = max(6000, min(30000, int(os.getenv("JARVIS_V4268_TRANSCRIPT_CHARS", "16000"))))
MAX_MEMORY_EVENTS = max(3, min(20, int(os.getenv("JARVIS_V4268_MEMORY_EVENTS", "8"))))
WHOLE_FILE_REWRITE_RATIO = max(0.55, min(0.95, float(os.getenv("JARVIS_V4268_WHOLE_FILE_RATIO", "0.86"))))
MEMORY_DIR = ".jarvis_memory"
MEMORY_DB = "project_memory.sqlite3"
MAX_SESSION_FILES = 3  # Primary owner plus two validator-proven dependencies.

_SESSION = threading.local()

_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["edit", "search", "view", "references", "symbol", "diagnose"],
        },
        "query": {"type": "string"},
        "path": {"type": "string"},
        "symbol": {"type": "string"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
        "replacements": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "search": {"type": "string"},
                    "replace": {"type": "string"},
                },
                "required": ["search", "replace"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _memory_container(root):
    root = Path(root).resolve()
    # generated_projects/.../<job>/trial_01 and trial_02 share one durable repair DB.
    # A portable snapshot is also written into each trial for checkpoint ZIPs.
    if re.fullmatch(r"trial_\d+", root.name, re.I):
        return root.parent
    return root


def _memory_path(root):
    path = _memory_container(root) / MEMORY_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / MEMORY_DB


def _portable_memory_path(root):
    path = Path(root).resolve() / MEMORY_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / "repair_memory.json"


def _memory_connect(root):
    db = sqlite3.connect(str(_memory_path(root)), timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute(
        """CREATE TABLE IF NOT EXISTS repair_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            target TEXT NOT NULL,
            issue_key TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            event_type TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 0,
            step INTEGER NOT NULL DEFAULT 0,
            accepted INTEGER NOT NULL DEFAULT 0,
            details TEXT NOT NULL DEFAULT ''
        )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_repair_events_target ON repair_events(target, id DESC)"
    )
    db.commit()
    return db


def _source_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()[:20]


def _issue_key(group):
    rows = []
    for row in (group or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "file": str(row.get("file") or ""),
                "kind": str(row.get("kind") or ""),
                "problem": str(row.get("problem") or ""),
            }
        )
    payload = {
        "file": str((group or {}).get("file") or ""),
        "rows": rows,
        "kinds": sorted(str(x or "") for x in ((group or {}).get("kinds") or [])),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def _write_portable_memory(root):
    """Keep a bounded JSON snapshot inside the trial so checkpoints carry repair memory."""
    try:
        with _memory_connect(root) as db:
            rows = db.execute(
                """SELECT created_at,target,issue_key,source_hash,event_type,attempt,step,accepted,details
                   FROM repair_events ORDER BY id DESC LIMIT 80"""
            ).fetchall()
        payload = [
            {
                "created_at": row[0], "target": row[1], "issue_key": row[2],
                "source_hash": row[3], "event_type": row[4], "attempt": row[5],
                "step": row[6], "accepted": bool(row[7]), "details": row[8],
            }
            for row in reversed(rows)
        ]
        path = _portable_memory_path(root)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"version": VERSION, "events": payload}, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except Exception:
        pass


def _restore_portable_memory(root):
    """Seed a new job DB from a checkpoint-carried memory snapshot when available."""
    portable = _portable_memory_path(root)
    if not portable.exists():
        return
    try:
        data = json.loads(portable.read_text(encoding="utf-8-sig"))
        events = data.get("events") if isinstance(data, dict) else []
        if not isinstance(events, list) or not events:
            return
        with _memory_connect(root) as db:
            count = int(db.execute("SELECT COUNT(*) FROM repair_events").fetchone()[0])
            if count:
                return
            for row in events[-80:]:
                if not isinstance(row, dict):
                    continue
                db.execute(
                    """INSERT INTO repair_events
                       (created_at,target,issue_key,source_hash,event_type,attempt,step,accepted,details)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        str(row.get("created_at") or _now()),
                        str(row.get("target") or ""),
                        str(row.get("issue_key") or ""),
                        str(row.get("source_hash") or ""),
                        str(row.get("event_type") or "restored"),
                        int(row.get("attempt") or 0),
                        int(row.get("step") or 0),
                        1 if row.get("accepted") else 0,
                        str(row.get("details") or "")[-8000:],
                    ),
                )
            db.commit()
    except Exception:
        pass


def _remember(root, target, group, source, event_type, details="", attempt=0, step=0, accepted=False):
    try:
        _restore_portable_memory(root)
        compact = str(details or "")
        if len(compact) > 8000:
            compact = compact[-8000:]
        with _memory_connect(root) as db:
            db.execute(
                """INSERT INTO repair_events
                   (created_at,target,issue_key,source_hash,event_type,attempt,step,accepted,details)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    _now(),
                    str(target),
                    _issue_key(group),
                    _source_hash(source),
                    str(event_type),
                    int(attempt or 0),
                    int(step or 0),
                    1 if accepted else 0,
                    compact,
                ),
            )
        _write_portable_memory(root)
    except Exception:
        pass


def _memory_summary(root, target, group, source, limit=MAX_MEMORY_EVENTS):
    try:
        _restore_portable_memory(root)
        with _memory_connect(root) as db:
            rows = db.execute(
                """SELECT created_at,event_type,attempt,step,accepted,source_hash,details
                   FROM repair_events WHERE target=? ORDER BY id DESC LIMIT ?""",
                (str(target), int(limit)),
            ).fetchall()
    except Exception:
        return "(no durable repair memory available)"
    if not rows:
        return "(no previous repair events for this target)"
    current_hash = _source_hash(source)
    out = []
    for created, event_type, attempt, step, accepted, src_hash, details in reversed(rows):
        relation = "current-source" if src_hash == current_hash else "earlier-source"
        text = re.sub(r"\s+", " ", str(details or "")).strip()
        if len(text) > 1400:
            text = text[-1400:]
        out.append(
            f"{created} [{relation}] {event_type} attempt={attempt} step={step} "
            f"accepted={bool(accepted)} :: {text}"
        )
    return "\n".join(out)


def _safe_tool_path(root, rel):
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel or rel.startswith(".jarvis"):
        return None
    try:
        if not transactions._safe_path(root, rel):
            return None
    except Exception:
        return None
    path = (Path(root).resolve() / rel).resolve()
    if any(part in transactions.SKIP for part in path.relative_to(Path(root).resolve()).parts):
        return None
    try:
        if transactions._IS_SENSITIVE(rel):
            return None
    except Exception:
        pass
    if not path.is_file() or path.stat().st_size > 180000:
        return None
    return path


def _view_file(root, rel, start_line=1, end_line=220):
    path = _safe_tool_path(root, rel)
    if path is None:
        return f"VIEW DENIED OR NOT FOUND: {rel}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(start_line or 1))
    end = max(start, min(len(lines), int(end_line or start + 219)))
    body = "\n".join(f"{n:>5}: {lines[n-1]}" for n in range(start, end + 1))
    return f"FILE {rel} lines {start}-{end} of {len(lines)}\n{body}"


def _repo_search(root, query, limit=18):
    query = str(query or "").strip()
    if not query:
        return "SEARCH needs a nonempty query."
    terms = [x for x in re.findall(r"[A-Za-z_][A-Za-z_0-9]{1,}", query) if len(x) >= 2]
    needle = query.lower()
    matches = []
    try:
        items = transactions.source_files(root)
    except Exception:
        items = []
    for rel, text in items:
        lines = str(text).splitlines()
        for i, line in enumerate(lines, 1):
            low = line.lower()
            score = (8 if needle in low else 0) + sum(1 for term in terms if term.lower() in low)
            if score:
                matches.append((score, rel, i, line.strip()))
    matches.sort(key=lambda item: (-item[0], item[1], item[2]))
    if not matches:
        return f"SEARCH {query!r}: no authored-source matches."
    return "\n".join(
        f"{rel}:{line_no}: {line[:300]}" for _, rel, line_no, line in matches[: int(limit)]
    )


def _references(root, symbol, limit=24):
    symbol = str(symbol or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", symbol):
        return "REFERENCES needs one identifier."
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    rows = []
    try:
        items = transactions.source_files(root)
    except Exception:
        items = []
    for rel, text in items:
        for i, line in enumerate(str(text).splitlines(), 1):
            if pattern.search(line):
                rows.append((rel, i, line.strip()))
                if len(rows) >= int(limit):
                    break
        if len(rows) >= int(limit):
            break
    if not rows:
        return f"REFERENCES {symbol}: none found in authored source."
    return "\n".join(f"{rel}:{line_no}: {line[:300]}" for rel, line_no, line in rows)


def _symbol_definition(root, symbol, limit=12):
    symbol = str(symbol or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", symbol):
        return "SYMBOL needs one identifier."
    escaped = re.escape(symbol)
    patterns = [
        re.compile(rf"\b(?:def|class|function|fn|struct|enum|trait|interface|type)\s+{escaped}\b"),
        re.compile(rf"\b(?:const|let|var|static)\s+{escaped}\b"),
        re.compile(rf"\b{escaped}\s*[:=]\s*(?:async\s*)?(?:\(|function\b)"),
    ]
    rows = []
    try:
        items = transactions.source_files(root)
    except Exception:
        items = []
    for rel, text in items:
        for i, line in enumerate(str(text).splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                rows.append((rel, i, line.strip()))
                if len(rows) >= int(limit):
                    break
        if len(rows) >= int(limit):
            break
    if not rows:
        return f"SYMBOL {symbol}: no obvious declaration found."
    return "\n".join(f"{rel}:{line_no}: {line[:350]}" for rel, line_no, line in rows)


def _identifiers(text):
    return set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]{2,}\b", str(text or "")))


def _local_binding_sets(text):
    text = str(text or "")
    declared = set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z_0-9]*)", text))
    for body in re.findall(r"\b(?:const|let|var)\s*\{([^{}]{1,600})\}\s*=", text):
        for raw in body.split(","):
            raw = raw.strip()
            if not raw or raw.startswith("..."):
                raw = raw[3:].strip()
            # {source: alias = default} -> alias, {name = default} -> name
            raw = raw.split("=", 1)[0].strip()
            if ":" in raw:
                raw = raw.rsplit(":", 1)[-1].strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", raw):
                declared.add(raw)
    return declared


def _local_closure_errors(rel, before, after):
    """Cheap lexical closure checks; compiler/language adapters remain authoritative."""
    suffix = Path(str(rel)).suffix.lower()
    if suffix not in {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}:
        return []
    before_bindings = _local_binding_sets(before)
    after_bindings = _local_binding_sets(after)
    errors = []
    for name in sorted(after_bindings):
        if name.startswith("_"):
            continue
        if len(re.findall(r"\b" + re.escape(name) + r"\b", str(after))) <= 1:
            errors.append(f"local closure: binding {name!r} is declared/destructured but never used")
    for name in sorted(before_bindings - after_bindings):
        if re.search(r"\b" + re.escape(name) + r"\b", str(after)):
            errors.append(
                f"local closure: old local binding {name!r} was removed but references to it remain"
            )
    return errors[:12]


def _changed_identifier_map(before, after, root):
    old_ids, new_ids = _identifiers(before), _identifiers(after)
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    rows = []
    for name in (added[:8] + removed[:8]):
        refs = _references(root, name, limit=6)
        rows.append(("ADDED" if name in added else "REMOVED") + f" {name}\n{refs}")
    return "\n\n".join(rows) or "(no identifier additions/removals detected)"


def _compact_diff(before, after, rel, limit=7000):
    diff = "\n".join(
        difflib.unified_diff(
            str(before).splitlines(),
            str(after).splitlines(),
            fromfile=rel + ":before",
            tofile=rel + ":draft",
            lineterm="",
            n=3,
        )
    )
    if len(diff) > int(limit):
        diff = diff[: int(limit)] + "\n...<diff truncated>"
    return diff or "(no diff)"


def _whole_file_rewrite_error(source, replacements):
    if len(str(source)) < 3000:
        return ""
    limit = int(len(str(source)) * WHOLE_FILE_REWRITE_RATIO)
    for block in replacements or []:
        search = str((block or {}).get("search") or "")
        if len(search) >= limit:
            return (
                "Existing nontrivial files must not be rewritten wholesale. "
                "Patch the smallest coherent function/method/region needed for closure."
            )
    return ""


def _parse_action(raw):
    text = owner_local._strip_fence(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid tool action JSON: {exc}") from exc
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("Tool action must be one JSON object with action.")
    if set(obj) - set(_TOOL_SCHEMA["properties"]):
        raise ValueError("Tool action contains unsupported fields.")
    return obj


def _contract(root, target, group, source, evidence, manifest, prior_errors):
    findings = json.dumps(
        (group or {}).get("rows") or (group or {}).get("problems") or [],
        ensure_ascii=False,
        default=str,
    )
    hints = transactions._scope_hints(group, source)
    names = []
    for token in re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}", findings + "\n" + hints):
        if token not in names and token not in transactions.STOP:
            names.append(token)
    reference_map = []
    for name in names[:8]:
        reference_map.append(f"## {name}\n{_references(root, name, limit=5)}")
    related = []
    for rel, text in evidence.items():
        if rel == target:
            continue
        excerpt = str(text)
        if len(excerpt) > 7000:
            excerpt = excerpt[:7000] + "\n...<related source truncated>"
        related.append(f"<<<RELATED path={rel}>>>\n{excerpt}\n<<<END RELATED>>>")
    manifest_note = owner_local._compact_manifest(manifest or {}, target)
    previous = "\n".join(str(x) for x in (prior_errors or [])[-4:])[-5500:] or "(none)"
    return (
        "REPAIR CONTRACT\n"
        f"OWNER: {target}\n"
        f"REPAIR CLASS: {owner_local._repair_class(group)}\n"
        f"VALIDATOR FINDINGS:\n{findings}\n"
        f"VALIDATOR-OWNED LOCATORS:\n{hints}\n"
        f"BUILD/TEST CONTRACT:\n{json.dumps(manifest_note, ensure_ascii=False, default=str)}\n"
        "INVARIANTS:\n"
        "- preserve the target's public API unless the requirement explicitly demands a change\n"
        "- use real providers/persistence/runtime APIs proven by project source\n"
        "- if a binding/import/declaration is removed, resolve every dependent reference in the same coherent edit\n"
        "- do not introduce an import/destructured binding unless the resulting code uses it\n"
        "- edit the smallest coherent function/method/region; do not rewrite an existing whole file\n"
        "- do not weaken tests, suppress diagnostics, add mocks, or invent unsupplied production APIs\n"
        "- only the disposable candidate workspace may be edited; accepted source is committed by Jarvis after proof\n"
        f"PREVIOUS OUTER REJECTION EVIDENCE:\n{previous}\n"
        "SYMBOL/REFERENCE MAP:\n" + ("\n".join(reference_map) or "(no specific symbols extracted)") + "\n"
        "RELATED READ-ONLY SOURCE:\n" + ("\n".join(related) or "(none)")
    )


def _quick_diagnostics(g, clone, manifest, target, before, draft):
    errors = []
    errors.extend(_local_closure_errors(target, before, draft))
    content_gate = g.get("_content_validation_error")
    if callable(content_gate):
        try:
            error = content_gate(target, draft)
            if error:
                errors.append("content validation: " + str(error)[-3500:])
        except Exception as exc:
            errors.append("content validation tool error: " + str(exc)[-1000:])
    try:
        error = gates._syntax_candidate_error(g, clone, manifest, target, draft)
        if error:
            errors.append("native/static diagnostics: " + str(error)[-5000:])
    except Exception as exc:
        errors.append("diagnostic adapter error: " + str(exc)[-1800:])
    semantic = g.get("_v4221_semantic_role_error")
    if callable(semantic):
        try:
            error = semantic(clone, manifest, target, draft)
            if error:
                errors.append("semantic role diagnostics: " + str(error)[-3500:])
        except Exception as exc:
            errors.append("semantic diagnostic tool error: " + str(exc)[-1000:])
    return errors[:16]


def _functional_preflight(root, clone, request, manifest, group):
    """Run Jarvis's own functional debt detector before ending the model session."""
    _SESSION.functional_blockers = []
    try:
        delta = transactions._cluster_functional_delta(
            Path(root).resolve(), Path(clone).resolve(), str(request), manifest or {}, group
        )
    except Exception as exc:
        return ["functional preflight tool error: " + str(exc)[-1800:]]
    added = transactions._new_functional_debt(delta)
    _SESSION.functional_blockers = added
    new_debt_errors = []
    if added:
        new_debt_errors = [
            "Candidate introduced new functional debt. Repair these dependencies in the SAME disposable "
            "candidate before requesting promotion; keep the useful caller draft:\n"
            + json.dumps(added, ensure_ascii=False, default=str)[:5500]
        ]
    if delta.get("improved"):
        return new_debt_errors
    owner_set = set(transactions._cluster_owner_files(group))
    after_rows = [
        row for row in (delta.get("after") or [])
        if isinstance(row, dict) and str(row.get("file") or "") in owner_set
    ] + new_debt_errors
    payload = after_rows or {
        "before_owned": delta.get("before_owned"),
        "after_owned": delta.get("after_owned"),
        "owner_before": delta.get("owner_before"),
        "owner_after": delta.get("owner_after"),
    }
    return [
        "functional preflight: candidate is statically clean but does not yet reduce the owned functional debt. "
        + json.dumps(payload, ensure_ascii=False, default=str)[:4500]
    ]


def _enroll_dependencies(root, clone, rows, manifest, evidence, originals, drafts, groups):
    """Only live validator findings can authorize another existing authored file.

    Complete original source is registered with the outer transaction before an
    edit is allowed. Neither a model-supplied path nor related-source ranking is
    sufficient to expand write scope.
    """
    candidates = {str(row.get('file') or '').replace('\\', '/') for row in rows if isinstance(row, dict)}
    if not candidates - set(drafts):
        return []
    declared = [item.get('path', '') if isinstance(item, dict) else item
                for item in (manifest or {}).get('files', [])]
    available = dict(transactions.source_files(root, declared))
    enrolled = []
    for rel in sorted(candidates - set(drafts)):
        if len(drafts) >= MAX_SESSION_FILES:
            break
        if (rel not in available or not transactions._safe_path(root, rel)
                or not transactions._safe_path(clone, rel)):
            continue
        accepted = _safe_tool_path(root, rel)
        candidate = _safe_tool_path(clone, rel)
        if accepted is None or candidate is None:
            continue
        original = available[rel]
        if candidate.read_text(encoding='utf-8', errors='replace') != original:
            raise ValueError('Dependency source changed since the candidate was cloned: ' + rel)
        owned = [row for row in rows if str(row.get('file') or '').replace('\\', '/') == rel]
        groups[rel] = {'file': rel, 'rows': owned,
                       'kinds': sorted({str(row.get('kind') or '') for row in owned}),
                       'problems': [str(row.get('problem') or '') for row in owned]}
        evidence[rel] = original
        originals[rel] = original
        drafts[rel] = original
        enrolled.append(rel)
    return enrolled


def _session_diagnostics(g, root, clone, request, manifest, group, target, before, draft,
                         originals=None, drafts=None):
    functional = _functional_preflight(root, clone, request, manifest, group)
    # Run cheap syntax/content checks while a connected operation is incomplete.
    # Once dependency closure is reached, real compiler/test proof runs in-session.
    _SESSION.defer_component_proof = bool(functional)
    _SESSION.failed_target = target
    try:
        errors = list(_quick_diagnostics(g, clone, manifest, target, before, draft) or []) + functional
        integrity = transactions._test_integrity_error(target, (originals or {}).get(target, before), draft)
        if integrity:
            errors.append(integrity)
        # A connected edit can cross compiler boundaries. Feed failures from
        # EVERY changed component back into this session before returning it.
        if not errors:
            for rel, text in (drafts or {}).items():
                original = (originals or {}).get(rel, text)
                if rel == target or text == original:
                    continue
                errors = list(_quick_diagnostics(g, clone, manifest, rel, original, text) or [])
                if errors:
                    _SESSION.failed_target = rel
                    break
        return errors
    finally:
        _SESSION.defer_component_proof = False


def _tool_result(action, root, clone, target, draft, obj):
    kind = str(obj.get("action") or "")
    if kind == "search":
        return _repo_search(root, obj.get("query"))
    if kind == "view":
        rel = str(obj.get("path") or target)
        # The current target view reflects the in-memory candidate, not accepted source.
        if rel.replace("\\", "/") == target.replace("\\", "/"):
            lines = str(draft).splitlines()
            start = max(1, int(obj.get("start_line") or 1))
            end = max(start, min(len(lines), int(obj.get("end_line") or start + 219)))
            return (
                f"CANDIDATE FILE {target} lines {start}-{end} of {len(lines)}\n"
                + "\n".join(f"{n:>5}: {lines[n-1]}" for n in range(start, end + 1))
            )
        return _view_file(root, rel, obj.get("start_line") or 1, obj.get("end_line") or 220)
    if kind == "references":
        return _references(root, obj.get("symbol"))
    if kind == "symbol":
        return _symbol_definition(root, obj.get("symbol"))
    return ""


def _progress(g, callback, text, **fields):
    try:
        g["_progress"](
            callback,
            text,
            stage=f"V{VERSION} tool-using repair session",
            percent=92,
            **fields,
        )
    except Exception:
        pass


def _agent_model_candidate(g, request, manifest, root, group, evidence, errors, attempt, callback, fallback):
    root = Path(root).resolve()
    target = str(group.get("file") or "")
    if not target or target not in evidence:
        return fallback(g, request, manifest, root, group, evidence, errors, attempt, callback)

    source = str(evidence[target] or "")
    # New workflow tests still use the proven raw-file endgame path.
    if is_test(target) and (not (root / target).exists() or not source.strip()):
        return fallback(g, request, manifest, root, group, evidence, errors, attempt, callback)

    clone = Path(getattr(_SESSION, "clone", "") or "")
    if not clone or not clone.exists():
        return fallback(g, request, manifest, root, group, evidence, errors, attempt, callback)

    primary = target
    originals = {target: source}
    drafts = {target: source}
    groups = {target: group}
    draft = source
    transcript = []
    inspection_steps = 0
    edit_rounds = 0
    last_diagnostics = list(errors or [])[-3:]
    _SESSION.last_target = target

    _remember(
        root, target, group, source, "session_started",
        f"repair_class={owner_local._repair_class(group)} dependency_closure=True",
        attempt=attempt,
    )

    for step in range(1, MAX_TOOL_STEPS + 1):
        from jarvis_v4240_repair import _STOP_EVENT, ProjectStopRequested
        if _STOP_EVENT.is_set():
            raise ProjectStopRequested('Stop requested inside a connected repair session.')
        if edit_rounds >= MAX_EDIT_ROUNDS:
            break
        source, draft = originals[target], drafts[target]
        current_group = groups[target]
        related = transactions.related_sources(clone, target, manifest)
        # Keep already edited callers visible while repairing their providers.
        related = {target: draft, **{rel: text for rel, text in drafts.items() if rel != target},
                   **{rel: text for rel, text in related.items() if rel not in drafts}}
        context = owner_local._select_evidence(related, target)
        contract = _contract(clone, target, current_group, source, context, manifest, errors)
        durable = _memory_summary(root, target, current_group, source)
        transcript_text = "\n\n".join(transcript)
        if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
            transcript_text = transcript_text[-MAX_TRANSCRIPT_CHARS:]
        prompt = (
            f"V{VERSION} TOOL-USING REPAIR SESSION. Stay on this issue until the candidate is statically clean.\n"
            "You have host-controlled tools: search, view, references, symbol, edit, diagnose.\n"
            "Use search/view/references/symbol only when the preloaded contract does not prove what you need.\n"
            "EDIT RULE: action=edit must contain exact SEARCH/REPLACE hunks against CURRENT CANDIDATE SOURCE. "
            "Patch the smallest coherent function/method/region. Never return whole-file content. "
            "After every edit Jarvis automatically writes only the disposable candidate and runs immediate diagnostics. "
            "If diagnostics fail, fix those diagnostics in the SAME repair session rather than starting over.\n"
            "SEARCH/VIEW are read-only. You cannot run arbitrary shell commands. "
            "Edit only the CURRENT target. To revisit another authorized file, view its path first. "
            "Only Jarvis's live validator may authorize a dependency file; naming a file does not authorize it.\n"
            f"AUTHORIZED CANDIDATE FILES: {', '.join(drafts)}\n\n"
            f"{contract}\n\n"
            "DURABLE PROJECT REPAIR MEMORY (previous trials/restarts):\n"
            f"{durable}\n\n"
            "CURRENT CANDIDATE SOURCE:\n"
            f"<<<CURRENT path={target}>>>\n{draft}\n<<<END CURRENT>>>\n\n"
            "SESSION TOOL RESULTS / DIAGNOSTICS:\n"
            f"{transcript_text or '(none yet)'}\n\n"
            "Return exactly one JSON tool action."
        )

        try:
            model_target = adaptive_io._route_target(
                g, f"V{VERSION} repair tool step {step}: {target}", "repair", prompt
            )
        except Exception:
            model_target = ""
        budget = min(
            owner_local._budget_for(model_target, owner_local._repair_class(current_group), max(1, edit_rounds + 1)),
            4096 if edit_rounds else 3072,
        )

        owner_local._CALL.repair_class = owner_local._repair_class(current_group)
        owner_local._CALL.attempt = max(1, edit_rounds + 1)
        owner_local._CALL.target = target
        try:
            _progress(
                g, callback,
                f"V{VERSION} repair session step {step}: {target} "
                f"(edit round {edit_rounds + 1}/{MAX_EDIT_ROUNDS})",
                repair_session_step=step,
                repair_edit_round=edit_rounds,
                issue_owner=target,
            )
            ok, raw = g["_qwen_call"](
                prompt,
                callback,
                f"V{VERSION} repair tool step {step}: {target}",
                profile="repair",
                max_tokens=budget,
                thinking=False,
                response_schema=_TOOL_SCHEMA,
                schema_name="v4268_repair_tool_action",
                strict_output=True,
            )
        finally:
            owner_local._CALL.repair_class = ""
            owner_local._CALL.attempt = 0
            owner_local._CALL.target = ""

        try:
            transactions.save_response(
                root,
                target,
                int(attempt) * 100 + step,
                raw,
                {target: draft},
                status="received" if ok else "transport_failed",
            )
        except Exception:
            pass
        if not ok:
            raise ValueError("V42.68 tool model call failed: " + str(raw)[-1800:])

        obj = _parse_action(raw)
        action = str(obj.get("action") or "")
        _remember(root, target, group, source, "tool_action", json.dumps(obj, ensure_ascii=False)[:5000], attempt, step)

        if action in {"search", "view", "references", "symbol"}:
            focus = str(obj.get('path') or '').replace('\\', '/')
            if action == 'view' and focus in drafts and focus != target:
                target = focus
                result = 'Focus changed to authorized candidate file ' + target + '; complete current source follows in the next prompt.'
            elif inspection_steps >= MAX_INSPECTION_STEPS:
                result = (
                    "Inspection budget reached. Use the supplied contract/current source and make the smallest coherent edit now."
                )
            else:
                result = _tool_result(action, clone, clone, target, draft, obj)
                inspection_steps += 1
            result = str(result)[:MAX_TOOL_RESULT_CHARS]
            transcript.append(f"TOOL {action.upper()} RESULT:\n{result}")
            continue

        if action == "diagnose":
            (clone / target).parent.mkdir(parents=True, exist_ok=True)
            (clone / target).write_text(draft, encoding="utf-8")
            diagnostics = _session_diagnostics(g, root, clone, request, manifest, group, target, source, draft, originals, drafts)
            result = "\n".join(diagnostics) if diagnostics else "Diagnostics are clean. Make/finish the necessary functional edit."
            transcript.append("DIAGNOSTICS:\n" + result[-MAX_TOOL_RESULT_CHARS:])
            _remember(root, target, group, source, "diagnostics", result, attempt, step)
            last_diagnostics = diagnostics
            continue

        if action != "edit":
            transcript.append("TOOL ERROR: unsupported action; choose search/view/references/symbol/edit/diagnose.")
            continue

        if str(obj.get('path') or target).replace('\\', '/') != target:
            transcript.append('EDIT REJECTED: path must match CURRENT target; view an authorized file first to change focus.')
            edit_rounds += 1
            continue
        replacements = obj.get("replacements")
        if not isinstance(replacements, list) or not replacements:
            transcript.append("EDIT REJECTED: edit action needs one or more exact SEARCH/REPLACE hunks.")
            continue
        whole = _whole_file_rewrite_error(draft, replacements)
        if whole:
            transcript.append("EDIT REJECTED: " + whole)
            _remember(root, target, group, source, "edit_rejected", whole, attempt, step)
            edit_rounds += 1
            continue
        try:
            replacements = transactions._scoped_replacements(current_group, draft, replacements)
            replacements = transactions._applicable_replacements(draft, replacements)
            if not replacements:
                raise ValueError("No exact in-scope hunks remain; SEARCH must match CURRENT CANDIDATE SOURCE exactly once.")
            new_draft = transactions._apply(draft, replacements)
        except Exception as exc:
            message = "EDIT REJECTED: " + str(exc)[-2500:]
            transcript.append(message)
            _remember(root, target, group, source, "edit_rejected", message, attempt, step)
            edit_rounds += 1
            continue

        if new_draft == draft:
            transcript.append("EDIT REJECTED: candidate did not change.")
            edit_rounds += 1
            continue

        (clone / target).parent.mkdir(parents=True, exist_ok=True)
        (clone / target).write_text(new_draft, encoding="utf-8")
        drafts[target] = new_draft
        diagnostics = _session_diagnostics(g, root, clone, request, manifest, group, target, draft, new_draft, originals, drafts)
        blockers = list(getattr(_SESSION, 'functional_blockers', []) or [])
        enrolled = _enroll_dependencies(root, clone, blockers, manifest, evidence, originals, drafts, groups)
        if enrolled:
            _remember(root, primary, group, originals[primary], 'dependency_enrolled',
                      json.dumps({'files': enrolled, 'findings': blockers}, ensure_ascii=False), attempt, step)
        diff = _compact_diff(draft, new_draft, target)
        impact = _changed_identifier_map(draft, new_draft, root)
        edit_rounds += 1

        _remember(
            root, target, group, source, "draft_preflight",
            "DIFF:\n" + diff + "\nDIAGNOSTICS:\n" + ("\n".join(diagnostics) if diagnostics else "clean"),
            attempt, step,
        )

        if not diagnostics:
            _progress(
                g, callback,
                f"V{VERSION} internal preflight clean for {target}; handing candidate to functional/component proof.",
                repair_session_step=step,
                repair_edit_round=edit_rounds,
                internal_preflight_clean=True,
            )
            _SESSION.last_draft = drafts[primary]
            return {rel: text for rel, text in drafts.items() if text != originals[rel]}

        draft = new_draft
        last_diagnostics = diagnostics
        transcript.append(
            "EDIT APPLIED TO DISPOSABLE CANDIDATE ONLY.\n"
            f"DIFF:\n{diff}\n"
            f"SYMBOL IMPACT:\n{impact}\n"
            "IMMEDIATE DIAGNOSTICS (fix these in the SAME session):\n"
            + "\n".join(diagnostics)
        )
        pending = [str(row.get('file') or '').replace('\\', '/') for row in blockers]
        # Keep the draft and move straight to the validator-owned dependency.
        # Once there, remain on it until its finding clears or the model revisits
        # another explicitly authorized target through view.
        if target not in pending:
            failed = str(getattr(_SESSION, 'failed_target', target))
            target = next((rel for rel in pending if rel in drafts), failed if failed in drafts else target)

    message = (
        f"V{VERSION} internal repair session exhausted before static preflight became clean. "
        "Last diagnostics:\n" + "\n".join(str(x) for x in last_diagnostics[-8:])
    )
    _remember(root, target, group, source, "session_exhausted", message, attempt, MAX_TOOL_STEPS)
    raise ValueError(message)


def install(g: dict[str, Any]):
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_model_candidate = transactions._model_candidate
    previous_repair_transaction = transactions.repair_transaction
    previous_prepare = transactions.prepare_candidate_workspace

    def prepare_candidate_workspace(g2, root, callback=None):
        handle, clone = previous_prepare(g2, root, callback)
        _SESSION.clone = str(Path(clone).resolve())
        return handle, clone

    def model_candidate(g2, request, manifest, root, group, evidence, errors, attempt, callback):
        return _agent_model_candidate(
            g2, request, manifest, root, group, evidence, errors, attempt, callback, previous_model_candidate
        )

    def repair_transaction(g2, request, manifest, root, group, callback=None, prior_errors=None):
        _SESSION.root = str(Path(root).resolve())
        _SESSION.last_target = str((group or {}).get("file") or "")
        _SESSION.last_draft = ""
        try:
            changed, out_errors = previous_repair_transaction(
                g2, request, manifest, root, group, callback, prior_errors
            )
            target = str(getattr(_SESSION, "last_target", "") or (group or {}).get("file") or "")
            try:
                current = (Path(root).resolve() / target).read_text(encoding="utf-8", errors="replace") if target else ""
            except Exception:
                current = ""
            _remember(
                root,
                target,
                group,
                current,
                "transaction_result",
                ("ACCEPTED" if changed else "REJECTED") + "\n" + "\n".join(str(x) for x in (out_errors or [])[-4:]),
                accepted=bool(changed),
            )
            return changed, out_errors
        finally:
            for name in ("clone", "root", "last_target", "last_draft", "functional_blockers", "defer_component_proof", "failed_target"):
                try:
                    delattr(_SESSION, name)
                except Exception:
                    pass

    transactions.prepare_candidate_workspace = prepare_candidate_workspace
    transactions._model_candidate = model_candidate
    transactions.repair_transaction = repair_transaction

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r"jarvis_v42(?:4[0-9]|5[0-9]|6[0-7])_repair", name):
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
            planner_mode="tool-using-durable-memory-repair-v42.68",
            tool_using_repair_session=True,
            host_controlled_sandbox_tools=["search", "view", "references", "symbol", "edit", "diagnose"],
            arbitrary_model_shell_access=False,
            durable_project_repair_memory=True,
            repair_memory_database=f"{MEMORY_DIR}/{MEMORY_DB}",
            current_errors_persist_across_trials=True,
            portable_checkpoint_repair_memory=True,
            same_transaction_draft_refinement=True,
            immediate_static_diagnostics_after_edit=True,
            functional_debt_preflight_inside_same_session=True,
            symbol_reference_contract_preloaded=True,
            local_symbol_closure_preflight=True,
            whole_file_rewrite_discouraged_and_bounded=True,
            exact_search_replace_existing_files=True,
            model_edits_disposable_candidate_only=True,
            max_internal_tool_steps=MAX_TOOL_STEPS,
            max_internal_edit_rounds=MAX_EDIT_ROUNDS,
            v4267_owner_local_evidence_preserved=True,
            v4267_compact_output_budgets_preserved=True,
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
        V4268_VERSION=VERSION,
        V4268_ENGINE=ENGINE,
    )
    try:
        Path(
            g.get("JARVIS_DIR") or Path(__file__).resolve().parent,
            "JARVIS_ACTIVE_ENGINE.txt",
        ).write_text("V" + VERSION + "\n", encoding="utf-8")
    except OSError:
        pass
