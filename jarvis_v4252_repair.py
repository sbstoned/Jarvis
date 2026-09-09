"""V42.52: retain functional progress through real resume and checkpoint paths."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

import jarvis_v4247_repair as audit47
import jarvis_v4249_repair as audit49
import jarvis_v4251_repair as transactions
from jarvis_sql_contracts import sqlite_contract_issues

VERSION = '42.52.0'
ENGINE = 'DURABLE_FUNCTIONAL_PROGRESS_FACTORY'
STRATEGY = 'functional-acceptance-v10-durable-resume-sql-prepare'
REPORT = 'JARVIS_V4252_FUNCTIONAL_PROGRESS.json'
_previous_functional = audit49.functional_acceptance_issues


def issue_key(row):
    from jarvis_workflow_contracts import debt_key
    return debt_key(row)


def functional_issues(root, request='', manifest=None):
    rows = list(_previous_functional(root, request, manifest) or [])
    declared = []
    for item in (manifest or {}).get('files', []):
        rel = item.get('path') if isinstance(item, dict) else item
        if isinstance(rel, str):
            declared.append(rel.replace('\\', '/'))
    files = list(transactions.source_files(root, declared))
    rows.extend(sqlite_contract_issues(files))
    # Use the broad authored-source inventory, including custom language files.
    from jarvis_workflow_contracts import workflow_issues
    rows = [row for row in rows if row.get('kind') != 'functional_test_coverage']
    rows.extend(workflow_issues(files, manifest, [row for row in rows if row.get('kind') == 'functional_bridge'], request))
    return list({issue_key(row): row for row in rows if isinstance(row, dict)}.values())


def enrich_snapshot(base, rows):
    snap = dict(base or {})
    compiler = tuple(snap.get('compiler_score') or snap.get('score') or (999, 999999, 999999))
    rows = list({issue_key(row): row for row in rows if isinstance(row, dict)}.values())
    deterministic = list(snap.get('deterministic_issues') or [])
    files = sorted({str(row.get('file')) for row in deterministic if row.get('file')})
    count = len({issue_key(row) for row in deterministic + rows})
    snap.update(compiler_score=compiler, score=compiler + (len(rows),),
                functional_issues=rows, functional_issue_count=len(rows),
                functional_issue_keys=[issue_key(row) for row in rows],
                deterministic_issue_files=files,
                issue_files=sorted(set(files) | {str(row.get('file')) for row in rows if row.get('file')}),
                issue_count=count, weighted_issues=int(base.get('weighted_issues') or 0) + 25 * len(rows),
                functional_score_version=STRATEGY, functionally_clean=not rows,
                fully_verified=snap.get('real_ok') is True and not deterministic and not rows)
    return snap


def new_functional_regressions(before, after):
    remaining = Counter(issue_key(row) for row in before.get('functional_issues') or [])
    introduced = []
    for row in after.get('functional_issues') or []:
        key = issue_key(row)
        if remaining[key]:
            remaining[key] -= 1
        elif row.get('kind') not in {'functional_bridge', 'functional_runtime_state'}:
            introduced.append(f"{row.get('file')}: {row.get('problem')}")
    return introduced


def install(g):
    previous_snapshot = g['_resume_validation_snapshot']
    previous_summary = g['_resume_snapshot_summary']
    previous_regressions = g['_resume_protected_regressions']
    previous_identity = g['_v36_release_identity']
    previous_write = g['_v429_write_audit']

    # Final publication, candidate deltas, and outer resume scoring must audit
    # the same current source with the same contracts.
    audit47.functional_acceptance_issues = functional_issues
    audit49.functional_acceptance_issues = functional_issues
    for version in ('4247', '4248', '4249'):
        g['_v' + version + '_functional_acceptance_issues'] = functional_issues

    def snapshot(work, manifest, user_request, include_real=True):
        base = previous_snapshot(work, manifest, user_request, include_real=include_real)
        try:
            rows = functional_issues(work, user_request, manifest)
        except Exception as exc:
            rows = [{'file': 'package', 'kind': 'functional_validation_unavailable',
                     'problem': 'Functional validation could not complete: ' + str(exc)}]
        result = enrich_snapshot(base, rows)
        try:
            payload = summary(result)
            payload.update(version='V' + VERSION, engine=ENGINE, issues=rows)
            (Path(work) / REPORT).write_text(json.dumps(payload, indent=2, default=str) + '\n', encoding='utf-8')
        except OSError:
            pass  # Reporting cannot change the validation result.
        return result

    def summary(snap):
        out = dict(previous_summary(snap) or {})
        for key in ('compiler_score', 'functional_issue_count', 'functionally_clean',
                    'fully_verified', 'functional_score_version'):
            out[key] = snap.get(key)
        if snap.get('real_ok') is True and snap.get('functional_issue_count'):
            out['verified_phase_label'] = 'compiled-with-functional-debt'
        return out

    def regressions(before, after):
        # Do not let adding functional issue files disable old clean-file
        # deterministic protections.
        old_before = dict(before)
        old_before['issue_files'] = before.get('deterministic_issue_files', before.get('issue_files', []))
        found = list(previous_regressions(old_before, after) or [])
        if before.get('real_ok') is True and after.get('real_ok') is not True:
            found.append('Previously passing real build/test/runtime validation no longer passes.')
        compiler_improved = tuple(after.get('compiler_score') or after.get('score') or ()) < tuple(before.get('compiler_score') or before.get('score') or ())
        if before.get('real_ok') is True or not compiler_improved:
            found.extend(new_functional_regressions(before, after))
        return found

    def write_audit(work, payload):
        result = previous_write(work, payload)
        # Legacy state recording ran before the final functional adapter appended
        # its findings. Synchronize the dashboard with the complete audit.
        try:
            state = g['_v4218_state'](work)
            rows = [row for row in payload.get('issues', []) if isinstance(row, dict)]
            count = sum(str(row.get('kind') or '').startswith(('functional_', 'persistence_')) for row in rows)
            record = dict(state.get('last_audit') or {})
            record.update(issue_count=len(rows), functional_issue_count=count,
                          clean=bool(payload.get('clean')) and not rows)
            state['last_audit'] = record
            state['current_blocker'] = rows[0] if rows else None
            g['_v4218_save_state'](work, state)
        except (OSError, KeyError, TypeError, ValueError):
            pass
        return result

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[01])_repair', name):
            module.VERSION = VERSION
            module.ENGINE = ENGINE
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY
    transactions.STRATEGY = STRATEGY

    def identity():
        out = dict(previous_identity() or {})
        out.update(version='V' + VERSION, engine=ENGINE, repair_strategy_generation=STRATEGY,
                   planner_mode='durable-functional-progress-v42.52',
                   functional_progress_in_resume_score=True, sqlite_constant_statement_prepare=True,
                   language_framework_toolchain_agnostic=True)
        return out

    g.update(_resume_validation_snapshot=snapshot, _resume_snapshot_summary=summary,
             _resume_protected_regressions=regressions, _v429_write_audit=write_audit,
             _v36_release_identity=identity, JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
             V4252_VERSION=VERSION, V4252_ENGINE=ENGINE)
