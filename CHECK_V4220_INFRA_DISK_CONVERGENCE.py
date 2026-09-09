import copy, json, os, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('JARVIS_QWEN_MODEL','auto')
import local_qwen_project as j
import jarvis_v42_runtime as rt
PASS=0;FAIL=0

def ck(name,cond,detail=''):
    global PASS,FAIL
    if cond:
        PASS+=1;print('PASS',name)
    else:
        FAIL+=1;print('FAIL',name,detail)

def write(p,text='x'):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
ck('V42.20 identity',ident.get('version')=='V42.20.0',ident)
ck('V42.20 engine',ident.get('engine')==j.V4220_ENGINE,ident.get('engine'))
for key in ('windows_batch_shim_call_wrapper','infrastructure_failures_never_source_repaired','soft_test_debt_retired_before_authoritative_audit','shared_resume_build_cache','cargo_validation_incremental_disabled','cargo_validation_debug_symbols_disabled','accepted_trial_rebuildable_cache_pruning'):
    ck(key,bool(ident.get(key)),ident.get(key))
ck('runtime identity',rt.V42_RUNTIME_VERSION=='42.20.0',(rt.V42_RUNTIME_VERSION,rt.V42_RUNTIME_ENGINE))

# Exact regression for Windows npm.CMD quoting: the batch path stays a separate
# argv token after CALL; it is never embedded as a pre-quoted one-string command.
cmd=[r'C:\Program Files\nodejs\npm.CMD','install','--no-audit','--no-fund']
wrapped=rt.CommandBroker._windows_batch_argv(cmd,comspec=r'C:\Windows\System32\cmd.exe')
ck('Windows batch wrapper uses constrained CALL',wrapped[:5]==[r'C:\Windows\System32\cmd.exe','/d','/s','/c','call'],wrapped)
ck('npm.CMD remains separate argv token',wrapped[5]==cmd[0],wrapped)
ck('wrapper does not prequote npm path',not wrapped[5].startswith('"'),wrapped[5])
try:
    rt.CommandBroker._windows_batch_argv([r'C:\Program Files\nodejs\npm.CMD','run','build&whoami'],comspec='cmd.exe')
    unsafe=False
except ValueError:
    unsafe=True
ck('batch shim metacharacter guard preserved',unsafe,'')

# Resume trials and the authoritative working tree share only rebuildable cache.
with tempfile.TemporaryDirectory(prefix='v4220_cache_') as td:
    job=Path(td);trial=job/'trial_01';working=job/'working';trial.mkdir();working.mkdir()
    bt=rt.CommandBroker(trial);bw=rt.CommandBroker(working)
    ck('trial/working share build cache root',bt.cache_root==bw.cache_root,(bt.cache_root,bw.cache_root))
    et=bt._prepare_env();ew=bw._prepare_env()
    ck('shared Cargo target',et.get('CARGO_TARGET_DIR')==ew.get('CARGO_TARGET_DIR'),(et.get('CARGO_TARGET_DIR'),ew.get('CARGO_TARGET_DIR')))
    ck('Cargo incremental validation disabled',et.get('CARGO_INCREMENTAL')=='0',et.get('CARGO_INCREMENTAL'))
    ck('Cargo dev debug symbols disabled',et.get('CARGO_PROFILE_DEV_DEBUG')=='0',et.get('CARGO_PROFILE_DEV_DEBUG'))
    ck('Cargo test debug symbols disabled',et.get('CARGO_PROFILE_TEST_DEBUG')=='0',et.get('CARGO_PROFILE_TEST_DEBUG'))

npm_failure='''V36 COMPONENT FAILED [react | react | .]:\nCommand failed (1): C:\\Program Files\\nodejs\\npm.CMD install --no-audit --no-fund\n'\\"C:\\Program Files\\nodejs\\npm.CMD\\"' is not recognized as an internal or external command, operable program or batch file.'''
ck('stopped GearTrack npm failure classified infrastructure',j._v4220_infrastructure_failure(npm_failure),npm_failure)
ck('TypeScript source compile error is not infrastructure',not j._v4220_infrastructure_failure("src/App.tsx(12,4): error TS2322: Type 'string' is not assignable to type 'number'."),'')
ck('Rust source compiler error is not infrastructure',not j._v4220_infrastructure_failure('error[E0308]: mismatched types at src/lib.rs:18:5'),'')
ck('WinError2 tool launch is infrastructure',j._v4220_infrastructure_failure('[WinError 2] The system cannot find the file specified'),'')
ck('generic resume existing tests/build does not request new tests',not j._explicit_tests_requested('Finish the project, make its existing tests/build pass.'),'')

