from pathlib import Path
import json
import tempfile
import sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import local_qwen_project as m
import jarvis_v4251_repair as tx
import jarvis_v4259_repair as io
from jarvis_workflow_contracts import workflow_issues

passed=0
def ck(name,cond,detail=''):
    global passed
    if not cond: raise AssertionError(f'{name}: {detail}')
    passed+=1; print('PASS',name)

ident=m._v36_release_identity()
ck('release is V42.65',ident.get('version')=='V42.65.0',ident)
ck('fast V42.61 connected scheduler preserved',ident.get('v4261_fast_connected_scheduler_preserved') is True,ident)
ck('connected owner limit remains six',ident.get('connected_cluster_owner_limit')==6,ident)
ck('one-owner-only policy is not installed',ident.get('minimal_atomic_one_owner_policy_enabled') is False,ident)

prod={'file':'src/service.ts','rows':[{'file':'src/service.ts','kind':'functional_mock','problem':'real persistence'}]}
test={'file':'tests/application.integration.test.ts','rows':[{'file':'tests/application.integration.test.ts','kind':'functional_test_coverage','problem':'workflow'}]}
ck('ordinary connected transaction budget remains four',tx._attempt_limit(prod)==4,tx._attempt_limit(prod))
ck('workflow-test endgame gets six bounded attempts',tx._attempt_limit(test)==6,tx._attempt_limit(test))
ck('workflow prompt is evidence-bound','Do not invent helper' in tx._workflow_test_guidance(test),tx._workflow_test_guidance(test))
budget,target,owners,findings=io._adaptive_functional_output({'_v426_route_for_call':lambda *a:('27b38q2','manual')}, 'WORKFLOW TEST ENDGAME: compact proof\nISSUE OWNER FILES: [\"tests/a.test.ts\"]\nCURRENT CONTRACT FINDINGS: [{\"kind\":\"functional_test_coverage\"}]\nAUTHORIZED VALIDATOR LOCATORS BY ISSUE OWNER:', 'V42.65 functional transaction 1: tests/a.test.ts', 'repair', 7000)
ck('workflow-test 27B output is capped compactly',budget<=8192,(budget,target,owners,findings))

# Exact V42.61 last-two failure: nested functional candidate clone must not copy
# Jarvis's live shared npm/cargo cache while package managers mutate it.
with tempfile.TemporaryDirectory(prefix='v4265_candidate_') as td:
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

# Test runner recovery must come from real project evidence, not a fabricated pass.
with tempfile.TemporaryDirectory(prefix='v4265_node_') as td:
    root=Path(td)
    (root/'package.json').write_text(json.dumps({'scripts':{'test':'vitest run'},'devDependencies':{'vitest':'^2'}}),encoding='utf-8')
    manifest={'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':''}],
              'files':[{'path':'tests/application.integration.test.ts','phase':'tests'}]}
    restored=m._v4265_sync_test_commands(root,manifest)
    ck('node test command recovered from package evidence',bool(restored) and manifest['components'][0]['test_command']=='npm test',restored)

with tempfile.TemporaryDirectory(prefix='v4265_rust_') as td:
    root=Path(td)
    (root/'Cargo.toml').write_text('[package]\nname="demo"\nversion="0.1.0"\n',encoding='utf-8')
    manifest={'components':[{'id':'rust','root':'.','toolchain_adapter':'rust','test_command':''}],
              'files':[{'path':'tests/application.rs','phase':'tests'}]}
    restored=m._v4265_sync_test_commands(root,manifest)
    ck('rust test command recovered from Cargo evidence',bool(restored) and manifest['components'][0]['test_command']=='cargo test',restored)

# Missing workflow tests remain explicit debt. V42.65 fixes the runner/repair path;
# it does not weaken the final test requirement.
files={'src/api.ts':'export async function load(){ return invoke("load"); }\n'}
manifest={'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':'npm test'}]}
issues=workflow_issues(files,manifest,request='finish')
ck('missing workflow test still blocks final acceptance',any(x.get('kind')=='functional_test_coverage' for x in issues),issues)

