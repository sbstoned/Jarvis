"""V42.38 component-scoped transport convergence and compiler hint repair.

V42.37 correctly isolated candidate validation by component, but keyed its
transport history to a whole-repository token.  An unrelated accepted edit in
another component therefore erased the failing component's timeout history.
After a ten-minute cooldown the same unchanged target also became eligible
again.  Long-running projects could consequently revisit identical files
without ever receiving patch bytes.

This install layer makes the component revision the durable convergence unit,
reconstructs transport evidence from the append-only journal, removes timed
retry re-entry, tries exact compiler suggestions before model inference, and
keeps explicit behavioral-test requests open when the only test is a linkage
smoke seed.  The policies use manifest component roots and compiler evidence;
they are not tied to a specific generated application.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import jarvis_v4237_repair as v4237


VERSION = "42.38.0"
ENGINE = "COMPONENT_SCOPED_TRANSPORT_CONVERGENCE_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
STATE_FILE = "JARVIS_V4238_COMPONENT_REPAIR_STATE.json"
BUNDLE_FILE = "JARVIS_V4238_REPAIR_BUNDLE.json"

_REVISION_NAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
    "yarn.lock", "bun.lock", "bun.lockb", "tsconfig.json", "tsconfig.node.json",
    "vite.config.ts", "vite.config.mts", "vite.config.js", "vite.config.mjs",
    "vitest.config.ts", "vitest.config.mts", "vitest.config.js", "vitest.config.mjs",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum", "pyproject.toml", "poetry.lock",
    "requirements.txt", "pipfile", "pipfile.lock", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "gradle.properties", "pubspec.yaml",
    "pubspec.lock", "package.swift", "cmakelists.txt", "makefile", "justfile",
}
_REVISION_SUFFIXES = set(v4237._SOURCE_SUFFIXES) | {
    ".json", ".jsonc", ".toml", ".yaml", ".yml", ".xml", ".props", ".targets",
}
_REVISION_SKIP = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "target", "dist",
    "build", "out", "coverage", ".next", ".nuxt", ".svelte-kit", ".turbo",
    ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    ".venv", "venv", "vendor", "bin", "obj", ".gradle", ".jarvis_build",
    ".jarvis_runtime", ".jarvis_backups",
}
_JOURNAL_FILE = "JARVIS_PROJECT_JOURNAL.jsonl"


def _norm(value: object) -> str:
    return v4237._norm(value)


def _component_identity(component: dict | None) -> tuple[str, str, str]:
    return v4237._component_identity(component)


def _component_for_rel(manifest: dict | None, rel: object) -> dict:
    return v4237._component_for_rel(manifest, rel)


def _path_in_root(rel: str, component_root: str) -> bool:
    rel = _norm(rel)
    root = _norm(component_root)
    return root == "." or rel == root or rel.startswith(root.rstrip("/") + "/")


def _component_source_token(work: Path | str, manifest: dict | None, component: dict | None) -> str:
    """Hash only authored source/config that belongs to the exact component.

    A root component excludes deeper manifest component roots.  This is the key
    invariant missing from V42.37: changing ``tests/...`` in a root React
    component cannot reset a nested ``src-tauri`` Rust component's repair state,
    and changing Rust cannot reset React state.
    """
    repo = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    cid, component_root, adapter = _component_identity(component)
    base = repo if component_root == "." else repo / component_root
    nested_roots: list[str] = []
    for row in manifest.get("components") or []:
        if not isinstance(row, dict) or row is component:
            continue
        _other_id, other_root, _other_adapter = _component_identity(row)
        if other_root == "." or other_root == component_root:
            continue
        if component_root == "." or other_root.startswith(component_root.rstrip("/") + "/"):
            nested_roots.append(other_root)

    values: list[tuple[str, str]] = []
    if base.is_dir():
        for directory, names, files in os.walk(base, topdown=True, followlinks=False):
            here = Path(directory)
            kept = []
            for name in names:
                child = here / name
                try:
                    rel_child = child.relative_to(repo).as_posix()
                except Exception:
                    continue
                if name.lower() in _REVISION_SKIP:
                    continue
                if any(rel_child == item or rel_child.startswith(item.rstrip("/") + "/") for item in nested_roots):
                    continue
                if child.is_symlink():
                    continue
                kept.append(name)
            names[:] = kept
            for name in files:
                path = here / name
                try:
                    rel = path.relative_to(repo).as_posix()
                except Exception:
                    continue
                if any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in nested_roots):
                    continue
                low_name = name.lower()
                if low_name.startswith("jarvis_") or low_name.startswith(".jarvis_"):
                    continue
                if low_name not in _REVISION_NAMES and path.suffix.lower() not in _REVISION_SUFFIXES:
                    continue
                try:
                    values.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))
                except Exception:
                    pass

    material = {"component": cid, "root": component_root, "adapter": adapter, "files": sorted(values)}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _event_files(event: dict) -> list[str]:
    values: list[str] = []
    if event.get("file"):
        values.append(_norm(event.get("file")))
    for value in event.get("files") or []:
        if value:
            values.append(_norm(value))
    for row in event.get("changes") or []:
        if isinstance(row, dict):
            value = row.get("file") or row.get("test_file") or row.get("path")
            if value:
                values.append(_norm(value))
    return list(dict.fromkeys(values))


def _event_matches_component(manifest: dict, component: dict, event: dict) -> bool:
    cid, component_root, _adapter = _component_identity(component)
    named = str(event.get("component") or "").strip()
    if named:
        return named == cid or _norm(named) == component_root
    files = _event_files(event)
    return bool(files) and any(
        _component_identity(_component_for_rel(manifest, rel))[0] == cid for rel in files
    )


def _accepted_component_event(manifest: dict, component: dict, event: dict) -> bool:
    kind = str(event.get("type") or "").lower()
    if not ("accepted" in kind or "committed" in kind):
        return False
    if kind in {"v4235_declared_test_contract_closed", "v4235_declared_test_runner_bootstrapped"}:
        return False
    return _event_matches_component(manifest, component, event)


def _journal_transport_counts(work: Path | str, manifest: dict, component: dict) -> dict[str, int]:
    """Rebuild timeout counts since the component's last accepted source edit."""
    path = Path(work) / _JOURNAL_FILE
    counts: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return counts
    for line in lines[-12000:]:
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        if _accepted_component_event(manifest, component, event):
            counts = {}
            continue
        kind = str(event.get("type") or "").lower()
        if kind not in {"v4237_model_transport_failed", "v4238_model_transport_failed"}:
            continue
        if not _event_matches_component(manifest, component, event):
            continue
        rel = _norm(event.get("file"))
        if rel and rel != ".":
            counts[rel] = int(counts.get(rel) or 0) + 1
    return counts