# Missing planner-only acceptance tests are removed at audit authority, but real
# existing tests and explicitly requested tests survive.
with tempfile.TemporaryDirectory(prefix='v4220_softtests_') as td:
    w=Path(td);write(w/'src/main.ts','export {};\n')
    m={'files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/acceptance.test.tsx','depends_on':['src/main.ts']}],
       'implementation_order':['src/main.ts','tests/acceptance.test.tsx'],
       'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':'npm test'}]}
    dropped=j._v4220_retire_soft_test_debt('finish this app',m,w)
    ck('planner-only missing acceptance test retired',dropped==['tests/acceptance.test.tsx'],dropped)
    ck('retired test absent from manifest','tests/acceptance.test.tsx' not in [x.get('path') for x in m.get('files') or []],m)
    ck('stale test command removed',not str((m.get('components') or [{}])[0].get('test_command') or '').strip(),m.get('components'))

with tempfile.TemporaryDirectory(prefix='v4220_generated_existing_') as td:
    w=Path(td);write(w/'src/main.ts','export {};\n');write(w/'tests/acceptance.test.tsx','bad generated test\n')
    m={'files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/acceptance.test.tsx','depends_on':['src/main.ts'],'v423_requirement_debt':'tests','purpose':'Real automated acceptance/integration tests for explicitly requested project behavior.'}],
       'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':'npm test'}]}
    dropped=j._v4220_retire_soft_test_debt('finish app',m,w)
    ck('prior Jarvis-generated existing acceptance test retired',dropped==['tests/acceptance.test.tsx'],dropped)
    ck('retired generated acceptance source removed',not (w/'tests/acceptance.test.tsx').exists(),'')

with tempfile.TemporaryDirectory(prefix='v4220_existingtests_') as td:
    w=Path(td);write(w/'src/main.ts','export {};\n');write(w/'tests/existing.test.ts','export {};\n')
    m={'files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/existing.test.ts','depends_on':['src/main.ts']}],
       'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':'npm test'}]}
    dropped=j._v4220_retire_soft_test_debt('finish app',m,w)
    ck('existing tests preserved',dropped==[] and any(x.get('path')=='tests/existing.test.ts' for x in m['files']),m)
    ck('existing test runner preserved',m['components'][0]['test_command']=='npm test',m['components'])

with tempfile.TemporaryDirectory(prefix='v4220_explicit_') as td:
    w=Path(td);write(w/'src/main.ts','export {};\n')
    m={'files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/acceptance.test.tsx','depends_on':[]}],
       'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':'npm test'}]}
    dropped=j._v4220_retire_soft_test_debt('finish app and include tests',m,w)
    ck('explicitly requested missing tests stay hard',dropped==[] and any(x.get('path')=='tests/acceptance.test.tsx' for x in m['files']),m)

# Audit reclassification is deterministic. Replace only the inherited audit body
# with a fixture so no compiler/network/model is invoked.
orig=j._v4220_prev_whole_project_audit
try:
    j._v4220_prev_whole_project_audit=lambda work,user_request,manifest,run_components=True,progress_callback=None: {
        'issues':[{'file':'.','kind':'component_validation','component':'react','problem':npm_failure}],
        'components':[{'id':'react','ok':False,'output':npm_failure}], 'clean':False
    }
    with tempfile.TemporaryDirectory(prefix='v4220_audit_') as td:
        m={'files':[],'components':[]}
        a=j._v429_whole_project_audit(Path(td),'finish app',m,True,None)
        ck('component launch failure becomes infrastructure issue',a['issues'][0]['kind']=='infrastructure',a)
        ck('infrastructure repair policy is deterministic only',a['issues'][0].get('repair_policy')=='deterministic_runtime_only',a)
