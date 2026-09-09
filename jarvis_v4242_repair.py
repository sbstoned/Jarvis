"""Jarvis V42.46 convergence control and compiler-hint last-mile repair.

V42.41 proved that deterministic, validator-gated repair can make large real
progress, but a volatile diagnostic fingerprint allowed the same accepted
repository revision to re-enter repair.  Once the bounded repair was exhausted,
older global audit wrappers also continued to run.

V42.46 keeps the accepted repository revision plus component the circuit-breaker
authority, normalizes compiler evidence for reporting, checkpoints automatically
at an exhausted safe boundary, emits live heartbeats, and shares structured
evidence with Jarvis workers through the local SQLite/WAL memory layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import jarvis_v4237_repair as v4237
import jarvis_v4240_repair as v4240
import jarvis_v4241_repair as v4241
import jarvis_v4242_memory as shared_memory


VERSION = "42.50.0"
ENGINE = "REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY"
ENGINE_MARKER = "JARVIS_ACTIVE_ENGINE.txt"
LEDGER_FILE = "JARVIS_V4242_REVISION_LEDGER.json"
TRACE_FILE = "JARVIS_V4242_CONVERGENCE_TRACE.jsonl"
STATUS_FILE = "JARVIS_V4242_REPAIR_STATUS.md"
RUN_STATE_FILE = "JARVIS_V4242_RUN_STATE.json"
TERMINAL_FILE = "JARVIS_V4242_TERMINAL_STATE.json"
VALIDATOR_EVIDENCE_FILE = "JARVIS_V4242_VALIDATOR_EVIDENCE.json"
VALIDATOR_OUTPUT_FILE = "JARVIS_V4242_LAST_VALIDATOR_OUTPUT.txt"
STRATEGY_GENERATION = "functional-acceptance-v8-regression-safe-component-proof"

_V4241_RUST_CANDIDATE = v4241.rust_compiler_candidate


class AutomaticRepairExhausted(v4240.ProjectStopRequested):
    """Raised only at a safe boundary after every bounded strategy is spent."""


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {} if default is None else default


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _append_jsonl(path: Path, value: dict) -> None:
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        pass


def _strip_ansi(value: object) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", str(value or ""))


def normalized_diagnostics(failure: object) -> dict:
    """Normalize compiler evidence without using timestamps or full output order."""
    raw = _strip_ansi(failure).replace("\\", "/")
    raw = re.sub(r"(?i)[A-Z]:/(?:[^\s:]+/)+(?:trial|working|candidate|generated_projects)[^\s:]*", "<workspace>", raw)
    files = sorted(set(
        item.lstrip("./") for item in re.findall(
            r"(?im)(?:-->|\bat\s+)(?:\s*)([^\s:]+\.(?:rs|tsx?|jsx?|py|go|java|kt|kts|cs|fs|cpp|cc|cxx|c|h|hpp|swift|dart))(?::\d+){0,2}",
            raw,
        )
    ))
    codes = sorted(set(x.upper() for x in re.findall(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", raw, re.I)))
    messages = []
    patterns = (
        r"(?im)^\s*error(?:\[[A-Z]+\d+\])?\s*:\s*(.+)$",
        r"(?im)^\s*[^\r\n:]+\(\d+,\d+\)\s*:\s*error\s+[A-Z]+\d+\s*:\s*(.+)$",
        r"(?im)^\s*[^\r\n:]+:\d+(?::\d+)?\s*:\s*(?:fatal\s+)?error\s*:\s*(.+)$",
    )
    for pattern in patterns:
        for message in re.findall(pattern, raw):
            stable = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s|sec|seconds?)\b", "#", message, flags=re.I)
            stable = re.sub(r"\s+", " ", stable).strip()
            if stable and stable not in messages:
                messages.append(stable[:500])
    material = {"codes": codes, "files": files, "messages": sorted(messages)[:80]}
    material["signature"] = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8", errors="replace")
    ).hexdigest()[:24]
    material["diagnostic_count"] = v4237.diagnostic_count(raw)
    return material


def compact_component_failure(failure: object, limit: int = 11200) -> str:
    """Keep representative diagnostics from the whole compiler stream.

    The legacy audit kept only the last 12,000 characters. Large compilers put
    distinct root causes first and repeat downstream type errors last, so that
    policy could erase exactly the imports/definitions needed for repair. This
    compactor retains diverse codes and files, plus the command header and
    compiler summary, while staying below the legacy transport boundary.
    """
    text = _strip_ansi(failure).replace("\r\n", "\n")
    limit = max(2400, min(int(limit or 11200), 11800))
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    start_re = re.compile(
        r"^\s*(?:error(?:\[[A-Z]+\d+\])?\s*:|"
        r"[^\n]+\(\d+,\d+\)\s*:\s*error\s+[A-Z]+\d+\s*:|"
        r"[^\n]+:\d+(?::\d+)?\s*:\s*(?:fatal\s+)?error\s*:|FAIL\s+\S+)",
        re.I,
    )
    starts = [index for index, line in enumerate(lines) if start_re.search(line)]
    if not starts:
        head = text[: limit // 2]
        tail = text[-(limit - len(head) - 80):]
        return head.rstrip() + "\n... compiler output compacted from the middle ...\n" + tail.lstrip()

    blocks = []
    for position, start in enumerate(starts):
        stop = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "\n".join(lines[start:stop]).strip()
        if not block:
            continue
        code_match = re.search(r"\b(?:E|TS|CS|FS|BC|KT)\d{3,5}\b", block, re.I)
        file_match = re.search(
            r"(?im)(?:-->|\bat\s+)\s*([^\s:]+\.(?:rs|tsx?|jsx?|py|go|java|kt|kts|cs|fs|cpp|cc|cxx|c|h|hpp|swift|dart))",
            block.replace("\\", "/"),
        )
        message = re.sub(r"\s+", " ", block.splitlines()[0]).strip()[:240]
        blocks.append({
            "text": block[:1500],
            "code": (code_match.group(0).upper() if code_match else ""),
            "file": (file_match.group(1) if file_match else ""),
            "message": message,
        })

    order = []
    seen_codes, seen_files = set(), set()
    for row in blocks:
        if row["code"] and row["code"] not in seen_codes:
            order.append(row); seen_codes.add(row["code"])
    for row in blocks:
        if row["file"] and row["file"] not in seen_files and row not in order:
            order.append(row); seen_files.add(row["file"])
    for row in blocks[:4] + blocks[-4:] + blocks:
        if row not in order:
            order.append(row)

    header = "\n".join(lines[:starts[0]]).strip()[:800]
    trailer_lines = [line for line in lines[-16:] if line.strip()]
    trailer = "\n".join(trailer_lines)[-1200:]
    selected = []
    used = len(header) + len(trailer) + 220
    for row in order:
        block = row["text"]
        if used + len(block) + 2 > limit:
            continue
        selected.append(block)
        used += len(block) + 2
    omitted = max(0, len(blocks) - len(selected))
    parts = [header] if header else []
    parts.extend(selected)
    if omitted:
        parts.append(f"... {omitted} duplicate or lower-priority diagnostic block(s) compacted ...")
    if trailer and trailer not in selected:
        parts.append(trailer)
    return "\n".join(part for part in parts if part).strip()[-limit:]


def _model_cycle_limit() -> int:
    try:
        return max(1, min(3, int(os.getenv("JARVIS_V4241_MODEL_CYCLES_PER_REVISION", "2"))))
    except Exception:
        return 2


def revision_key(component: dict | None, repository_token: object) -> str:
    cid, root, adapter = v4237._component_identity(component or {})
    material = {"component": cid, "root": root, "adapter": adapter, "repository_token": str(repository_token or "")}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _remove_use_symbol(source: str, symbol: str) -> tuple[str, bool]:
    changed = False
    direct = re.compile(rf"(?m)^\s*use\s+[^;\n]*::{re.escape(symbol)}\s*;\s*\r?\n")
    source, count = direct.subn("", source)
    changed = changed or bool(count)

    grouped = re.compile(r"(?m)^(?P<indent>\s*)use\s+(?P<prefix>[^;\n]*?)::\{(?P<body>[^}\n]+)\}\s*;\s*$")

    def rewrite(match):
        nonlocal changed
        names = [item.strip() for item in match.group("body").split(",") if item.strip()]
        kept = [item for item in names if item.split(" as ", 1)[0].strip() != symbol]
        if len(kept) == len(names):
            return match.group(0)
        changed = True
        if not kept:
            return ""
        if len(kept) == 1:
            return f"{match.group('indent')}use {match.group('prefix')}::{kept[0]};"
        return f"{match.group('indent')}use {match.group('prefix')}::{{{', '.join(kept)}}};"

    source = grouped.sub(rewrite, source)
    source = re.sub(r"(?m)^\s*\r?\n(?=\s*use\s+)", "", source)
    return source, changed


def _remove_use_from_prefix(source: str, prefix: str, symbol: str) -> tuple[str, bool]:
    changed = False
    direct = re.compile(
        rf"(?m)^\s*use\s+{re.escape(prefix)}::{re.escape(symbol)}\s*;\s*\r?\n"
    )
    source, count = direct.subn("", source)
    changed = bool(count)
    grouped = re.compile(
        rf"(?m)^(?P<indent>\s*)use\s+{re.escape(prefix)}::\{{(?P<body>[^}}\n]+)\}}\s*;\s*$"
    )

    def rewrite(match):
        nonlocal changed
        names = [item.strip() for item in match.group("body").split(",") if item.strip()]
        kept = [item for item in names if item.split(" as ", 1)[0].strip() != symbol]
        if len(kept) == len(names):
            return match.group(0)
        changed = True
        if not kept:
            return ""
        if len(kept) == 1:
            return f"{match.group('indent')}use {prefix}::{kept[0]};"
        return f"{match.group('indent')}use {prefix}::{{{', '.join(kept)}}};"

    return grouped.sub(rewrite, source), changed


def _rust_common_candidate(source: str, failure: str, rel: object) -> tuple[str, list[str]]:
    if not str(rel or "").lower().endswith(".rs"):
        return source, []
    updated = source
    reasons = []

    for symbol in sorted(set(re.findall(r"error\[E0255\]:\s+the name `([^`]+)` is defined multiple times", failure))):
        if re.search(rf"(?m)^\s*(?:pub\s+)?(?:async\s+)?fn\s+{re.escape(symbol)}\b", updated):
            updated, changed = _remove_use_symbol(updated, symbol)
            if changed:
                reasons.append(f"remove duplicate imported definition {symbol}")

    unresolved = sorted(set(re.findall(r"error\[E0432\]:\s+unresolved import `([^`]+)`", failure)))
    for import_path in unresolved:
        if "::" not in import_path:
            continue
        prefix, symbol = import_path.rsplit("::", 1)
        if symbol == "Pool" and re.search(r"\bPool\b", updated):
            updated, changed = _remove_use_from_prefix(updated, prefix, symbol)
            if changed and "use sqlx::SqlitePool as Pool;" not in updated:
                updated = "use sqlx::SqlitePool as Pool;\n" + updated
                reasons.append("import SQLx SqlitePool directly instead of a nonexistent private project alias")
        elif re.search(rf"error\[E0733\]:\s+recursion in an async fn", failure) and re.search(
            rf"(?m)^\s*pub\s+async\s+fn\s+{re.escape(symbol)}\b", updated
        ):
            updated, changed = _remove_use_from_prefix(updated, prefix, symbol)
            call = re.compile(rf"(?m)^(?P<indent>\s*){re.escape(symbol)}\([^\n]*\)\.await\??\s*;?\s*$")
            updated, count = call.subn(lambda m: f"{m.group('indent')}Ok(())", updated, count=1)
            if changed or count:
                reasons.append(f"remove unresolved self-import and direct async recursion for {symbol}")

    if "cannot find `Error` in `thiserror`" in failure and "-> Result<" in updated:
        updated, count = re.subn(r"\b(?:thiserror::)?Error::Msg\s*\(", "sqlx::Error::Protocol(", updated)
        if count:
            reasons.append("use the declared SQLx error type instead of the thiserror derive macro")

    if "no method named `join` found for reference `&PathResolver" in failure:
        updated, count = re.subn(
            r"\.path\(\)\.join\((?P<arg>[^\n]+?)\)\.unwrap\(\)",
            r".path().app_data_dir()?.join(\g<arg>)",
            updated,
        )
        if count:
            reasons.append("use the Tauri 2 PathResolver app_data_dir API before joining a filename")

    if (
        "expected reference `&Pool<_>`" in failure
        and "found struct `Pool<_>`" in failure
        and re.search(r"(?m)^\s*let\s+pool\s*=", updated)
    ):
        updated, count = re.subn(
            r"(?m)^(?P<indent>\s*)(?P<callee>[A-Za-z_]\w*)\(pool\)\.await\?;\s*$",
            r"\g<indent>\g<callee>(&pool).await?;",
            updated,
            count=1,
        )
        if count:
            reasons.append("borrow the SQLx pool required by the called function signature")

    return updated, reasons


def _rust_path_display_candidate(source: str, failure: object, rel: object) -> tuple[str, list[str]]:
    """Apply rustc's explicit `.display()` fix for Path/PathBuf in `format!`.

    This is intentionally compiler-directed rather than project-specific.  We act
    only when rustc proves the Display trait failure, explicitly recommends
    `.display()`, and the exact current source line containing the named format
    capture is present in the compiler evidence.  This prevents broad textual
    rewrites and keeps the real Cargo build as final authority.
    """
    if not str(rel or "").lower().endswith(".rs"):
        return source, []
    text = _strip_ansi(failure).replace("\\", "/")
    if "E0277" not in text or ".display()" not in text:
        return source, []
    if not re.search(r"`(?:PathBuf|Path)`[^\n]*doesn(?:'|’)t implement `std::fmt::Display`", text):
        return source, []

    updated = source
    reasons = []
    # `format!("...{name}...")` is valid named-capture syntax, but Path/PathBuf
    # has no Display impl.  Convert only a compiler-evidenced single-argument
    # format invocation to ordinary positional formatting with `name.display()`.
    pattern = re.compile(
        r'format!\(\s*"(?P<body>(?:[^"\\]|\\.)*\{(?P<var>[A-Za-z_]\w*)\}(?:[^"\\]|\\.)*)"\s*\)'
    )
    matches = list(pattern.finditer(source))
    for match in reversed(matches):
        var = match.group("var")
        body = match.group("body")
        # Require the exact source line to be echoed in the compiler output. Rustc
        # does this for primary-site diagnostics and it is the strongest ownership
        # signal available without guessing from variable names.
        line_start = source.rfind("\n", 0, match.start()) + 1
        line_end = source.find("\n", match.end())
        if line_end < 0:
            line_end = len(source)
        source_line = source[line_start:line_end].strip().replace("\\", "/")
        if source_line and source_line not in text:
            continue
        # Avoid changing an identically named non-path capture unless the local
        # source also has path-shaped evidence.  An explicit type annotation is
        # strongest; common path-producing APIs are accepted because rustc has
        # already proved that the value at this exact use site is Path/PathBuf.
        local_prefix = source[max(0, line_start - 1800):line_start]
        path_evidence = bool(
            re.search(rf"\blet\s+(?:mut\s+)?{re.escape(var)}\s*:\s*(?:std::path::)?PathBuf\b", local_prefix)
            or re.search(rf"\blet\s+(?:mut\s+)?{re.escape(var)}\b[^;\n]*\.(?:join|to_path_buf)\s*\(", local_prefix)
            or re.search(rf"\blet\s+(?:mut\s+)?{re.escape(var)}\b[^;\n]*(?:_dir|path)\s*\(\)", local_prefix)
        )
        if not path_evidence:
            continue
        new_body = body.replace("{" + var + "}", "{}", 1)
        replacement = f'format!("{new_body}", {var}.display())'
        updated = updated[:match.start()] + replacement + updated[match.end():]
        reasons.append(
            f"apply rustc-recommended Path/PathBuf Display adapter for {var} at the failing format site"
        )
        break
    return updated, reasons


def rust_compiler_candidate(source: str, failure: object, rel: object) -> tuple[str, list[str]]:
    text = _strip_ansi(failure)
    updated, reasons = _V4241_RUST_CANDIDATE(source, text, rel)
    updated, extra = _rust_common_candidate(updated, text, rel)
    reasons.extend(extra)
    updated, extra = _rust_path_display_candidate(updated, text, rel)
    reasons.extend(extra)
    return updated, list(dict.fromkeys(reasons))



def _rust_function_ranges(source: str):
    """Yield (start, open_brace, end) for Rust functions using brace balancing."""
    pattern = re.compile(r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+[A-Za-z_]\w*[^\n{]*\{")
    for match in pattern.finditer(source):
        open_brace = source.find("{", match.start(), match.end())
        if open_brace < 0:
            continue
        depth = 0
        index = open_brace
        while index < len(source):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    yield match.start(), open_brace, index + 1
                    break
            index += 1


def _find_rust_struct_fields(root: Path, struct_name: str) -> list[tuple[str, str]]:
    """Find a named struct and return its named fields without assuming a project layout."""
    pattern = re.compile(
        rf"(?ms)(?:^|\n)\s*(?:pub(?:\([^)]*\))?\s+)?struct\s+{re.escape(struct_name)}\s*\{{(?P<body>.*?)\n\s*\}}"
    )
    field_pattern = re.compile(
        r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^,\n]+)\s*,?\s*$"
    )
    for path in root.rglob("*.rs"):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        match = pattern.search(source)
        if not match:
            continue
        fields = []
        for field in field_pattern.finditer(match.group("body")):
            name = field.group("name")
            if name.startswith("_"):
                continue
            fields.append((name, field.group("type").strip()))
        if fields:
            return fields
    return []



def _query_as_to_query(expr: str) -> tuple[str, bool]:
    """Convert one sqlx::query_as[::<...>](...) head to sqlx::query(...)."""
    marker = "sqlx::query_as"
    start = expr.find(marker)
    if start < 0:
        return expr, False
    pos = start + len(marker)
    while pos < len(expr) and expr[pos].isspace():
        pos += 1
    if expr.startswith("::<", pos):
        angle = pos + 2
        depth = 0
        index = angle
        while index < len(expr):
            char = expr[index]
            if char == "<":
                depth += 1
            elif char == ">":
                depth -= 1
                if depth == 0:
                    pos = index + 1
                    break
            index += 1
        else:
            return expr, False
        while pos < len(expr) and expr[pos].isspace():
            pos += 1
    if pos >= len(expr) or expr[pos] != "(":
        return expr, False
    return expr[:start] + "sqlx::query" + expr[pos:], True

def _sqlx_joined_struct_candidate(root: Path, source: str, failure: object, rel: object) -> tuple[str, list[str]]:
    """Repair SQLx `(Struct, Extra)` joined-row decoding at the query site.

    SQLx tuple FromRow treats every tuple member as one database column. A normal
    `#[derive(FromRow)] struct` therefore cannot be used as the first scalar tuple
    member of `(Struct, Option<T>)`. When rustc proves this exact shape, convert
    only the offending `query_as(...).fetch_optional(...)` to a raw row query and
    explicitly reconstruct the struct from named columns. The real component
    validator remains the acceptance authority.
    """
    if not str(rel or "").lower().endswith(".rs"):
        return source, []
    text = _strip_ansi(failure)
    if "E0277" not in text or "sqlx::" not in text or "FromRow" not in text:
        return source, []
    names = list(dict.fromkeys(re.findall(
        r"trait bound `([A-Z][A-Za-z0-9_]*):\s*sqlx::(?:Decode|Type)[^`]*` is not satisfied", text
    )))
    if not names:
        return source, []

    updated = source
    reasons = []
    # Work from the end so replacements cannot invalidate earlier source offsets.
    ranges = list(_rust_function_ranges(updated))
    for fn_start, _brace, fn_end in reversed(ranges):
        function = updated[fn_start:fn_end]
        for struct_name in names:
            tuple_match = re.search(
                rf"Option\s*<\s*\(\s*{re.escape(struct_name)}\s*,\s*(?P<extra>Option\s*<[^>]+>|[A-Za-z_:][A-Za-z0-9_:<> ,]*)\s*\)\s*>",
                function,
            )
            if not tuple_match:
                continue
            if not re.search(r"(?is)SELECT\s+[A-Za-z_]\w*\.\*", function):
                continue
            aliases = re.findall(r"(?i)\bas\s+([A-Za-z_]\w*)", function)
            if not aliases:
                continue
            extra_column = aliases[-1]
            fields = _find_rust_struct_fields(root, struct_name)
            if not fields:
                continue

            stmt = re.search(
                r"(?ms)(?P<indent>^[ \t]*)let\s+(?P<var>[A-Za-z_]\w*)\s*=\s*"
                r"(?P<expr>sqlx::query_as.*?\.fetch_optional\s*\(.*?\)\s*\.await\?)\s*;",
                function,
            )
            if not stmt:
                continue
            expr = stmt.group("expr")
            raw_expr, converted = _query_as_to_query(expr)
            if not converted:
                continue
            indent = stmt.group("indent")
            var = stmt.group("var")
            extra_type = re.sub(r"\s+", " ", tuple_match.group("extra").strip())
            field_lines = "\n".join(
                f'{indent}                {name}: row.try_get("{name}")?,' for name, _type in fields
            )
            replacement = (
                f"{indent}let {var} = {raw_expr}\n"
                f"{indent}    .map(|row| -> Result<({struct_name}, {extra_type}), sqlx::Error> {{\n"
                f"{indent}        use sqlx::Row as _;\n"
                f"{indent}        Ok((\n"
                f"{indent}            {struct_name} {{\n{field_lines}\n{indent}            }},\n"
                f'{indent}            row.try_get("{extra_column}")?,\n'
                f"{indent}        ))\n"
                f"{indent}    }})\n"
                f"{indent}    .transpose()?;"
            )
            local_start, local_end = stmt.span()
            function = function[:local_start] + replacement + function[local_end:]
            updated = updated[:fn_start] + function + updated[fn_end:]
            reasons.append(
                f"decode SQLx joined row into {struct_name} fields plus {extra_column} instead of treating {struct_name} as a scalar tuple column"
            )
            break
        if reasons:
            break
    return updated, reasons

def _cargo_candidate(source: str, failure: object) -> tuple[str, list[str]]:
    text = _strip_ansi(failure)
    updated = source
    reasons = []
    missing = sorted(set(re.findall(r"cannot find module or crate `([A-Za-z_][A-Za-z0-9_-]*)` in this scope", text)))
    versions = {"chrono": '{ version = "0.4", features = ["clock"] }'}
    for crate in missing:
        if crate not in versions:
            continue
        if re.search(rf"(?m)^\s*{re.escape(crate)}\s*=", updated):
            continue
        marker = re.search(r"(?m)^\[dependencies\]\s*$", updated)
        if marker:
            pos = marker.end()
            updated = updated[:pos] + f"\n{crate} = {versions[crate]}" + updated[pos:]
            reasons.append(f"add compiler-required direct dependency {crate}")
    return updated, reasons


def _diagnostic_targets(failure: object) -> list[str]:
    raw = _strip_ansi(failure).replace("\\", "/")
    values = re.findall(
        r"(?im)-->(?:\s*)([^\r\n:]+\.(?:rs|toml))(?::\d+){0,2}", raw
    )
    return list(dict.fromkeys(item.lstrip("./") for item in values))


def _warm_rust_compile_gate(g: dict, accepted_root: Path, clone_root: Path, component: dict,
                            changed: list[str], progress_callback=None) -> dict:
    """Compile a Rust candidate against the accepted workspace's warm Cargo target cache.

    Candidate clones deliberately exclude bulky build artifacts. Running a full Rust
    validator in such a clone can spend the entire bounded repair window rebuilding
    third-party dependencies before rustc reaches the edited crate. For compiler-
    directed source repairs, the safe intermediate authority is a real `cargo build`
    of the disposable candidate while reusing only the accepted workspace's Cargo
    *artifact cache*. Source still comes from the clone; only target artifacts are
    shared. Final acceptance still reruns the normal full component validator from
    the accepted workspace after promotion.
    """
    override = g.get("_v4245_compile_gate_override") or g.get("_v4244_compile_phase_probe_override")
    if callable(override):
        try:
            result = override(clone_root, {}, component, list(changed))
            if isinstance(result, dict):
                return result
            if isinstance(result, (tuple, list)) and len(result) >= 2:
                return {
                    "available": True, "ok": bool(result[0]), "output": str(result[1] or ""),
                    "kind": "override", "attempts": 1,
                }
        except Exception as exc:
            return {
                "available": True, "ok": False, "output": str(exc),
                "kind": "override_exception", "attempts": 1,
            }

    cid, component_root, adapter = v4237._component_identity(component)
    candidate_cwd = clone_root if component_root in {"", "."} else clone_root / component_root
    accepted_cwd = accepted_root if component_root in {"", "."} else accepted_root / component_root
    if adapter != "rust" or not (candidate_cwd / "Cargo.toml").is_file():
        return {
            "available": False, "ok": False, "output": "", "kind": "not_applicable",
            "attempts": 0,
        }

    cargo = shutil.which("cargo")
    runner = g.get("_run_command")
    if not cargo or not callable(runner):
        return {
            "available": False, "ok": False, "output": "cargo/build runner unavailable",
            "kind": "unavailable", "attempts": 0,
        }

    # The accepted workspace has already produced the compiler evidence we are
    # repairing, so its target directory is normally warm. Cargo fingerprints keep
    # source identity separate; sharing this directory reuses dependencies without
    # copying candidate source or accepting unvalidated files.
    shared_target = accepted_cwd / "target"
    try:
        shared_target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        timeout = max(60, min(900, int(os.getenv("JARVIS_V4246_COMPILE_GATE_TIMEOUT", os.getenv("JARVIS_V4246_COMPILE_GATE_TIMEOUT", "300")))))
    except Exception:
        timeout = 300
    try:
        max_attempts = max(1, min(2, int(os.getenv("JARVIS_V4246_COMPILE_GATE_ATTEMPTS", os.getenv("JARVIS_V4246_COMPILE_GATE_ATTEMPTS", "2")))))
    except Exception:
        max_attempts = 2

    command = [cargo, "build", "--target-dir", str(shared_target)]
    outputs = []
    timed_out = False
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            try:
                g["_progress"](
                    progress_callback,
                    f"V42.46 continuing warmed {cid} compiler proof {attempt}/{max_attempts}",
                    stage="V42.46 warm compiler proof", percent=85, component=cid,
                    files=list(changed),
                )
            except Exception:
                pass
        try:
            ok, output = runner(command, candidate_cwd, timeout)
            text = str(output or "")
            outputs.append(text)
            timeout_hit = "timed out" in text.lower() or "timeout" in text.lower()
            if bool(ok):
                return {
                    "available": True, "ok": True, "output": "\n".join(outputs),
                    "kind": "cargo_build_shared_target", "component": cid,
                    "cwd": str(candidate_cwd), "target_dir": str(shared_target),
                    "attempts": attempt, "timed_out": False,
                }
            if timeout_hit and attempt < max_attempts:
                timed_out = True
                continue
            return {
                "available": True, "ok": False, "output": "\n".join(outputs),
                "kind": "cargo_build_shared_target", "component": cid,
                "cwd": str(candidate_cwd), "target_dir": str(shared_target),
                "attempts": attempt, "timed_out": bool(timeout_hit or timed_out),
            }
        except v4240.ProjectStopRequested:
            raise
        except Exception as exc:
            text = str(exc)
            outputs.append(text)
            timeout_hit = "timed out" in text.lower() or "timeout" in text.lower()
            if timeout_hit and attempt < max_attempts:
                timed_out = True
                continue
            return {
                "available": True, "ok": False, "output": "\n".join(outputs),
                "kind": "cargo_build_shared_target", "component": cid,
                "cwd": str(candidate_cwd), "target_dir": str(shared_target),
                "attempts": attempt, "timed_out": bool(timeout_hit or timed_out),
            }

    return {
        "available": True, "ok": False, "output": "\n".join(outputs),
        "kind": "cargo_build_shared_target", "component": cid,
        "cwd": str(candidate_cwd), "target_dir": str(shared_target),
        "attempts": max_attempts, "timed_out": timed_out,
    }


def _actual_transaction_delta(root: Path, clone: Path, files: list[str]) -> list[str]:
    """Return only transaction files whose bytes actually differ."""
    output = []
    for rel in files:
        try:
            if (root / rel).read_bytes() != (clone / rel).read_bytes():
                output.append(rel)
        except Exception:
            continue
    return list(dict.fromkeys(output))


def deterministic_component_transaction(g: dict, request: object, manifest: dict,
                                        root: Path, failure: object, component: dict,
                                        progress_callback=None) -> tuple[bool, dict]:
    """Run a compiler-directed multi-file Rust cluster in a disposable clone."""
    cid, component_root, adapter = v4237._component_identity(component)
    before = v4237.diagnostic_count(failure)
    if adapter != "rust" or before <= 0:
        return False, {"result": "not_applicable", "before": before, "after": before, "files": []}
    try:
        rows = list(g["_v4236_native_diagnostics"](root, manifest, failure) or [])
        targets = list(g["_v4236_rank_native_targets"](rows, failure) or [])
    except Exception:
        targets = []
    raw_targets = list(dict.fromkeys(_diagnostic_targets(failure) + targets))
    targets = []
    for rel in raw_targets:
        if not str(rel).lower().endswith(".rs"):
            continue
        candidates = [str(rel).replace("\\", "/")]
        if component_root not in {"", "."}:
            candidates.append(str(Path(component_root) / str(rel)).replace("\\", "/"))
        resolved = next((candidate for candidate in candidates if (root / candidate).is_file()), None)
        if resolved and resolved not in targets:
            targets.append(resolved)
    handle = None
    try:
        handle, clone = g["_copy_project_for_candidate_validation"](root)
        clone = Path(clone).resolve()
        changed = []
        reasons = []
        for rel in targets[:12]:
            path = clone / rel
            if not path.is_file():
                continue
            original = path.read_text(encoding="utf-8", errors="replace")
            candidate, found = _sqlx_joined_struct_candidate(clone, original, failure, rel)
            if candidate == original:
                candidate, found = rust_compiler_candidate(original, failure, rel)
            if candidate != original:
                path.write_text(candidate, encoding="utf-8")
                changed.append(rel)
                reasons.extend(found)

        cargo_rel = str(Path(component_root) / "Cargo.toml").replace("\\", "/")
        cargo = clone / cargo_rel
        if cargo.is_file():
            original = cargo.read_text(encoding="utf-8", errors="replace")
            candidate, found = v4241._ensure_sqlx_derive_feature(original)
            candidate, more = _cargo_candidate(candidate, failure)
            found.extend(more)
            if candidate != original:
                cargo.write_text(candidate, encoding="utf-8")
                changed.append(cargo_rel)
                reasons.extend(found)

        changed = list(dict.fromkeys(changed))
        if not changed:
            return False, {"result": "no_candidate", "before": before, "after": before, "files": []}
        g["_progress"](
            progress_callback,
            f"V42.46 validating one {cid} multi-file compiler transaction",
            stage="V42.46 compiler cluster repair", percent=84, component=cid,
            files=changed, diagnostic_count=before,
        )
        actual_changed = _actual_transaction_delta(root, clone, changed)
        if not actual_changed:
            return False, {
                "result": "candidate_lost_delta", "before": before, "after": before,
                "files": [], "reasons": reasons, "validator_ok": False,
            }

        # V42.46 does not cold-run the entire Rust fetch/build/test validator inside
        # a source-only clone. It first requires real compiler proof using the warm
        # Cargo artifact cache from the accepted workspace. A successful build is
        # sufficient to promote *intermediate compiler progress*; it is never final
        # acceptance. The normal full validator reruns immediately from the accepted
        # revision after commit and exposes tests/runtime failures as the next blocker.
        proof = _warm_rust_compile_gate(
            g, root, clone, component, actual_changed, progress_callback=progress_callback
        )
        full_validator_ok = False
        if not proof.get("available") and callable(g.get("_v35_validate_component")):
            # Compatibility/fail-safe path: environments that intentionally inject a
            # component validator (or hosts without a directly invokable cargo runner)
            # retain the mature validator authority. This is not the normal V42.46
            # Windows path; when Cargo is available the warm-cache gate above wins.
            full_validator_ok, fallback_output = g["_v35_validate_component"](
                clone, manifest, component, str(request or "")
            )
            proof = {
                "available": True,
                "ok": bool(full_validator_ok),
                "output": str(fallback_output or ""),
                "kind": "full_component_validator_fallback",
                "attempts": 1,
                "timed_out": False,
            }

        proof_output = str(proof.get("output") or "")
        phase_progress = bool(proof.get("available") and proof.get("ok"))
        after = 0 if phase_progress else v4237.diagnostic_count(proof_output)
        improved = bool(phase_progress or (before > 0 and 0 < after < before))

        if not improved:
            if proof.get("timed_out") and after == 0:
                result_name = "compile_gate_inconclusive_timeout"
            elif not proof.get("available"):
                result_name = "compile_gate_unavailable"
            elif after == 0:
                result_name = "compile_gate_failed_unclassified"
            else:
                result_name = "no_delta"
            return False, {
                "result": result_name, "before": before, "after": after,
                "files": actual_changed, "reasons": reasons, "validator_ok": False,
                "phase_progress": False, "proof_kind": proof.get("kind"),
                "proof_attempts": proof.get("attempts"), "proof_timed_out": proof.get("timed_out"),
                "proof_target_dir": proof.get("target_dir"),
                "proof_tail": proof_output[-8000:],
            }

        committed, detail = v4237._commit_component_transaction(
            g, root, clone, actual_changed, before, after, component
        )
        result_name = (
            "committed_full_green" if committed and full_validator_ok else
            "committed_compile_phase" if committed and phase_progress else
            "committed_diagnostic_delta" if committed else
            "commit_failed"
        )
        if committed:
            try:
                g["_append_project_event"](
                    root, "v4245_warm_compile_progress_committed",
                    (
                        f"V42.46 promoted a compiler-proven {cid} repair "
                        f"({before} -> {after} compiler diagnostics) using the accepted workspace's warm Cargo cache; "
                        "Jarvis will now rerun the full component/test/runtime validator from the improved accepted revision."
                    ),
                    component=cid, files=actual_changed, before=before, after=after,
                    final_acceptance=False, proof_kind=proof.get("kind"),
                    proof_attempts=proof.get("attempts"), proof_target_dir=proof.get("target_dir"),
                )
            except Exception:
                pass
        return bool(committed), {
            "result": result_name, "before": before, "after": after, "files": actual_changed,
            "reasons": list(dict.fromkeys(reasons)), "validator_ok": bool(full_validator_ok),
            "phase_progress": bool(phase_progress), "proof_kind": proof.get("kind"),
            "proof_attempts": proof.get("attempts"), "proof_timed_out": proof.get("timed_out"),
            "proof_target_dir": proof.get("target_dir"), "proof_tail": proof_output[-8000:],
            "commit_detail": str(detail or "")[-1600:],
        }
    except v4240.ProjectStopRequested:
        raise
    except Exception as exc:
        return False, {"result": "sandbox_failure", "before": before, "after": before, "files": [], "error": str(exc)[-2000:]}
    finally:
        v4237._cleanup_temp(handle)


def _new_ledger(g: dict) -> dict:
    return {"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"](), "revisions": {}}


def _revision_record(g: dict, root: Path, component: dict, failure: object) -> tuple[dict, dict, Path]:
    token = str(v4237._repo_token(g, root))
    cid, component_root, adapter = v4237._component_identity(component)
    key = revision_key(component, token)
    path = root / LEDGER_FILE
    ledger = _load(path, _new_ledger(g))
    prior_ledger_version = str(ledger.get("version") or "")
    prior_generation = str(ledger.get("strategy_generation") or "legacy")
    ledger.update({
        "version": "V" + VERSION, "engine": ENGINE,
        "strategy_generation": STRATEGY_GENERATION, "updated_at": g["_utc_stamp"](),
    })
    evidence = normalized_diagnostics(failure)
    record = ledger.setdefault("revisions", {}).setdefault(key, {
        "id": key, "repository_token": token, "component": cid,
        "component_root": component_root, "adapter": adapter,
        "first_seen": g["_utc_stamp"](), "last_seen": g["_utc_stamp"](),
        "seen_count": 0, "diagnostic_signatures": [], "attempts": [],
        "model_cycles": 0, "exhausted": False, "terminal": False,
        "strategy_generation": STRATEGY_GENERATION,
    })
    record["last_seen"] = g["_utc_stamp"]()
    record["seen_count"] = int(record.get("seen_count") or 0) + 1
    record["diagnostic_count"] = evidence["diagnostic_count"]
    if evidence["signature"] not in record.setdefault("diagnostic_signatures", []):
        record["diagnostic_signatures"].append(evidence["signature"])
    record["codes"] = evidence["codes"]
    record["files"] = evidence["files"]

    record_generation = str(record.get("strategy_generation") or prior_generation or "legacy")
    strategy_reopened = record_generation != STRATEGY_GENERATION
    if strategy_reopened:
        history = list(record.get("prior_strategy_generations") or [])
        history.append({
            "strategy_generation": record_generation,
            "model_cycles": int(record.get("model_cycles") or 0),
            "exhausted": bool(record.get("exhausted")),
            "terminal": bool(record.get("terminal")),
        })
        record["prior_strategy_generations"] = history[-8:]
        record["strategy_generation"] = STRATEGY_GENERATION
        record["model_cycles"] = 0
        record["exhausted"] = False
        record["terminal"] = False
        record["reopened_for_new_strategy_at"] = g["_utc_stamp"]()
    if prior_ledger_version and prior_ledger_version != "V" + VERSION:
        record["reopened_from_version"] = prior_ledger_version
        record["reopened_at"] = g["_utc_stamp"]()

    # Migrate/summarize every V42.41 issue for this exact accepted revision.
    legacy = _load(root / v4241.LEDGER_FILE, {})
    matching = [
        item for item in (legacy.get("issues") or {}).values()
        if str(item.get("repository_token") or "") == token
        and str(item.get("component") or "") == cid
    ]
    if matching:
        record["legacy_issue_ids"] = sorted(set(str(item.get("id") or "") for item in matching if item.get("id")))
        # Old strategy exhaustion is evidence, not authority after a new repair
        # strategy generation is installed. Import only legacy-controller issues
        # that explicitly belong to the *current* strategy generation.
        matching_current = [
            item for item in matching
            if str(item.get("strategy_generation") or "legacy") == STRATEGY_GENERATION
        ]
        if not strategy_reopened and matching_current:
            record["model_cycles"] = max(
                int(record.get("model_cycles") or 0),
                sum(1 for item in matching_current for attempt in item.get("attempts") or []
                    if attempt.get("strategy") == "bounded_model_component_transaction"),
            )
            if (
                any(bool(item.get("exhausted")) for item in matching_current)
                and int(record.get("model_cycles") or 0) >= _model_cycle_limit()
            ):
                record["exhausted"] = True
    _save(path, ledger)
    return ledger, record, path


def _record(g: dict, root: Path, ledger: dict, record: dict, path: Path,
            strategy: str, result: str, **fields) -> None:
    row = {"at": g["_utc_stamp"](), "strategy": strategy, "result": result}
    row.update(fields)
    record.setdefault("attempts", []).append(row)
    record["last_strategy"] = strategy
    record["last_result"] = result
    ledger["updated_at"] = g["_utc_stamp"]()
    _save(path, ledger)
    _append_jsonl(root / TRACE_FILE, {
        "at": g["_utc_stamp"](), "version": "V" + VERSION, "engine": ENGINE,
        "revision": record.get("id"), "repository_token": record.get("repository_token"),
        "component": record.get("component"), **row,
    })


def _write_run_state(g: dict, root: Path, **fields) -> dict:
    path = root / RUN_STATE_FILE
    state = _load(path, {})
    state.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"](), **fields})
    _save(path, state)
    return state


def _write_status(g: dict, root: Path, record: dict) -> None:
    attempts = list(record.get("attempts") or [])
    last = attempts[-1] if attempts else {}
    lines = [
        "# Jarvis V42.46 repair status", "",
        f"Updated: {g['_utc_stamp']()}",
        f"Component: {record.get('component') or 'unknown'} ({record.get('adapter') or 'unknown'})",
        f"Compiler diagnostics: {record.get('diagnostic_count') or 0}",
        f"Repository revision token: {record.get('repository_token') or 'unknown'}",
        f"Normalized evidence signatures seen: {len(record.get('diagnostic_signatures') or [])}",
        f"Model cycles for this revision/component: {record.get('model_cycles') or 0}",
        f"Last strategy: {last.get('strategy') or record.get('last_strategy') or 'none'}",
        f"Last result: {last.get('result') or record.get('last_result') or 'pending'}",
        f"Exhausted: {bool(record.get('exhausted'))}",
        f"Terminal checkpoint required: {bool(record.get('terminal'))}", "",
        "The circuit breaker is scoped to the accepted repository revision and component. Diagnostic text churn cannot reopen it.",
    ]
    (root / STATUS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mark_terminal(g: dict, root: Path, record: dict, reason: str) -> None:
    payload = {
        "version": "V" + VERSION, "engine": ENGINE,
        "status": "automatic_exhausted_checkpoint_required",
        "created_at": g["_utc_stamp"](), "reason": reason,
        "repository_token": record.get("repository_token"),
        "revision_key": record.get("id"), "component": record.get("component"),
        "diagnostic_count": record.get("diagnostic_count"),
        "normalized_signatures": record.get("diagnostic_signatures") or [],
        "next_action": "Resume from the checkpoint only with fresh source or a newly implemented repair strategy.",
    }
    _save(root / TERMINAL_FILE, payload)
    run_fields = dict(payload)
    run_fields.pop("version", None)
    run_fields.pop("engine", None)
    run_fields.pop("status", None)
    _write_run_state(g, root, status="exhausted", final_action="checkpoint", **run_fields)
    try:
        store = shared_memory.default_store(Path(g["__file__"]).resolve().parent)
        store.append_event(
            "repair_exhausted", payload, scope="project", project=root,
            repository_token=record.get("repository_token"), status="blocked", confidence=1.0,
        )
        store.export_project_snapshot(root, extra=payload)
    except Exception:
        pass


def _reconcile_project_state(g: dict, root: Path, event_type: str = "") -> dict:
    """Project current truth from fresh audit/terminal evidence, never old prose."""
    state_path = root / g.get("PROJECT_STATE_FILE", "JARVIS_PROJECT_STATE.json")
    state = _load(state_path, {})
    if not isinstance(state, dict):
        state = {}
    event_key = str(event_type or "").strip().lower()
    audit = _load(root / "JARVIS_V429_WHOLE_PROJECT_AUDIT.json", {})
    terminal = _load(root / TERMINAL_FILE, {})
    changed = False

    if "audit" in event_key and isinstance(audit, dict) and audit:
        issues = [row for row in (audit.get("issues") or []) if isinstance(row, dict)]
        clean = bool(audit.get("clean")) and not issues and all(
            bool(row.get("ok")) for row in (audit.get("components") or []) if isinstance(row, dict)
        )
        summaries = []
        for row in issues[:80]:
            rel = str(row.get("file") or row.get("component") or "project")
            kind = str(row.get("kind") or "validation")
            problem = re.sub(r"\s+", " ", str(row.get("problem") or "")).strip()[:1200]
            summaries.append(f"[{kind}] {rel}: {problem}")
        state["unresolved_requirements"] = summaries
        state["current_blocker"] = issues[0] if issues else None
        state["last_audit"] = {
            "updated_at": audit.get("updated_at"),
            "accepted_token": audit.get("accepted_token"),
            "issue_count": len(issues),
            "clean": clean,
            "components": [
                {
                    "id": row.get("id"), "root": row.get("root"),
                    "adapter": row.get("adapter"), "ok": bool(row.get("ok")),
                }
                for row in (audit.get("components") or []) if isinstance(row, dict)
            ],
        }
        state["stage"] = "verified" if clean else "repairing"
        state["fresh_validation_required"] = False
        changed = True

    if any(token in event_key for token in (
        "whole_project_green", "final_acceptance_passed",
        "project_complete", "publication_accepted",
    )):
        state["unresolved_requirements"] = []
        state["current_blocker"] = None
        state["stage"] = "complete"
        state["fresh_validation_required"] = False
        changed = True

    if "exhausted" in event_key and isinstance(terminal, dict) and terminal:
        state["current_blocker"] = {
            "component": terminal.get("component"),
            "kind": "automatic_repair_exhausted",
            "problem": terminal.get("reason"),
            "diagnostic_count": terminal.get("diagnostic_count"),
            "repository_token": terminal.get("repository_token"),
        }
        state["unresolved_requirements"] = [str(terminal.get("reason") or "Automatic repair budget exhausted.")]
        state["stage"] = "automatic_checkpoint"
        state["fresh_validation_required"] = False
        changed = True

    if changed:
        state.update({"version": "V" + VERSION, "engine": ENGINE, "updated_at": g["_utc_stamp"]()})
        _save(state_path, state)
    return state


def install(g: dict) -> None:
    PathType = g["Path"]
    # All nested repair ledgers use this token. A new token intentionally grants
    # one fresh bounded attempt at the same accepted source revision; ordinary
    # restarts with the same token remain suppressed.
    g["JARVIS_REPAIR_STRATEGY_GENERATION"] = STRATEGY_GENERATION
    previous_component = g["_v4237_repair_component_failure"]
    previous_identity = g["_v36_release_identity"]
    previous_skills = g["_v36_stack_skill_names"]
    previous_generate = g["generate_project_zip"]
    previous_edit = g["analyze_and_edit_project_zip"]
    previous_checkpoint = g["checkpoint_stopped_project"]
    previous_validate_component = g["_v35_validate_component"]
    durable_append = g.get("_v4235_durable_append_project_event", g["_append_project_event"])
    base_progress = g.get("_v4235_base_progress", g["_progress"])
    base_qwen = g.get("_v4235_previous_qwen_call", g["_qwen_call"])

    # V42.41's live controller looks up these module globals at call time.
    # Replacing them upgrades its deterministic candidate without duplicating
    # the mature component transaction and exact validator authority.
    v4241.rust_compiler_candidate = rust_compiler_candidate
    v4241._deterministic_component_transaction = deterministic_component_transaction
    v4240.VERSION = VERSION
    v4240.ENGINE = ENGINE

    def append_event(work, event_type, message, **fields):
        v4240.register_project_work(g, work)
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        rendered = re.sub(r"\bV(?:3[5-9]|4[0-3])(?:\.\d+){0,2}\b(?!\.\d)", "V42.46", str(message or ""))
        event = durable_append(work, event_type, rendered, **values)
        root = Path(work).resolve()
        try:
            # Preserve the mature V42.36 component-aware projection reducer.
            # V42.46 owns release stamping and shared memory, but accepted edits
            # must still invalidate only the stale blocker they actually touch.
            v4236 = getattr(v4241, "v4236", None)
            if v4236 is not None:
                v4236._component_aware_invalidate(g, root, event_type, values)
            projection = root / g.get("V4225_PROJECTION_FILE", "JARVIS_V4225_EVENT_PROJECTION.json")
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
        try:
            _reconcile_project_state(g, root, event_type)
        except Exception:
            pass
        try:
            shared_memory.default_store(Path(g["__file__"]).resolve().parent).append_event(
                str(event_type or "project_event"), {"message": rendered, **values},
                scope="project", project=root,
                repository_token=values.get("repository_token", ""),
                status=str(values.get("status") or ""),
            )
        except Exception:
            pass
        return event

    def validate_component(work, manifest, component, user_request=""):
        ok, output = previous_validate_component(work, manifest, component, user_request)
        raw = _strip_ansi(output)
        compact = raw if ok else compact_component_failure(raw)
        try:
            root = Path(work).resolve()
            full_output = raw
            if len(full_output) > 500000:
                full_output = (
                    full_output[:250000]
                    + "\n... validator output exceeded 500000 characters; middle omitted ...\n"
                    + full_output[-250000:]
                )
            (root / VALIDATOR_OUTPUT_FILE).write_text(full_output, encoding="utf-8")
            _save(root / VALIDATOR_EVIDENCE_FILE, {
                "version": "V" + VERSION,
                "engine": ENGINE,
                "updated_at": g["_utc_stamp"](),
                "component": str((component or {}).get("id") or (component or {}).get("root") or "component"),
                "adapter": str((component or {}).get("toolchain_adapter") or ""),
                "ok": bool(ok),
                "original_characters": len(raw),
                "compacted_characters": len(compact),
                "diagnostic_count": 0 if ok else v4237.diagnostic_count(compact),
                "full_output_sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
                "compacted_output": compact,
            })
        except Exception:
            pass
        return bool(ok), compact

    def _publish_control(text: str, values: dict) -> None:
        try:
            with v4240._CONTROL_LOCK:
                if v4240._ACTIVE.get("job_id") is not None:
                    v4240._ACTIVE.update({
                        "last_heartbeat": g["_utc_stamp"](),
                        "activity": text,
                        "stage": values.get("stage", ""),
                        "percent": values.get("percent"),
                        "diagnostic_count": values.get("diagnostic_count"),
                        "repository_token": values.get("repository_token", ""),
                        "generated_tokens_estimate": values.get("generated_tokens_estimate"),
                    })
            v4240._save_control(g)
        except Exception:
            pass

    def progress(callback, text=None, **fields):
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested from the Jarvis dashboard.")
        rendered = re.sub(r"\bV(?:3[5-9]|4[0-3])(?:\.\d+){0,2}\b(?!\.\d)", "V42.46", str(text or ""))
        values = dict(fields)
        values["engine_version"] = "V" + VERSION
        _publish_control(rendered, values)
        return base_progress(callback, rendered, **values)

    def record_project_heartbeat(info=None):
        values = dict(info or {}) if isinstance(info, dict) else {"message": str(info or "")}
        rendered = re.sub(
            r"\bV(?:3[5-9]|4[0-3])(?:\.\d+){0,2}\b(?!\.\d)",
            "V42.46", str(values.get("message") or "Jarvis project worker heartbeat"),
        )
        values["engine_version"] = "V" + VERSION
        _publish_control(rendered, values)
        try:
            root = v4240._find_active_work(g)
            if root is not None:
                _write_run_state(
                    g, root, activity=rendered, stage=values.get("stage", ""),
                    percent=values.get("percent"),
                    generated_tokens_estimate=values.get("generated_tokens_estimate"),
                    model_profile=values.get("model_profile", ""),
                    model_role=values.get("model_role", ""),
                    streaming=values.get("streaming"),
                )
        except Exception:
            pass

    def qwen_call(prompt, progress_callback=None, stage="Generating", profile="chat", **kwargs):
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested before the next model call.")
        authority = """