def _merge_transport_evidence(existing: dict, journal: dict) -> dict[str, int]:
    keys = set(existing) | set(journal)
    return {key: max(int(existing.get(key) or 0), int(journal.get(key) or 0)) for key in keys}


def _replacement_with_original_indent(old_line: str, replacement: str) -> str:
    if replacement[:1].isspace():
        return replacement
    return re.match(r"\s*", old_line).group(0) + replacement


def _compiler_exact_suggestions(source: str, failure: str, rel: str) -> list[tuple[str, str]]:
    """Return exact line substitutions printed by compilers as ``N -``/``N +``."""
    changes: list[tuple[str, str]] = []
    lines = source.splitlines()
    pattern = re.compile(r"(?m)^\s*(\d+)\s*-\s?(.*?)\r?\n\s*\1\s*\+\s?(.*?)\s*$")
    normalized_rel = _norm(rel).lower()
    for match in pattern.finditer(str(failure or "")):
        prefix = str(failure or "")[max(0, match.start() - 1400):match.start()].replace("\\", "/").lower()
        if normalized_rel not in prefix and Path(normalized_rel).name not in prefix:
            continue
        line_no = int(match.group(1))
        if line_no < 1 or line_no > len(lines):
            continue
        current = lines[line_no - 1]
        old = match.group(2).rstrip()
        new = match.group(3).rstrip()
        if current.strip() != old.strip():
            continue
        replacement = _replacement_with_original_indent(current, new)
        changes.append((current, replacement))
    return changes


