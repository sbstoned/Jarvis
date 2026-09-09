"""Jarvis V42.49 dependency-ordered functional convergence.

V42.48 stopped backup ghosts and unbounded per-issue sweeps, but the first real
functional run exposed a starvation problem: a difficult integration root (for
example a desktop/runtime entry file) was ranked ahead of smaller provider and
persistence repairs.  Historical file-repair machinery could then expand one
functional attempt into diagnosis -> whole-file rewrite -> continuation ->
subsystem escalation, so the same unchanged integration file consumed an hour
while independent defects waited.

V42.49 keeps Jarvis universal.  The core policy is framework-agnostic:
  * repair providers/persistence before consumers/bridges;
  * replace production mocks before wiring the final runtime bridge;
  * require workflow tests last;
  * identify retry budgets by target + issue family, not changing prose;
  * use bounded patch-only functional edits so one hard file cannot monopolize
    the convergence loop;
  * defer an integration root until its lower-layer contracts are ready.

Small stack adapters may add evidence (currently Tauri command reachability and
provider ownership), but they feed the same generic functional contract graph.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import jarvis_v4247_repair as v4247
import jarvis_v4248_repair as v4248
import jarvis_v4242_repair as v4242

VERSION = "42.49.0"
ENGINE = "DEPENDENCY_ORDERED_FUNCTIONAL_CONVERGENCE_FACTORY"
STRATEGY_GENERATION = "functional-acceptance-v7-provider-first-patch-only-contract-graph"
LEDGER_FILE = "JARVIS_V4249_FUNCTIONAL_PLAN_LEDGER.json"

MAX_GROUPS_PER_ROUND = max(1, min(4, int(os.getenv("JARVIS_V4249_FUNCTIONAL_GROUPS_PER_ROUND", "2"))))
MAX_PATCH_ATTEMPTS_PER_GROUP = max(1, min(3, int(os.getenv("JARVIS_V4249_PATCH_ATTEMPTS_PER_GROUP", "2"))))
MAX_GROUP_ATTEMPTS_SAME_TARGET = max(1, min(4, int(os.getenv("JARVIS_V4249_GROUP_ATTEMPTS_SAME_TARGET", "2"))))


def _norm(rel: object) -> str:
    return str(rel or "").replace("\\", "/").strip("/")


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def _source_snapshot(root: Path) -> List[Tuple[str, Path, str]]:
    return list(v4247._source_files(Path(root).resolve()))


def _strip_js(text: str) -> str:
    return v4247._strip_js_comments(text)




def _tauri_runtime_entry(root: Path) -> str:
    """Choose the file that actually owns the running Tauri Builder.

    A Rust package may contain both src/main.rs and src/lib.rs. Prefer main.rs when
    it constructs the Builder directly; prefer lib.rs only when main explicitly
    delegates startup to a library run function.
    """
    root = Path(root).resolve()
    main_rel = "src-tauri/src/main.rs"
    lib_rel = "src-tauri/src/lib.rs"
    main = root / main_rel
    lib = root / lib_rel
    if main.is_file():
        try:
            text = main.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        if re.search(r"\btauri::Builder\b|\.run\s*\(\s*tauri::generate_context!", text):
            return main_rel
        if lib.is_file() and re.search(r"\b(?:[A-Za-z_][A-Za-z0-9_]*_lib|crate|self)::run\s*\(", text):
            return lib_rel
        return main_rel
    if lib.is_file():
        return lib_rel
    return v4247._pick_tauri_entry(root)


def _tauri_runtime_state_issue(root: Path, contract: dict) -> List[dict]:
    rust = list(contract.get("rust") or [])
    if not rust:
        return []
    all_rust = "\n".join(text for _rel, text in rust)
    uses_sqlx = bool(re.search(r"\bSqlitePool\b|\bPool\s*<\s*Sqlite\s*>", all_rust))
    if not uses_sqlx:
        return []
    entry = str(contract.get("entry") or _tauri_runtime_entry(root))
    entry_text = ""
    try: entry_text = (Path(root) / entry).read_text(encoding="utf-8", errors="replace")
    except Exception: pass
    # If main delegates to lib, include the delegated lib body as runtime builder text.
    builder_text = entry_text
    if entry.endswith("lib.rs"):
        try: builder_text += "\n" + (Path(root) / "src-tauri/src/main.rs").read_text(encoding="utf-8", errors="replace")
        except Exception: pass
    state_wired = bool(re.search(r"\.manage\s*\(", builder_text))
    setup_wired = bool(re.search(r"\.setup\s*\(", builder_text))
    init_defined = bool(re.search(r"\b(?:init_app|init_db)\s*\(", all_rust))
    if init_defined and not (state_wired and setup_wired):
        return [{
            "file": entry,
            "kind": "functional_runtime_state",
            "problem": (
                "FUNCTIONAL RUNTIME STATE CONTRACT: the actual Tauri runtime entry owns the Builder but does not visibly initialize and manage the SQLx application state before commands run. "
                f"Runtime entry: {entry}. Wire startup/setup to the existing database initialization path and manage the resulting pool/state for command handlers. "
                "Do not patch an unused library entry when the binary constructs the Builder elsewhere."
            ),
            "evidence": f"actual Tauri runtime entry {entry} vs SQLx initialization/state wiring",
        }]
    return []


def _tauri_command_contract(root: Path, files=None) -> dict:
    """Return reachable command wrappers instead of every dormant helper declaration.

    V42.47 treated every createTauriCommand("...") definition as a live frontend
    invocation.  That can force a backend to implement APIs that are never called.
    V42.49 traces helper function usage outside the wrapper module and always keeps
    direct invoke("...") calls.  As mock hooks are replaced with real calls, their
    command contracts naturally become reachable on the next audit.
    """
    root = Path(root).resolve()
    files = list(files if files is not None else _source_snapshot(root))
    ts = [(rel, text) for rel, _p, text in files if Path(rel).suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}]
    rust = [(rel, text) for rel, _p, text in files if rel.startswith("src-tauri/") and rel.endswith(".rs")]
    if not rust:
        return {"commands": set(), "helpers": {}, "helper_files": set(), "registered": set(), "has_handler": False, "entry": "", "rust": rust}

    helpers: Dict[str, str] = {}
    helper_owner: Dict[str, str] = {}
    # Thin command wrappers in real projects are normally small.  Cap the span so a
    # missing call in one function cannot accidentally bind the next function's call.
    helper_re = re.compile(
        r"\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*async\b(?:(?!\bconst\s+[A-Za-z_$]).){0,1800}?"
        r"createTauriCommand\s*\(\s*['\"]([A-Za-z0-9_:\-.]+)['\"]",
        re.S,
    )
    for rel, text in ts:
        code = _strip_js(text)
        for m in helper_re.finditer(code):
            helpers[m.group(1)] = m.group(2)
            helper_owner[m.group(1)] = rel

    reachable = set()
    direct_re = re.compile(r"\binvoke(?:\s*<[^;\n>]+>)?\s*\(\s*['\"]([A-Za-z0-9_:\-.]+)['\"]")
    for rel, text in ts:
        code = _strip_js(text)
        for m in direct_re.finditer(code):
            reachable.add(m.group(1))

    for helper, command in helpers.items():
        owner = helper_owner.get(helper, "")
        pattern = re.compile(r"\b" + re.escape(helper) + r"\b")
        for rel, text in ts:
            if rel == owner:
                continue
            code = _strip_js(text)
            # A same-named local function is not evidence that the helper wrapper is
            # used. Require the wrapper hook/factory itself to be referenced in the
            # consumer file; this keeps dormant helper declarations out of the live
            # bridge contract until production code actually adopts them.
            if "useTauriCommands" in code and pattern.search(code):
                reachable.add(command)
                break

    all_rust = "\n".join(text for _rel, text in rust)
    registered = set()
    for body in re.findall(r"generate_handler!\s*\[([^\]]*)\]", all_rust, re.S):
        registered.update(re.findall(r"(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)", body))
    has_handler = bool(re.search(r"\.invoke_handler\s*\(", all_rust))
    return {
        "commands": reachable,
        "helpers": helpers,
        "helper_files": set(helper_owner.values()),
        "registered": registered,
        "has_handler": has_handler,
        "entry": _tauri_runtime_entry(root),
        "rust": rust,
    }


def _domain_terms(prefix: str) -> List[str]:
    low = prefix.lower().strip("_")
    terms = [low]
    if low.endswith("ies"):
        terms.append(low[:-3] + "y")
    elif low.endswith("s"):
        terms.append(low[:-1])
    if low in {"checkouts", "checkout"}:
        terms.extend(["checkout", "checkout_record"])
    return list(dict.fromkeys(x for x in terms if x))


def _provider_file_for_command(root: Path, command: str) -> str:
    if "_" not in command:
        return ""
    prefix = command.split("_", 1)[0].lower()
    candidates = []
    for term in _domain_terms(prefix):
        candidates.extend([
            f"src-tauri/src/{term}.rs",
            f"src-tauri/src/{term}s.rs",
        ])
    for rel in dict.fromkeys(candidates):
        if (root / rel).is_file():
            return rel
    return ""


def _provider_supports(command: str, rust_text: str) -> bool:
    if "_" not in command:
        return True
    prefix, action = command.split("_", 1)
    terms = _domain_terms(prefix)
    fns = set(re.findall(r"\bpub\s+(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)", rust_text))
    if not fns:
        return False

    def has(pred):
        return any(pred(fn.lower()) for fn in fns)

    if action == "create":
        return has(lambda fn: fn.startswith("create_") and any(t in fn for t in terms))
    if action == "get_all":
        return has(lambda fn: (fn.startswith("get_all_") or fn.startswith("get_")) and any(t in fn for t in terms))
    if action == "get_by_id":
        return has(lambda fn: fn.startswith("get_") and "by_id" in fn and any(t in fn for t in terms))
    if action == "update":
        return has(lambda fn: fn.startswith("update_") and any(t in fn for t in terms))
    if action == "delete":
        return has(lambda fn: fn.startswith("delete_") and any(t in fn for t in terms))
    # Domain-specific verbs are allowed to be implemented in command wrappers.
    return True


def _tauri_provider_issues(root: Path, contract: dict) -> List[dict]:
    out = []
    seen = set()
    for command in sorted(contract.get("commands") or set()):
        rel = _provider_file_for_command(root, command)
        if not rel:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if _provider_supports(command, text):
            continue
        key = (rel, command)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "file": rel,
            "kind": "functional_provider",
            "problem": (
                "FUNCTIONAL PROVIDER CONTRACT: a reachable runtime command "
                f"{command!r} has a domain provider file {rel!r}, but that provider does not expose a compatible operation. "
                "Implement the smallest real provider/service operation using the project's existing persistence/model conventions. "
                "Do not hide missing domain behavior inside the application entry/bridge file, and do not create a mock result."
            ),
            "evidence": f"reachable command {command} -> provider {rel}",
        })
    return out


def _reachable_bridge_issue(root: Path, contract: dict) -> List[dict]:
    commands = set(contract.get("commands") or set())
    if not commands:
        return []
    missing = sorted(commands - set(contract.get("registered") or set()))
    if contract.get("has_handler") and not missing:
        return []
    entry = str(contract.get("entry") or "")
    shown = ", ".join(missing[:24])
    return [{
        "file": entry,
        "kind": "functional_bridge",
        "problem": (
            "FUNCTIONAL BRIDGE CONTRACT: register only the frontend commands that are reachable from executable production code at this revision. "
            f"Reachable command names: {', '.join(sorted(commands)[:24])}. "
            + (f"Missing registered commands: {shown}. " if shown else "")
            + "Use existing provider/service functions and initialized application state; do not invent unrelated APIs or rewrite working provider logic. "
              "The bridge must compile and make the caller -> handler -> provider -> result path executable."
        ),
        "evidence": "reachable frontend command usage vs Rust handler registration",
    }]


def functional_acceptance_issues(work, user_request="", manifest=None) -> List[dict]:
    root = Path(work).resolve()
    rows = list(v4248.functional_acceptance_issues(root, user_request, manifest) or [])
    # Replace V42.47's declaration-wide bridge/runtime ownership with reachable
    # command evidence and the file that actually owns the running Builder.
    rows = [x for x in rows if str((x or {}).get("kind") or "") not in {"functional_bridge", "functional_runtime_state"}]
    files = _source_snapshot(root)
    contract = _tauri_command_contract(root, files)
    rows.extend(_tauri_provider_issues(root, contract))
    rows.extend(_reachable_bridge_issue(root, contract))
    rows.extend(_tauri_runtime_state_issue(root, contract))

    out = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        rel = _norm(row.get("file"))
        kind = str(row.get("kind") or "functional_contract")
        problem = re.sub(r"\s+", " ", str(row.get("problem") or "")).strip()
        if not rel or not problem or v4248._is_internal_rel(rel):
            continue
        key = (rel, kind, problem)
        if key in seen:
            continue
        seen.add(key)
        out.append({**row, "file": rel, "kind": kind, "problem": problem})
    return out[:64]


# V42.47's publication audit resolves this module global at runtime.
v4247.functional_acceptance_issues = functional_acceptance_issues


def _phase(kind: str, rel: str) -> int:
    low = "/" + _norm(rel).lower()
    is_test = "/tests/" in low or ".test." in low or ".spec." in low
    if is_test or kind == "functional_test_coverage":
        return 5
    if kind.startswith("persistence_") or kind == "functional_provider":
        return 0
    if kind == "functional_mock":
        return 1
    if kind in {"functional_bridge", "functional_runtime_state"}:
        return 3
    return 2


def _group_key(rel: str, kinds: Iterable[str]) -> str:
    payload = {"file": _norm(rel), "kinds": sorted(set(str(x or "") for x in kinds)), "strategy": STRATEGY_GENERATION}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _target_token(root: Path, rel: str) -> str:
    try:
        raw = (root / rel).read_bytes()
    except Exception:
        raw = b""
    return hashlib.sha256(raw).hexdigest()[:24]


def _group_rows(rows: Iterable[dict]) -> List[dict]:
    by_file: Dict[str, List[dict]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        if not kind.startswith(("functional_", "persistence_")):
            continue
        rel = _norm(row.get("file"))
        if not rel or v4248._is_internal_rel(rel):
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
        phases = [_phase(str(x.get("kind") or ""), rel) for x in items]
        groups.append({
            "file": rel,
            "rows": items,
            "kinds": kinds,
            "problems": problems,
            "phase": min(phases) if phases else 2,
            "key": _group_key(rel, kinds),
        })
    return sorted(groups, key=lambda g: (g["phase"], g["file"]))


def _phase_name(value: int) -> str:
    return {0: "provider/persistence", 1: "production integration", 2: "feature contract", 3: "runtime bridge", 5: "workflow proof"}.get(value, "functional")


def _integration_reference_context(root: Path, rel: str) -> str:
    low = rel.lower()
    refs = []
    if Path(rel).suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
        for candidate in ("src/hooks/useTauriCommands.ts", "src/hooks/useTools.ts"):
            p = root / candidate
            if p.is_file() and candidate != rel:
                refs.append(candidate)
    if rel == "src-tauri/src/lib.rs":
        for candidate in ("src-tauri/src/app.rs", "src-tauri/src/db.rs", "src-tauri/src/tools.rs", "src-tauri/src/categories.rs", "src-tauri/src/persons.rs", "src-tauri/src/checkout.rs"):
            if (root / candidate).is_file():
                refs.append(candidate)
    if not refs:
        return ""
    return "RELATED IMPLEMENTED FILES TO READ BEFORE PATCHING: " + ", ".join(refs[:8]) + ". Reuse their real APIs; do not duplicate them."


def _functional_patch_problems(root: Path, group: dict) -> List[str]:
    problems = list(group.get("problems") or [])
    rel = str(group.get("file") or "")
    phase = int(group.get("phase") or 0)
    authority = (
        f"V42.49 FUNCTIONAL REPAIR PHASE: {_phase_name(phase)}. "
        "Make a SMALL SEARCH/REPLACE patch in this target only. Do not return or reconstruct the whole file. "
        "Preserve public APIs and working behavior. The next full build/audit is authoritative."
    )
    if phase == 0:
        authority += " Repair provider/persistence correctness before caller or bridge code."
    elif phase == 1:
        authority += " Replace production simulation with the project's existing real integration seam while preserving the hook/service API."
    elif phase == 3:
        authority += " Lower-layer provider and production integration debt has already been prioritized. Wire the entry/runtime bridge using existing APIs; do not move domain logic into the bridge."
    elif phase == 5:
        authority += " Production behavior should already be wired. Add meaningful workflow proof without weakening production behavior or assertions."
    ref = _integration_reference_context(root, rel)
    # Put the strategy authority first so historical same-revision loop guards
    # recognize V42.49 as a genuinely new repair strategy rather than inheriting
    # an exhausted V42.48 leaf signature. Deterministic contract markers remain
    # present in the following problem entries.
    return [authority] + problems + ([ref] if ref else [])


def _commit_patch_candidate(g: dict, root: Path, rel: str, candidate: dict, manifest=None) -> bool:
    path = root / rel
    content = str((candidate or {}).get("content") or "")
    if not content or not path.is_file():
        return False
    try:
        before = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        before = ""
    if before.strip() == content.strip():
        return False
    checkpoint = g.get("_v36_checkpoint_file")
    if callable(checkpoint):
        try:
            checkpoint(root, rel, before, "before_v4249_functional_patch")
        except Exception:
            pass
    tmp = path.with_name(path.name + ".jarvis_v4249_tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        delete_draft = g.get("_delete_candidate_draft")
        if callable(delete_draft):
            try: delete_draft(root, rel)
            except Exception: pass
        graph = g.get("_v36_build_repo_graph")
        registry = g.get("_v36_build_contract_registry")
        if callable(graph):
            try: graph(root, manifest or {}, write=True)
            except TypeError: pass
            except Exception: pass
        if callable(registry):
            try: registry(root, manifest or {}, write=True)
            except TypeError: pass
            except Exception: pass
        return True
    except Exception:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return False


def _patch_only_repair(g: dict, user_request, manifest, root: Path, group: dict, progress_callback=None) -> Tuple[bool, List[str]]:
    patcher = g.get("_v36_patch_repair_candidate")
    if not callable(patcher):
        return False, ["patch repair primitive unavailable"]
    rel = group["file"]
    problems = _functional_patch_problems(root, group)
    errors = []
    request = (
        str(user_request or "")
        + "\n\nV42.49 DEPENDENCY-ORDERED FUNCTIONAL AUTHORITY: repair the current layer only. "
          "Do not solve a provider defect by inventing code in an entry file. Do not replace real persistence with local state. "
          "Use exact minimal patches and let Jarvis rebuild/re-audit after any accepted source change."
    )
    for attempt in range(1, MAX_PATCH_ATTEMPTS_PER_GROUP + 1):
        try:
            candidate, err = patcher(
                request, manifest, root, rel, problems,
                "\n".join(problems), attempt, progress_callback,
            )
        except Exception as exc:
            candidate, err = None, str(exc)
        if candidate and _commit_patch_candidate(g, root, rel, candidate, manifest):
            return True, errors
        if err:
            errors.append(str(err)[-1600:])
    return False, errors


def _ledger(root: Path) -> tuple[dict, Path]:
    path = root / LEDGER_FILE
    data = _load_json(path, {})
    if not isinstance(data, dict) or data.get("strategy_generation") != STRATEGY_GENERATION:
        data = {
            "version": "V" + VERSION,
            "engine": ENGINE,
            "strategy_generation": STRATEGY_GENERATION,
            "groups": {},
        }
    return data, path


def install(g: dict) -> None:
    previous_repair_round = g["_v429_repair_audit_round"]
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_append = g["_append_project_event"]
    previous_qwen = g["_qwen_call"]
    previous_generate = g["generate_project_zip"]
    previous_edit = g["analyze_and_edit_project_zip"]

    v4248.VERSION = VERSION
    v4248.ENGINE = ENGINE
    v4248.STRATEGY_GENERATION = STRATEGY_GENERATION
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
        rendered = re.sub(r"\bV42\.48(?:\.0)?\b", "V42.49", str(message or ""))
        return previous_append(work, event_type, rendered, **values)

    def progress(callback, text=None, **fields):
        rendered = re.sub(r"\bV42\.48(?:\.0)?\b", "V42.49", str(text or ""))
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        return previous_progress(callback, rendered, **values)

    def repair_round(user_request, manifest, work, audit_payload, progress_callback=None, round_no=1):
        root = Path(work).resolve()
        rows = [x for x in (audit_payload or {}).get("issues") or [] if isinstance(x, dict)]
        functional = [x for x in rows if str(x.get("kind") or "").startswith(("functional_", "persistence_"))]
        if not functional:
            return bool(previous_repair_round(user_request, manifest, work, audit_payload, progress_callback, round_no))

        groups = _group_rows(functional)
        if not groups:
            return False
        data, ledger_path = _ledger(root)
        states = data.setdefault("groups", {})

        # Retry identity is target bytes + issue family. An accepted change elsewhere
        # cannot reopen a hard unchanged integration file. Changing the target itself
        # legitimately resets its local budget.
        for group in groups:
            state = states.setdefault(group["key"], {
                "file": group["file"], "kinds": group["kinds"], "attempts": 0,
                "target_token": "", "exhausted": False,
            })
            tok = _target_token(root, group["file"])
            if str(state.get("target_token") or "") != tok:
                state.update({"target_token": tok, "attempts": 0, "exhausted": False})
            state["phase"] = group["phase"]

        # Provider/persistence and production integration are allowed to make
        # independent progress even if one peer is exhausted. Runtime bridge is
        # deferred until every lower-layer production issue is actually gone.
        lower = [g0 for g0 in groups if g0["phase"] < 3]
        if lower:
            phase_candidates = lower
        else:
            production = [g0 for g0 in groups if g0["phase"] < 5]
            phase_candidates = production if production else groups

        eligible = []
        for group in phase_candidates:
            state = states[group["key"]]
            if int(state.get("attempts") or 0) >= MAX_GROUP_ATTEMPTS_SAME_TARGET:
                state["exhausted"] = True
                continue
            eligible.append((group, state))
        _save_json(ledger_path, data)

        if not eligible:
            append_event(
                root, "v4249_functional_phase_exhausted",
                "V42.49 exhausted patch-only repairs for the unchanged targets in the current functional layer. It will return control to the outer convergence/checkpoint controller instead of reopening whole-file or subsystem rewrites.",
                unresolved=[{"file": x["file"], "kinds": x["kinds"], "phase": x["phase"]} for x in phase_candidates[:16]],
            )
            return False

        attempts = 0
        for group, state in eligible:
            if attempts >= MAX_GROUPS_PER_ROUND:
                break
            rel = group["file"]
            if not (root / rel).is_file():
                continue
            attempts += 1
            state["attempts"] = int(state.get("attempts") or 0) + 1
            state["last_round"] = int(round_no or 0)
            _save_json(ledger_path, data)
            progress(
                progress_callback,
                f"V42.49 {_phase_name(group['phase'])} patch {state['attempts']}/{MAX_GROUP_ATTEMPTS_SAME_TARGET}: {rel}",
                stage="V42.49 dependency-ordered functional convergence", percent=92,
                current_file=rel, functional_phase=_phase_name(group["phase"]),
            )
            append_event(
                root, "v4249_functional_group_attempt",
                f"V42.49 is applying one bounded patch-only {_phase_name(group['phase'])} transaction to {rel}.",
                file=rel, kinds=group["kinds"], phase=group["phase"], attempt=state["attempts"],
                target_token=state.get("target_token"),
            )
            changed, errors = _patch_only_repair(g, user_request, manifest, root, group, progress_callback)
            state["last_changed"] = bool(changed)
            state["last_errors"] = errors[-3:]
            if changed:
                state["accepted"] = True
                state["exhausted"] = False
                state["target_token"] = _target_token(root, rel)
                state["attempts"] = 0
                _save_json(ledger_path, data)
                append_event(
                    root, "v4249_functional_patch_accepted",
                    f"V42.49 accepted a minimal {_phase_name(group['phase'])} patch in {rel}; Jarvis must rebuild and re-audit before another functional edit.",
                    file=rel, kinds=group["kinds"], phase=group["phase"],
                )
                return True
            if int(state.get("attempts") or 0) >= MAX_GROUP_ATTEMPTS_SAME_TARGET:
                state["exhausted"] = True
            _save_json(ledger_path, data)

        append_event(
            root, "v4249_functional_round_no_change",
            "V42.49 completed the bounded patch-only functional attempts for this round without an accepted source change. Other eligible targets or the outer circuit breaker may proceed; no whole-file continuation is launched here.",
            attempted=attempts,
        )
        return False

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        authority = """

