"""Universal evidence-based convergence; native adapters still own verification.

Only a proven pre-existing missing-test discovery failure may be deferred during
production repair. Final acceptance requires the complete existing audit.
"""
from __future__ import annotations
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import jarvis_v4250_repair as gates
import jarvis_v4251_repair as tx
from jarvis_workflow_contracts import debt_key, is_test
from jarvis_workspace_copy import clear_workspace_failure, workspace_failure

VERSION = '42.54.0'
ENGINE = 'EVIDENCE_BASED_WORKFLOW_CONVERGENCE_FACTORY'
STRATEGY = 'functional-acceptance-v11-executable-sql-staged-workflow-proof'
REPORT = 'JARVIS_V4254_CONVERGENCE.json'
_SESSION = ContextVar('jarvis_v4254_validation_session', default=None)
_AUDITS, _BRIEFS = {}, {}
_PREVIOUS_PROOF = gates._component_candidate_proof
_PREVIOUS_BLOCKER = gates._is_component_blocker
_PREVIOUS_DELTA = gates._functional_delta


def missing_test_failure(output):
    text = re.sub(r'\x1b\[[0-9;]*m', '', str(output or ''))
    missing = re.search(r'no test files found|no tests (?:were )?(?:found|collected|ran)|collected 0 items|no tests to run', text, re.I)
    compiler = re.search(r'error\s+TS\d+|error\[E\d+\]|SyntaxError|error CS\d+|BUILD FAILED|compilation failed|error: (?!no tests?\b)', text, re.I)
    return bool(missing and not compiler)


def is_component_blocker(row):
    if row.get('kind') == 'component_validation' and missing_test_failure(row.get('problem')):
        return False
    return _PREVIOUS_BLOCKER(row)


def _declared(manifest):
    return [str(item.get('path') if isinstance(item, dict) else item).replace('\\','/')
            for item in (manifest or {}).get('files', [])]