def _rust_from_row_candidate(source: str, failure: str, rel: str) -> str:
    """Apply only compiler-proven missing sqlx::FromRow derives."""
    if Path(rel).suffix.lower() != ".rs" or "FromRow" not in str(failure or ""):
        return source
    names = set(re.findall(r"trait bound [`']?(?:for<'[^>]+>\s+)?([A-Za-z_]\w*)\s*:\s*FromRow", str(failure or "")))
    candidate = source
    for name in names:
        struct_pattern = re.compile(
            r"(?P<derive>#\[derive\((?P<items>[^\]]*)\)\]\s*)?(?P<decl>(?:pub\s+)?struct\s+" + re.escape(name) + r"\b)"
        )
        match = struct_pattern.search(candidate)
        if not match:
            continue
        derive = match.group("derive") or ""
        if "FromRow" in derive:
            continue
        if derive:
            items = match.group("items").rstrip()
            replacement = "#[derive(" + items + (", " if items else "") + "sqlx::FromRow)]\n" + match.group("decl")
        else:
            replacement = "#[derive(sqlx::FromRow)]\n" + match.group("decl")
        candidate = candidate[:match.start()] + replacement + candidate[match.end():]
    return candidate


def _deterministic_candidate(source: str, failure: str, rel: str) -> tuple[str, list[str]]:
    candidate = source
    reasons: list[str] = []
    for old, new in _compiler_exact_suggestions(candidate, failure, rel):
        if old in candidate:
            candidate = candidate.replace(old, new, 1)
            reasons.append("compiler_exact_replacement")
    rust = _rust_from_row_candidate(candidate, failure, rel)
    if rust != candidate:
        candidate = rust
        reasons.append("compiler_proven_sqlx_from_row")
    return candidate, reasons


def _model_patch_prompt(g: dict, work: Path, manifest: dict, component: dict, target: str, connected: list[str], failure: str) -> str:
    """V42.37's prompt contract with a materially smaller inference window."""
    cid, component_root, adapter = _component_identity(component)
    command = component.get("build_command") or manifest.get("build_command") or "adapter-native validation"
    try:
        live_command, live_cwd = g["_v429_live_component_command"](work, manifest, component)
        if live_command:
            command = " ".join(str(value) for value in live_command)
            component_root = _norm(Path(live_cwd).resolve().relative_to(work.resolve()).as_posix())
    except Exception:
        pass
    related = []
    related_chars = 0
    for rel in connected:
        if rel == target or related_chars >= 1400:
            continue
        window = v4237._source_window(g, work, rel, failure, 1200)
        if window:
            block = f"--- {rel} (read-only) ---\n{window}"
            related.append(block)
            related_chars += len(block)
    item = next((row for row in manifest.get("files") or [] if isinstance(row, dict) and _norm(row.get("path")) == target), {})
    contract = json.dumps({
        "purpose": item.get("purpose"), "exports": item.get("exports") or [],
        "contracts": item.get("contracts") or [], "depends_on": item.get("depends_on") or [],
    }, ensure_ascii=False)
    prompt = (
        "V42.38 COMPONENT PATCH. Return only complete Aider SEARCH/REPLACE blocks; no JSON, fences, prose, or whole-file rewrite.\n"
        "<<<<<<< SEARCH\nexact current source\n=======\nreplacement source\n>>>>>>> REPLACE\n\n"
        f"COMPONENT: id={cid}; adapter={adapter}; root={component_root}\nVALIDATOR: {command}\n"
        f"TARGET: {target}\nDIAGNOSTIC FILES: {', '.join(connected)}\n"
        "Make the smallest root-cause correction supported by the compiler. Preserve public behavior. Do not suppress diagnostics, weaken tests, add placeholders, duplicate canonical types, edit another component, or change toolchains. Validation is isolated and promotion requires a strict diagnostic decrease.\n\n"
        f"CONTRACT:\n{contract[:900]}\n\n"
        f"COMPILER EVIDENCE:\n{v4237._diagnostic_excerpt(target, failure, 2800)}\n\n"
        f"CURRENT SOURCE:\n{v4237._source_window(g, work, target, failure, 4800)}\n\n"
        + "\n\n".join(related)
    )
    return prompt[:10000]


