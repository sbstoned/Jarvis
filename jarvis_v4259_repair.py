"""V42.59: adaptive model I/O for connected convergence.

V42.58 made evidence-connected issue clusters the repair unit. Real runs then
showed the next bottleneck: structured multi-file repairs could still be asked to
fit inside a small fixed output allowance even when the selected local model had
a much larger live context. V42.59 keeps every V42.58 validation/rollback gate,
but sizes functional-transaction output to the selected model and cluster, uses
more of a genuinely available live context, and retries a transport-level length
truncation as a smaller complete transaction instead of immediately throwing the
whole reasoning pass away.

Nothing here is GearTrack-, Rust-, React-, Tauri-, or language-specific. The
signals are model profile, live context, connected owner count, finding count,
and transport finish_reason.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any

import jarvis_v4251_repair as transactions

VERSION = '42.59.0'
ENGINE = 'ADAPTIVE_MODEL_IO_CONNECTED_CLUSTER_FACTORY'
STRATEGY = 'functional-acceptance-v16-adaptive-model-io-connected-clusters'

RELATED_SOURCE_CHARS = max(120000, int(os.getenv('JARVIS_V4259_RELATED_SOURCE_CHARS', '300000')))
LENGTH_RETRIES = max(0, min(3, int(os.getenv('JARVIS_V4259_LENGTH_RETRIES', '2'))))
CAP_27B = max(16384, int(os.getenv('JARVIS_V4259_27B_REPAIR_OUTPUT_TOKENS', '65536')))
CAP_9B = max(12288, int(os.getenv('JARVIS_V4259_9B_REPAIR_OUTPUT_TOKENS', '32768')))
CAP_OTHER = max(8192, int(os.getenv('JARVIS_V4259_OTHER_REPAIR_OUTPUT_TOKENS', '24576')))


def _round_up(value: int, quantum: int = 4096) -> int:
    value = max(1, int(value))
    return ((value + quantum - 1) // quantum) * quantum


def _owner_count(stage: str, prompt: str) -> int:
    # Prefer the machine-readable owner list in the transaction prompt.
    match = re.search(r'ISSUE OWNER FILES:\s*(\[[^\n]*\])', str(prompt or ''))
    if match:
        try:
            rows = json.loads(match.group(1))
            if isinstance(rows, list) and rows:
                return max(1, len(rows))
        except Exception:
            pass
    # Stage labels use "file + file + file". This is only a budgeting fallback,
    # never authorization evidence.
    text = str(stage or '')
    if 'functional transaction' in text.lower() and ':' in text:
        tail = text.split(':', 1)[1]
        return max(1, tail.count(' + ') + 1)
    return 1


def _finding_count(prompt: str) -> int:
    text = str(prompt or '')
    marker = 'CURRENT CONTRACT FINDINGS:'
    end_marker = 'AUTHORIZED VALIDATOR LOCATORS BY ISSUE OWNER:'
    if marker in text:
        section = text.split(marker, 1)[1]
        if end_marker in section:
            section = section.split(end_marker, 1)[0]
        count = section.count('"kind"') + section.count("'kind'")
        if count:
            return min(16, count)
    return 1


def _route_target(g: dict[str, Any], stage: str, profile: str, prompt: str) -> str:
    try:
        target, _reason = g['_v426_route_for_call'](stage, profile, prompt)
        return str(target or '').strip().lower()
    except Exception:
        try:
            return str(g['_v426_active_profile']() or '').strip().lower()
        except Exception:
            return ''


def _model_cap(target: str) -> int:
    low = str(target or '').lower()
    if low.startswith('27b') or '27b38' in low:
        return CAP_27B
    if '9b35' in low or low.startswith('9b'):
        return CAP_9B
    return CAP_OTHER


def _adaptive_functional_output(g: dict[str, Any], prompt: str, stage: str, profile: str, requested=None) -> tuple[int, str, int, int]:
    target = _route_target(g, stage, profile, prompt)
    owners = _owner_count(stage, prompt)
    findings = _finding_count(prompt)
    # Exact replacement JSON repeats old/new source, so connected edits need an
    # emission budget that grows materially with owner/finding count. Prompt size
    # adds only a small increment; it must never incentivize a whole-repo rewrite.
    base = 8192 + max(0, owners - 1) * 4096 + min(8, findings) * 1024
    if len(str(prompt or '')) >= 180000:
        base += 4096
    if target.startswith('27b') or '27b38' in target:
        base = max(base, 16384)
    elif '9b35' in target or target.startswith('9b'):
        base = max(base, 12288)
    try:
        explicit = int(requested or 0)
    except Exception:
        explicit = 0
    desired = _round_up(max(base, explicit))
    cap = _model_cap(target)
    return min(desired, cap), target, owners, findings


def _is_length_failure(result) -> bool:
    try:
        ok, raw = result
    except Exception:
        return False
    if ok:
        return False
    try:
        return str((getattr(raw, 'metadata', {}) or {}).get('finish_reason') or '').lower() == 'length'
    except Exception:
        return False


def _partial_text(result) -> str:
    try:
        _ok, raw = result
    except Exception:
        return ''
    partial = getattr(raw, 'partial_text', '')
    return str(partial or '')


def _length_retry_note(partial: str, retry_no: int, max_tokens: int) -> str:
    paths = []
    for rel in re.findall(r'"file"\s*:\s*"([^"\n]+)"', str(partial or '')):
        if rel not in paths:
            paths.append(rel)
    excerpt = str(partial or '')[-5000:]
    return (
        '\n\nV42.59 TRUNCATION RECOVERY: The prior response reached its output limit. '
        'Do not continue an unterminated JSON string and do not try to repair every owner at once. '
        'Return ONE fresh, complete JSON transaction that makes the smallest high-confidence functional improvement. '
        'For a large connected cluster it is valid, and preferred, to repair only 1-2 issue-owner files whose change can be '
        'fully expressed and validated now; Jarvis will commit real progress, re-audit, and return for the remaining owners. '
        'Respect the framework/runtime calling conventions visible in supplied source (lifecycle hooks, context/state handles, '
        'dependency injection, actors/threads, transactions, etc.); acquire such handles only at legal scope and reuse them '
        'inside nested callbacks rather than calling lifecycle-only APIs from arbitrary helpers. '
        f'This retry allows up to {int(max_tokens):,} output tokens. '
        + ('Files started in the truncated response: ' + json.dumps(paths[:8]) + '. ' if paths else '')
        + ('Diagnostic tail of the truncated response (evidence only; still copy SEARCH from CURRENT ORIGINAL source):\n' + excerpt if excerpt else '')
    )


def _initial_emission_note(max_tokens: int, owners: int) -> str:
    return (
        '\n\nV42.59 ADAPTIVE EMISSION POLICY: The connected cluster is a validation/progress unit, not an obligation to edit every owner '
        f'in one answer. This call has an adaptive output allowance of up to {int(max_tokens):,} tokens for {int(owners)} issue-owner file(s). '
        'Prefer the smallest complete transaction that strictly reduces real debt. If the full cluster would make the JSON large, '
        'repair only the coherent 1-2 owner subset that can be completed safely; Jarvis will validate, commit, re-audit, and continue. '
        'Preserve framework/runtime calling conventions shown by the source; do not move lifecycle-only APIs into illegal nested scopes.'
    )


def _builder_with_note(builder, note: str):
    if not callable(builder):
        return None
    def wrapped(budget):
        reserve = len(note) + 64
        base = builder(max(1, int(budget) - reserve))
        return str(base) + note
    return wrapped


def install(g):
    previous_identity = g['_v36_release_identity']
    previous_qwen_call = g['_qwen_call']

    transactions.VERSION = VERSION
    transactions.ENGINE = ENGINE
    transactions.STRATEGY = STRATEGY
    transactions.MAX_CHARS = max(int(getattr(transactions, 'MAX_CHARS', 120000)), RELATED_SOURCE_CHARS)

    # Let non-atomic/model-native calls use more of a genuinely available large
    # live context too. These are ceilings, not padding: small prompts stay small,
    # and _qwen_effective_context_tokens remains authoritative so Jarvis never
    # assumes a 262K server slot that is not actually running.
    context_floor_updates = {
        'QWEN38_WORKING_CONTEXT_GENERATE': 131072,
        'QWEN38_WORKING_CONTEXT_REPAIR': 262144,
        'QWEN38_WORKING_CONTEXT_PLAN': 131072,
        'QWEN38_WORKING_CONTEXT_AUDIT': 98304,
        'QWEN38_WORKING_CONTEXT_MAX': 262144,
        'QWEN35_WORKING_CONTEXT_GENERATE': 65536,
        'QWEN35_WORKING_CONTEXT_REPAIR': 98304,
        'QWEN35_WORKING_CONTEXT_PLAN': 65536,
        'QWEN35_WORKING_CONTEXT_AUDIT': 49152,
        'QWEN35_WORKING_CONTEXT_MAX': 131072,
    }
    for key, floor in context_floor_updates.items():
        env_name = 'JARVIS_' + key
        if env_name not in os.environ and key in g:
            try:
                g[key] = max(int(g[key]), int(floor))
            except Exception:
                pass

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-8])_repair', name):
            module.VERSION = VERSION
            module.ENGINE = ENGINE
            if hasattr(module, 'STRATEGY'):
                module.STRATEGY = STRATEGY
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY

    def adaptive_qwen_call(prompt, progress_callback=None, stage='Generating', profile='chat', **kwargs):
        stage_text = str(stage or '')
        is_functional = 'functional transaction' in stage_text.lower()
        if not is_functional or str(profile or '').lower() != 'repair':
            return previous_qwen_call(prompt, progress_callback, stage, profile=profile, **kwargs)

        options = dict(kwargs)
        requested = options.get('max_tokens')
        budget, target, owners, findings = _adaptive_functional_output(g, prompt, stage_text, profile, requested)
        options['max_tokens'] = budget
        original_builder = options.get('prompt_builder')
        note = _initial_emission_note(budget, owners)
        if callable(original_builder):
            options['prompt_builder'] = _builder_with_note(original_builder, note)
            call_prompt = prompt
        else:
            call_prompt = str(prompt or '') + note

        try:
            g['_progress'](
                progress_callback,
                f'V42.59 adaptive model I/O: {target or "selected Qwen"}, {owners} connected owner(s), '
                f'{findings} finding(s), requesting up to {budget:,} output tokens.',
                stage='V42.59 adaptive model I/O', percent=92,
                model_profile=target or None, output_token_budget=budget,
            )
        except Exception:
            pass

        result = previous_qwen_call(call_prompt, progress_callback, stage, profile=profile, **options)
        retries = 0
        current_budget = budget
        truncation_history = []
        while retries < LENGTH_RETRIES and _is_length_failure(result):
            partial_before_retry = _partial_text(result)
            try:
                _failed_ok, _failed_raw = result
                failed_meta = dict(getattr(_failed_raw, 'metadata', {}) or {})
            except Exception:
                failed_meta = {}
            truncation_history.append({
                'finish_reason': failed_meta.get('finish_reason'),
                'requested_max_tokens': failed_meta.get('max_tokens') or current_budget,
                'received_chars': failed_meta.get('received_chars'),
                'partial_chars': len(partial_before_retry),
                'partial_sha256': hashlib.sha256(partial_before_retry.encode()).hexdigest() if partial_before_retry else '',
            })
            retries += 1
            cap = _model_cap(target)
            next_budget = min(cap, _round_up(max(current_budget + 8192, current_budget * 2)))
            # V42.62: a hardware-fit cap is not a reason to skip recovery.
            # At the cap, keep the same allowance and request a smaller complete
            # transaction. LENGTH_RETRIES still bounds this transport recovery.
            partial = partial_before_retry
            retry_note = _length_retry_note(partial, retries, next_budget)
            retry_options = dict(kwargs)
            retry_options['max_tokens'] = next_budget
            if callable(original_builder):
                retry_options['prompt_builder'] = _builder_with_note(original_builder, retry_note)
                retry_prompt = prompt
            else:
                retry_prompt = str(prompt or '') + retry_note
            try:
                g['_progress'](
                    progress_callback,
                    f'V42.59 response hit finish_reason=length; retrying the same connected transaction as a smaller complete '
                    f'candidate with up to {next_budget:,} output tokens ({retries}/{LENGTH_RETRIES}).',
                    stage='V42.59 truncation recovery', percent=92,
                    model_profile=target or None, output_token_budget=next_budget,
                )
            except Exception:
                pass
            result = previous_qwen_call(retry_prompt, progress_callback, stage, profile=profile, **retry_options)
            current_budget = next_budget

        # Attach the adaptive-I/O history to the final provider response so the
        # existing bounded model-response receipt records it in checkpoints.
        try:
            _ok, raw = result
            metadata = getattr(raw, 'metadata', None)
            if isinstance(metadata, dict):
                metadata['v4259_model_target'] = target
                metadata['v4259_owner_count'] = owners
                metadata['v4259_finding_count'] = findings
                metadata['v4259_initial_output_budget'] = budget
                metadata['v4259_final_output_budget'] = current_budget
                metadata['v4259_length_retries'] = retries
                metadata['v4259_truncation_history'] = truncation_history
        except Exception:
            pass
        return result

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='adaptive-model-io-connected-cluster-convergence-v42.59',
            connected_functional_clusters=True,
            cluster_progress_is_acceptance_unit=True,
            adaptive_functional_output_budget=True,
            adaptive_budget_signals=['selected_model','connected_owner_count','finding_count','prompt_size'],
            manual_model_selection_strict_lock=True,
            manual_27b_hauhau_aggressive_supported=True,
            qwen27b_functional_output_cap=CAP_27B,
            qwen9b_functional_output_cap=CAP_9B,
            transport_length_retry_as_smaller_complete_transaction=True,
            transport_length_retry_count=LENGTH_RETRIES,
            max_related_source_chars=transactions.MAX_CHARS,
            live_context_is_authoritative=True,
            qwen38_native_context_target=262144,
            qwen38_native_context_max=262144,
            does_not_force_unavailable_context=True,
            active_stream_absolute_timeout_seconds=0,
            active_stream_wall_clock_unbounded=True,
            dead_stream_idle_timeout_preserved=True,
            cooperative_user_stop_preserved=True,
            compiler_and_functional_gates_preserved=True,
            rejected_candidate_source_never_promoted=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _qwen_call=adaptive_qwen_call,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4259_VERSION=VERSION,
        V4259_ENGINE=ENGINE,
    )