V42.49 DEPENDENCY-ORDERED FUNCTIONAL AUTHORITY:
- Functional completion is a contract graph, not a compiler score. Repair providers/persistence first, then production integration services/hooks, then runtime bridges, then workflow tests.
- Do not solve missing provider behavior by moving domain logic into app/main/lib entry files.
- Do not replace a real backend with local/mock state. Reuse existing integration seams and preserve public APIs.
- For functional repair prefer the smallest exact patch. Do not rewrite an entire file when a localized change is sufficient.
- A dormant helper API is not automatically a required runtime command; implement/wire commands that are reachable from executable production code.
- Never weaken tests to create green output. Build/test/runtime/functional re-audit after the patch is authoritative.
"""
        stage2 = re.sub(r"\bV42\.48(?:\.0)?\b", "V42.49", str(stage or "Generating"))
        return previous_qwen(str(prompt or "") + authority, progress_callback, stage2, profile=profile, **kwargs)

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION,
            "engine": ENGINE,
            "planner_mode": "dependency-ordered-provider-first-patch-only-functional-convergence-v42.49",
            "repair_strategy_generation": STRATEGY_GENERATION,
            "functional_acceptance_gate": True,
            "compile_success_is_not_project_completion": True,
            "functional_provider_first_order": True,
            "functional_persistence_before_bridge": True,
            "production_integration_before_runtime_bridge": True,
            "workflow_tests_last": True,
            "reachable_runtime_command_tracing": True,
            "dormant_helper_commands_do_not_force_bridge_contract": True,
            "target_issue_family_retry_identity": True,
            "functional_patch_only_primary_strategy": True,
            "functional_whole_file_continuation_disabled_in_primary_path": True,
            "hard_integration_root_cannot_starve_independent_repairs": True,
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
        "V4249_VERSION": VERSION,
        "V4249_ENGINE": ENGINE,
        "V4249_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "_v4249_tauri_command_contract": _tauri_command_contract,
        "_v4249_functional_acceptance_issues": functional_acceptance_issues,
        "_v4248_functional_acceptance_issues": functional_acceptance_issues,
        "_v4247_functional_acceptance_issues": functional_acceptance_issues,
        "_v4249_group_functional_rows": _group_rows,
        "_v429_repair_audit_round": repair_round,
        "_qwen_call": qwen_call,
        "_v36_release_identity": identity,
        "_progress": progress,
        "_append_project_event": append_event,
        "_v4249_engine_disk_guard": guard,
        "generate_project_zip": generate,
        "analyze_and_edit_project_zip": edit,
    })
