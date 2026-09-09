"""V42.65: restore V42.61 fast connected convergence and finish the workflow-test endgame.

A real V42.61 GearTrack run reduced functional debt from 12 -> 2 quickly.  The two
remaining blockers were executable React and Rust workflow tests.  Jarvis did generate
a valid second Rust test transaction, but candidate validation failed before compilation
because the legacy nested candidate clone copied `.jarvis_shared_build_cache` while npm
was mutating `_cacache`; Windows raised WinError 3 for disappearing cache blobs.

V42.65 intentionally keeps the fast V42.61/V42.58 connected-cluster scheduler instead
of V42.63's one-owner batching.  It adds only endgame durability and test-specific
convergence improvements:
  * every functional candidate clone reuses V42.61's source-only resume clone policy,
    so shared npm/cargo/build caches are never copied into validation candidates;
  * if a later infrastructure exception escapes after a resume trial has objectively
    improved, preserve that trial only when a fresh score strictly improves and no
    protected regression exists;
  * missing workflow-test transactions get a few extra bounded retries and a compact,
    evidence-bound test prompt (implemented in jarvis_v4251_repair) while ordinary
    production repairs retain the historical V42.61 attempt budget;
  * final acceptance remains unchanged: tests must exist, execute, and pass before a
    project may be labeled complete.

The behavior remains language/framework/toolchain agnostic.  Native adapters still own
syntax/build/test/runtime proof.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

VERSION = '42.65.0'
ENGINE = 'FAST_CONNECTED_ENDGAME_RECOVERY_FACTORY'
STRATEGY = 'functional-acceptance-v22-fast-connected-endgame-recovery'


def _score(snapshot):
    try:
        value = tuple((snapshot or {}).get('score') or ())
        return value if value else (999, 999999, 999999, 999999)
    except Exception:
        return (999, 999999, 999999, 999999)


def _issue_strings(snapshot, tail_error=''):
    rows = list((snapshot or {}).get('deterministic_issues') or []) + list((snapshot or {}).get('functional_issues') or [])
    out = []
    for row in rows:
        if isinstance(row, dict):
            rel = str(row.get('file') or '').strip()
            problem = str(row.get('problem') or row.get('kind') or '').strip()
            out.append((rel + ': ' if rel else '') + problem)
        elif str(row).strip():
            out.append(str(row))
    if not out and (snapshot or {}).get('real_ok') is False and (snapshot or {}).get('real_output'):
        out.append(str(snapshot.get('real_output'))[-12000:])
    if tail_error:
        out.append('Resume infrastructure interruption after accepted trial progress: ' + str(tail_error)[-6000:])
    return out[:80]



def _norm(value):
    text = str(value or '').replace('\\', '/').strip()
    if text in {'', './'}:
        return '.'
    return text.strip('/') or '.'


def _load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8', errors='replace'))
    except Exception:
        return {} if default is None else default


def _component_key(comp):
    return str((comp or {}).get('id') or '').strip(), _norm((comp or {}).get('root'))


def _component_root(root, comp):
    rel = _norm((comp or {}).get('root'))
    return Path(root) if rel == '.' else Path(root) / rel


def _is_noop(g, command):
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


def _package_test_command(cwd, g):
    package = _load_json(Path(cwd) / 'package.json', {})
    if not isinstance(package, dict):
        return ''
    scripts = package.get('scripts') or {}
    test_script = str(scripts.get('test') or '').strip() if isinstance(scripts, dict) else ''
    if test_script and not _is_noop(g, test_script):
        if (Path(cwd) / 'pnpm-lock.yaml').exists(): return 'pnpm test'
        if (Path(cwd) / 'yarn.lock').exists(): return 'yarn test'
        if (Path(cwd) / 'bun.lockb').exists() or (Path(cwd) / 'bun.lock').exists(): return 'bun run test'
        return 'npm test'
    deps = {}
    for key in ('dependencies', 'devDependencies'):
        if isinstance(package.get(key), dict): deps.update(package[key])
    if 'vitest' in deps: return 'npm exec -- vitest run'
    if 'jest' in deps: return 'npm exec -- jest'
    return ''


def _persisted_test_commands(root):
    data = _load_json(Path(root) / 'JARVIS_V35_COMPONENT_GRAPH.json', {})
    out = {}
    for comp in data.get('components') or [] if isinstance(data, dict) else []:
        if isinstance(comp, dict) and str(comp.get('test_command') or '').strip():
            out[_component_key(comp)] = str(comp.get('test_command')).strip()
    return out


def _discover_test_command(g, root, comp, persisted=None):
    current = str((comp or {}).get('test_command') or '').strip()
    if current and not _is_noop(g, current):
        return current
    persisted = persisted if isinstance(persisted, dict) else _persisted_test_commands(root)
    command = str(persisted.get(_component_key(comp)) or '').strip()
    if command and not _is_noop(g, command):
        return command
    cwd = _component_root(root, comp)
    command = _package_test_command(cwd, g)
    if command: return command
    if (cwd / 'Cargo.toml').exists(): return 'cargo test'
    if (cwd / 'go.mod').exists(): return 'go test ./...'
    if (cwd / 'Package.swift').exists(): return 'swift test'
    if (cwd / 'pubspec.yaml').exists():
        adapter = str((comp or {}).get('toolchain_adapter') or '').lower()
        return 'flutter test' if adapter == 'flutter' or (cwd / 'lib').exists() else 'dart test'
    if (cwd / 'pom.xml').exists(): return 'mvn test'
    if (cwd / 'gradlew').exists() or (cwd / 'gradlew.bat').exists(): return 'gradlew test'
    if next(cwd.glob('*.sln'), None) or next(cwd.glob('*.csproj'), None): return 'dotnet test'
    if (cwd / 'pytest.ini').exists() or (cwd / 'conftest.py').exists(): return 'python -m pytest'
    return ''


def _planned_or_existing_tests(root, manifest, comp):
    croot = _norm((comp or {}).get('root'))
    prefix = '' if croot == '.' else croot.rstrip('/') + '/'
    test_re = re.compile(r'(^|/)(tests?|__tests__)/|\.(?:test|spec)\.[A-Za-z0-9]+$|(^|/)test_[^/]+\.py$|_test\.go$', re.I)
    for item in (manifest or {}).get('files') or []:
        rel = item.get('path') if isinstance(item, dict) else item
        rel = str(rel or '').replace('\\', '/')
        if rel.startswith(prefix) and test_re.search(rel):
            return True
    cwd = _component_root(root, comp)
    if cwd.exists():
        count = 0
        for path in cwd.rglob('*'):
            if not path.is_file(): continue
            if any(part in {'node_modules','target','dist','build','.git','.jarvis_build','.jarvis_runtime','.jarvis_shared_build_cache'} for part in path.parts):
                continue
            count += 1
            if count > 2000: break
            rel = path.relative_to(cwd).as_posix()
            if test_re.search(rel): return True
    return False


def _sync_test_commands(g, root, manifest, required_ids=None):
    if not isinstance(manifest, dict): return []
    root = Path(root).resolve()
    required_ids = {str(x) for x in (required_ids or ()) if str(x)}
    persisted = _persisted_test_commands(root)
    restored = []
    for comp in manifest.get('components') or []:
        if not isinstance(comp, dict): continue
        cid, croot = _component_key(comp)
        current = str(comp.get('test_command') or '').strip()
        if current and not _is_noop(g, current): continue
        if cid not in required_ids and not _planned_or_existing_tests(root, manifest, comp):
            continue
        command = _discover_test_command(g, root, comp, persisted)
        if command and not _is_noop(g, command):
            comp['test_command'] = command
            restored.append({'component':cid or croot,'root':croot,'test_command':command})
    return restored

def install(g):
    previous_identity = g['_v36_release_identity']
    previous_progress = g['_progress']
    previous_run_resume_sweeps = g['_run_resume_sweeps']
    previous_audit = g['_v429_whole_project_audit']
    previous_deterministic = g.get('_deterministic_acceptance_issues')

    def copy_project_for_candidate_validation(work):
        """Clone stable authored state only for functional candidate validation.

        This is the exact V42.61 endgame bug fix: do not maintain a second stale
        ignore list here.  Reuse the active resume clone policy, which already knows
        every Jarvis-owned volatile cache directory including
        `.jarvis_shared_build_cache`.
        """
        source = Path(work).resolve()
        temp = tempfile.TemporaryDirectory(prefix='jarvis_candidate_')
        clone = Path(temp.name) / 'project'
        try:
            g['_copy_resume_workspace'](source, clone)
        except Exception:
            temp.cleanup()
            raise
        return temp, clone

    def run_resume_sweeps(user_request, manifest, work, job_root, progress_callback=None,
                          generic_resume=True, prior_issues=None, max_sweeps=None):
        """Keep a freshly proven better trial if later infrastructure fails.

        Normal promotion remains owned by V42.61's inherited engine.  This activates
        only when that engine unexpectedly raises after a trial may already contain
        accepted repairs.  It never promotes based on file changes alone.
        """
        try:
            return previous_run_resume_sweeps(
                user_request, manifest, work, job_root, progress_callback,
                generic_resume=generic_resume, prior_issues=prior_issues,
                max_sweeps=max_sweeps,
            )
        except Exception as exc:
            work = Path(work)
            job_root = Path(job_root)
            stop_requested = exc.__class__.__name__ == 'ProjectStopRequested'
            baseline = g['_resume_validation_snapshot'](
                work, manifest, user_request, include_real=True
            )
            trials = [p for p in job_root.glob('trial_*') if p.is_dir()]
            trials.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            for trial in trials:
                try:
                    snap = g['_resume_validation_snapshot'](
                        trial, manifest, user_request, include_real=True
                    )
                    regressions = list(g['_resume_protected_regressions'](baseline, snap) or [])
                    if _score(snap) >= _score(baseline) or regressions:
                        continue
                    checkpoint_dir = job_root / 'checkpoints' / (
                        'before_v4265_fatal_recovery_' + datetime.now().strftime('%Y%m%d_%H%M%S')
                    )
                    g['_commit_resume_trial'](trial, work, checkpoint_dir)
                    event = g.get('_append_project_event')
                    if callable(event):
                        event(
                            work, 'v4265_fatal_boundary_progress_promoted',
                            'V42.65 preserved an objectively better validated resume trial after a later infrastructure interruption.',
                            previous_score=list(_score(baseline)), new_score=list(_score(snap)),
                            interruption=str(exc)[-6000:], regressions=[], final_acceptance=False,
                        )
                    if stop_requested:
                        raise
                    return False, _issue_strings(snap, str(exc)), snap
                except Exception as inner:
                    if inner is exc or inner.__class__.__name__ == 'ProjectStopRequested':
                        raise
                    continue
            raise

    def deterministic(work, manifest):
        restored = _sync_test_commands(g, work, manifest)
        rows = list(previous_deterministic(work, manifest) or []) if callable(previous_deterministic) else []
        if restored:
            roots = {_norm(x['root']) for x in restored}
            rows = [row for row in rows if not (
                isinstance(row, dict) and str(row.get('kind') or '') == 'test_substrate'
                and _norm(row.get('file')) in roots
            )]
        return rows

    def audit(root, request, manifest, run_components=True, progress_callback=None):
        value = previous_audit(root, request, manifest, run_components=run_components, progress_callback=progress_callback)
        rows = [row for row in (value or {}).get('issues') or [] if isinstance(row, dict)]
        required = {str(row.get('component') or '') for row in rows
                    if str(row.get('kind') or '') == 'functional_test_coverage' and str(row.get('component') or '')}
        restored = _sync_test_commands(g, root, manifest, required)
        if restored and isinstance(value, dict):
            command_by_component = {x['component']:x['test_command'] for x in restored}
            filtered = []
            valid_roots = {_norm(x['root']) for x in restored}
            for row in rows:
                if str(row.get('kind') or '') == 'test_substrate' and _norm(row.get('file')) in valid_roots:
                    continue
                if str(row.get('kind') or '') == 'functional_test_coverage':
                    cid = str(row.get('component') or '')
                    if cid in command_by_component:
                        row = dict(row)
                        evidence = dict(row.get('evidence') or {})
                        evidence['test_command'] = command_by_component[cid]
                        row['evidence'] = evidence
                filtered.append(row)
            value = dict(value)
            value['issues'] = filtered
            value['clean'] = bool(value.get('clean')) and not filtered
        return value

    # Keep durable ledgers/status coherent without changing historical scheduling.
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9]|6[0-1])_repair', name):
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
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent, 'JARVIS_ACTIVE_ENGINE.txt').write_text(
            'V' + VERSION + '\n', encoding='utf-8'
        )
    except Exception:
        pass

    def progress(callback, text=None, **fields):
        if text is not None:
            text = str(text).replace('V42.61', 'V42.65')
        fields = dict(fields)
        fields['engine_version'] = 'V' + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='fast-connected-endgame-recovery-v42.65',
            v4261_fast_connected_scheduler_preserved=True,
            connected_functional_clusters=True,
            connected_cluster_owner_limit=6,
            minimal_atomic_one_owner_policy_enabled=False,
            workflow_test_extra_bounded_retries=True,
            workflow_test_attempt_limit=6,
            workflow_test_compact_evidence_bound_prompt=True,
            evidence_proven_test_command_recovery=True,
            false_test_substrate_filtered_only_when_command_is_proven=True,
            functional_candidate_clone_uses_resume_source_policy=True,
            candidate_clone_skips_shared_build_cache=True,
            candidate_clone_skips_volatile_dependency_caches=True,
            fatal_boundary_objective_progress_recovery=True,
            fatal_boundary_requires_strict_score_improvement=True,
            fatal_boundary_protected_regressions_rejected=True,
            final_acceptance_gate_unchanged=True,
            workflow_tests_must_execute_before_completion=True,
            qwen38_native_context_max=262144,
            qwen38_runtime_context_default=40960,
            active_stream_wall_clock_unbounded=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _copy_project_for_candidate_validation=copy_project_for_candidate_validation,
        _v429_whole_project_audit=audit,
        _deterministic_acceptance_issues=deterministic,
        _v4265_sync_test_commands=lambda root, manifest, required_ids=None: _sync_test_commands(g, root, manifest, required_ids),
        _run_resume_sweeps=run_resume_sweeps,
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4265_VERSION=VERSION,
        V4265_ENGINE=ENGINE,
    )