finally:
    j._v4220_prev_whole_project_audit=orig

# Infrastructure-only specialist path never calls the inherited model specialist.
called={'n':0};origsp=j._v4220_prev_specialist_audit
try:
    def bomb(*a,**k):called['n']+=1;raise AssertionError('model specialist should not be called')
    j._v4220_prev_specialist_audit=bomb
    with tempfile.TemporaryDirectory(prefix='v4220_infrasp_') as td:
        brief=j._v429_specialist_whole_audit('finish',{},Path(td),{'issues':[{'file':'.','kind':'infrastructure','problem':npm_failure}]},None,'test')
        ck('infrastructure-only specialist suppressed',called['n']==0 and 'suppressed' in brief.lower(),(called,brief))
finally:j._v4220_prev_specialist_audit=origsp

# Accepted trial pruning deletes only rebuildable state, not authored source or
# small Jarvis convergence state.
with tempfile.TemporaryDirectory(prefix='v4220_prune_') as td:
    r=Path(td);write(r/'src/App.tsx','export default 1;\n');write(r/'node_modules/x/a.js','x');write(r/'src-tauri/target/debug/x','x');write(r/'.jarvis_runtime/cargo-target/debug/x','x');write(r/'.jarvis_runtime/v4219_fast_convergence.json','{}')
    removed=j._v4220_prune_rebuildable_tree(r)
    ck('authored source survives cache prune',(r/'src/App.tsx').exists(),removed)
    ck('node_modules removed',not (r/'node_modules').exists(),removed)
    ck('Cargo target removed',not (r/'src-tauri/target').exists(),removed)
    ck('runtime cargo target removed',not (r/'.jarvis_runtime/cargo-target').exists(),removed)
    ck('small convergence state preserved',(r/'.jarvis_runtime/v4219_fast_convergence.json').exists(),removed)

# Terminal packaging cleanup removes the shared resume build cache after the ZIP/checkpoint is produced.
origpkg=j._v4220_prev_package_workspace_zip
try:
    with tempfile.TemporaryDirectory(prefix='v4220_package_') as td:
        job=Path(td);w=job/'working';w.mkdir();write(w/'src/main.ts','export {};\n');write(job/'.jarvis_shared_build_cache/cargo-target/blob','x')
        dummy=job/'dummy.zip';dummy.write_bytes(b'zip')
        j._v4220_prev_package_workspace_zip=lambda work,name_stem,stamp=None:(dummy,1)
        out,count=j._package_workspace_zip(w,'x')
        ck('terminal packaging deletes shared build cache',not (job/'.jarvis_shared_build_cache').exists(),(out,count))
finally:j._v4220_prev_package_workspace_zip=origpkg

# Fast defaults now constrain the high-level loops in addition to per-call walls.
ck('global audit rounds <=3',j.V4213_GLOBAL_MAX_ROUNDS<=3,j.V4213_GLOBAL_MAX_ROUNDS)
ck('V429 audit rounds <=3',j.V429_AUDIT_ROUNDS<=3,j.V429_AUDIT_ROUNDS)
ck('resume sweeps <=2',j.RESUME_SWEEPS<=2,j.RESUME_SWEEPS)
ck('worker call <=180 sec',j.V4220_WORKER_MAX_SECONDS<=180,j.V4220_WORKER_MAX_SECONDS)
ck('specialist call <=300 sec',j.V4220_SPECIALIST_MAX_SECONDS<=300,j.V4220_SPECIALIST_MAX_SECONDS)
ck('file generation wall <=300 sec',j.FILE_GENERATION_WALL_SECONDS<=300,j.FILE_GENERATION_WALL_SECONDS)
ck('file repair wall <=240 sec',j.FILE_REPAIR_WALL_SECONDS<=240,j.FILE_REPAIR_WALL_SECONDS)

report={'version':'V42.20.0','pass':PASS,'fail':FAIL,'total':PASS+FAIL,'identity':ident}
(ROOT/'V42_20_VALIDATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f'RESULT {PASS}/{PASS+FAIL} PASS')
raise SystemExit(1 if FAIL else 0)