def revision(root, manifest=None):
    """Hash source/config/locks, never timestamps, token counts or audit reports."""
    root = Path(root).resolve()
    declared = set(_declared(manifest))
    digest = hashlib.sha256()
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in tx.SKIP and not d.startswith('.jarvis'))
        for name in sorted(files):
            path = Path(directory, name)
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or name.startswith(('JARVIS_', '.jarvis')) or tx.planner.v4248._is_internal_rel(rel):
                continue
            if path.suffix.lower() not in tx.SUFFIXES | {'.lock','.txt','.csv','.feature','.kts','.sln','.csproj','.ini','.cfg','.properties'} and rel not in declared and name not in {'Makefile','Dockerfile','Gemfile','Rakefile','.env'}:
                continue
            digest.update(rel.encode() + b'\0')
            with path.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
    spec = {key:(manifest or {}).get(key) for key in ('build_command','test_command','dependency_command','requirements','acceptance_criteria','canonical_domain_contracts')}
    spec['components'] = [{key:row.get(key) for key in ('id','root','toolchain_adapter','build_command','test_command','dependency_command','run_command','language','platform')}
                          for row in (manifest or {}).get('components',[]) if isinstance(row,dict)]
    spec['files'] = [{key:row.get(key) for key in ('path','purpose','phase','language','component','exports','contracts','requires')} if isinstance(row,dict) else row
                     for row in (manifest or {}).get('files',[])]
    digest.update(json.dumps(spec, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _validation_inputs(root, manifest):
    files = dict(tx.source_files(root, _declared(manifest)))
    commands = ' '.join(str(c.get(key) or '') for c in [manifest or {}, *(manifest or {}).get('components',[])] for key in ('test_command','dependency_command'))
    return {rel:text for rel,text in files.items() if is_test(rel) or Path(rel).suffix in {'.json','.toml','.yaml','.yml','.xml','.gradle','.cmake','.ini','.cfg'}
            or Path(rel).name in {'Makefile','Dockerfile'} or Path(rel).name in commands}


def _build(g, root, manifest, rel, component):
    # The old accepted-marker cache is invalid inside an uncommitted clone.
    # Use the same underlying adapter with a fresh command execution.
    quick = g.get('_v4218_prev_validate_production_component') or g.get('_v4216_validate_production_component')
    result = quick(root, manifest, rel) if callable(quick) else None
    if result is not None:
        return result
    command = component.get('build_command') or (manifest or {}).get('build_command')
    runner, noop = g.get('_v34_run_declared_command'), g.get('_v35_is_noop_command')
    if command and callable(runner) and callable(noop) and not noop(command):
        return runner(gates._component_cwd(Path(root), component), command, 'production build proof')
    return False, 'No independent registered production build proof is available.'


def component_candidate_proof(g, root, clone, manifest, rel, callback=None):
    proof = _PREVIOUS_PROOF(g, root, clone, manifest, rel, callback)
    if proof.get('ok') or not missing_test_failure(proof.get('output')):
        return proof
    # New/edited tests must actually pass. Discovery/config changes cannot reuse
    # the baseline's missing-test failure to obtain staged acceptance.
    if is_test(rel) or _validation_inputs(root, manifest) != _validation_inputs(clone, manifest):
        return proof
    component = gates._resolve_component(g, Path(root), manifest, rel)
    validator = g.get('_v35_validate_component')
    if not component or not callable(validator):
        return proof
    baseline_ok, baseline_out = validator(root, manifest, component, 'V42.54 baseline test-discovery proof')
    if baseline_ok or not missing_test_failure(baseline_out):
        return proof
    before_build = _build(g, root, manifest, rel, component)
    after_build = _build(g, clone, manifest, rel, component)
    if not before_build[0] or not after_build[0]:
        return {**proof, 'ok':False, 'kind':'production_build_regression',
                'output':str(before_build[1]) + '\n' + str(after_build[1])}
    return {**proof, 'ok':True, 'kind':'build_passed_with_preexisting_missing_tests',
            'final_acceptance':False, 'deferred_test_debt':True,
            'output':str(after_build[1]) + '\nUnresolved test discovery: ' + str(proof.get('output'))}


def functional_delta(root, clone, request, manifest, group):
    value = _PREVIOUS_DELTA(root, clone, request, manifest, group)
    if 'functional_test_coverage' in (group.get('kinds') or []):
        keys = {debt_key(row) for row in value['before'] if row.get('file') == group.get('file') and row.get('kind') == 'functional_test_coverage'}
        if keys:
            before = sum(debt_key(row) in keys for row in value['before'])
            after = sum(debt_key(row) in keys for row in value['after'])
            value.update(before_group=before, after_group=after, improved=after < before)
    return value


def _root_key(root):
    return str(Path(root).resolve())


def repair_evidence(root, manifest, group=None):
    record = _AUDITS.get(_root_key(root), {})
    current = revision(root, manifest)
    audit = record.get('audit', {}) if record.get('revision') == current else {}
    components = [{key:c.get(key) for key in ('id','root','toolchain_adapter','build_command','test_command','dependency_command')}
                  for c in (manifest or {}).get('components', [])]
    return {'source_revision':current, 'components':components,
            'requirements':{key:(manifest or {}).get(key) for key in ('requirements','acceptance_criteria','canonical_domain_contracts')},
            'validator_results':audit.get('components', []), 'remaining_findings':audit.get('issues', [])[:32],
            'specialist_brief':_BRIEFS.get((_root_key(root), current), ''),
            'new_test_rule':'Use the supplied runner/configuration. Add a real feature workflow; never suppress no-tests or failing assertions.'}


def _failure_signature(audit):
    keys = []
    for row in audit.get('issues', []):
        if row.get('kind') == 'component_validation' and missing_test_failure(row.get('problem')):
            # Test runners print fresh start times/durations on identical failures.
            keys.append((row.get('component') or row.get('file'), 'component_validation', 'missing_test_discovery'))
        else:
            key = debt_key(row)
            problem = re.sub(r'(?m)^\s*(?:Start at|Duration|Finished in|Elapsed time)\b[^\n]*', '', key[2])
            keys.append((*key[:2],problem))
    return hashlib.sha256(json.dumps(sorted(keys,key=str),default=str).encode()).hexdigest()


def _score(audit):
    rows = audit.get('issues', [])
    return (sum(is_component_blocker(row) for row in rows),
            sum(str(row.get('kind') or '').startswith(('functional_', 'persistence_')) and row.get('kind') != 'functional_test_coverage' for row in rows), len(rows))


def _limit(name, default, low, high):
    try: return max(low, min(high, int(os.getenv(name, str(default)))))
    except ValueError: return default


def install(g):
    previous_validate = g['_v35_validate_component']
    previous_audit = g['_v429_whole_project_audit']
    previous_identity = g['_v36_release_identity']

    def validate(root, manifest, component, request=''):
        session = _SESSION.get()
        # Red reuse is scoped to this invocation and exact authored inputs.
        environment = hashlib.sha256(json.dumps(dict(os.environ),sort_keys=True).encode()).hexdigest()
        cwd = gates._component_cwd(Path(root), component)
        dependencies = tuple((name, (cwd/name).stat().st_mtime_ns if (cwd/name).exists() else None)
                             for name in ('node_modules/.package-lock.json','.venv/pyvenv.cfg','.dart_tool/package_config.json'))
        key = (_root_key(root), revision(root, manifest), json.dumps(component, sort_keys=True, default=str), environment, dependencies)
        if session is not None and key in session:
            return session[key]
        result = previous_validate(root, manifest, component, request)
        if session is not None and not result[0] and missing_test_failure(result[1]):
            session[key] = result
        return result

    def audit(root, request, manifest, run_components=True, progress_callback=None):
        value = previous_audit(root, request, manifest, run_components=run_components, progress_callback=progress_callback)
        if run_components:
            _AUDITS[_root_key(root)] = {'revision':revision(root,manifest), 'audit':value}
            if len(_AUDITS) > 64: del _AUDITS[next(iter(_AUDITS))]
        return value

    def specialist(request, manifest, root, current, callback=None, reason=''):
        evidence = repair_evidence(root,manifest)
        selected = {}
        for row in current.get('issues', []):
            rel = row.get('file')
            if not rel or not tx._safe_path(root,rel): continue
            for name, content in tx.related_sources(root,rel,manifest).items():
                if name in selected: continue
                if len(selected) >= tx.MAX_FILES or sum(map(len,selected.values())) + len(content) > tx.MAX_CHARS: continue
                selected[name] = content
        if not selected:
            tx._event(g,root,'v4254_specialist_no_source','No source evidence for a specialist repair; preserving actionable validator debt.')
            return ''
        evidence.update(reason=reason, current_findings=current.get('issues', []), complete_source_files=selected, user_request=str(request))
        prompt = ('READ-ONLY ROOT-CAUSE REPAIR AUDIT. Use the exact current source and commands below. '
                  'Return concrete repair targets and a changed strategy for the remaining failures. '
                  'Do not invent owners or APIs, weaken tests, or claim a build proves functionality. '
                  'Missing tests are workflow debt, not evidence of a broken ownership graph.\n'
                  + json.dumps(evidence,ensure_ascii=False,default=str))
        try:
            ok, text = g['_qwen_call'](prompt,callback,'V42.54 evidence-backed repair audit',profile='audit',max_tokens=2200,thinking=False)
        except Exception as exc:
            ok, text = False, str(exc)
        brief = str(text or '') if ok else ''
        _BRIEFS[(_root_key(root), revision(root,manifest))] = brief[-8000:]
        tx._event(g,root,'v4254_specialist_evidence','Supplied current source, requirements and validator results to the repair audit.',files=list(selected))
        return brief

    def contract(request, manifest, root, visits, reason, callback=None):
        if g.get('V428_SPECIALIST_TAKEOVER') is False: return ''
        owners = g.get('_v40_domain_owner_payload', lambda m:{})(manifest or {}).get('owners', [])
        if not owners and not (manifest or {}).get('canonical_domain_contracts'):
            tx._event(g,root,'v4254_empty_ownership_audit_skipped','No ownership graph was supplied; retaining source/test repair debt.')
            return ''
        key = (_root_key(root), revision(root,manifest), 'ownership')
        if key in _BRIEFS: return _BRIEFS[key]
        rows = [{'file':row.get('provider'), 'kind':'contract',
                 'problem':str(reason), 'owner':row} for row in owners if row.get('provider')]
        brief = specialist(request,manifest,root,{'issues':rows},callback,
                           'Reconcile the supplied ownership graph using actual providers: ' + str(reason))
        _BRIEFS[key] = brief
        return brief

    def convergence(request, manifest, root, callback=None):
        # One controller; real compiler repairs retain their existing adapters.
        token = _SESSION.set({})
        started = time.monotonic()
        max_rounds = _limit('JARVIS_V4254_MAX_ROUNDS', 60, 2, 200)
        wall = _limit('JARVIS_V4254_WALL_SECONDS', 7200, 120, 86400)
        stalls, unchanged = 0, 0
        audited, history = set(), []
        request_key = hashlib.sha256(str(request).encode()).hexdigest()
        def completed():
            tx.planner._save_json(Path(root)/REPORT, {'version':VERSION,'strategy':STRATEGY,
                'status':'whole_audit_passed','whole_audit_clean':True,'issues':[],
                'history':history[-80:],'source_revision':revision(root,manifest),
                'final_acceptance_authority':'existing final publication gates'})
            return True, []
        try:
            current = g['_v429_whole_project_audit'](root,request,manifest,run_components=True,progress_callback=callback)
            saved = tx.planner._load_json(Path(root)/REPORT,{})
            if (not current.get('clean') and saved.get('strategy') == STRATEGY
                    and saved.get('exhausted_revision') == revision(root,manifest)
                    and saved.get('request_key') == request_key
                    and saved.get('failure_signature') == _failure_signature(current)):
                tx._event(g,root,'v4254_unchanged_budget_reused','Unchanged source and failures already exhausted this strategy; retaining checkpoint debt.')
                return False, list(current.get('issues') or [])
            for round_no in range(1,max_rounds + 1):
                if current.get('clean') and not current.get('issues'): return completed()
                if time.monotonic() - started >= wall: break
                before, before_score = revision(root,manifest), _score(current)
                signature = _failure_signature(current)
                clear_workspace_failure()
                g['_v429_repair_audit_round'](request,manifest,root,current,callback,round_no)
                infrastructure_error = workspace_failure(root)
                if infrastructure_error:
                    # A broken clone cannot be repaired by another model audit.
                    # Keep this resumable after the filesystem is fixed, without
                    # marking unchanged authored source as a spent strategy.
                    issues = list(current.get('issues') or []) + [{
                        'file':'.', 'kind':'validation_infrastructure',
                        'problem':infrastructure_error,
                    }]
                    tx.planner._save_json(Path(root)/REPORT, {
                        'version':VERSION, 'strategy':STRATEGY,
                        'status':'infrastructure_blocked', 'final_acceptance':False,
                        'history':history[-80:], 'issues':issues,
                        'source_revision':revision(root,manifest),
                        'model_budget_exhausted':False,
                    })
                    return False, issues
                after = revision(root,manifest)
                if after != before:
                    # Metadata churn cannot reach this branch. Each source edit
                    # gets the complete build/test/runtime/functional audit.
                    fresh = g['_v429_whole_project_audit'](root,request,manifest,run_components=True,progress_callback=callback)
                    improved = _score(fresh) < before_score
                    stalls, unchanged = (0 if improved else stalls + 1), 0
                    history.append({'round':round_no, 'source_changed':True, 'improved':improved,
                                    'before':before_score, 'after':_score(fresh), 'revision':after})
                    current = fresh
                    if current.get('clean') and not current.get('issues'): return completed()
                else:
                    unchanged, stalls = unchanged + 1, stalls + 1
                    history.append({'round':round_no, 'source_changed':False, 'improved':False,
                                    'revision':after, 'failure_signature':signature})
                    # Don't rebuild identical failures. Allow one source-backed
                    # strategy change before returning an honest checkpoint.
                    key = (after,signature)
                    if unchanged == 1 and key not in audited:
                        audited.add(key)
                        g['_v429_specialist_whole_audit'](request,manifest,root,current,callback,'No accepted source change; supply a different evidence-based repair strategy.')
                tx.planner._save_json(Path(root)/REPORT, {'version':VERSION,'strategy':STRATEGY,
                    'final_acceptance':False,'history':history[-80:], 'issues':current.get('issues',[])})
                if unchanged >= 2 or stalls >= 3: break
            tx._event(g,root,'v4254_no_progress_checkpoint',
                      'Repair budget ended without enough verified progress; preserve the best resumable project, not a final release.',
                      issues=current.get('issues',[]), rounds=len(history), final_acceptance=False)
            tx.planner._save_json(Path(root)/REPORT, {'version':VERSION,'strategy':STRATEGY,
                'final_acceptance':False, 'history':history[-80:], 'issues':current.get('issues',[]),
                'exhausted_revision':revision(root,manifest), 'request_key':request_key,
                'failure_signature':_failure_signature(current)})
            return False, list(current.get('issues') or [])
        finally:
            _SESSION.reset(token)

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-3])_repair', name):
            module.VERSION, module.ENGINE = VERSION, ENGINE
            if hasattr(module,'STRATEGY_GENERATION'): module.STRATEGY_GENERATION = STRATEGY
            if hasattr(module,'STRATEGY'): module.STRATEGY = STRATEGY
    tx.STRATEGY = STRATEGY
    gates._is_component_blocker = is_component_blocker
    gates._component_candidate_proof = component_candidate_proof
    gates._functional_delta = functional_delta

    def identity():
        result = dict(previous_identity())
        result.update(version='V'+VERSION, engine=ENGINE, repair_strategy_generation=STRATEGY,
                      planner_mode='evidence-based-workflow-convergence-v42.54',
                      sql_requires_execution_seam=True, missing_tests_are_functional_debt=True,
                      staged_repairs_require_passing_build=True, new_workflow_tests_supported=True,
                      accepted_source_progress_budget=True, language_framework_toolchain_agnostic=True)
        return result

    g.update(_v35_validate_component=validate, _v429_whole_project_audit=audit,
             _v429_whole_project_convergence=convergence, _v429_specialist_whole_audit=specialist,
             _v428_specialist_contract_audit=contract, _v4254_repair_evidence=repair_evidence,
             _v36_release_identity=identity, JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
             V4254_VERSION=VERSION, V4254_ENGINE=ENGINE)