V42.46 ATOMIC REPAIR CONTRACT:
- Treat compiler failures as a connected multi-file component cluster, not an isolated line.
- Use the exact current compiler output, definitions, imports, callers, configuration, and dependency manifest supplied in this prompt.
- Produce an applicable structured patch through the caller's required patch protocol; a prose-only diagnosis is not a repair.
- Make the smallest coherent root-cause change. Do not rewrite unrelated working files.
- State the files affected, but do not claim success. Jarvis's exact component validator is the only acceptance authority.
- The accepted repository revision and component share one repair budget across every worker/provider and every wording variation of the same failure.
- If the evidence is insufficient to create a patch, return that limitation once; do not repeat speculative edits.
""".rstrip()
        stage_text = re.sub(r"\bV(?:3[5-9]|4[0-3])(?:\.\d+){0,2}\b(?!\.\d)", "V42.46", str(stage or "Generating"))
        result = base_qwen(str(prompt or "") + authority, progress_callback, stage_text, profile=profile, **kwargs)
        if v4240._STOP_EVENT.is_set():
            raise v4240.ProjectStopRequested("Stop requested after the active model stream closed.")
        return result

    def component_repair(request, manifest, work, failure, callback=None):
        root = Path(work).resolve()
        manifest = manifest if isinstance(manifest, dict) else {}
        component = v4237.component_from_failure(manifest, failure)
        if not component:
            return bool(previous_component(request, manifest, root, failure, callback))
        ledger, record, path = _revision_record(g, root, component, failure)
        _write_status(g, root, record)
        _write_run_state(
            g, root, status="repairing", component=record.get("component"),
            diagnostic_count=record.get("diagnostic_count"),
            repository_token=record.get("repository_token"),
            normalized_signature=(record.get("diagnostic_signatures") or [""])[-1],
            accepted_change=False,
        )

        if record.get("exhausted"):
            record["terminal"] = True
            reason = (
                f"V42.46 automatically stopped because {record.get('component')} repair is exhausted "
                f"at accepted revision {record.get('repository_token')} with "
                f"{record.get('diagnostic_count')} diagnostics."
            )
            _record(g, root, ledger, record, path, "revision_component_circuit_breaker", "automatic_checkpoint", reason=reason)
            _write_status(g, root, record)
            _mark_terminal(g, root, record, reason)
            append_event(
                root, "v4242_revision_exhausted_checkpoint",
                reason, component=record.get("component"), diagnostic_count=record.get("diagnostic_count"),
                repository_token=record.get("repository_token"), status="AUTOMATIC_CHECKPOINT",
            )
            if (
                os.getenv("JARVIS_V4242_AUTO_CHECKPOINT_ON_EXHAUSTION", "1").strip().lower()
                not in {"0", "false", "no", "off"}
                and v4240._ACTIVE.get("job_id") is not None
            ):
                raise AutomaticRepairExhausted(reason)
            return False

        before_token = str(v4237._repo_token(g, root))
        repaired = bool(previous_component(request, manifest, root, failure, callback))
        after_token = str(v4237._repo_token(g, root))
        # The V42.41 controller returns True only after exact component
        # validation and atomic promotion.  Its accepted-revision projection
        # can be written just after the source promotion, so an unchanged
        # progress token must not negate that authoritative validated result.
        if repaired:
            _record(
                g, root, ledger, record, path, "authoritative_component_controller", "committed",
                before_repository_token=before_token, after_repository_token=after_token,
            )
            record["resolved"] = True
            _save(path, ledger)
            state = _write_run_state(
                g, root, status="progress", component=record.get("component"),
                diagnostic_count=record.get("diagnostic_count"), repository_token=after_token,
                accepted_change=True, final_action="revalidate",
            )
            try:
                store = shared_memory.default_store(Path(g["__file__"]).resolve().parent)
                store.append_event(
                    "repair_committed", state, scope="project", project=root,
                    repository_token=after_token, status="accepted", confidence=1.0,
                )
                store.export_project_snapshot(root, extra=state)
            except Exception:
                pass
            return True

        record["model_cycles"] = int(record.get("model_cycles") or 0) + 1
        if record["model_cycles"] < _model_cycle_limit():
            record["exhausted"] = False
            record["terminal"] = False
            reason = (
                f"V42.46 kept {record.get('component')} revision {record.get('repository_token')} open after "
                f"repair cycle {record.get('model_cycles')}/{_model_cycle_limit()} produced no accepted change; "
                "the next cycle receives representative evidence from the full validator stream."
            )
            _record(
                g, root, ledger, record, path, "authoritative_component_controller",
                "retry_pending_full_evidence", source_changed=after_token != before_token, reason=reason,
            )
            _write_status(g, root, record)
            _write_run_state(
                g, root, status="repairing", component=record.get("component"),
                diagnostic_count=record.get("diagnostic_count"),
                repository_token=record.get("repository_token"), accepted_change=False,
                final_action="revalidate_with_full_evidence",
            )
            append_event(
                root, "v4242_revision_retry_pending", reason,
                component=record.get("component"), diagnostic_count=record.get("diagnostic_count"),
                repository_token=record.get("repository_token"), status="RETRY_PENDING",
            )
            return False
        record["exhausted"] = True
        record["terminal"] = True
        reason = (
            f"V42.46 exhausted the bounded {record.get('component')} repair budget at accepted revision "
            f"{record.get('repository_token')}; the component validator still reports "
            f"{record.get('diagnostic_count')} diagnostics and no source change was accepted."
        )
        _record(
            g, root, ledger, record, path, "authoritative_component_controller", "exhausted_no_accepted_change",
            source_changed=after_token != before_token, reason=reason,
        )
        _write_status(g, root, record)
        _mark_terminal(g, root, record, reason)
        append_event(
            root, "v4242_revision_exhausted_checkpoint", reason,
            component=record.get("component"), diagnostic_count=record.get("diagnostic_count"),
            repository_token=record.get("repository_token"), status="AUTOMATIC_CHECKPOINT",
        )
        if (
            os.getenv("JARVIS_V4242_AUTO_CHECKPOINT_ON_EXHAUSTION", "1").strip().lower()
            not in {"0", "false", "no", "off"}
            and v4240._ACTIVE.get("job_id") is not None
        ):
            raise AutomaticRepairExhausted(reason)
        return False

    def checkpoint(job_id=None, reason=""):
        return previous_checkpoint(job_id, reason)

    def identity():
        data = dict(previous_identity() or {})
        data.update({
            "version": "V" + VERSION, "engine": ENGINE,
            "planner_mode": "warm-cache-compiler-promotion-shared-memory-v42.46",
            "revision_component_circuit_breaker": True,
            "diagnostic_text_churn_cannot_reopen_revision": True,
            "automatic_exhausted_checkpoint": True,
            "normalized_compiler_evidence": True,
            "multi_file_compiler_transaction_v4242": True,
            "shared_sqlite_wal_worker_memory": True,
            "memory_scopes": ["personal", "project", "run", "worker"],
            "worker_structured_handoff_contract": True,
            "active_project_heartbeat": True,
            "durable_nested_workspace_registration": True,
            "full_stream_representative_diagnostics": True,
            "model_cycles_per_revision_default": _model_cycle_limit(),
            "repair_strategy_generation": STRATEGY_GENERATION,
            "sqlx_joined_struct_row_repair": True,
            "rust_path_display_compiler_hint_repair": True,
            "small_tail_deterministic_before_model_fallback": True,
            "phase_aware_compile_progress_promotion": True,
            "warm_cargo_target_candidate_compile_gate": True,
            "cold_clone_dependency_rebuild_avoidance": True,
            "failed_validator_zero_diagnostics_requires_positive_compile_proof": True,
            "compiler_primary_site_beats_help_definition_for_sqlx_composites": True,
            "semantic_no_delta_scoped_to_strategy_generation": True,
            "project_shared_context_snapshot": shared_memory.PROJECT_SNAPSHOT_FILE,
            "revision_ledger": LEDGER_FILE,
            "convergence_trace": TRACE_FILE,
            "terminal_state": TERMINAL_FILE,
            "language_framework_toolchain_agnostic": True,
        })
        return data

    def stack_skills(manifest):
        names = list(previous_skills(manifest) or [])
        for name in (
            "revision-scoped-convergence", "shared-worker-memory",
            "structured-worker-handoff", "automatic-exhausted-checkpoint",
        ):
            if name not in names:
                names.append(name)
        return names[:28]

    def engine_guard():
        marker = PathType(g["__file__"]).resolve().with_name(ENGINE_MARKER)
        try:
            disk = marker.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            disk = ""
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
        "V4246_VERSION": VERSION, "V4246_ENGINE": ENGINE,
        "V4245_VERSION": VERSION, "V4245_ENGINE": ENGINE,
        "V4244_VERSION": VERSION, "V4244_ENGINE": ENGINE,
        "V4242_VERSION": VERSION, "V4242_ENGINE": ENGINE,
        # Compatibility aliases intentionally represent the active installed release.
        "V4241_VERSION": VERSION, "V4241_ENGINE": ENGINE,
        "V4240_VERSION": VERSION, "V4240_ENGINE": ENGINE,
        "V4242_LEDGER_FILE": LEDGER_FILE, "V4242_TRACE_FILE": TRACE_FILE,
        "V4242_STATUS_FILE": STATUS_FILE, "V4242_RUN_STATE_FILE": RUN_STATE_FILE,
        "V4242_TERMINAL_FILE": TERMINAL_FILE,
        "V4242_VALIDATOR_EVIDENCE_FILE": VALIDATOR_EVIDENCE_FILE,
        "V4242_VALIDATOR_OUTPUT_FILE": VALIDATOR_OUTPUT_FILE,
        "V4246_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "V4245_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "V4244_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "V4243_REPAIR_STRATEGY_GENERATION": STRATEGY_GENERATION,
        "AutomaticRepairExhausted": AutomaticRepairExhausted,
        "_v4242_normalized_diagnostics": normalized_diagnostics,
        "_v4242_compact_component_failure": compact_component_failure,
        "_v4242_revision_key": revision_key,
        "_v4242_rust_compiler_candidate": rust_compiler_candidate,
        "_v4246_rust_path_display_candidate": _rust_path_display_candidate,
        "_v4243_sqlx_joined_struct_candidate": _sqlx_joined_struct_candidate,
        "_v4246_warm_rust_compile_gate": lambda accepted_work, clone_work, component, files, callback=None: _warm_rust_compile_gate(
            g, Path(accepted_work).resolve(), Path(clone_work).resolve(), component or {}, list(files or []), callback
        ),
        "_v4245_warm_rust_compile_gate": lambda accepted_work, clone_work, component, files, callback=None: _warm_rust_compile_gate(
            g, Path(accepted_work).resolve(), Path(clone_work).resolve(), component or {}, list(files or []), callback
        ),
        # Compatibility alias for older diagnostics/tests. It now uses the same
        # workspace as both source and cache owner and therefore remains fail-closed.
        "_v4244_focused_compile_phase_proof": lambda work, manifest, component, files: _warm_rust_compile_gate(
            g, Path(work).resolve(), Path(work).resolve(), component or {}, list(files or [])
        ),
        "_v4242_reconcile_project_state": lambda work, event_type="": _reconcile_project_state(
            g, Path(work).resolve(), event_type
        ),
        "record_project_heartbeat": record_project_heartbeat,
        "_v4242_deterministic_component_transaction": lambda request, manifest, work, failure, component, callback=None: deterministic_component_transaction(
            g, request, manifest, Path(work).resolve(), failure, component, callback
        ),
        "_v35_validate_component": validate_component,
        "_v4237_repair_component_failure": component_repair,
        "_append_project_event": append_event, "_progress": progress, "_qwen_call": qwen_call,
        "_v36_release_identity": identity, "_v36_stack_skill_names": stack_skills,
        "_v4242_engine_disk_guard": engine_guard, "_v4241_engine_disk_guard": engine_guard,
        "_v4240_engine_disk_guard": engine_guard,
        "checkpoint_stopped_project": checkpoint,
        "generate_project_zip": generate_project_zip,
        "analyze_and_edit_project_zip": analyze_and_edit_project_zip,
    })