def _call_compact_editor(g: dict, prompt: str, target: str, progress_callback=None):
    base_call = g.get("_v36_base_qwen_call")
    if not callable(base_call):
        return False, "compact model entrypoint unavailable", "infrastructure"
    try:
        mode = str(g.get("_v426_mode", lambda: "auto")() or "auto")
    except Exception:
        mode = "auto"
    worker = str(g.get("V426_AUTO_WORKER", "9b35"))
    specialist = str(g.get("V426_AUTO_SPECIALIST", "27b38q2"))
    routes = [worker, specialist] if mode == "auto" else [mode]
    errors = []
    for ordinal, route in enumerate(dict.fromkeys(routes), start=1):
        if mode == "auto":
            try:
                switched, detail = g["_v426_switch_for_call"](
                    route, "V42.38 compact component editor" if ordinal == 1 else "V42.38 bounded peer rescue", progress_callback,
                )
                if not switched:
                    errors.append(str(detail))
                    continue
            except Exception as exc:
                errors.append(str(exc))
                continue
        try:
            worker_timeout = max(30, min(180, int(os.getenv("JARVIS_V4238_WORKER_PATCH_TIMEOUT", "90"))))
            specialist_timeout = max(45, min(240, int(os.getenv("JARVIS_V4238_SPECIALIST_PATCH_TIMEOUT", "150"))))
        except Exception:
            worker_timeout, specialist_timeout = 90, 150
        call_timeout = worker_timeout if route == worker else specialist_timeout
        g["_progress"](
            progress_callback, f"V42.38 compact component patch {ordinal}/{len(routes)}: {target}",
            stage="V42.38 component transaction", percent=85, current_file=target,
            model_profile=route, model_role="worker" if route == worker else "specialist",
        )
        try:
            ok, raw = base_call(
                prompt, progress_callback, f"V42.38 compact component patch {ordinal}/{len(routes)}: {target}",
                profile="repair", max_tokens=900, thinking=False, response_schema=None,
                strict_output=False, hard_timeout=call_timeout,
            )
        except BaseException as exc:
            ok, raw = False, str(exc)
        if ok:
            return True, str(raw or ""), ""
        errors.append(str(raw or "model call failed"))
    text = "\n".join(errors)[-5000:]
    kind = "transport" if any(token in text.lower() for token in (
        "watchdog", "timed out", "timeout", "connection", "server", "context window", "model call failed",
    )) else "model"
    return False, text, kind


