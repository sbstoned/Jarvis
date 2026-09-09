from pathlib import Path
import tempfile, sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import local_qwen_project as m

passed=0
def ck(name,cond,detail=''):
    global passed
    if not cond: raise AssertionError(f'{name}: {detail}')
    passed+=1; print('PASS',name)

# The exact V42.61 miss: nested functional candidate validation must never clone
# Jarvis's live shared npm/cargo/etc cache.
with tempfile.TemporaryDirectory(prefix='v4262_candidate_') as td:
    root=Path(td); work=root/'working'
    (work/'src').mkdir(parents=True)
    (work/'src'/'main.ts').write_text('export const ok = true;\n',encoding='utf-8')
    blob=work/'.jarvis_shared_build_cache'/'cache'/'npm'/'_cacache'/'content-v2'/'sha512'/'aa'/'blob'
    blob.parent.mkdir(parents=True); blob.write_text('volatile',encoding='utf-8')
    handle,clone=m._copy_project_for_candidate_validation(work)
    try:
        ck('candidate clone preserves authored source',(Path(clone)/'src'/'main.ts').exists())
        ck('candidate clone excludes shared build cache',not (Path(clone)/'.jarvis_shared_build_cache').exists())
    finally:
        handle.cleanup()

# If a later infrastructure exception escapes after accepted trial edits have made
# objective progress, V42.62 must retain that better trial instead of discarding it.
orig_accept=m._acceptance_repair_cycle
orig_snapshot=m._resume_validation_snapshot
orig_reg=m._resume_protected_regressions
try:
    with tempfile.TemporaryDirectory(prefix='v4262_progress_') as td:
        root=Path(td); work=root/'working'; job=root/'job'
        (work/'src').mkdir(parents=True); job.mkdir()
        (work/'src'/'a.py').write_text('state = "old"\n',encoding='utf-8')
        manifest={'project_name':'demo','files':[{'path':'src/a.py'}]}
        def snap(path,manifest,request,include_real=True):
            text=(Path(path)/'src'/'a.py').read_text(encoding='utf-8')
            old='old' in text
            issue={'file':'src/a.py','kind':'functional_mock','problem':'old state'}
            return {
                'score':(0,0,0,1 if old else 0), 'compiler_score':(0,0,0),
                'issue_count':1 if old else 0, 'weighted_issues':25 if old else 0,
                'issue_files':['src/a.py'] if old else [],
                'deterministic_issues':[], 'functional_issues':[issue] if old else [],
                'real_ok':True, 'real_output':'', 'hashes':{'src/a.py':'old' if old else 'new'},
                'stable_issue_keys':[],
            }
        def acceptance(_req,_manifest,trial,_callback):
            (Path(trial)/'src'/'a.py').write_text('state = "new"\n',encoding='utf-8')
            raise RuntimeError('simulated candidate-validation infrastructure crash')
        m._resume_validation_snapshot=snap
        m._resume_protected_regressions=lambda before,after: []
        m._acceptance_repair_cycle=acceptance
        ok,issues,best=m._run_resume_sweeps('finish this project',manifest,work,job,max_sweeps=1)
        ck('fatal-boundary recovery does not claim final success',ok is False,ok)
        ck('objectively better trial promoted after later crash','new' in (work/'src'/'a.py').read_text(encoding='utf-8'))
        ck('recovery reports infrastructure interruption',any('infrastructure interruption' in str(x).lower() for x in issues),issues)

    # Protected regressions still block fatal-boundary promotion.
    with tempfile.TemporaryDirectory(prefix='v4262_regression_') as td:
        root=Path(td); work=root/'working'; job=root/'job'
        (work/'src').mkdir(parents=True); job.mkdir()
        (work/'src'/'a.py').write_text('state = "old"\n',encoding='utf-8')
        manifest={'project_name':'demo','files':[{'path':'src/a.py'}]}
        def snap2(path,manifest,request,include_real=True):
            text=(Path(path)/'src'/'a.py').read_text(encoding='utf-8')
            old='old' in text
            return {'score':(0,0,0,1 if old else 0),'issue_count':1 if old else 0,
                    'weighted_issues':1 if old else 0,'issue_files':['src/a.py'] if old else [],
                    'deterministic_issues':[],'functional_issues':[],'real_ok':True,
                    'real_output':'','hashes':{'src/a.py':'old' if old else 'new'},'stable_issue_keys':[]}
        def acceptance2(_req,_manifest,trial,_callback):
            (Path(trial)/'src'/'a.py').write_text('state = "new"\n',encoding='utf-8')
            raise RuntimeError('simulated crash with regression')
        m._resume_validation_snapshot=snap2
        m._resume_protected_regressions=lambda before,after: ['new protected regression']
        m._acceptance_repair_cycle=acceptance2
        raised=False
        try:
            m._run_resume_sweeps('finish this project',manifest,work,job,max_sweeps=1)
        except RuntimeError:
            raised=True
        ck('protected regression still rejects fatal-boundary trial',raised)
        ck('authoritative working remains unchanged on regression','old' in (work/'src'/'a.py').read_text(encoding='utf-8'))
finally:
    m._acceptance_repair_cycle=orig_accept
    m._resume_validation_snapshot=orig_snapshot
    m._resume_protected_regressions=orig_reg

ident=m._v36_release_identity()
ck('release is V42.64',ident.get('version')=='V42.64.0',ident)
ck('identity advertises candidate cache isolation',ident.get('candidate_clone_skips_shared_build_cache') is True,ident)
ck('identity preserves final acceptance gate',ident.get('final_acceptance_gate_unchanged') is True,ident)
ck('27B hardware-fit runtime preserved',int(ident.get('qwen38_runtime_context_default',0))==40960,ident)

print(f'V42.62 candidate-cache/fatal-progress checks passed: {passed}/11')
