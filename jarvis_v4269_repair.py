"""V42.69: compiler-in-the-loop repair sessions with export-aware closure checks.

V42.68 established durable project repair memory and bounded host-controlled tools.
V42.69 fixes three live-run failure modes observed on GearTrack:
1) exported JS/TS bindings are not falsely treated as unused locals;
2) one unambiguous JSON tool action may be safely extracted from common wrappers;
3) real component compiler/test proof feeds back into the SAME internal repair session.

The outer V42.51+ functional/component/regression gates remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import jarvis_v4250_repair as gates
import jarvis_v4251_repair as transactions
import jarvis_v4268_repair as sessions

VERSION = "42.69.0"
ENGINE = "COMPILER_LOOP_MEMORY_REPAIR_FACTORY"
STRATEGY = "functional-acceptance-v26-compiler-loop-memory-repair"

# One extra edit round is enough to repair compiler feedback without restoring
# the long unbounded behavior that V42.67 intentionally removed.
MAX_EDIT_ROUNDS = 4
MAX_TOOL_STEPS = 9

_JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}


def _exported_bindings(text: str) -> set[str]:
    """Best-effort exported declarations that are public API, not unused locals."""
    text = str(text or "")
    names: set[str] = set()
    declaration = re.compile(
        r"\bexport\s+(?:default\s+)?(?:declare\s+)?(?:async\s+)?"
        r"(?:function|class|const|let|var)\s+([A-Za-z_][A-Za-z_0-9]*)"
    )
    names.update(declaration.findall(text))
    for body in re.findall(r"\bexport\s*\{([^{}]{1,1200})\}", text):
        for raw in body.split(","):
            raw = re.sub(r"\s+as\s+[A-Za-z_][A-Za-z_0-9]*\s*$", "", raw.strip())
            raw = raw.split("/*", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", raw):
                names.add(raw)
    return names


def _closure_errors(rel, before, after):
    """V42.68 closure check, corrected for exported/public JS/TS bindings."""
    suffix = Path(str(rel)).suffix.lower()
    if suffix not in _JS_SUFFIXES:
        return []
    before_bindings = sessions._local_binding_sets(before)
    after_bindings = sessions._local_binding_sets(after)
    exported = _exported_bindings(after)
    errors = []
    for name in sorted(after_bindings):
        if name.startswith("_") or name in exported:
            continue
        if len(re.findall(r"\b" + re.escape(name) + r"\b", str(after))) <= 1:
            errors.append(
                f"local closure: binding {name!r} is declared/destructured but never used"
            )
    for name in sorted(before_bindings - after_bindings):
        if re.search(r"\b" + re.escape(name) + r"\b", str(after)):
            errors.append(
                f"local closure: old local binding {name!r} was removed but references to it remain"
            )
    return errors[:12]


def _validate_action(obj):
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("Tool action must be one JSON object with action.")
    allowed = set(sessions._TOOL_SCHEMA["properties"])
    if set(obj) - allowed:
        raise ValueError("Tool action contains unsupported fields.")
    action = str(obj.get("action") or "")
    if action not in set(sessions._TOOL_SCHEMA["properties"]["action"]["enum"]):
        raise ValueError("Tool action contains unsupported action.")
    return obj


def _parse_action(raw):
    """Accept direct JSON or one unambiguous valid action wrapped by the model.

    This deliberately does NOT repair malformed JSON and does not guess between
    multiple different actions. It only extracts a fully decoded, schema-valid
    object that is already present in the response.
    """
    text = sessions.owner_local._strip_fence(raw).strip()
    try:
        return _validate_action(json.loads(text))
    except Exception:
        pass

    candidates = []
    for body in re.findall(r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", text, re.I):
        try:
            candidates.append(_validate_action(json.loads(body.strip())))
        except Exception:
            pass

    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(text):
        brace = text.find("{", pos)
        if brace < 0:
            break
        try:
            value, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            pos = brace + 1
            continue
        try:
            candidates.append(_validate_action(value))
        except Exception:
            pass
        pos = max(end, brace + 1)

    unique = {}
    for obj in candidates:
        key = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        unique[key] = obj
    if len(unique) == 1:
        return next(iter(unique.values()))
    if len(unique) > 1:
        raise ValueError("Ambiguous response contained multiple different valid tool actions.")
    raise ValueError("Invalid tool action JSON: no complete schema-valid action found.")


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _proof_key(clone, rel):
    clone = Path(clone).resolve()
    return (str(clone), str(rel).replace("\\", "/"), _file_digest(clone / rel))


def _topology_hint(root, target):
    """Small deterministic topology hint for entrypoints without hard-coding a project."""
    target_path = Path(str(target).replace("\\", "/"))
    stem = target_path.stem.lower()
    if stem not in {"main", "app", "server", "index", "lib"}:
        return ""
    parent = (Path(root).resolve() / target_path).parent
    sibling_names = []
    try:
        for p in sorted(parent.iterdir()):
            if p.is_file() and p.name != target_path.name and p.suffix.lower() in {
                ".rs", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".cs"
            }:
                sibling_names.append(p.name)
    except Exception:
        pass
    manifests = []
    for name in ("Cargo.toml", "package.json", "pyproject.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts"):
        p = parent / name
        if p.exists():
            manifests.append(name)
        elif (parent.parent / name).exists():
            manifests.append("../" + name)
    if not sibling_names and not manifests:
        return ""
    return (
        "\nENTRYPOINT/MODULE TOPOLOGY HINT:\n"
        f"- sibling authored modules: {', '.join(sibling_names[:16]) or '(none)'}\n"
        f"- nearby manifests: {', '.join(manifests[:8]) or '(none)'}\n"
        "- before adding wrappers or module-qualified calls, reuse definitions already present in the real module/library topology\n"
        "- do not duplicate an existing handler/provider merely to make an entrypoint compile\n"
    )


def install(g: dict[str, Any]):
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]

    sessions._local_closure_errors = _closure_errors
    sessions._parse_action = _parse_action
    sessions.MAX_EDIT_ROUNDS = max(int(getattr(sessions, "MAX_EDIT_ROUNDS", 3)), MAX_EDIT_ROUNDS)
    sessions.MAX_TOOL_STEPS = max(int(getattr(sessions, "MAX_TOOL_STEPS", 7)), MAX_TOOL_STEPS)

    previous_contract = sessions._contract

    def contract(root, target, group, source, evidence, manifest, prior_errors):
        base = previous_contract(root, target, group, source, evidence, manifest, prior_errors)
        return (
            base
            + _topology_hint(root, target)
            + "\nCOMPILER-IN-THE-LOOP AUTHORITY:\n"
            "- after each syntactically clean edit Jarvis may run the real affected-component compiler/test proof\n"
            "- if that proof fails, treat its exact diagnostics as authoritative and repair them inside this SAME session\n"
            "- do not discard a useful draft merely because the first real compiler pass found fixable errors\n"
            "- prefer existing handlers/providers/types discovered by search/view/symbol/references over invented wrappers\n"
        )

    sessions._contract = contract

    previous_component_proof = gates._component_candidate_proof

    def component_proof(g2, root, clone, manifest, rel, progress_callback=None):
        key = _proof_key(clone, rel)
        cache = getattr(sessions._SESSION, "v4269_component_proof_cache", None)
        if isinstance(cache, dict) and key in cache:
            return dict(cache[key])
        result = previous_component_proof(g2, root, clone, manifest, rel, progress_callback)
        if not isinstance(cache, dict):
            cache = {}
            sessions._SESSION.v4269_component_proof_cache = cache
        cache[key] = dict(result or {})
        return result

    gates._component_candidate_proof = component_proof

    previous_quick = sessions._quick_diagnostics

    def quick_diagnostics(g2, clone, manifest, target, before, draft):
        errors = list(previous_quick(g2, clone, manifest, target, before, draft) or [])
        if errors or str(before) == str(draft):
            return errors

        root_value = str(getattr(sessions._SESSION, "root", "") or "")
        if not root_value:
            return errors
        accepted_root = Path(root_value).resolve()
        try:
            proof = gates._component_candidate_proof(
                g2, accepted_root, Path(clone).resolve(), manifest or {}, target, None
            )
        except Exception as exc:
            return ["component compiler preflight error: " + str(exc)[-2500:]]

        if not proof.get("ok"):
            tail = str(proof.get("output") or "")[-7000:]
            kind = str(proof.get("kind") or "component_proof")
            message = (
                f"REAL COMPONENT COMPILER/TEST PREFLIGHT FAILED ({kind}). "
                "Repair these exact diagnostics in this SAME session before returning a candidate:\n"
                + tail
            )
            try:
                source = (accepted_root / target).read_text(encoding="utf-8", errors="replace")
            except Exception:
                source = str(before or "")
            try:
                sessions._remember(
                    accepted_root, target, {"file": target}, source,
                    "component_preflight_failed", message,
                    attempt=int(getattr(sessions.owner_local._CALL, "attempt", 0) or 0),
                    step=0,
                )
            except Exception:
                pass
            return [message]
        return []

    sessions._quick_diagnostics = quick_diagnostics

    previous_repair_transaction = transactions.repair_transaction

    def repair_transaction(g2, request, manifest, root, group, callback=None, prior_errors=None):
        sessions._SESSION.v4269_component_proof_cache = {}
        try:
            return previous_repair_transaction(
                g2, request, manifest, root, group, callback, prior_errors
            )
        finally:
            try:
                delattr(sessions._SESSION, "v4269_component_proof_cache")
            except Exception:
                pass

    transactions.repair_transaction = repair_transaction

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r"jarvis_v42(?:4[0-9]|5[0-9]|6[0-8])_repair", name):
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
            planner_mode="compiler-loop-durable-memory-repair-v42.69",
            export_aware_js_ts_closure=True,
            wrapped_tool_action_extraction=True,
            ambiguous_tool_action_rejected=True,
            real_component_proof_inside_same_repair_session=True,
            exact_compiler_feedback_reused_in_session=True,
            exact_component_proof_cache=True,
            same_transaction_compiler_refinement=True,
            entrypoint_module_topology_hint=True,
            durable_project_repair_memory=True,
            host_controlled_sandbox_tools=["search", "view", "references", "symbol", "edit", "diagnose"],
            arbitrary_model_shell_access=False,
            exact_search_replace_existing_files=True,
            whole_file_rewrite_discouraged_and_bounded=True,
            max_internal_tool_steps=sessions.MAX_TOOL_STEPS,
            max_internal_edit_rounds=sessions.MAX_EDIT_ROUNDS,
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
        V4269_VERSION=VERSION,
        V4269_ENGINE=ENGINE,
    )
    try:
        Path(
            g.get("JARVIS_DIR") or Path(__file__).resolve().parent,
            "JARVIS_ACTIVE_ENGINE.txt",
        ).write_text("V" + VERSION + "\n", encoding="utf-8")
    except OSError:
        pass