def _commit_component_transaction(g: dict, work: Path, clone: Path, files: list[str], before: int, after: int, component: dict, reason: str) -> tuple[bool, str]:
    originals: dict[str, bytes] = {}
    temporaries: list[Path] = []
    try:
        for rel in files:
            source = clone / rel
            destination = work / rel
            if not source.is_file() or source.suffix.lower() not in v4237._SOURCE_SUFFIXES:
                return False, f"unsafe transaction member: {rel}"
            if not destination.resolve(strict=False).is_relative_to(work.resolve()):
                return False, f"transaction path escapes project: {rel}"
            originals[rel] = destination.read_bytes()
            try:
                g["_v36_checkpoint_file"](work, rel, originals[rel].decode("utf-8", errors="replace"), "before_v4238_component_transaction")
            except Exception:
                pass
            temporary = destination.with_name(destination.name + ".v4238.tmp")
            temporary.write_bytes(source.read_bytes())
            temporaries.append(temporary)
        for rel, temporary in zip(files, temporaries):
            os.replace(temporary, work / rel)
        for rel in files:
            try:
                g["_v413_mark_accepted"](work, rel, "v4238_component_compiler_delta")
            except Exception:
                pass
        cid, component_root, adapter = _component_identity(component)
        g["_append_project_event"](
            work, "v4238_component_transaction_committed",
            f"V42.38 atomically promoted {len(files)} {cid} source edit(s); isolated diagnostics decreased {before} -> {after}.",
            component=cid, component_root=component_root, adapter=adapter,
            files=files, before=before, after=after, repair_reason=reason,
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


def _save_transport_block(g: dict, root: Path, state_path: Path, state: dict, entry: dict, component: dict, targets: list[str], limit: int, token: str) -> None:
    entry["result"] = "transport_exhausted"
    entry["blocked_until_component_source_changes"] = True
    entry["blocked_component_token"] = token
    already = entry.get("last_transport_block_event_token") == token
    entry["last_transport_block_event_token"] = token
    v4237._save(state_path, state)
    if already:
        return
    cid, component_root, adapter = _component_identity(component)
    g["_append_project_event"](
        root, "v4238_component_transport_blocked",
        f"V42.38 stopped model repair for unchanged {cid} source after the bounded no-response allowance. Resume requires a real {cid} source/config revision; unrelated repository edits and elapsed time cannot reset it.",
        component=cid, component_root=component_root, adapter=adapter, files=targets,
        component_token=token, transport_limit=limit, action="save checkpoint; restore model service or edit this component before resuming",
    )


def repair_component_failure(g: dict, user_request: object, manifest: dict | None, work: Path | str, failure: object, progress_callback=None) -> bool:
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    text = str(failure or "")
    component = v4237.component_from_failure(manifest, text)
    if not component:
        return False
    cid, component_root, adapter = _component_identity(component)
    if adapter in v4237._NODE_ADAPTERS:
        return False
    try:
        rows = list(g["_v4236_native_diagnostics"](root, manifest, text) or [])
        targets = list(g["_v4236_rank_native_targets"](rows, text) or [])
    except Exception:
        rows, targets = [], []
    targets = [rel for rel in targets if _component_identity(_component_for_rel(manifest, rel))[0] == cid]
    if not targets:
        return False

    before = v4237.diagnostic_count(text)
    if before <= 0:
        try:
            before = int(g.get("_v4236_native_error_count", lambda value: 0)(text) or 0)
        except Exception:
            before = 0
    signature = v4237._failure_signature(component, rows, text)
    token = _component_source_token(root, manifest, component)
    journal_counts = _journal_transport_counts(root, manifest, component)
    state_path = root / STATE_FILE
    state = v4237._load(state_path, {"failures": {}})
    failures = state.setdefault("failures", {})
    entry = failures.setdefault(signature, {
        "component": cid, "component_root": component_root, "adapter": adapter,
        "component_token": token, "semantic_no_delta": [], "transport_failures": {}, "transactions": [],
    })
    if entry.get("component_token") != token:
        entry.update({
            "component_token": token, "semantic_no_delta": [], "transport_failures": dict(journal_counts),
            "transactions": [], "result": "component_revision_changed",
            "blocked_until_component_source_changes": False,
        })
    else:
        entry["transport_failures"] = _merge_transport_evidence(dict(entry.get("transport_failures") or {}), journal_counts)
    entry["journal_transport_evidence"] = dict(journal_counts)
    exhausted = set(entry.get("semantic_no_delta") or [])
    try:
        max_targets = max(1, min(5, int(os.getenv("JARVIS_V4238_COMPONENT_TARGETS_PER_TRANSACTION", "3"))))
        transport_limit = max(1, min(4, int(os.getenv("JARVIS_V4238_TRANSPORT_ATTEMPTS_PER_COMPONENT_REVISION", "2"))))
    except Exception:
        max_targets, transport_limit = 3, 2
    transport_counts = dict(entry.get("transport_failures") or {})
    eligible = [
        (int(transport_counts.get(rel) or 0), ordinal, rel)
        for ordinal, rel in enumerate(targets)
        if rel not in exhausted and int(transport_counts.get(rel) or 0) < transport_limit
    ]
    candidates = [rel for _count, _ordinal, rel in sorted(eligible)[:max_targets]]
    if not candidates:
        if any(int(transport_counts.get(rel) or 0) >= transport_limit for rel in targets if rel not in exhausted):
            _save_transport_block(g, root, state_path, state, entry, component, targets, transport_limit, token)
            g["_progress"](
                progress_callback,
                f"V42.38 stopped repeated no-response repair for unchanged {cid}; save the checkpoint and restore model availability before resuming.",
                stage="V42.38 model transport blocked", percent=82, component=cid,
            )
        else:
            entry["result"] = "semantic_targets_exhausted"
            v4237._save(state_path, state)
        return False

    command = None
    command_cwd = component_root
    try:
        command, cwd = g["_v429_live_component_command"](root, manifest, component)
        if cwd:
            command_cwd = _norm(Path(cwd).resolve().relative_to(root).as_posix())
    except Exception:
        pass
    v4237._save(root / BUNDLE_FILE, {
        "version": "V" + VERSION, "engine": ENGINE,
        "component": {"id": cid, "root": component_root, "adapter": adapter},
        "validator": {"command": command or component.get("build_command") or "adapter-native", "cwd": command_cwd},
        "diagnostic_count": before, "diagnostic_files": targets, "selected_targets": candidates,
        "failure_signature": signature, "component_source_token": token,
        "transport_counts": transport_counts, "transport_limit": transport_limit,
        "policy": "component-scoped durable history; deterministic compiler hints first; exact isolated validation; strict diagnostic decrease",
    })
    g["_append_project_event"](
        root, "v4238_component_transaction_started",
        f"V42.38 opened a disposable {cid} transaction using durable component-scoped convergence state.",
        component=cid, component_root=component_root, adapter=adapter, files=candidates,
        diagnostic_count=before, validator_command=command, validator_cwd=command_cwd,
        component_token=token,
    )

    temp_handle = None
    try:
        temp_handle, clone = g["_copy_project_for_candidate_validation"](root)
        clone = Path(clone).resolve()
        staged: list[str] = []
        semantic_attempted: set[str] = set()
        transport_only: set[str] = set()
        current_failure = text
        current_count = before
        for target in candidates:
            path = clone / target
            try:
                original = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            deterministic, reasons = _deterministic_candidate(original, current_failure, target)
            if deterministic != original:
                safety = v4237._candidate_safety(g, clone, manifest, target, deterministic, current_failure)
                if not safety:
                    path.write_text(deterministic, encoding="utf-8")
                    valid, replay = g["_v35_validate_component"](clone, manifest, component, str(user_request or ""))
                    replay = str(replay or "")
                    after = 0 if valid else v4237.diagnostic_count(replay)
                    improved = bool(valid or (current_count > 0 and after > 0 and after < current_count))
                    entry.setdefault("transactions", []).append({
                        "target": target, "result": "deterministic_improved" if improved else "deterministic_no_delta",
                        "reasons": reasons, "before": current_count, "after": after, "at": g["_utc_stamp"](),
                    })
                    v4237._save(state_path, state)
                    if improved:
                        changed = v4237._diff_selected(root, clone, [target])
                        committed, reason = _commit_component_transaction(
                            g, root, clone, changed, before, after, component, "+".join(reasons)
                        )
                        entry["result"] = "committed" if committed else "commit_failed"
                        entry["last_commit_error"] = reason[-1200:]
                        v4237._save(state_path, state)
                        return bool(committed)
                    path.write_text(original, encoding="utf-8")

            prompt = _model_patch_prompt(g, clone, manifest, component, target, targets, current_failure)
            ok, raw, failure_kind = _call_compact_editor(g, prompt, target, progress_callback)
            if not ok:
                transport_counts = dict(entry.get("transport_failures") or {})
                transport_counts[target] = int(transport_counts.get(target) or 0) + 1
                entry["transport_failures"] = transport_counts
                entry["last_transport_error"] = str(raw or "")[-1800:]
                entry["last_transport_at"] = g["_utc_stamp"]()
                entry.setdefault("transactions", []).append({"target": target, "result": failure_kind + "_failure", "at": g["_utc_stamp"]()})
                transport_only.add(target)
                v4237._save(state_path, state)
                g["_append_project_event"](
                    root, "v4238_model_transport_failed",
                    f"V42.38 received no patch bytes for {target}; the durable component-revision transport budget was recorded without consuming semantic budget.",
                    file=target, component=cid, component_root=component_root,
                    component_token=token, failure_kind=failure_kind,
                    transport_count=transport_counts[target], transport_limit=transport_limit,
                )
                continue

            entry.setdefault("transport_failures", {})[target] = 0
            try:
                replacements, parse_error = g["_v38_parse_search_replace_blocks"](raw)
            except Exception as exc:
                replacements, parse_error = [], str(exc)
            if not replacements:
                semantic_attempted.add(target)
                entry.setdefault("transactions", []).append({"target": target, "result": "malformed_patch", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = str(parse_error or "")[-1200:]
                v4237._save(state_path, state)
                continue
            try:
                candidate, patch_error = g["_v36_apply_search_replace"](original, replacements)
            except Exception as exc:
                candidate, patch_error = "", str(exc)
            if patch_error or not candidate or candidate == original:
                semantic_attempted.add(target)
                entry.setdefault("transactions", []).append({"target": target, "result": "unusable_patch", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = str(patch_error or "no source delta")[-1200:]
                v4237._save(state_path, state)
                continue
            safety = v4237._candidate_safety(g, clone, manifest, target, candidate, current_failure)
            if safety:
                semantic_attempted.add(target)
                entry.setdefault("transactions", []).append({"target": target, "result": "safety_rejected", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = safety[-1200:]
                v4237._save(state_path, state)
                continue
            path.write_text(candidate, encoding="utf-8")
            staged.append(target)
            semantic_attempted.add(target)
            valid, replay = g["_v35_validate_component"](clone, manifest, component, str(user_request or ""))
            replay = str(replay or "")
            after = 0 if valid else v4237.diagnostic_count(replay)
            improved = bool(valid or (current_count > 0 and after > 0 and after < current_count))
            entry.setdefault("transactions", []).append({
                "target": target, "staged": list(staged), "before": current_count, "after": after,
                "validator_ok": bool(valid), "result": "improved" if improved else "no_delta", "at": g["_utc_stamp"](),
            })
            entry["last_validation_output"] = replay[-5000:]
            v4237._save(state_path, state)
            if improved:
                changed = v4237._diff_selected(root, clone, staged)
                committed, reason = _commit_component_transaction(g, root, clone, changed, before, after, component, "model_patch")
                entry["result"] = "committed" if committed else "commit_failed"
                entry["last_commit_error"] = reason[-1200:]
                v4237._save(state_path, state)
                return bool(committed)
            path.write_text(original, encoding="utf-8")
            staged = [rel for rel in staged if rel != target]

        if transport_only and not semantic_attempted:
            counts = dict(entry.get("transport_failures") or {})
            exhausted_now = all(int(counts.get(rel) or 0) >= transport_limit for rel in targets if rel not in exhausted)
            entry["result"] = "transport_exhausted" if exhausted_now else "transport_deferred"
            entry["blocked_until_component_source_changes"] = exhausted_now
            v4237._save(state_path, state)
            g["_append_project_event"](
                root, "v4238_component_transport_deferred",
                f"V42.38 discarded no code because the {cid} editor returned no patch bytes; this is model transport state, not semantic code no-progress.",
                component=cid, files=sorted(transport_only), component_token=token,
                transport_exhausted=exhausted_now,
            )
            return False

        no_delta = list(entry.get("semantic_no_delta") or [])
        for rel in semantic_attempted:
            if rel not in no_delta:
                no_delta.append(rel)
        entry["semantic_no_delta"] = no_delta
        entry["result"] = "bounded_semantic_no_delta"
        v4237._save(state_path, state)
        g["_append_project_event"](
            root, "v4238_component_transaction_no_delta",
            f"V42.38 discarded the disposable {cid} transaction because actual candidate bytes did not reduce exact-component diagnostics.",
            component=cid, files=sorted(semantic_attempted), diagnostic_count=before,
        )
        return False
    except Exception as exc:
        entry["result"] = "sandbox_failure"
        entry["last_error"] = str(exc)[-1800:]
        v4237._save(state_path, state)
        try:
            g["_append_project_event"](
                root, "v4238_component_sandbox_failed",
                "V42.38 discarded the disposable transaction after infrastructure failure; authoritative source was not modified.",
                component=cid, error=str(exc)[-1200:],
            )
        except Exception:
            pass
        return False
    finally:
        v4237._cleanup_temp(temp_handle)


def _bootstrap_only_test(text: str) -> bool:
    low = re.sub(r"\s+", " ", str(text or "")).lower()
    signatures = (
        "links the real application entry component",
        "expect(typeof app).tobe('function')",
        'expect(typeof app).tobe("function")',
        "canonical_production_contracts_are_linked",
        "std::any::type_name::<",
    )
    return any(value in low for value in signatures)


def _explicit_test_quality_issues(g: dict, work: Path | str, manifest: dict | None) -> list[dict]:
    manifest = manifest if isinstance(manifest, dict) else {}
    request = str(manifest.get("_original_user_request") or "")
    try:
        explicit = bool(g["_explicit_tests_requested"](request))
    except Exception:
        explicit = False
    if not explicit:
        return []
    issues = []
    for item in manifest.get("files") or []:
        if not isinstance(item, dict):
            continue
        rel = _norm(item.get("path"))
        if rel == ".":
            continue
        low = "/" + rel.lower()
        name = Path(rel).name.lower()
        if not ("/tests/" in low or "/test/" in low or name.startswith("test_") or ".test." in name or ".spec." in name or str(item.get("phase") or "").lower() == "test"):
            continue
        path = Path(work) / rel
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if _bootstrap_only_test(source):
            issues.append({
                "file": rel, "kind": "test_quality",
                "problem": "V42.38 explicit-test gate: this file only proves that production symbols link. The user requested real tests, so at least one behavior, state transition, public command, or rendered interaction must be exercised before acceptance.",
            })
    return issues


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_real_repair = g["_repair_real_validation_failure"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_qwen = g["_qwen_call"]
    previous_acceptance_issues = g["_deterministic_acceptance_issues"]
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])
    previous_append = g["_append_project_event"]
    base_progress = g.get("_v4235_base_progress", g["_progress"])

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        event = previous_append(work, event_type, message, **values)
        try:
            projection = Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            data = v4237._load(projection, {})
            if isinstance(data, dict):
                data.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
                v4237._save(projection, data)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        value = re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.38", str(text or ""))
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

    def deterministic_acceptance_issues(work, manifest):
        issues = list(previous_acceptance_issues(work, manifest) or [])
        known = {(str(row.get("file") or ""), str(row.get("problem") or "")) for row in issues if isinstance(row, dict)}
        for row in _explicit_test_quality_issues(g, work, manifest):
            key = (row["file"], row["problem"])
            if key not in known:
                known.add(key)
                issues.append(row)
        return issues

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = (
            "\n\nV42.38 FINAL AUTHORITY: Convergence state belongs to the exact component source revision. "
            "Elapsed time and unrelated component edits never reset no-response history. Try compiler-provided exact corrections before inference. "
            "After bounded transport failures, stop and checkpoint with MODEL_TRANSPORT_BLOCKED instead of retrying unchanged targets. "
            "Transport-only attempts are not semantic no-progress. An explicit request for tests requires behavioral evidence; a symbol-linkage smoke seed only bootstraps the runner. "
            "Continue through every component's build, real tests, safe runtime checks, integration contracts, and original requirements before publication."
        )
        return previous_qwen(
            str(prompt or "") + authority, progress_callback,
            re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.38", str(stage or "Generating")),
            profile=profile, **kwargs,
        )

    def release_identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION, "engine": ENGINE,
            "planner_mode": "component-scoped-durable-transport-convergence-v42.38",
            "component_source_revision_transport_state": True,
            "root_component_excludes_nested_component_sources": True,
            "journal_transport_state_reconstruction": True,
            "unrelated_component_edits_cannot_reset_repair_budget": True,
            "elapsed_time_cannot_reset_transport_budget": True,
            "transport_retry_cooldown_prevents_tight_loop": False,
            "model_transport_blocked_requires_component_revision": True,
            "transport_only_not_semantic_no_delta": True,
            "compiler_exact_suggestions_before_model": True,
            "compiler_proven_rust_from_row_repair": True,
            "bounded_component_prompt_chars": 10000,
            "bounded_component_patch_tokens": 900,
            "explicit_tests_reject_linkage_only_smoke": True,
            "exact_component_candidate_replay": True,
            "strict_component_diagnostic_delta": True,
            "language_framework_toolchain_agnostic": True,
            "new_project_and_existing_project_edit_modes": True,
        })
        return data

    def stack_skill_names(manifest):
        names = list(previous_skills(manifest) or [])
        for name in ("component-revision-convergence", "compiler-hint-transaction"):
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
        "V4238_VERSION": VERSION, "V4238_ENGINE": ENGINE,
        "V4238_STATE_FILE": STATE_FILE, "V4238_BUNDLE_FILE": BUNDLE_FILE,
        "_v4238_component_source_token": _component_source_token,
        "_v4238_journal_transport_counts": _journal_transport_counts,
        "_v4238_deterministic_candidate": _deterministic_candidate,
        "_v4238_bootstrap_only_test": _bootstrap_only_test,
        "_v4238_repair_component_failure": lambda request, manifest, work, failure, callback=None: repair_component_failure(g, request, manifest, work, failure, callback),
        "_v429_repair_audit_round": repair_round,
        "_repair_real_validation_failure": real_repair,
        "_deterministic_acceptance_issues": deterministic_acceptance_issues,
        "_append_project_event": append_event, "_progress": progress, "_qwen_call": qwen_call,
        "_v36_release_identity": release_identity, "_v36_stack_skill_names": stack_skill_names,
        "_v4238_engine_disk_guard": engine_guard, "_v4237_engine_disk_guard": engine_guard,
        "generate_project_zip": generate_project_zip, "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
