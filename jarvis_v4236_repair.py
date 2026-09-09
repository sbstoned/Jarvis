"""V42.36 fresh-component authority and native-compiler convergence patch.

V42.35 made TypeScript candidate validation trustworthy, but a mixed React/Rust
resume exposed two remaining orchestration defects:

* a component blocker stored as ``.`` survived a committed file repair because
  invalidation compared filenames instead of component ownership; and
* the inherited global TypeScript fast-recovery pass could edit a green frontend
  while the fresh failing validator was Cargo/Rust.

This focused install layer makes each freshly executed component validator the
owner of current-blocker state, resolves compiler paths relative to their real
component root, and gives non-TypeScript compiler failures a bounded, source-
revision-aware repair route.  The implementation is deliberately adapter-generic;
Rust is the captured regression, not a hard-coded project special case.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path


VERSION = "42.36.0"
ENGINE = "FRESH_COMPONENT_NATIVE_COMPILER_AUTHORITY_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
STATE_FILE = "JARVIS_V4236_NATIVE_FAILURE_STATE.json"

_NODE_ADAPTERS = {
    "node", "react", "vite", "nextjs", "vue", "sveltekit", "nuxt",
    "angular", "electron", "react_native", "expo",
}
_SOURCE_EXTENSIONS = (
    "c", "cc", "cpp", "cxx", "h", "hh", "hpp", "hxx", "rs", "go",
    "java", "kt", "kts", "cs", "fs", "vb", "swift", "m", "mm", "dart",
    "php", "rb", "py", "pyw", "ts", "tsx", "mts", "cts", "js", "jsx",
)
_SOURCE_SUFFIXES = {"." + value for value in _SOURCE_EXTENSIONS}
_SKIP_PARTS = {
    ".git", ".cargo", "registry", "rustc", "node_modules", "target", "vendor", ".gradle", "caches", ".nuget",
    ".jarvis_runtime", ".jarvis_build", ".jarvis_candidates", "dist", "build",
}


def _norm(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/\"")
    text = re.sub(r"^\./", "", text)
    return "." if text in {"", "."} else text


def _json_load(path: Path, default=None):
    fallback = {} if default is None else default
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value
    except Exception:
        return fallback


def _json_save(path: Path, value: object) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".v4236.tmp")
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass


def _manifest_from_disk(work: Path | str) -> dict:
    root = Path(work)
    for name in ("JARVIS_V33_ARCHITECTURE.json", "JARVIS_PROJECT_STATE.json"):
        data = _json_load(root / name, {})
        if not isinstance(data, dict):
            continue
        if name == "JARVIS_PROJECT_STATE.json" and isinstance(data.get("manifest"), dict):
            data = data["manifest"]
        if isinstance(data.get("components"), list):
            return data
    return {}


def _component_for_rel(manifest: dict | None, rel: object) -> dict:
    target = _norm(rel)
    matches = []
    fallback = None
    for component in (manifest or {}).get("components") or []:
        if not isinstance(component, dict):
            continue
        root = _norm(component.get("root") or ".")
        if root == ".":
            fallback = fallback or component
            continue
        if target == root or target.startswith(root.rstrip("/") + "/"):
            matches.append((len(root.split("/")), component))
    if matches:
        return max(matches, key=lambda item: item[0])[1]
    return fallback or {}


def _component_identity(component: dict | None) -> tuple[str, str, str]:
    component = component or {}
    root = _norm(component.get("root") or ".")
    adapter = str(component.get("toolchain_adapter") or component.get("adapter") or "").strip().lower()
    cid = str(component.get("id") or root or adapter or "component")
    return cid, root, adapter


def _component_from_failure(manifest: dict | None, failure: object) -> dict:
    text = str(failure or "")
    match = re.search(
        r"COMPONENT FAILED\s*\[\s*([^|\]]+)\|\s*([^|\]]+)\|\s*([^\]]+)\]",
        text,
        re.I,
    )
    if match:
        cid, adapter, root = (part.strip() for part in match.groups())
        for component in (manifest or {}).get("components") or []:
            if not isinstance(component, dict):
                continue
            ccid, croot, cadapter = _component_identity(component)
            if ccid == cid or croot == _norm(root):
                return component
        return {"id": cid, "root": _norm(root), "toolchain_adapter": adapter.lower()}
    low = text.lower()
    inferred = ""
    if "cargo" in low or "rustc" in low or re.search(r"error\[e\d{4}\]", low):
        inferred = "rust"
    elif "go test" in low or "go build" in low:
        inferred = "go"
    elif "dotnet" in low or re.search(r"\berror\s+cs\d{4}\b", low):
        inferred = "dotnet"
    elif "gradle" in low or "maven" in low or "javac" in low or "kotlinc" in low:
        inferred = "java"
    elif "swift build" in low or "xcodebuild" in low:
        inferred = "swift"
    if inferred:
        for component in (manifest or {}).get("components") or []:
            if not isinstance(component, dict):
                continue
            _cid, _root, adapter = _component_identity(component)
            if inferred in adapter or (inferred == "java" and adapter in {"android_gradle", "kotlin_gradle", "java_gradle", "java_maven"}):
                return component
    return {}


def _existing_project_rel(work: Path | str, raw_path: object, component_root: object = ".") -> str:
    root = Path(work).resolve()
    raw = str(raw_path or "").strip().strip("\"'<> ").replace("\\", "/")
    raw = re.sub(r"^file:/+", "/", raw, flags=re.I)
    raw = re.sub(r"^\./", "", raw)
    if not raw:
        return ""

    # Exact absolute path on the current host.
    try:
        candidate = Path(raw)
        if candidate.is_absolute():
            rel = candidate.resolve(strict=False).relative_to(root).as_posix()
            if (root / rel).is_file():
                return _norm(rel)
    except Exception:
        pass

    # Never accept dependency/toolchain diagnostics as project repair targets.
    lowered_parts = {part.lower() for part in raw.split("/") if part}
    if lowered_parts & _SKIP_PARTS:
        return ""

    values = []
    plain = re.sub(r"^[A-Za-z]:/", "", raw).lstrip("/")
    if plain:
        values.append(plain)
    component_root = _norm(component_root)
    if component_root != "." and plain and not plain.startswith(component_root.rstrip("/") + "/"):
        values.insert(0, component_root.rstrip("/") + "/" + plain)

    # Compiler output may prefix a cwd. Try every suffix, but accept only a real file.
    for value in list(values):
        parts = value.split("/")
        values.extend("/".join(parts[index:]) for index in range(1, len(parts)))
    seen = set()
    for value in values:
        rel = _norm(value)
        if rel in seen:
            continue
        seen.add(rel)
        path = root / rel
        try:
            if path.is_file() and path.resolve(strict=False).is_relative_to(root):
                return rel
        except Exception:
            continue
    return ""


def native_diagnostics(work: Path | str, manifest: dict | None, failure: object) -> list[dict]:
    """Extract real project locations from native compiler output.

    Paths emitted relative to a component cwd (for example Cargo's ``src/tools.rs``
    while running in ``src-tauri``) are converted to project-relative paths.
    """
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(failure or ""))
    component = _component_from_failure(manifest, text)
    cid, component_root, adapter = _component_identity(component)
    extension_group = "|".join(re.escape(value) for value in _SOURCE_EXTENSIONS)
    marker_pattern = re.compile(
        rf"(?P<marker>-->|:::)\s*(?P<file>.+?\.(?:{extension_group})):(?P<line>\d+)(?::(?P<col>\d+))?\s*$",
        re.I,
    )
    ordinary_pattern = re.compile(
        rf"^(?P<file>.+?\.(?:{extension_group})):(?P<line>\d+)(?::(?P<col>\d+))?(?::|\s+-)?\s*(?P<message>.*)$",
        re.I,
    )
    dotnet_pattern = re.compile(
        r"^(?P<file>.+?\.(?:cs|fs|vb))\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<message>.*)$",
        re.I,
    )
    rows = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = marker_pattern.search(line)
        role = "definition" if match and match.group("marker") == ":::" else "primary"
        if not match:
            match = dotnet_pattern.match(line) or ordinary_pattern.match(line)
            role = "primary"
        if not match:
            continue
        rel = _existing_project_rel(work, match.group("file"), component_root)
        if not rel or Path(rel).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        key = (rel, match.group("line"), match.groupdict().get("col") or "", role)
        if key in seen:
            continue
        seen.add(key)
        message = str(match.groupdict().get("message") or "").strip()
        code_match = re.search(r"\b(?:error\s*)?\[?([A-Z]{1,4}\d{3,5})\]?", message, re.I)
        rows.append({
            "file": rel,
            "line": int(match.group("line")),
            "col": int(match.groupdict().get("col") or 0),
            "role": role,
            "code": code_match.group(1).upper() if code_match else "",
            "message": message,
            "raw": line,
            "component": cid,
            "component_root": component_root,
            "adapter": adapter,
        })
    return rows


def _native_error_count(failure: object) -> int:
    text = str(failure or "")
    totals = [int(value) for value in re.findall(r"(?:due to|aborting due to)\s+(\d+)\s+previous errors?", text, re.I)]
    totals += [int(value) for value in re.findall(r"Found\s+(\d+)\s+errors?", text, re.I)]
    explicit = len(re.findall(r"(?m)^\s*(?:error(?:\[[A-Z]?\d+\])?|[^\n:]+:\d+(?::\d+)?:\s*error\b)", text, re.I))
    return max(totals + [explicit, 0])


def _native_kind(manifest: dict | None, failure: object) -> str:
    _cid, _root, adapter = _component_identity(_component_from_failure(manifest, failure))
    if adapter:
        return adapter
    low = str(failure or "").lower()
    if "cargo" in low or "rustc" in low or re.search(r"error\[e\d{4}\]", low):
        return "rust"
    if "dotnet" in low or re.search(r"\berror\s+cs\d{4}\b", low):
        return "dotnet"
    if "go test" in low or "go build" in low:
        return "go"
    return "native"


def _native_signature(work: Path | str, manifest: dict | None, failure: object) -> str:
    rows = native_diagnostics(work, manifest, failure)
    codes = sorted(set(re.findall(r"\b(?:E|CS|TS|FS|BC|KT)\d{3,5}\b", str(failure or ""), re.I)))
    files = sorted({row["file"] for row in rows})
    material = {
        "kind": _native_kind(manifest, failure),
        "files": files,
        "codes": [value.upper() for value in codes],
        "count": _native_error_count(failure),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return "native:" + digest


def _is_native_compiler_failure(work: Path | str, manifest: dict | None, failure: object) -> bool:
    rows = native_diagnostics(work, manifest, failure)
    if not rows:
        return False
    kind = _native_kind(manifest, failure)
    if kind in _NODE_ADAPTERS:
        return False
    text = str(failure or "").lower()
    return bool(
        _native_error_count(failure)
        or "command failed" in text
        or "could not compile" in text
        or "compilation failed" in text
        or re.search(r"error\[[a-z]?\d{3,5}\]", text)
    )


def _rank_native_targets(rows: list[dict], failure: object) -> list[str]:
    by_file = {}
    for row in rows:
        info = by_file.setdefault(row["file"], {"primary": 0, "definition": 0, "total": 0})
        info[row.get("role") or "primary"] = info.get(row.get("role") or "primary", 0) + 1
        info["total"] += 1
    low = str(failure or "").lower()
    # Provider-first is useful for ordinary missing trait implementations, but SQLx
    # composite row decoding is different: `(Struct, Extra)` asks SQLx to decode
    # `Struct` as one scalar column. The struct definition is only a help/note site;
    # the actual repair belongs to the query/use site that constructed the tuple.
    sqlx_composite_fromrow = bool(
        re.search(r"trait bound `?[A-Z][A-Za-z0-9_]*: sqlx::(?:Decode|Type)", str(failure or ""), re.I)
        and re.search(r"required for `\([^`]+\)` to implement .*FromRow", str(failure or ""), re.I)
    )
    definition_first = (not sqlx_composite_fromrow) and any(token in low for token in (
        "trait bound", "is not implemented for", "doesn't satisfy", "defined multiple times",
        "cannot find type", "unresolved import", "unresolved module", "cannot find symbol",
    ))
    def key(item):
        rel, info = item
        provider = info.get("definition", 0)
        primary = info.get("primary", 0)
        preferred = provider if definition_first else primary
        secondary = primary if definition_first else provider
        return (-int(preferred > 0), -preferred, -secondary, -info.get("total", 0), rel)
    return [rel for rel, _info in sorted(by_file.items(), key=key)]


def _projection_path(g: dict, work: Path | str) -> Path:
    return Path(work) / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")


def _write_current_blocker(g: dict, work: Path | str, blocker: dict | None, reason: str) -> None:
    root = Path(work)
    path = _projection_path(g, root)
    data = _json_load(path, {})
    if not isinstance(data, dict):
        data = {}
    data.update({
        "version": "V" + VERSION,
        "engine": ENGINE,
        "updated_at": g["_utc_stamp"](),
        "fresh_validation_required": False,
        "blocker_authority": "fresh_component_validator",
        "blocker_authority_reason": reason,
    })
    if blocker:
        data["current_blocker"] = blocker
        data["component"] = blocker.get("component")
        data["file"] = blocker.get("file")
    else:
        data.pop("current_blocker", None)
    _json_save(path, data)

    # The convergence controller has its own compact state in addition to the
    # journal projection. Keep both views atomic so an older fallback cannot read
    # a stale React blocker after the projection has already moved to Rust.
    try:
        convergence = g["_v4218_state"](root)
        if not isinstance(convergence, dict):
            convergence = {}
        convergence["current_blocker"] = blocker
        convergence["stalled"] = False
        convergence["v4236_blocker_authority"] = reason
        convergence["v4236_updated_at"] = g["_utc_stamp"]()
        g["_v4218_save_state"](root, convergence)
    except Exception:
        pass

    # Keep the dashboard's compact status aligned with the same authoritative fact.
    status_path = root / g.get("V33_BUILD_STATUS_FILE", "JARVIS_V33_BUILD_STATUS.json")
    status = _json_load(status_path, {})
    if isinstance(status, dict) and status:
        status.update({"version": "V" + VERSION, "engine": ENGINE})
        if blocker:
            status["current_blocker"] = blocker
            status["current_file"] = blocker.get("file") or ""
            status["stage"] = "fresh component compiler failure"
        else:
            old = status.get("current_blocker")
            if isinstance(old, dict):
                status.pop("current_blocker", None)
        _json_save(status_path, status)


def record_component_result(
    g: dict,
    work: Path | str,
    manifest: dict | None,
    component: dict | None,
    ok: bool,
    output: object,
) -> None:
    manifest = manifest if isinstance(manifest, dict) else _manifest_from_disk(work)
    cid, component_root, adapter = _component_identity(component)
    projection = _json_load(_projection_path(g, work), {})
    current = projection.get("current_blocker") if isinstance(projection, dict) else None
    current_component = str((current or {}).get("component") or "") if isinstance(current, dict) else ""
    if ok:
        if current_component == cid:
            _write_current_blocker(g, work, None, f"fresh green validation for {cid}")
        return
    rows = native_diagnostics(work, manifest, output)
    targets = _rank_native_targets(rows, output)
    blocker = {
        "file": targets[0] if targets else component_root,
        "kind": "component_validation",
        "component": cid,
        "component_root": component_root,
        "adapter": adapter,
        "problem": str(output or "")[-12000:],
        "diagnostic_files": targets[:12],
        "diagnostic_count": _native_error_count(output),
        "signature": _native_signature(work, manifest, output) if rows else "",
    }
    _write_current_blocker(g, work, blocker, f"fresh failing validation for {cid}")


def reconcile_saved_validation(g: dict, work: Path | str, manifest: dict | None) -> None:
    data = _json_load(Path(work) / g.get("V35_VALIDATION_FILE", "JARVIS_V35_VALIDATION.json"), {})
    if not isinstance(data, dict):
        return
    by_id = {}
    for component in (manifest or {}).get("components") or []:
        if isinstance(component, dict):
            by_id[_component_identity(component)[0]] = component
    for row in data.get("components") or []:
        if not isinstance(row, dict):
            continue
        component = by_id.get(str(row.get("id") or "")) or {
            "id": row.get("id"), "root": row.get("root"),
            "toolchain_adapter": row.get("adapter"),
        }
        record_component_result(g, work, manifest, component, bool(row.get("ok")), row.get("output"))


def _source_hashes(work: Path | str, manifest: dict | None) -> dict[str, str]:
    root = Path(work)
    candidates = []
    for item in (manifest or {}).get("files") or []:
        if isinstance(item, dict) and item.get("path"):
            candidates.append(_norm(item.get("path")))
    if not candidates:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            try:
                rel = path.relative_to(root)
            except Exception:
                continue
            if {part.lower() for part in rel.parts} & _SKIP_PARTS:
                continue
            candidates.append(rel.as_posix())
    output = {}
    for rel in dict.fromkeys(candidates):
        path = root / rel
        try:
            if path.is_file():
                output[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            pass
    return output


def _repo_token(g: dict, work: Path | str) -> str:
    try:
        return str(g["_v429_progress_token"](work))
    except Exception:
        rows = _source_hashes(work, {})
        return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def repair_native_compiler_failure(
    g: dict,
    previous_file_repair,
    user_request: object,
    manifest: dict | None,
    work: Path | str,
    failure: object,
    progress_callback=None,
) -> bool:
    manifest = manifest if isinstance(manifest, dict) else _manifest_from_disk(work)
    rows = native_diagnostics(work, manifest, failure)
    targets = _rank_native_targets(rows, failure)
    if not targets:
        return False
    component = _component_from_failure(manifest, failure) or _component_for_rel(manifest, targets[0])
    cid, component_root, adapter = _component_identity(component)
    signature = _native_signature(work, manifest, failure)
    token = _repo_token(g, work)
    state_path = Path(work) / STATE_FILE
    state = _json_load(state_path, {})
    entries = state.setdefault("failures", {}) if isinstance(state, dict) else {}
    entry = entries.setdefault(signature, {
        "component": cid,
        "component_root": component_root,
        "adapter": adapter,
        "repo_token": token,
        "attempted_targets": [],
        "attempts": 0,
    })
    if entry.get("repo_token") != token:
        entry.update({"repo_token": token, "attempted_targets": [], "attempts": 0, "stopped": False})
    attempted = list(entry.get("attempted_targets") or [])
    target = next((value for value in targets if value not in attempted), "")
    max_targets = max(1, min(6, int(os.getenv("JARVIS_V4236_NATIVE_TARGETS_PER_REVISION", "4"))))
    if not target or len(attempted) >= max_targets:
        if not entry.get("stopped"):
            entry["stopped"] = True
            entry["stopped_at"] = g["_utc_stamp"]()
            state.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
            _json_save(state_path, state)
            g["_append_project_event"](
                work,
                "v4236_native_no_progress_stop",
                f"V42.36 stopped the unchanged {cid} compiler failure after bounded, distinct compiler-owned targets; it did not rotate into a green component.",
                component=cid,
                files=targets[:12],
                failure_signature=signature,
                attempted_targets=attempted,
            )
        return False

    entry["attempted_targets"] = attempted + [target]
    entry["attempts"] = int(entry.get("attempts") or 0) + 1
    entry["last_attempt_at"] = g["_utc_stamp"]()
    state.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
    _json_save(state_path, state)
    exact = "\n".join(row["raw"] for row in rows if row["file"] == target)[:5000]
    connected = ", ".join(targets[:10])
    problem = (
        "V42.36 FRESH NATIVE-COMPILER AUTHORITY. The currently executed component validator, "
        f"not a checkpoint or stale audit, identifies component {cid!r} ({adapter}, root {component_root!r}). "
        f"Repair compiler-owned target {target!r}. Connected compiler locations: {connected}. "
        "Use complete current source and the actual public contracts. For a definition/trait/schema error, repair the canonical definition; "
        "for a type/call mismatch, repair the consuming edge. Do not touch another green component. Do not silence errors with placeholders, "
        "fake values, disabled tests, broad suppressions, or duplicated compatibility types. The candidate is accepted only when replay of the "
        "same native component strictly reduces its compiler error count or fully passes.\n\n"
        f"TARGET-SPECIFIC LOCATIONS:\n{exact or target}\n\n"
        f"FRESH NATIVE COMPILER OUTPUT:\n{str(failure or '')[-12000:]}"
    )
    g["_progress"](
        progress_callback,
        f"V42.36 fresh compiler routing: repairing {target} in failing component {cid}; green components are frozen.",
        stage="V42.36 native compiler repair",
        percent=84,
        current_file=target,
        component=cid,
    )
    g["_append_project_event"](
        work,
        "v4236_native_target_selected",
        f"V42.36 selected {target} from fresh {cid} compiler locations and excluded green-component recovery.",
        file=target,
        files=targets[:12],
        component=cid,
        failure_signature=signature,
        diagnostic_count=_native_error_count(failure),
    )

    before_hashes = _source_hashes(work, manifest)
    before_token = _repo_token(g, work)
    saved_fast = g.get("_v4221_fast_static_recovery")
    if saved_fast is not None:
        g["_v4221_fast_static_recovery"] = lambda *args, **kwargs: []
    try:
        repaired = bool(previous_file_repair(
            user_request,
            manifest,
            work,
            target,
            [problem],
            progress_callback,
            validation_failure=str(failure or ""),
        ))
    except Exception as exc:
        repaired = False
        entry["last_error"] = str(exc)[:1800]
    finally:
        if saved_fast is not None:
            g["_v4221_fast_static_recovery"] = saved_fast

    after_hashes = _source_hashes(work, manifest)
    changed_files = sorted({
        rel for rel in set(before_hashes) | set(after_hashes)
        if before_hashes.get(rel) != after_hashes.get(rel)
    })
    if repaired and changed_files and _repo_token(g, work) == before_token:
        marker = g.get("_v413_mark_accepted")
        if marker:
            for rel in changed_files:
                try:
                    marker(work, rel, "v4236_native_compiler_delta")
                except Exception:
                    pass
    accepted = bool(repaired and changed_files and _repo_token(g, work) != before_token)
    entry["result"] = "accepted" if accepted else "no_accepted_delta"
    entry["changed_files"] = changed_files[:20]
    entry["repo_token_after"] = _repo_token(g, work)
    _json_save(state_path, state)
    if accepted:
        g["_append_project_event"](
            work,
            "v4236_native_repair_accepted",
            f"V42.36 accepted a source-changing repair in {cid}; a fresh native rebuild is now mandatory before another target is chosen.",
            file=target,
            files=changed_files,
            component=cid,
            failure_signature=signature,
        )
    else:
        g["_append_project_event"](
            work,
            "v4236_native_target_no_delta",
            f"V42.36 obtained no accepted source delta for {target}; the target is bounded at this repository revision.",
            file=target,
            component=cid,
            failure_signature=signature,
        )
    return accepted


def _changed_event_files(fields: dict) -> list[str]:
    values = []
    for key in ("file", "files", "changed_files"):
        raw = fields.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif raw:
            values.append(raw)
    for row in fields.get("changes") or []:
        if isinstance(row, dict):
            values.append(row.get("file") or row.get("path"))
        elif row:
            values.append(row)
    return list(dict.fromkeys(_norm(value) for value in values if value))


def _component_aware_invalidate(g: dict, work: Path | str, event_type: object, fields: dict) -> None:
    event = str(event_type or "").lower()
    progress_event = any(token in event for token in (
        "committed", "accepted", "repaired", "fast_fix", "removed", "closed", "reconciled",
    ))
    improved = False
    try:
        improved = int(fields.get("after")) < int(fields.get("before"))
    except Exception:
        pass
    if not (progress_event or improved):
        return
    path = _projection_path(g, work)
    data = _json_load(path, {})
    blocker = data.get("current_blocker") if isinstance(data, dict) else None
    if not isinstance(blocker, dict):
        return
    manifest = _manifest_from_disk(work)
    blocker_component = str(blocker.get("component") or "")
    if not blocker_component:
        blocker_component = _component_identity(_component_for_rel(manifest, blocker.get("file")))[0]
    changed_files = _changed_event_files(fields)
    changed_components = {
        _component_identity(_component_for_rel(manifest, rel))[0]
        for rel in changed_files
    }
    blocker_file = _norm(blocker.get("file"))
    exact = blocker_file in changed_files
    same_component = bool(blocker_component and blocker_component in changed_components)
    if exact or same_component:
        data.pop("current_blocker", None)
        data["fresh_validation_required"] = True
        data["invalidated_blocker"] = {
            "file": blocker_file,
            "component": blocker_component,
            "by_event": event,
            "changed_files": changed_files[:20],
            "at": g["_utc_stamp"](),
        }
        _json_save(path, data)
        try:
            convergence = g["_v4218_state"](work)
            if isinstance(convergence, dict):
                convergence["current_blocker"] = None
                convergence["stalled"] = False
                convergence["v4236_blocker_authority"] = "component repair requires fresh validation"
                g["_v4218_save_state"](work, convergence)
        except Exception:
            pass


def install(g: dict) -> None:
    PathType = g["Path"]
    previous_real_repair = g["_repair_real_validation_failure"]
    previous_file_repair = g["_repair_file_for_issues"]
    previous_validate_component = g["_v35_validate_component"]
    previous_whole_audit = g["_v429_whole_project_audit"]
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_resume_seed = g["_resume_seed_from_workspace"]
    previous_copy_candidate = g["_copy_project_for_candidate_validation"]
    previous_clone_cluster = g["_v4224_clone_workspace"]
    previous_runtime_present = g["_runtime_failure_still_present"]
    previous_failure_signature = g["_validation_failure_signature"]
    previous_identity = g["_v36_release_identity"]
    previous_skill_names = g["_v36_stack_skill_names"]
    previous_generate = g.get("_v4235_previous_generate_project_zip", g["generate_project_zip"])
    previous_edit = g.get("_v4235_previous_analyze_project_zip", g["analyze_and_edit_project_zip"])
    previous_qwen = g.get("_v4235_previous_qwen_call", g["_qwen_call"])
    durable_append = g.get("_v4235_durable_append_project_event", g["_append_project_event"])
    base_progress = g.get("_v4235_base_progress", g["_progress"])
    prepare_runtime = g["_v4235_prepare_candidate_runtime"]

    def append_event(work, event_type, message, **fields):
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        event = durable_append(work, event_type, message, **values)
        try:
            path = _projection_path(g, work)
            data = _json_load(path, {})
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
                _json_save(path, data)
            _component_aware_invalidate(g, work, event_type, values)
        except Exception:
            pass
        return event

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(
                r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)",
                "V42.36",
                str(text),
            )
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return base_progress(callback, text, **values)

    def validate_component(work, manifest, component, user_request=""):
        ok, output = previous_validate_component(work, manifest, component, user_request)
        try:
            record_component_result(g, work, manifest, component, bool(ok), output)
        except Exception:
            pass
        return ok, output

    def whole_project_audit(work, user_request, manifest, run_components=True, progress_callback=None):
        # V42.21's inherited pre-audit pass scans every TS/TSX file and may change a
        # green component before the current failing validator is even executed.
        saved_fast = g.get("_v4221_fast_static_recovery")
        if saved_fast is not None:
            g["_v4221_fast_static_recovery"] = lambda *args, **kwargs: []
        try:
            payload = previous_whole_audit(work, user_request, manifest, run_components, progress_callback)
        finally:
            if saved_fast is not None:
                g["_v4221_fast_static_recovery"] = saved_fast
        # Prefer a fresh component compiler failure over static/checkpoint ordering.
        failures = []
        for row in (payload or {}).get("issues") or []:
            if not isinstance(row, dict) or str(row.get("kind") or "") != "component_validation":
                continue
            if _is_native_compiler_failure(work, manifest, row.get("problem")):
                failures.append(row)
        if failures:
            selected = failures[0]
            component = next((
                item for item in (manifest or {}).get("components") or []
                if isinstance(item, dict) and _component_identity(item)[0] == str(selected.get("component") or "")
            ), None) or _component_from_failure(manifest, selected.get("problem"))
            record_component_result(g, work, manifest, component, False, selected.get("problem"))
        return payload

    def repair_native(user_request, manifest, work, failure, progress_callback=None):
        return repair_native_compiler_failure(
            g, g.get("_repair_file_for_issues", previous_file_repair),
            user_request, manifest, work, failure, progress_callback
        )

    def real_failure_repair(user_request, manifest, work, failure, progress_callback=None):
        if _is_native_compiler_failure(work, manifest, failure):
            return repair_native(user_request, manifest, work, failure, progress_callback)
        return bool(previous_real_repair(user_request, manifest, work, failure, progress_callback))

    def repair_audit_round(user_request, manifest, work, audit, progress_callback=None, round_no=1):
        # Route a current native compiler failure before the inherited global
        # deterministic TypeScript scan. If it cannot advance, return no progress
        # to the existing circuit breaker instead of editing a green component.
        for row in (audit or {}).get("issues") or []:
            if not isinstance(row, dict) or str(row.get("kind") or "") != "component_validation":
                continue
            failure = str(row.get("problem") or "")
            if _is_native_compiler_failure(work, manifest, failure):
                return repair_native(user_request, manifest, work, failure, progress_callback)
        return previous_repair_round(user_request, manifest, work, audit, progress_callback, round_no)

    def resume_seed(work, source_zip, user_request):
        seed = previous_resume_seed(work, source_zip, user_request)
        try:
            reconcile_saved_validation(g, work, seed.get("manifest") or {})
        except Exception:
            pass
        return seed

    def copy_candidate(work):
        temporary, clone = previous_copy_candidate(work)
        try:
            prepare_runtime(work, clone, _manifest_from_disk(work))
        except Exception:
            pass
        return temporary, clone

    def clone_cluster(work):
        temporary, clone = previous_clone_cluster(work)
        try:
            prepare_runtime(work, clone, _manifest_from_disk(work))
        except Exception:
            pass
        return temporary, clone

    def runtime_failure_still_present(original_failure, replay_failure):
        # A native candidate advances only on a strict native diagnostic decrease,
        # not merely because line numbers or the last truncated diagnostic changed.
        original_manifest = {}
        original_kind = _native_kind(original_manifest, original_failure)
        original_count = _native_error_count(original_failure)
        if original_count and original_kind not in _NODE_ADAPTERS:
            replay_text = str(replay_failure or "")
            replay_count = _native_error_count(replay_text)
            replay_kind = _native_kind({}, replay_text)
            replay_failed = bool(re.search(r"\b(error|failed|could not compile|command failed)\b", replay_text, re.I))
            if replay_failed and replay_kind != original_kind:
                return True
            if replay_count:
                return replay_count >= original_count
            if replay_failed:
                return True
            return False
        return previous_runtime_present(original_failure, replay_failure)

    def failure_signature(failure):
        text = str(failure or "")
        if _native_error_count(text) and (
            "cargo" in text.lower() or "could not compile" in text.lower() or re.search(r"error\[e\d{4}\]", text, re.I)
        ):
            # No project path is needed for the state signature: compiler codes and
            # normalized path text are stable across line movement and temp roots.
            codes = sorted(set(re.findall(r"\bE\d{4}\b", text, re.I)))
            paths = sorted(set(
                _norm(value) for value in re.findall(r"(?:-->|:::)\s*(.+?\.rs):\d+(?::\d+)?", text)
            ))
            material = {"kind": "rust", "codes": [x.upper() for x in codes], "paths": paths, "count": _native_error_count(text)}
            return "native:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:24]
        return previous_failure_signature(failure)

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = (
            "\n\nV42.36 FINAL AUTHORITY: Fresh native compiler/build/test output owns repair routing. "
            "Resolve every diagnostic path relative to the component command working directory, and modify only compiler-owned files in the failing component. "
            "Freeze components that just passed. Treat checkpoint projections and old audits as historical evidence, never as authority over a newer validator. "
            "Stage related provider/consumer changes transactionally and accept them only when replay of the same component strictly lowers its native diagnostic count or passes. "
            "Candidate workspaces must share the accepted dependency substrate without packaging dependencies. Continue through all builds, tests, runtime smoke, integration contracts, and explicit requirements before publication. "
            "These rules apply to every supported language, framework, engine, and custom declared toolchain."
        )
        return previous_qwen(
            str(prompt or "") + authority,
            progress_callback,
            re.sub(r"\bV(?:3[5-9]|4[0-2])(?:\.\d+){0,2}\b(?!\.\d)", "V42.36", str(stage or "Generating")),
            profile=profile,
            **kwargs,
        )

    def release_identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "fresh-component-native-compiler-authority-v42.36",
            "fresh_component_result_owns_current_blocker": True,
            "component_relative_diagnostic_path_resolution": True,
            "green_component_freeze_during_foreign_component_failure": True,
            "global_pre_audit_source_mutation_disabled": True,
            "native_compiler_distinct_target_budget": True,
            "native_candidate_requires_strict_error_count_delta": True,
            "stable_native_failure_signature_ignores_line_movement": True,
            "generic_candidate_dependency_parity": True,
            "component_aware_stale_blocker_invalidation": True,
            "language_framework_toolchain_agnostic": True,
            "new_project_and_existing_project_edit_modes": True,
        })
        return data

    def stack_skill_names(manifest):
        names = list(previous_skill_names(manifest) or [])
        if "native-compiler-authority" not in names:
            names.append("native-compiler-authority")
        return names[:24]

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
        return previous_generate(
            user_request,
            max_files=max_files,
            max_audit_passes=max_audit_passes,
            progress_callback=progress_callback,
        )

    def analyze_and_edit_project_zip(user_request, source_zip, max_audit_passes=None, progress_callback=None):
        ok, message = engine_guard()
        if not ok:
            return False, message, None
        return previous_edit(
            user_request,
            source_zip,
            max_audit_passes=max_audit_passes,
            progress_callback=progress_callback,
        )

    g.update({
        "V4236_VERSION": VERSION,
        "V4236_ENGINE": ENGINE,
        "V4236_STATE_FILE": STATE_FILE,
        "_v4236_native_diagnostics": lambda work, manifest, failure: native_diagnostics(work, manifest, failure),
        "_v4236_rank_native_targets": _rank_native_targets,
        "_v4236_is_native_compiler_failure": lambda work, manifest, failure: _is_native_compiler_failure(work, manifest, failure),
        "_v4236_record_component_result": lambda work, manifest, component, ok, output: record_component_result(g, work, manifest, component, ok, output),
        "_v4236_reconcile_saved_validation": lambda work, manifest: reconcile_saved_validation(g, work, manifest),
        "_v4236_repair_native_compiler_failure": repair_native,
        "_v4236_engine_disk_guard": engine_guard,
        "_copy_project_for_candidate_validation": copy_candidate,
        "_v4224_clone_workspace": clone_cluster,
        "_v35_validate_component": validate_component,
        "_v429_whole_project_audit": whole_project_audit,
        "_v429_repair_audit_round": repair_audit_round,
        "_repair_real_validation_failure": real_failure_repair,
        "_resume_seed_from_workspace": resume_seed,
        "_runtime_failure_still_present": runtime_failure_still_present,
        "_validation_failure_signature": failure_signature,
        "_append_project_event": append_event,
        "_progress": progress,
        "_qwen_call": qwen_call,
        "_v36_release_identity": release_identity,
        "_v36_stack_skill_names": stack_skill_names,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
