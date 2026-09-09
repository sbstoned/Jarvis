"""V42.37 component-isolated repair transactions and precise sandbox evidence.

The V42.36 run selected the correct Rust component, but its inherited candidate
replay executed the first non-Python component in the repository.  A React/Vite
failure could therefore reject an improving Rust candidate.  The same run also
showed that model transport timeouts consumed semantic loop budgets and caused
the fallback editor to be blocked without ever producing a candidate.

This install layer keeps the architecture adapter-driven:

* replay the exact component that produced the failure;
* stage model edits in a disposable dependency-parity workspace;
* validate only that component before promotion;
* promote a bounded multi-file transaction only on a strict compiler delta;
* distinguish model transport failure from a rejected repair strategy; and
* deterministically remove a broken bundler alias only when it shadows an
  installed package and fresh component validation proves the correction.

Rust/Vite are the captured regression.  Component identity, commands, roots,
diagnostics, and dependency manifests remain the authority for other stacks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path


VERSION = "42.37.0"
ENGINE = "COMPONENT_ISOLATED_TRANSACTION_SANDBOX_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
STATE_FILE = "JARVIS_V4237_COMPONENT_REPAIR_STATE.json"
BUNDLE_FILE = "JARVIS_V4237_REPAIR_BUNDLE.json"

_SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
    ".rs", ".go", ".java", ".kt", ".kts", ".cs", ".fs", ".vb",
    ".swift", ".m", ".mm", ".dart", ".php", ".rb", ".py", ".pyw",
    ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".vue", ".svelte",
}
_TRANSACTION_CONFIG_NAMES = {
    "Cargo.toml", "package.json", "tsconfig.json", "pyproject.toml",
    "requirements.txt", "go.mod", "pom.xml", "build.gradle",
    "build.gradle.kts", "CMakeLists.txt",
}
_NODE_ADAPTERS = {
    "node", "react", "vite", "typescript", "javascript", "nextjs", "vue",
    "svelte", "sveltekit", "nuxt", "angular", "electron", "react_native", "expo",
}
_CONFIG_NAMES = (
    "vite.config.ts", "vite.config.mts", "vite.config.js", "vite.config.mjs",
    "vitest.config.ts", "vitest.config.mts", "vitest.config.js", "vitest.config.mjs",
)


def _norm(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/\"'")
    text = re.sub(r"^\./", "", text)
    return "." if text in {"", "."} else text


def _load(path: Path, default=None):
    fallback = {} if default is None else default
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value
    except Exception:
        return fallback


def _save(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".v4237.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass


def _component_identity(component: dict | None) -> tuple[str, str, str]:
    row = component or {}
    root = _norm(row.get("root") or ".")
    adapter = str(row.get("toolchain_adapter") or row.get("adapter") or "").strip().lower()
    cid = str(row.get("id") or root or adapter or "component")
    return cid, root, adapter


def _component_for_rel(manifest: dict | None, rel: object) -> dict:
    target = _norm(rel)
    matches: list[tuple[int, dict]] = []
    fallback: dict | None = None
    for component in (manifest or {}).get("components") or []:
        if not isinstance(component, dict):
            continue
        _cid, root, _adapter = _component_identity(component)
        if root == ".":
            fallback = fallback or component
        elif target == root or target.startswith(root.rstrip("/") + "/"):
            matches.append((len(root.split("/")), component))
    return max(matches, key=lambda item: item[0])[1] if matches else (fallback or {})


def component_from_failure(manifest: dict | None, failure: object) -> dict:
    """Resolve the exact component named by validator evidence."""
    text = str(failure or "")
    match = re.search(
        r"COMPONENT FAILED\s*\[\s*([^|\]]+)\|\s*([^|\]]+)\|\s*([^\]]+)\]",
        text,
        re.I,
    )
    if match:
        wanted_id, wanted_adapter, wanted_root = (part.strip() for part in match.groups())
        for component in (manifest or {}).get("components") or []:
            if not isinstance(component, dict):
                continue
            cid, root, _adapter = _component_identity(component)
            if cid == wanted_id or root == _norm(wanted_root):
                return component
        return {
            "id": wanted_id,
            "root": _norm(wanted_root),
            "toolchain_adapter": wanted_adapter.lower(),
        }

    low = text.lower()
    inferred = ""
    if "cargo" in low or "rustc" in low or re.search(r"error\[e\d{4}\]", low):
        inferred = "rust"
    elif "go build" in low or "go test" in low:
        inferred = "go"
    elif "dotnet" in low or re.search(r"\berror\s+(?:cs|fs|bc)\d+", low):
        inferred = "dotnet"
    elif "gradle" in low or "maven" in low or "javac" in low or "kotlinc" in low:
        inferred = "java"
    elif "swift build" in low or "xcodebuild" in low:
        inferred = "swift"
    elif "flutter" in low:
        inferred = "flutter"
    elif "dart analyze" in low:
        inferred = "dart"
    if inferred:
        for component in (manifest or {}).get("components") or []:
            if not isinstance(component, dict):
                continue
            _cid, _root, adapter = _component_identity(component)
            if inferred in adapter or (inferred == "java" and adapter in {"android_gradle", "kotlin_gradle", "java_gradle", "java_maven"}):
                return component
    return {}


def diagnostic_count(failure: object) -> int:
    """Count compiler diagnostics without treating warnings as progress."""
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(failure or ""))
    totals: list[int] = []
    patterns = (
        r"(?:due to|aborting due to)\s+(\d+)\s+previous errors?",
        r"Found\s+(\d+)\s+errors?",
        r"(\d+)\s+Error\(s\)",
        r"BUILD FAILED.*?(\d+)\s+(?:errors?|failures?)",
    )
    for pattern in patterns:
        totals.extend(int(value) for value in re.findall(pattern, text, re.I | re.S))
    explicit_patterns = (
        r"(?m)^\s*error(?:\[[A-Z]*\d+\])?\s*[:\[]",
        r"(?m)^.+?\(\d+,\d+\):\s*error\s+(?:CS|FS|BC)\d+",
        r"(?m)^.+?:\d+(?::\d+)?:\s*(?:fatal\s+)?error\b",
        r"(?m)^\s*FAIL\s+\S+",
    )
    explicit = sum(len(re.findall(pattern, text, re.I)) for pattern in explicit_patterns)
    return max(totals + [explicit, 0])


def _failure_signature(component: dict, rows: list[dict], failure: object) -> str:
    cid, root, adapter = _component_identity(component)
    codes = sorted(set(re.findall(r"\b(?:E|CS|FS|BC|KT|TS)\d{3,5}\b", str(failure or ""), re.I)))
    material = {
        "component": cid,
        "root": root,
        "adapter": adapter,
        "files": sorted({_norm(row.get("file")) for row in rows if row.get("file")}),
        "codes": [value.upper() for value in codes],
        "count": diagnostic_count(failure),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _repo_token(g: dict, work: Path | str) -> str:
    try:
        return str(g["_v429_progress_token"](work))
    except Exception:
        root = Path(work)
        values = []
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES:
                try:
                    values.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
                except Exception:
                    pass
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _cleanup_temp(handle) -> None:
    try:
        if hasattr(handle, "cleanup"):
            handle.cleanup()
        elif handle:
            shutil.rmtree(handle, ignore_errors=True)
    except Exception:
        pass


def _source_window(g: dict, work: Path, rel: str, failure: str, limit: int = 7000) -> str:
    path = work / rel
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(source) <= limit:
        return source
    try:
        localization = g["_v36_localize_failure"](work, failure)
        value = str(g["_v4218_raw_edit_window"](work, rel, localization) or "")
        if value:
            return value[:limit]
    except Exception:
        pass
    return source[: limit // 2] + "\n/* ... bounded middle omitted ... */\n" + source[-limit // 2 :]


def _diagnostic_excerpt(rel: str, failure: str, limit: int = 4800) -> str:
    lines = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(failure or "")).splitlines()
    names = {rel.lower(), Path(rel).name.lower()}
    chosen: list[str] = []
    for index, line in enumerate(lines):
        low = line.lower().replace("\\", "/")
        if any(name and name in low for name in names) or re.search(r"\berror(?:\[[A-Z]*\d+\])?\b", line, re.I):
            start = max(0, index - 2)
            end = min(len(lines), index + 7)
            chosen.extend(lines[start:end])
    if not chosen:
        chosen = lines[-120:]
    compact = "\n".join(dict.fromkeys(chosen))
    return compact[-limit:]


def _model_patch_prompt(
    g: dict,
    work: Path,
    manifest: dict,
    component: dict,
    target: str,
    connected: list[str],
    failure: str,
) -> str:
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
    for rel in connected:
        if rel == target or len("\n".join(related)) >= 3200:
            continue
        window = _source_window(g, work, rel, failure, 3000)
        if window:
            related.append(f"--- {rel} (read-only connected source) ---\n{window}")
    item = next((row for row in manifest.get("files") or [] if isinstance(row, dict) and _norm(row.get("path")) == target), {})
    contract = json.dumps({
        "purpose": item.get("purpose"),
        "exports": item.get("exports") or [],
        "contracts": item.get("contracts") or [],
        "depends_on": item.get("depends_on") or [],
    }, ensure_ascii=False)
    return (
        "V42.37 COMPONENT PATCH. Return only complete Aider SEARCH/REPLACE blocks; no JSON, Markdown fences, prose, or whole-file rewrite.\n"
        "Format exactly:\n<<<<<<< SEARCH\nexact current source\n=======\nreplacement source\n>>>>>>> REPLACE\n\n"
        f"FAILING COMPONENT: id={cid}; adapter={adapter}; root={component_root}\n"
        f"VALIDATOR COMMAND: {command}\nTARGET: {target}\nCONNECTED DIAGNOSTIC FILES: {', '.join(connected)}\n"
        "GOAL: make the smallest real root-cause correction. Preserve public behavior. A definition/trait/schema diagnostic permits fixing the canonical definition; a call/type mismatch permits fixing its consumer. "
        "Do not add placeholders, suppress diagnostics, weaken tests, duplicate types, edit another component, or change the toolchain. The candidate runs in a disposable sandbox and is promoted only if this exact component passes or its diagnostic count strictly decreases.\n\n"
        f"TARGET CONTRACT:\n{contract[:1800]}\n\n"
        f"TARGET-SPECIFIC COMPILER EVIDENCE:\n{_diagnostic_excerpt(target, failure)}\n\n"
        f"EXACT CURRENT TARGET SOURCE:\n{_source_window(g, work, target, failure)}\n\n"
        + ("\n\n".join(related) if related else "")
    )[:19000]


def _call_compact_editor(g: dict, prompt: str, target: str, progress_callback=None):
    """Use a small direct editor call; transport failures do not imply bad code."""
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
                    route,
                    "V42.37 compact component editor" if ordinal == 1 else "V42.37 bounded peer rescue",
                    progress_callback,
                )
                if not switched:
                    errors.append(str(detail))
                    continue
            except Exception as exc:
                errors.append(str(exc))
                continue
        try:
            try:
                strategy_generation = str(g.get("JARVIS_REPAIR_STRATEGY_GENERATION") or "")
                fast_tail = strategy_generation.startswith("rust-compiler-hints-v4-") or strategy_generation.startswith("functional-acceptance-v5-")
                worker_default = "120" if fast_tail else "240"
                specialist_default = "240" if fast_tail else "480"
                worker_timeout = max(60, min(600, int(os.getenv("JARVIS_V4237_WORKER_PATCH_TIMEOUT", worker_default))))
                specialist_timeout = max(120, min(900, int(os.getenv("JARVIS_V4237_SPECIALIST_PATCH_TIMEOUT", specialist_default))))
            except Exception:
                worker_timeout, specialist_timeout = 120, 240
            call_timeout = worker_timeout if route == worker else specialist_timeout
            g["_progress"](
                progress_callback,
                f"V42.37 compact component patch {ordinal}/{len(routes)}: {target}",
                stage="V42.37 component transaction",
                percent=85,
                current_file=target,
                model_profile=route,
                model_role="worker" if route == worker else "specialist",
            )
            ok, raw = base_call(
                prompt,
                progress_callback,
                f"V42.37 compact component patch {ordinal}/{len(routes)}: {target}",
                profile="repair",
                max_tokens=1200,
                thinking=False,
                response_schema=None,
                strict_output=False,
                hard_timeout=call_timeout,
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


def _candidate_safety(g: dict, work: Path, manifest: dict, rel: str, content: str, failure: str) -> str:
    try:
        basic = str(g["_content_validation_error"](rel, content) or "")
        if basic:
            return basic
    except Exception as exc:
        return str(exc)
    context = g.get("_V4225_CTX")
    old = getattr(context, "provisional_cluster", False) if context is not None else False
    try:
        if context is not None:
            context.provisional_cluster = True
        return str(g["_candidate_transaction_error"](
            work,
            manifest,
            rel,
            content,
            user_request=manifest.get("_original_user_request") or "",
            validation_failure=failure,
            target_problems=["fresh component compiler diagnostics"],
        ) or "")
    except Exception as exc:
        return "candidate safety gate failed: " + str(exc)
    finally:
        if context is not None:
            context.provisional_cluster = old


def _diff_selected(original: Path, clone: Path, targets: list[str]) -> list[str]:
    changed = []
    for rel in targets:
        try:
            if (original / rel).read_bytes() != (clone / rel).read_bytes():
                changed.append(rel)
        except Exception:
            pass
    return changed


def _commit_component_transaction(g: dict, work: Path, clone: Path, files: list[str], before: int, after: int, component: dict) -> tuple[bool, str]:
    originals: dict[str, bytes] = {}
    temporaries: list[Path] = []
    try:
        for rel in files:
            source = clone / rel
            destination = work / rel
            safe_member = source.suffix.lower() in _SOURCE_SUFFIXES or source.name in _TRANSACTION_CONFIG_NAMES
            if not source.is_file() or not safe_member:
                return False, f"unsafe transaction member: {rel}"
            resolved = destination.resolve(strict=False)
            if not resolved.is_relative_to(work.resolve()):
                return False, f"transaction path escapes project: {rel}"
            originals[rel] = destination.read_bytes()
            try:
                g["_v36_checkpoint_file"](work, rel, originals[rel].decode("utf-8", errors="replace"), "before_v4237_component_transaction")
            except Exception:
                pass
            temporary = destination.with_name(destination.name + ".v4237.tmp")
            temporary.write_bytes(source.read_bytes())
            temporaries.append(temporary)
        for rel, temporary in zip(files, temporaries):
            os.replace(temporary, work / rel)
        for rel in files:
            try:
                g["_v413_mark_accepted"](work, rel, "v4237_component_compiler_delta")
            except Exception:
                pass
        cid, root, adapter = _component_identity(component)
        g["_append_project_event"](
            work,
            "v4237_component_transaction_committed",
            f"V42.37 atomically promoted {len(files)} {cid} source edit(s) because isolated component diagnostics decreased {before} -> {after}.",
            component=cid,
            component_root=root,
            adapter=adapter,
            files=files,
            before=before,
            after=after,
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


def repair_component_failure(g: dict, user_request: object, manifest: dict | None, work: Path | str, failure: object, progress_callback=None) -> bool:
    """Repair one compiler component in a disposable multi-file transaction."""
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    text = str(failure or "")
    component = component_from_failure(manifest, text)
    if not component:
        return False
    cid, component_root, adapter = _component_identity(component)
    if adapter in _NODE_ADAPTERS:
        return False
    try:
        rows = list(g["_v4236_native_diagnostics"](root, manifest, text) or [])
        targets = list(g["_v4236_rank_native_targets"](rows, text) or [])
    except Exception:
        rows, targets = [], []
    targets = [rel for rel in targets if _component_identity(_component_for_rel(manifest, rel))[0] == cid]
    if not targets:
        return False

    before = diagnostic_count(text)
    if before <= 0:
        try:
            before = int(g.get("_v4236_native_error_count", lambda value: 0)(text) or 0)
        except Exception:
            before = 0
    signature = _failure_signature(component, rows, text)
    token = _repo_token(g, root)
    state_path = root / STATE_FILE
    state = _load(state_path, {"failures": {}})
    failures = state.setdefault("failures", {})
    strategy_generation = str(g.get("JARVIS_REPAIR_STRATEGY_GENERATION") or "legacy")
    entry = failures.setdefault(signature, {
        "component": cid,
        "component_root": component_root,
        "adapter": adapter,
        "repo_token": token,
        "strategy_generation": strategy_generation,
        "semantic_no_delta": [],
        "transport_failures": {},
        "transport_last_epoch": {},
        "transactions": [],
    })
    generation_changed = str(entry.get("strategy_generation") or "legacy") != strategy_generation
    if entry.get("repo_token") != token or generation_changed:
        if generation_changed:
            history = list(entry.get("prior_strategy_generations") or [])
            history.append({
                "strategy_generation": str(entry.get("strategy_generation") or "legacy"),
                "repo_token": str(entry.get("repo_token") or token),
                "semantic_no_delta": list(entry.get("semantic_no_delta") or []),
                "transaction_count": len(entry.get("transactions") or []),
            })
            entry["prior_strategy_generations"] = history[-8:]
        entry.update({
            "repo_token": token,
            "strategy_generation": strategy_generation,
            "semantic_no_delta": [],
            "transport_failures": {},
            "transport_last_epoch": {},
            "transactions": [],
        })
    exhausted = set(entry.get("semantic_no_delta") or [])
    try:
        max_targets = max(1, min(5, int(os.getenv("JARVIS_V4237_COMPONENT_TARGETS_PER_TRANSACTION", "3"))))
        strategy_generation = str(g.get("JARVIS_REPAIR_STRATEGY_GENERATION") or "")
        fast_tail = strategy_generation.startswith("rust-compiler-hints-v4-") or strategy_generation.startswith("functional-acceptance-v5-")
        transport_default = "1" if fast_tail else "2"
        cooldown_default = "1800" if fast_tail else "600"
        transport_limit = max(1, min(4, int(os.getenv("JARVIS_V4237_TRANSPORT_RETRIES_PER_STATE", transport_default))))
        transport_cooldown = max(60, min(3600, int(os.getenv("JARVIS_V4237_TRANSPORT_RETRY_COOLDOWN_SECONDS", cooldown_default))))
    except Exception:
        max_targets, transport_limit, transport_cooldown = 3, 1, 1800
    transport_counts = dict(entry.get("transport_failures") or {})
    transport_times = dict(entry.get("transport_last_epoch") or {})
    now = time.time()
    eligible = []
    for ordinal, rel in enumerate(targets):
        if rel in exhausted:
            continue
        count = int(transport_counts.get(rel) or 0)
        last = float(transport_times.get(rel) or 0.0)
        if count >= transport_limit and now - last < transport_cooldown:
            continue
        if count >= transport_limit:
            transport_counts[rel] = 0
            count = 0
        eligible.append((count, ordinal, rel))
    entry["transport_failures"] = transport_counts
    entry["transport_last_epoch"] = transport_times
    candidates = [rel for _count, _ordinal, rel in sorted(eligible)[:max_targets]]
    if not candidates:
        entry["result"] = "transport_cooldown" if any(
            int(transport_counts.get(rel) or 0) >= transport_limit for rel in targets if rel not in exhausted
        ) else "semantic_targets_exhausted"
        _save(state_path, state)
        return False

    command = None
    command_cwd = component_root
    try:
        command, cwd = g["_v429_live_component_command"](root, manifest, component)
        if cwd:
            command_cwd = _norm(Path(cwd).resolve().relative_to(root).as_posix())
    except Exception:
        pass
    bundle = {
        "version": "V" + VERSION,
        "engine": ENGINE,
        "component": {"id": cid, "root": component_root, "adapter": adapter},
        "validator": {"command": command or component.get("build_command") or "adapter-native", "cwd": command_cwd},
        "diagnostic_count": before,
        "diagnostic_files": targets,
        "selected_targets": candidates,
        "failure_signature": signature,
        "repository_token": token,
        "policy": "disposable component-only validation; promote only on strict diagnostic decrease",
    }
    _save(root / BUNDLE_FILE, bundle)
    g["_append_project_event"](
        root,
        "v4237_component_transaction_started",
        f"V42.37 opened a disposable {cid} repair transaction with exact component validator authority.",
        component=cid,
        component_root=component_root,
        adapter=adapter,
        files=candidates,
        diagnostic_count=before,
        validator_command=command,
        validator_cwd=command_cwd,
    )

    temp_handle = None
    try:
        temp_handle, clone = g["_copy_project_for_candidate_validation"](root)
        clone = Path(clone).resolve()
        staged: list[str] = []
        current_failure = text
        current_count = before
        for target in candidates:
            prompt = _model_patch_prompt(g, clone, manifest, component, target, targets, current_failure)
            ok, raw, failure_kind = _call_compact_editor(g, prompt, target, progress_callback)
            if not ok:
                transport = dict(entry.get("transport_failures") or {})
                transport[target] = int(transport.get(target) or 0) + 1
                entry["transport_failures"] = transport
                transport_times = dict(entry.get("transport_last_epoch") or {})
                transport_times[target] = time.time()
                entry["transport_last_epoch"] = transport_times
                entry["last_transport_error"] = str(raw or "")[-1800:]
                entry["last_transport_at"] = g["_utc_stamp"]()
                entry.setdefault("transactions", []).append({
                    "target": target,
                    "result": failure_kind + "_failure",
                    "at": g["_utc_stamp"](),
                })
                _save(state_path, state)
                g["_append_project_event"](
                    root,
                    "v4237_model_transport_failed",
                    f"V42.37 received no patch bytes for {target}; transport failure did not consume semantic no-progress budget.",
                    file=target,
                    component=cid,
                    failure_kind=failure_kind,
                )
                continue
            transport = dict(entry.get("transport_failures") or {})
            transport[target] = 0
            entry["transport_failures"] = transport
            transport_times = dict(entry.get("transport_last_epoch") or {})
            transport_times.pop(target, None)
            entry["transport_last_epoch"] = transport_times
            try:
                replacements, parse_error = g["_v38_parse_search_replace_blocks"](raw)
            except Exception as exc:
                replacements, parse_error = [], str(exc)
            if not replacements:
                entry.setdefault("transactions", []).append({"target": target, "result": "malformed_patch", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = str(parse_error or "")[-1200:]
                _save(state_path, state)
                continue
            path = clone / target
            try:
                original = path.read_text(encoding="utf-8", errors="replace")
                candidate, patch_error = g["_v36_apply_search_replace"](original, replacements)
            except Exception as exc:
                candidate, patch_error = "", str(exc)
            if patch_error or not candidate or candidate == original:
                entry.setdefault("transactions", []).append({"target": target, "result": "unusable_patch", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = str(patch_error or "no source delta")[-1200:]
                _save(state_path, state)
                continue
            safety = _candidate_safety(g, clone, manifest, target, candidate, current_failure)
            if safety:
                entry.setdefault("transactions", []).append({"target": target, "result": "safety_rejected", "at": g["_utc_stamp"]()})
                entry["last_patch_error"] = safety[-1200:]
                _save(state_path, state)
                continue
            path.write_text(candidate, encoding="utf-8")
            staged.append(target)

            valid, replay = g["_v35_validate_component"](clone, manifest, component, str(user_request or ""))
            replay = str(replay or "")
            after = 0 if valid else diagnostic_count(replay)
            improved = bool(valid or (current_count > 0 and after > 0 and after < current_count))
            entry.setdefault("transactions", []).append({
                "target": target,
                "staged": list(staged),
                "before": current_count,
                "after": after,
                "validator_ok": bool(valid),
                "result": "improved" if improved else "no_delta",
                "at": g["_utc_stamp"](),
            })
            entry["last_validation_output"] = replay[-5000:]
            _save(state_path, state)
            if improved:
                changed = _diff_selected(root, clone, staged)
                committed, reason = _commit_component_transaction(g, root, clone, changed, before, after, component)
                entry["result"] = "committed" if committed else "commit_failed"
                entry["last_commit_error"] = reason[-1200:]
                _save(state_path, state)
                return bool(committed)
            if after > current_count > 0:
                path.write_text(original, encoding="utf-8")
                staged = [rel for rel in staged if rel != target]
            else:
                current_failure = replay or current_failure
                current_count = after or current_count
        no_delta = list(entry.get("semantic_no_delta") or [])
        for rel in staged or candidates:
            if rel not in no_delta and int((entry.get("transport_failures") or {}).get(rel) or 0) == 0:
                no_delta.append(rel)
        entry["semantic_no_delta"] = no_delta
        entry["result"] = "bounded_no_delta"
        _save(state_path, state)
        g["_append_project_event"](
            root,
            "v4237_component_transaction_no_delta",
            f"V42.37 discarded the disposable {cid} transaction because exact-component diagnostics did not decrease.",
            component=cid,
            files=staged or candidates,
            diagnostic_count=before,
        )
        return False
    except Exception as exc:
        entry["result"] = "sandbox_failure"
        entry["last_error"] = str(exc)[-1800:]
        _save(state_path, state)
        try:
            g["_append_project_event"](
                root,
                "v4237_component_sandbox_failed",
                "V42.37 discarded the disposable component transaction after an infrastructure failure; authoritative source was not modified.",
                component=cid,
                error=str(exc)[-1200:],
            )
        except Exception:
            pass
        return False
    finally:
        _cleanup_temp(temp_handle)


def _dependency_names(package: dict) -> set[str]:
    output = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = package.get(key) or {}
        if isinstance(values, dict):
            output.update(str(name) for name in values)
    return output


def _suspicious_alias(value: str, component_root: Path, failure: str) -> bool:
    raw = str(value or "").replace("\\", "/")
    low = raw.lower()
    if low.endswith((".json", ".toml", ".yaml", ".yml", ".xml")):
        return True
    if raw.startswith(("/", "./", "../")):
        candidate = component_root / raw.lstrip("/")
        if not candidate.is_dir():
            return True
    normalized_failure = str(failure or "").replace("\\", "/").lower()
    return bool(raw and low.rstrip("/") + "/" in normalized_failure and "could not load" in normalized_failure)


def repair_dependency_alias(g: dict, work: Path | str, manifest: dict | None, failure: object, progress_callback=None) -> bool:
    """Remove a proven package-shadowing alias and validate it transactionally."""
    text = str(failure or "")
    low = text.lower()
    if not ("could not load" in low and "imported by" in low and ("vite:" in low or "rollup" in low)):
        return False
    root = Path(work).resolve()
    manifest = manifest if isinstance(manifest, dict) else {}
    components = [row for row in manifest.get("components") or [] if isinstance(row, dict)]
    node_components = [row for row in components if _component_identity(row)[2] in _NODE_ADAPTERS]
    for component in node_components:
        _cid, rel_root, _adapter = _component_identity(component)
        component_root = root if rel_root == "." else root / rel_root
        package_path = component_root / "package.json"
        package = _load(package_path, {})
        dependencies = _dependency_names(package) if isinstance(package, dict) else set()
        if not dependencies:
            continue
        for name in _CONFIG_NAMES:
            config = component_root / name
            if not config.is_file():
                continue
            source = config.read_text(encoding="utf-8", errors="replace")
            line_pattern = re.compile(
                r"(?m)^(?P<indent>[ \t]*)(?P<q>['\"])(?P<key>[^'\"]+)(?P=q)[ \t]*:[ \t]*(?P<vq>['\"])(?P<value>[^'\"]+)(?P=vq)[ \t]*,?[ \t]*(?:\r?\n|$)"
            )
            removals = []
            for match in line_pattern.finditer(source):
                key = match.group("key")
                value = match.group("value")
                if key in dependencies and _suspicious_alias(value, component_root, text):
                    removals.append(match.span())
            if not removals:
                continue
            candidate = source
            for start, end in reversed(removals):
                candidate = candidate[:start] + candidate[end:]
            rel = config.relative_to(root).as_posix()
            if _candidate_safety(g, root, manifest, rel, candidate, text):
                continue
            temp_handle = None
            try:
                temp_handle, clone = g["_copy_project_for_candidate_validation"](root)
                clone = Path(clone)
                candidate_path = clone / rel
                candidate_path.write_text(candidate, encoding="utf-8")
                ok, replay = g["_v35_validate_component"](clone, manifest, component, manifest.get("_original_user_request") or "")
                replay_text = str(replay or "")
                if not ok and "could not load" in replay_text.lower() and "imported by" in replay_text.lower():
                    continue
                original = config.read_text(encoding="utf-8", errors="replace")
                try:
                    g["_v36_checkpoint_file"](root, rel, original, "before_v4237_package_alias_repair")
                except Exception:
                    pass
                temporary = config.with_name(config.name + ".v4237.tmp")
                temporary.write_text(candidate, encoding="utf-8")
                os.replace(temporary, config)
                try:
                    g["_v413_mark_accepted"](root, rel, "v4237_validated_package_alias_repair")
                except Exception:
                    pass
                g["_append_project_event"](
                    root,
                    "v4237_package_shadow_alias_removed",
                    f"V42.37 removed {len(removals)} broken bundler alias(es) that shadowed installed packages; fresh component replay cleared the load failure.",
                    file=rel,
                    component=_cid,
                    aliases_removed=len(removals),
                    validator_ok=bool(ok),
                )
                g["_progress"](
                    progress_callback,
                    f"V42.37 repaired a package-shadowing alias in {rel}; rebuilding the exact component.",
                    stage="V42.37 deterministic configuration repair",
                    percent=82,
                    current_file=rel,
                    component=_cid,
                )
                return True
            finally:
                _cleanup_temp(temp_handle)
    return False


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_infrastructure = g["_v4220_infrastructure_failure"]
    previous_replay = g["_replay_validation_for_failure"]
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_real_repair = g["_repair_real_validation_failure"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_qwen = g["_qwen_call"]
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])
    previous_append = g["_append_project_event"]
    base_progress = g.get("_v4235_base_progress", g["_progress"])

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        # Preserve V42.36's component-aware stale-blocker invalidation before
        # projecting the current release identity. Bypassing this wrapper made
        # a newly accepted fix look blocked by already-repaired evidence.
        event = previous_append(work, event_type, message, **values)
        try:
            projection = Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
            data = _load(projection, {})
            if isinstance(data, dict):
                data.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
                _save(projection, data)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        value = str(text or "")
        value = re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.37", value)
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return base_progress(callback, value, **values)

    def infrastructure_failure(text):
        low = str(text or "").lower()
        # A compiler/bundler successfully launched and reported a project import.
        # That is source/config evidence, not a missing executable/spawn failure.
        if "could not load" in low and "imported by" in low and any(token in low for token in ("vite:", "rollup", "webpack", "esbuild")):
            return False
        if any(token in low for token in ("module not found", "cannot resolve module", "failed to resolve import")) and "spawn" not in low:
            return False
        return bool(previous_infrastructure(text))

    def replay_validation(work, user_request, manifest, failure):
        component = component_from_failure(manifest, failure)
        if component:
            try:
                return g["_v35_validate_component"](work, manifest, component, user_request)
            except Exception:
                pass
        return previous_replay(work, user_request, manifest, failure)

    def repair_round(user_request, manifest, work, audit, progress_callback=None, round_no=1):
        issues = [row for row in (audit or {}).get("issues") or [] if isinstance(row, dict)]
        for row in issues:
            if repair_dependency_alias(g, work, manifest, row.get("problem"), progress_callback):
                return True
        for row in issues:
            failure = str(row.get("problem") or "")
            try:
                native = bool(g["_v4236_is_native_compiler_failure"](work, manifest, failure))
            except Exception:
                native = False
            if native:
                # Resolve the repair controller at call time.  Newer releases
                # replace this registered entrypoint with additional deterministic
                # strategies and durable memory.  Calling the local implementation
                # directly captured V42.37 forever and silently bypassed every
                # later controller installed after this closure was created.
                controller = g.get("_v4237_repair_component_failure")
                if callable(controller):
                    return bool(controller(user_request, manifest, work, failure, progress_callback))
                return repair_component_failure(g, user_request, manifest, work, failure, progress_callback)
        return bool(previous_repair_round(user_request, manifest, work, audit, progress_callback, round_no))

    def real_repair(user_request, manifest, work, failure, progress_callback=None):
        if repair_dependency_alias(g, work, manifest, failure, progress_callback):
            return True
        try:
            if g["_v4236_is_native_compiler_failure"](work, manifest, failure):
                # Keep the native repair path dynamically dispatchable for the
                # same reason as repair_round above.  This is the production
                # path used by edit/resume runs, not merely a test hook.
                controller = g.get("_v4237_repair_component_failure")
                if callable(controller):
                    return bool(controller(user_request, manifest, work, failure, progress_callback))
                return repair_component_failure(g, user_request, manifest, work, failure, progress_callback)
        except Exception:
            pass
        return bool(previous_real_repair(user_request, manifest, work, failure, progress_callback))

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = (
            "\n\nV42.37 FINAL AUTHORITY: Repair evidence is component-scoped. Use the exact validator command/root and compiler-owned files in the current repair bundle. "
            "Candidate edits remain in a disposable sandbox until that same component passes or its diagnostic count strictly decreases. An unrelated component cannot veto an improving candidate. "
            "Model timeout is transport failure, not semantic no-progress. Package-loader ENOENT after a successful compiler launch is project configuration evidence, not missing-tool infrastructure. "
            "Preserve passing components and continue full build, test, runtime, integration, and requirement acceptance before publication."
        )
        return previous_qwen(
            str(prompt or "") + authority,
            progress_callback,
            re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.37", str(stage or "Generating")),
            profile=profile,
            **kwargs,
        )

    def release_identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "component-isolated-transaction-sandbox-v42.37",
            "exact_component_candidate_replay": True,
            "foreign_component_failure_cannot_veto_candidate": True,
            "disposable_component_transaction_sandbox": True,
            "atomic_multifile_native_commit": True,
            "strict_component_diagnostic_delta": True,
            "model_transport_failure_not_semantic_budget": True,
            "bounded_component_patch_watchdogs_seconds": {"worker": 240, "specialist": 480},
            "transport_retry_cooldown_prevents_tight_loop": True,
            "compact_direct_component_editor": True,
            "repair_bundle_records_command_cwd_files": True,
            "bundler_package_shadow_alias_repair": True,
            "package_loader_enoent_is_source_config_evidence": True,
            "generic_candidate_dependency_parity": True,
            "language_framework_toolchain_agnostic": True,
            "new_project_and_existing_project_edit_modes": True,
        })
        return data

    def stack_skill_names(manifest):
        names = list(previous_skills(manifest) or [])
        for name in ("component-transaction-sandbox", "compiler-evidence-bundle"):
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
        "V4237_VERSION": VERSION,
        "V4237_ENGINE": ENGINE,
        "V4237_STATE_FILE": STATE_FILE,
        "V4237_BUNDLE_FILE": BUNDLE_FILE,
        "_v4237_component_from_failure": component_from_failure,
        "_v4237_diagnostic_count": diagnostic_count,
        "_v4237_repair_component_failure": lambda request, manifest, work, failure, callback=None: repair_component_failure(g, request, manifest, work, failure, callback),
        "_v4237_repair_dependency_alias": lambda work, manifest, failure, callback=None: repair_dependency_alias(g, work, manifest, failure, callback),
        "_v4220_infrastructure_failure": infrastructure_failure,
        "_replay_validation_for_failure": replay_validation,
        "_v429_repair_audit_round": repair_round,
        "_repair_real_validation_failure": real_repair,
        "_append_project_event": append_event,
        "_progress": progress,
        "_qwen_call": qwen_call,
        "_v36_release_identity": release_identity,
        "_v36_stack_skill_names": stack_skill_names,
        "_v4237_engine_disk_guard": engine_guard,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