# Crash-safe outer recovery: if accepted trial work exists and a later infrastructure
# exception escapes, preserve it only after a fresh strict score improvement.
orig_accept=m._acceptance_repair_cycle
orig_snapshot=m._resume_validation_snapshot
orig_reg=m._resume_protected_regressions
try:
    with tempfile.TemporaryDirectory(prefix='v4265_progress_') as td:
        root=Path(td); work=root/'working'; job=root/'job'
        (work/'src').mkdir(parents=True); job.mkdir()
        (work/'src'/'a.py').write_text('state = "old"\n',encoding='utf-8')
        manifest={'project_name':'demo','files':[{'path':'src/a.py'}]}
        def snap(path,manifest,request,include_real=True):
            text=(Path(path)/'src'/'a.py').read_text(encoding='utf-8')
            old='old' in text
            issue={'file':'src/a.py','kind':'functional_mock','problem':'old state'}
            return {'score':(0,0,0,1 if old else 0),'compiler_score':(0,0,0),
                    'issue_count':1 if old else 0,'weighted_issues':25 if old else 0,
                    'issue_files':['src/a.py'] if old else [],'deterministic_issues':[],
                    'functional_issues':[issue] if old else [],'real_ok':True,'real_output':'',
                    'hashes':{'src/a.py':'old' if old else 'new'},'stable_issue_keys':[]}
        def acceptance(_req,_manifest,trial,_callback):
            (Path(trial)/'src'/'a.py').write_text('state = "new"\n',encoding='utf-8')
            raise RuntimeError('simulated candidate validation infrastructure crash')
        m._resume_validation_snapshot=snap
        m._resume_protected_regressions=lambda before,after: []
        m._acceptance_repair_cycle=acceptance
        ok,issues,best=m._run_resume_sweeps('finish this project',manifest,work,job,max_sweeps=1)
        ck('fatal recovery never claims final success',ok is False,ok)
        ck('strictly better trial is preserved after later crash','new' in (work/'src'/'a.py').read_text(encoding='utf-8'))
        ck('infrastructure interruption is reported',any('infrastructure interruption' in str(x).lower() for x in issues),issues)

    with tempfile.TemporaryDirectory(prefix='v4265_regression_') as td:
        root=Path(td); work=root/'working'; job=root/'job'
        (work/'src').mkdir(parents=True); job.mkdir()
        (work/'src'/'a.py').write_text('state = "old"\n',encoding='utf-8')
        manifest={'project_name':'demo','files':[{'path':'src/a.py'}]}
        def snap2(path,manifest,request,include_real=True):
            text=(Path(path)/'src'/'a.py').read_text(encoding='utf-8'); old='old' in text
            return {'score':(0,0,0,1 if old else 0),'issue_count':1 if old else 0,
                    'weighted_issues':1 if old else 0,'issue_files':['src/a.py'] if old else [],
                    'deterministic_issues':[],'functional_issues':[],'real_ok':True,'real_output':'',
                    'hashes':{'src/a.py':'old' if old else 'new'},'stable_issue_keys':[]}
        def acceptance2(_req,_manifest,trial,_callback):
            (Path(trial)/'src'/'a.py').write_text('state = "new"\n',encoding='utf-8')
            raise RuntimeError('simulated crash with regression')
        m._resume_validation_snapshot=snap2
        m._resume_protected_regressions=lambda before,after:['protected regression']
        m._acceptance_repair_cycle=acceptance2
        raised=False
        try:
            m._run_resume_sweeps('finish this project',manifest,work,job,max_sweeps=1)
        except RuntimeError:
            raised=True
        ck('protected regression still blocks fatal recovery',raised)
        ck('working stays unchanged when regression exists','old' in (work/'src'/'a.py').read_text(encoding='utf-8'))
finally:
    m._acceptance_repair_cycle=orig_accept
    m._resume_validation_snapshot=orig_snapshot
    m._resume_protected_regressions=orig_reg

ck('final acceptance gate explicitly unchanged',ident.get('final_acceptance_gate_unchanged') is True,ident)
ck('27B hardware-fit runtime preserved',int(ident.get('qwen38_runtime_context_default',0))==40960,ident)
ck('active stream wall remains unbounded',ident.get('active_stream_wall_clock_unbounded') is True,ident)
print(f'V42.65 fast connected endgame recovery checks passed: {passed}/21')
