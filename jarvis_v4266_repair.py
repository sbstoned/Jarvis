"""V42.66: fast bounded connected repair with safe malformed-output recovery.

This layer keeps the V42.61/V42.58 connected functional scheduler and all newer
candidate/build/acceptance gates, but prevents a single slow local-model response
from trying to serialize an entire large connected cluster at once.

Key rules:
- keep connected clusters as the validation/progress unit;
- focus each model emission on one issue owner while retaining related evidence;
- cap functional-repair output to a compact budget instead of expanding a caller's
  explicit 9k request to 16k/20k+ merely because multiple owners are connected;
- if a response is malformed only because a trailing edit is incomplete, salvage
  only fully parsed leading edit objects. No source text is repaired or invented;
  every salvaged edit still passes exact-replacement, syntax/build, functional,
  component, and regression gates before promotion;
- keep ordinary production attempts bounded and allow a few extra attempts only
  for missing executable workflow tests;
- give resume enough bounded sweeps to retain successive verified improvements.

The behavior is language/framework/toolchain agnostic.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

import jarvis_v4251_repair as transactions
import jarvis_v4259_repair as adaptive_io

VERSION = '42.66.0'
ENGINE = 'FAST_BOUNDED_CONNECTED_REPAIR_FACTORY'
STRATEGY = 'functional-acceptance-v23-fast-bounded-connected-repair'

MODEL_OWNER_FOCUS = max(1, min(2, int(os.getenv('JARVIS_V4266_MODEL_OWNER_FOCUS', '1'))))
PRODUCTION_OUTPUT_CAP_27B = max(4096, min(12288, int(os.getenv('JARVIS_V4266_27B_OUTPUT_TOKENS', '6144'))))
PRODUCTION_OUTPUT_CAP_9B = max(4096, min(12288, int(os.getenv('JARVIS_V4266_9B_OUTPUT_TOKENS', '8192'))))
PRODUCTION_OUTPUT_CAP_OTHER = max(4096, min(12288, int(os.getenv('JARVIS_V4266_OTHER_OUTPUT_TOKENS', '6144'))))
WORKFLOW_TEST_OUTPUT_CAP = max(4096, min(8192, int(os.getenv('JARVIS_V4266_WORKFLOW_TEST_OUTPUT_TOKENS', '8192'))))
RELATED_SOURCE_CHAR_CAP = max(60000, min(160000, int(os.getenv('JARVIS_V4266_RELATED_SOURCE_CHARS', '120000'))))
PRODUCTION_ATTEMPTS = max(2, min(4, int(os.getenv('JARVIS_V4266_PRODUCTION_ATTEMPTS', '4'))))
WORKFLOW_TEST_ATTEMPTS = max(PRODUCTION_ATTEMPTS, min(6, int(os.getenv('JARVIS_V4266_WORKFLOW_TEST_ATTEMPTS', '6'))))
RESUME_SWEEPS = max(3, min(12, int(os.getenv('JARVIS_V4266_RESUME_SWEEPS', '8'))))
PREFIX_SALVAGE_MAX_EDITS = max(1, min(2, int(os.getenv('JARVIS_V4266_PREFIX_SALVAGE_MAX_EDITS', '1'))))

_ATTEMPT_LOCK = threading.RLock()


def _rows(group):
    return [row for row in ((group or {}).get('rows') or []) if isinstance(row, dict)]


def _is_workflow_test_group(group) -> bool:
    rows = _rows(group)
    if any(str(row.get('kind') or '') == 'functional_test_coverage' for row in rows):
        return True
    rel = str((group or {}).get('file') or '')
    try:
        return bool(transactions.is_test(rel))
    except Exception:
        return bool(re.search(r'(^|/)(tests?|__tests__)/|\.(?:test|spec)\.', rel, re.I))


def _attempt_limit(group) -> int:
    return WORKFLOW_TEST_ATTEMPTS if _is_workflow_test_group(group) else PRODUCTION_ATTEMPTS


def _workflow_test_guidance(group) -> str:
    return (
        'WORKFLOW TEST ENDGAME: produce the smallest executable proof using only public APIs, '
        'types, commands, runners, fixtures, and setup visible in supplied project evidence. '
        'Do not invent helper modules, provider APIs, test-only production behavior, or a passing '
        'assertion that is not supported by current requirements. Cover a real success path and '
        'a meaningful failure/postcondition path, then let the native test runner prove it.'
    )


def _single_owner_group(group, attempt: int = 1):
    owners = list(transactions._owner_groups(group) or [])
    if len(owners) <= MODEL_OWNER_FOCUS:
        return group
    # Focus the first model call on one owner. If the same connected cluster reaches
    # another internal attempt, rotate deterministically so one difficult owner does
    # not consume the entire bounded repair budget.
    start = max(0, int(attempt) - 1) % len(owners)
    chosen = [owners[(start + i) % len(owners)] for i in range(MODEL_OWNER_FOCUS)]
    rows = [row for owner in chosen for row in (owner.get('rows') or [])]
    kinds = sorted({str(x or '') for owner in chosen for x in (owner.get('kinds') or [])})
    problems = [p for owner in chosen for p in (owner.get('problems') or [])]
    files = [str(owner.get('file') or '') for owner in chosen if str(owner.get('file') or '')]
    if not files:
        return group
    narrowed = dict(group)
    narrowed.update(
        file=files[0],
        files=files,
        owner_groups=chosen,
        rows=rows,
        kinds=kinds,
        problems=problems,
        cluster=len(chosen) > 1,
    )
    return narrowed


def _strip_optional_fence(text: str) -> str:
    text = str(text or '').strip().lstrip('\ufeff')
    fenced = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', text, re.I)
    return fenced.group(1).strip() if fenced else text


def _complete_edit_prefix(raw, max_edits: int = PREFIX_SALVAGE_MAX_EDITS):
    """Return only fully decoded leading edit objects from a malformed response.

    This deliberately does not balance braces, close strings, repair commas, or
    reconstruct source. It accepts only edit objects that json.JSONDecoder can
    already decode completely before the malformed/incomplete tail begins.
    """
    text = _strip_optional_fence(raw)
    match = re.match(r'\s*\{\s*"edits"\s*:\s*\[', text)
    if not match:
        return None
    decoder = json.JSONDecoder()
    pos, n = match.end(), len(text)
    edits = []
    while pos < n and len(edits) < int(max_edits):
        while pos < n and text[pos].isspace():
            pos += 1
        if pos < n and text[pos] == ',':
            pos += 1
            continue
        if pos >= n or text[pos] == ']':
            break
        try:
            value, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        if not isinstance(value, dict):
            break
        edits.append(value)
        pos = end
        while pos < n and text[pos].isspace():
            pos += 1
        if pos < n and text[pos] == ',':
            pos += 1
            continue
        if pos < n and text[pos] == ']':
            break
        break
    return {'edits': edits} if edits else None


def _target_cap(target: str, workflow: bool) -> int:
    if workflow:
        return WORKFLOW_TEST_OUTPUT_CAP
    low = str(target or '').lower()
    if low.startswith('27b') or '27b38' in low:
        return PRODUCTION_OUTPUT_CAP_27B
    if low.startswith('9b') or '9b35' in low:
        return PRODUCTION_OUTPUT_CAP_9B
    return PRODUCTION_OUTPUT_CAP_OTHER


def install(g: dict[str, Any]):
    previous_identity = g['_v36_release_identity']
    previous_progress = g['_progress']

    # Preserve the V42.61 connected scheduler, but stop letting related-source
    # evidence expand far beyond what the default 40,960-token live slot can use
    # efficiently for one bounded repair emission.
    transactions.MAX_CHARS = min(int(getattr(transactions, 'MAX_CHARS', RELATED_SOURCE_CHAR_CAP)), RELATED_SOURCE_CHAR_CAP)

    original_parse_object = transactions.parse_object
    original_model_candidate = transactions._model_candidate
    original_repair_transaction = transactions.repair_transaction
    original_adaptive_output = adaptive_io._adaptive_functional_output

    def parse_object_bounded(raw):
        try:
            return original_parse_object(raw)
        except ValueError:
            prefix = _complete_edit_prefix(raw)
            if prefix:
                return prefix
            raise

    def model_candidate(g2, request, manifest, root, group, evidence, errors, attempt, callback):
        effective = _single_owner_group(group, attempt)
        if effective is not group:
            try:
                g2['_progress'](
                    callback,
                    f'V{VERSION} bounded connected emission: focusing this model call on '
                    + ' + '.join(transactions._cluster_owner_files(effective)),
                    stage=f'V{VERSION} fast bounded connected repair', percent=92,
                    issue_owner_focus=len(transactions._cluster_owner_files(effective)),
                    connected_validation_owners=len(transactions._cluster_owner_files(group)),
                )
            except Exception:
                pass
        # Add compact workflow-test guidance through the existing rejection/evidence
        # channel without changing the accepted source or validator ownership.
        local_errors = list(errors or [])
        if _is_workflow_test_group(effective) and _workflow_test_guidance(effective) not in local_errors:
            local_errors.append(_workflow_test_guidance(effective))
        return original_model_candidate(
            g2, request, manifest, root, effective, evidence, local_errors, attempt, callback
        )

    def repair_transaction(g2, request, manifest, root, group, callback=None, prior_errors=None):
        # The historical function reads MAX_ATTEMPTS from its module global. Guard
        # the temporary value so concurrent jobs cannot race this compatibility shim.
        with _ATTEMPT_LOCK:
            old = transactions.MAX_ATTEMPTS
            transactions.MAX_ATTEMPTS = _attempt_limit(group)
            try:
                return original_repair_transaction(
                    g2, request, manifest, root, group, callback, prior_errors
                )
            finally:
                transactions.MAX_ATTEMPTS = old

    def adaptive_functional_output(g2, prompt, stage, profile, requested=None):
        budget, target, owners, findings = original_adaptive_output(
            g2, prompt, stage, profile, requested
        )
        text = str(prompt or '')
        workflow = ('WORKFLOW TEST ENDGAME' in text or 'functional_test_coverage' in text)
        cap = _target_cap(target, workflow)
        # The transaction layer deliberately requests <=9k. Treat that explicit
        # request as a ceiling, not a floor; V42.59 previously expanded it to
        # 16k/20k+ for connected owners, which produced very long local-model calls.
        try:
            explicit = int(requested or 0)
        except Exception:
            explicit = 0
        if explicit > 0:
            cap = min(cap, explicit)
        return max(2048, min(int(budget), int(cap))), target, owners, findings

    transactions.parse_object = parse_object_bounded
    transactions._model_candidate = model_candidate
    transactions.repair_transaction = repair_transaction
    transactions._attempt_limit = _attempt_limit
    transactions._workflow_test_guidance = _workflow_test_guidance
    adaptive_io._adaptive_functional_output = adaptive_functional_output

    transactions.VERSION = VERSION
    transactions.ENGINE = ENGINE
    transactions.STRATEGY = STRATEGY
    adaptive_io.VERSION = VERSION
    adaptive_io.ENGINE = ENGINE
    adaptive_io.STRATEGY = STRATEGY

    try:
        g['RESUME_SWEEPS'] = max(int(g.get('RESUME_SWEEPS') or 0), RESUME_SWEEPS)
    except Exception:
        g['RESUME_SWEEPS'] = RESUME_SWEEPS

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9]|6[0-5])_repair', name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass
            if hasattr(module, 'STRATEGY'):
                module.STRATEGY = STRATEGY
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r'V42\.\d+(?:\.\d+)?(?!\d)', 'V' + VERSION, str(text))
        fields = dict(fields)
        fields['engine_version'] = 'V' + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='fast-bounded-connected-repair-v42.66',
            v4261_fast_connected_scheduler_preserved=True,
            connected_functional_clusters=True,
            connected_cluster_owner_limit=int(getattr(transactions, 'MAX_CLUSTER_OWNERS', 6)),
            model_issue_owner_focus=MODEL_OWNER_FOCUS,
            compact_functional_output=True,
            qwen27b_production_output_cap=PRODUCTION_OUTPUT_CAP_27B,
            qwen9b_production_output_cap=PRODUCTION_OUTPUT_CAP_9B,
            workflow_test_output_cap=WORKFLOW_TEST_OUTPUT_CAP,
            explicit_transaction_output_is_ceiling=True,
            malformed_json_complete_prefix_salvage=True,
            prefix_salvage_max_edits=PREFIX_SALVAGE_MAX_EDITS,
            truncated_or_incomplete_edit_never_reconstructed=True,
            related_source_char_cap=transactions.MAX_CHARS,
            production_attempt_limit=PRODUCTION_ATTEMPTS,
            workflow_test_attempt_limit=WORKFLOW_TEST_ATTEMPTS,
            resume_sweeps_default=g.get('RESUME_SWEEPS'),
            candidate_validation_gate_preserved=True,
            compiler_and_functional_gates_preserved=True,
            protected_regression_gate_preserved=True,
            rejected_candidate_source_never_promoted=True,
            manual_model_selection_strict_lock=True,
            active_stream_wall_clock_unbounded=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4266_VERSION=VERSION,
        V4266_ENGINE=ENGINE,
    )
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent, 'JARVIS_ACTIVE_ENGINE.txt').write_text(
            'V' + VERSION + '\n', encoding='utf-8'
        )
    except OSError:
        pass
