"""V42.64: durable functional promotion with test-substrate policy reconciliation.

A real V42.63 GearTrack resume exposed a cross-generation policy conflict.  The
minimal one-owner repair *did* reduce functional debt from 8 -> 7 inside a trial,
but the outer resume scorer discarded that better source because an older soft-test
layer had cleared the React test command.  V42.10 then reported a new
``test_substrate`` deterministic issue, making the candidate score look much worse
than the retained 8-issue workspace.  The test command actually existed in the real
project (package.json / persisted component graph), and missing workflow tests were
already explicit later functional debt.

V42.64 makes the layers agree without weakening final acceptance:
  * recover a component's native test command from current project evidence when a
    workflow test is required or test source is planned/existing;
  * remove only *false* test-substrate findings when a runnable command is proven;
  * score genuine test-only substrate/quality debt as deferred during production
    functional convergence, so a compiler-safe 8 -> 7 improvement is retained;
  * final acceptance remains strict: workflow tests still must exist, be meaningful,
    execute, and pass before a project can be labeled complete;
  * preserve V42.63 one-owner-first repair batches, V42.62 cache/crash recovery,
    V42.60 hardware-fit 27B runtime, and all rollback/component proofs.

The policy is toolchain-agnostic.  Discovery prefers persisted current component
metadata and real project manifests, then conservative native-toolchain defaults.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

VERSION = '42.64.0'
ENGINE = 'DURABLE_FUNCTIONAL_PROMOTION_TEST_SUBSTRATE_RECONCILIATION_FACTORY'
STRATEGY = 'functional-acceptance-v21-durable-production-progress-test-substrate-reconciled'

# One-owner repairs may need several outer sweeps when the selected local model is
# slow.  Keep this bounded, but do not checkpoint after only three objectively
# improving owners merely because the historical resume default was three.
DEFAULT_RESUME_SWEEPS = max(3, min(12, int(os.getenv('JARVIS_V4264_RESUME_SWEEPS', '8'))))
_DEFER_TEST_KINDS = {'test_substrate', 'test_quality'}
_REQUIRED_TEST_COMPONENTS: dict[str, set[str]] = {}


def _norm(value) -> str:
    text = str(value or '').replace('\\', '/').strip()
    if text in {'', './'}:
        return '.'
    return text.strip('/') or '.'


def _load_json(path: Path, default=None):
    try:
        value = json.loads(path.read_text(encoding='utf-8', errors='replace'))
        return value
    except Exception:
        return {} if default is None else default


def _component_key(comp: dict) -> tuple[str, str]:
    return str((comp or {}).get('id') or '').strip(), _norm((comp or {}).get('root'))


def _component_root_path(root: Path, comp: dict) -> Path:
    rel = _norm((comp or {}).get('root'))
    return root if rel == '.' else root / rel


def _is_noop(g, command: str) -> bool:
    command = str(command or '').strip()
    if not command:
        return True
    fn = g.get('_v35_is_noop_command')
    if callable(fn):
        try:
            return bool(fn(command))
        except Exception:
            pass
    low = re.sub(r'\s+', ' ', command.lower()).strip()
    return low in {'true', 'echo', 'echo no tests', 'echo no test', 'exit 0', ':'} or 'no test specified' in low


def _planned_or_existing_tests(g, root: Path, manifest: dict, comp: dict) -> bool:
    cid, croot = _component_key(comp)
    if cid and cid in _REQUIRED_TEST_COMPONENTS.get(str(root.resolve()), set()):
        return True
    # Planned test source in the current manifest.
    component_for_rel = g.get('_v362_component_root_for_rel')
    is_test = g.get('_v4216_is_test_rel') or g.get('_v38_is_testish')
    for item in (manifest or {}).get('files') or []:
        if not isinstance(item, dict):
            continue
        rel = _norm(item.get('path'))
        if rel == '.':
            continue
        try:
            testish = bool(is_test(rel)) if callable(is_test) else bool(re.search(r'(^|/)(tests?|__tests__)/|\.(?:test|spec)\.', rel, re.I))
        except Exception:
            testish = bool(re.search(r'(^|/)(tests?|__tests__)/|\.(?:test|spec)\.', rel, re.I))
        if not testish:
            continue
        if callable(component_for_rel):
            try:
                if _norm(component_for_rel(manifest, rel)) == croot:
                    return True
                continue
            except Exception:
                pass
        prefix = '' if croot == '.' else croot.rstrip('/') + '/'
        if (croot == '.' and '/' not in rel.split('/')[0]) or rel.startswith(prefix):
            return True
    # Existing conventional test files in this component.
    cwd = _component_root_path(root, comp)
    if cwd.exists():
        for path in cwd.rglob('*'):
            if not path.is_file():
                continue
            rel = path.relative_to(cwd).as_posix()
            if any(part in {'node_modules', 'target', 'dist', 'build', '.git', '.jarvis_build', '.jarvis_runtime'} for part in path.parts):
                continue
            if re.search(r'(^|/)(tests?|__tests__)/|\.(?:test|spec)\.[A-Za-z0-9]+$|(^|/)test_[^/]+\.py$|_test\.go$', rel, re.I):
                return True
    return False


def _persisted_component_commands(root: Path) -> dict[tuple[str, str], str]:
    data = _load_json(root / 'JARVIS_V35_COMPONENT_GRAPH.json', {})
    out: dict[tuple[str, str], str] = {}
    for comp in data.get('components') or [] if isinstance(data, dict) else []:
        if not isinstance(comp, dict):
            continue
        command = str(comp.get('test_command') or '').strip()
        if command:
            out[_component_key(comp)] = command
    return out


def _package_test_command(cwd: Path, g) -> str:
    package = _load_json(cwd / 'package.json', {})
    if not isinstance(package, dict):
        return ''
    scripts = package.get('scripts') or {}
    test_script = str(scripts.get('test') or '').strip() if isinstance(scripts, dict) else ''
    if test_script and not _is_noop(g, test_script):
        if (cwd / 'pnpm-lock.yaml').exists():
            return 'pnpm test'
        if (cwd / 'yarn.lock').exists():
            return 'yarn test'
        if (cwd / 'bun.lockb').exists() or (cwd / 'bun.lock').exists():
            return 'bun run test'
        return 'npm test'
    deps = {}
    for key in ('dependencies', 'devDependencies'):
        if isinstance(package.get(key), dict):
            deps.update(package[key])
    if 'vitest' in deps:
        return 'npm exec -- vitest run'
    if 'jest' in deps:
        return 'npm exec -- jest'
    return ''


def _discover_test_command(g, root: Path, manifest: dict, comp: dict, persisted=None) -> str:
    current = str((comp or {}).get('test_command') or '').strip()
    if current and not _is_noop(g, current):
        return current
    persisted = persisted if isinstance(persisted, dict) else _persisted_component_commands(root)
    key = _component_key(comp)
    command = str(persisted.get(key) or '').strip()
    if command and not _is_noop(g, command):
        return command
    cwd = _component_root_path(root, comp)
    command = _package_test_command(cwd, g)
    if command:
        return command
    adapter = str((comp or {}).get('toolchain_adapter') or '').strip().lower()
    # Evidence from actual native project files outranks adapter naming.
    if (cwd / 'Cargo.toml').exists():
        return 'cargo test'
    if (cwd / 'go.mod').exists():
        return 'go test ./...'
    if (cwd / 'Package.swift').exists():
        return 'swift test'
    if (cwd / 'pubspec.yaml').exists() and (adapter == 'flutter' or (cwd / 'lib').exists()):
        return 'flutter test'
    if (cwd / 'pom.xml').exists():
        return 'mvn test'
    if (cwd / 'gradlew').exists() or (cwd / 'gradlew.bat').exists():
        return 'gradlew test'
    if next(cwd.glob('*.sln'), None) or next(cwd.glob('*.csproj'), None):
        return 'dotnet test'
    if (cwd / 'pytest.ini').exists() or (cwd / 'conftest.py').exists():
        return 'python -m pytest'
    # Last fallback is Jarvis's registered adapter catalog, not a guessed language.
    catalog = g.get('_v34_toolchain_catalog')
    if callable(catalog) and adapter:
        try:
            command = str((catalog().get(adapter) or {}).get('test_command') or '').strip()
            if command and not _is_noop(g, command):
                return command
        except Exception:
            pass
    return ''


def _sync_test_commands(g, root, manifest, required_ids=None):
    """Restore only evidence-proven test commands for components that need tests.

    We never manufacture a passing test or suppress no-tests.  This only restores
    the executable *runner substrate* so the workflow-test repair can eventually be
    generated and proven by the normal final gates.
    """
    if not isinstance(manifest, dict):
        return []
    root = Path(root).resolve()
    required_ids = set(str(x) for x in (required_ids or ())) | _REQUIRED_TEST_COMPONENTS.get(str(root), set())
    persisted = _persisted_component_commands(root)
    restored = []
    for comp in (manifest.get('components') or []):
        if not isinstance(comp, dict):
            continue
        cid, _croot = _component_key(comp)
        current = str(comp.get('test_command') or '').strip()
        if current and not _is_noop(g, current):
            continue
        if cid not in required_ids and not _planned_or_existing_tests(g, root, manifest, comp):
            continue
        command = _discover_test_command(g, root, manifest, comp, persisted)
        if command and not _is_noop(g, command):
            comp['test_command'] = command
            restored.append({'component': cid or _croot, 'root': _croot, 'test_command': command})
    return restored


def _production_functional_rows(snapshot):
    return [row for row in (snapshot or {}).get('functional_issues') or []
            if isinstance(row, dict) and str(row.get('kind') or '') != 'functional_test_coverage']


def _normalize_intermediate_score(snapshot):
    """Do not let test-only deterministic debt erase real production progress.

    This is only an intermediate resume score.  The issue rows remain in the
    snapshot and ``fully_verified`` remains false, so final acceptance is unchanged.
    """
    snap = dict(snapshot or {})
    deterministic = [row for row in snap.get('deterministic_issues') or [] if isinstance(row, dict)]
    hard = [row for row in deterministic if str(row.get('kind') or '') not in _DEFER_TEST_KINDS]
    deferred = [row for row in deterministic if str(row.get('kind') or '') in _DEFER_TEST_KINDS]
    production = _production_functional_rows(snap)
    if not production or hard or not deferred:
        return snap
    # Never hide compiler diagnostics.  Only normalize the legacy deterministic
    # phase bump caused exclusively by test runner/quality debt.
    ts_count = int(snap.get('typescript_diagnostics') or snap.get('typescript_diagnostic_count') or 0)
    syntax_count = int(snap.get('typescript_syntax_diagnostics') or snap.get('typescript_syntax_diagnostic_count') or 0)
    if syntax_count:
        compiler = (3, syntax_count * 1000 + ts_count, 0)
    elif ts_count:
        compiler = (2, ts_count, 0)
    elif snap.get('real_ok') is True:
        compiler = (0, 0, 0)
    else:
        # Candidate transactions already require a fresh affected-component proof.
        # Treat unresolved workflow-test execution as post-compile debt, not source
        # syntax debt, until the final whole-project gate runs it successfully.
        compiler = (1, 1, 0)
    functional_count = int(snap.get('functional_issue_count') or len(snap.get('functional_issues') or []))
    snap['compiler_score'] = compiler
    snap['score'] = compiler + (functional_count,)
    snap['deferred_test_deterministic_issues'] = deferred
    snap['intermediate_test_debt_deferred_for_promotion'] = True
    snap['verified_phase'] = compiler[0]
    snap['verified_phase_label'] = 'post-compile-runtime-or-integration-debt-with-deferred-workflow-test-substrate'
    snap['fully_verified'] = False
    return snap


def install(g):
    previous_identity = g['_v36_release_identity']
    previous_progress = g['_progress']
    previous_deterministic = g['_deterministic_acceptance_issues']
    previous_snapshot = g['_resume_validation_snapshot']
    previous_summary = g['_resume_snapshot_summary']
    previous_audit = g['_v429_whole_project_audit']

    # One-owner convergence needs enough outer promotion opportunities to retain
    # successive improvements.  Still bounded and user-overridable.
    try:
        g['RESUME_SWEEPS'] = max(int(g.get('RESUME_SWEEPS') or 0), DEFAULT_RESUME_SWEEPS)
    except Exception:
        g['RESUME_SWEEPS'] = DEFAULT_RESUME_SWEEPS

    def deterministic(work, manifest):
        root = Path(work).resolve()
        restored = _sync_test_commands(g, root, manifest)
        rows = list(previous_deterministic(work, manifest) or [])
        # If a historical wrapper produced a test_substrate row before seeing the
        # restored command, remove only the now-factually-false row.
        if restored:
            valid_roots = {_norm(x['root']) for x in restored}
            rows = [row for row in rows if not (
                isinstance(row, dict)
                and str(row.get('kind') or '') == 'test_substrate'
                and _norm(row.get('file')) in valid_roots
            )]
        return rows

    def audit(root, request, manifest, run_components=True, progress_callback=None):
        value = previous_audit(root, request, manifest, run_components=run_components, progress_callback=progress_callback)
        issues = [row for row in (value or {}).get('issues') or [] if isinstance(row, dict)]
        required = {str(row.get('component') or '') for row in issues if str(row.get('kind') or '') == 'functional_test_coverage' and str(row.get('component') or '')}
        _REQUIRED_TEST_COMPONENTS[str(Path(root).resolve())] = required
        restored = _sync_test_commands(g, root, manifest, required)
        if restored and isinstance(value, dict):
            valid_roots = {_norm(x['root']) for x in restored}
            filtered = [row for row in issues if not (
                str(row.get('kind') or '') == 'test_substrate' and _norm(row.get('file')) in valid_roots
            )]
            if len(filtered) != len(issues):
                value = dict(value)
                value['issues'] = filtered
                value['clean'] = bool(value.get('clean')) and not filtered
                try:
                    writer = g.get('_v429_write_audit')
                    if callable(writer):
                        writer(root, value)
                except Exception:
                    pass
            try:
                event = g.get('_append_project_event')
                if callable(event):
                    event(root, 'v4264_test_substrate_reconciled',
                          'V42.64 restored an evidence-proven native test command required by current workflow acceptance.',
                          restored=restored, final_acceptance=False)
            except Exception:
                pass
        return value

    def snapshot(work, manifest, user_request, include_real=True):
        root = Path(work).resolve()
        _sync_test_commands(g, root, manifest)
        snap = previous_snapshot(work, manifest, user_request, include_real=include_real)
        return _normalize_intermediate_score(snap)

    def summary(snap):
        out = dict(previous_summary(snap) or {})
        if (snap or {}).get('intermediate_test_debt_deferred_for_promotion'):
            out['intermediate_test_debt_deferred_for_promotion'] = True
            out['deferred_test_deterministic_issue_count'] = len((snap or {}).get('deferred_test_deterministic_issues') or [])
            out['score'] = list((snap or {}).get('score') or ())
            out['compiler_score'] = list((snap or {}).get('compiler_score') or ())
            out['verified_phase'] = (snap or {}).get('verified_phase')
            out['verified_phase_label'] = (snap or {}).get('verified_phase_label')
        return out

    # Keep release identity coherent across installed repair modules.
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9]|6[0-3])_repair', name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass
            if hasattr(module, 'STRATEGY'):
                module.STRATEGY = STRATEGY
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY

    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent, 'JARVIS_ACTIVE_ENGINE.txt').write_text('V' + VERSION + '\n', encoding='utf-8')
    except Exception:
        pass

    def progress(callback, text=None, **fields):
        if text is not None:
            text = str(text).replace('V42.63', 'V42.64')
        fields = dict(fields)
        fields['engine_version'] = 'V' + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='durable-functional-promotion-test-substrate-reconciled-v42.64',
            false_test_substrate_cannot_block_production_progress=True,
            native_test_command_recovered_from_current_project_evidence=True,
            workflow_test_debt_still_blocks_final_acceptance=True,
            intermediate_test_only_debt_deferred_for_resume_scoring=True,
            compiler_diagnostics_never_deferred=True,
            functional_reduction_retained_across_resume_sweeps=True,
            resume_sweeps_default=DEFAULT_RESUME_SWEEPS,
            minimal_atomic_one_owner_first_preserved=True,
            max_issue_owners_per_atomic_transaction=2,
            candidate_component_proof_preserved=True,
            protected_regression_gate_preserved=True,
            v4262_cache_and_crash_safe_progress_preserved=True,
            qwen38_runtime_context_default=40960,
            qwen38_native_context_max=262144,
            active_stream_wall_clock_unbounded=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _deterministic_acceptance_issues=deterministic,
        _v429_whole_project_audit=audit,
        _resume_validation_snapshot=snapshot,
        _resume_snapshot_summary=summary,
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4264_VERSION=VERSION,
        V4264_ENGINE=ENGINE,
        _v4264_sync_test_commands=lambda root, manifest, required_ids=None: _sync_test_commands(g, root, manifest, required_ids),
        _v4264_normalize_intermediate_score=_normalize_intermediate_score,
    )
