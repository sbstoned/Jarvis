from pathlib import Path
import tempfile
import json
import local_qwen_project as j
import jarvis_v4249_repair as v

passed=failed=0
def check(name,cond,detail=''):
    global passed,failed
    if cond:
        passed+=1; print('PASS',name)
    else:
        failed+=1; print('FAIL',name,detail)

def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
check('active version',ident.get('version')=='V42.50.0',ident.get('version'))
check('active engine',ident.get('engine')=='REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY',ident.get('engine'))
check('strategy generation',ident.get('repair_strategy_generation')==v.STRATEGY_GENERATION,ident.get('repair_strategy_generation'))
check('marker',Path('JARVIS_ACTIVE_ENGINE.txt').read_text().strip()=='V42.50.0','')
check('patch-only advertised',ident.get('functional_patch_only_primary_strategy') is True,ident)

# Runtime ownership: direct Builder in main.rs outranks an unused lib.rs.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/lib.rs','pub fn run(){ tauri::Builder::default().run(tauri::generate_context!()).unwrap(); }')
    write(r/'src-tauri/src/main.rs','fn main(){ tauri::Builder::default().run(tauri::generate_context!()).unwrap(); }')
    check('direct main builder is runtime owner',v._tauri_runtime_entry(r)=='src-tauri/src/main.rs',v._tauri_runtime_entry(r))
    write(r/'src-tauri/src/main.rs','fn main(){ sample_lib::run(); }')
    check('delegating main selects lib',v._tauri_runtime_entry(r)=='src-tauri/src/lib.rs',v._tauri_runtime_entry(r))

# Reachability: helper declaration alone is not a live command. A consumer using
# useTauriCommands plus the helper name activates it.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/main.rs','fn main(){ tauri::Builder::default().run(tauri::generate_context!()).unwrap(); }')
    write(r/'src/hooks/useTauriCommands.ts',"const createTool=async()=>createTauriCommand('tools_create'); const getTools=async()=>createTauriCommand('tools_get_all');")
    write(r/'src/hooks/useFake.ts',"const createTool=async()=>({id:'x'}); // same local name, no real seam\n")
    c=v._tauri_command_contract(r)
    check('dormant helper excluded',not c['commands'],c['commands'])
    write(r/'src/hooks/useTools.ts',"import {useTauriCommands} from './useTauriCommands'; export const x=()=>{const {getTools}=useTauriCommands(); return getTools();};")
    c=v._tauri_command_contract(r)
    check('executable wrapper use activates only used command',c['commands']=={'tools_get_all'},c['commands'])

# Dependency order and bridge deferral.
rows=[
 {'file':'src-tauri/src/main.rs','kind':'functional_bridge','problem':'wire bridge'},
 {'file':'src-tauri/src/main.rs','kind':'functional_runtime_state','problem':'manage state'},
 {'file':'src/hooks/usePeople.ts','kind':'functional_mock','problem':'replace mock'},
 {'file':'src-tauri/src/data.rs','kind':'persistence_returning','problem':'fix SQL'},
 {'file':'tests/app.test.ts','kind':'functional_test_coverage','problem':'prove workflow'},
]
groups=v._group_rows(rows)
check('persistence phase first',groups[0]['phase']==0 and groups[0]['file']=='src-tauri/src/data.rs',groups)
check('mock before bridge',next(g['phase'] for g in groups if g['file']=='src/hooks/usePeople.ts') < next(g['phase'] for g in groups if g['file']=='src-tauri/src/main.rs'),groups)
check('tests last',max(g['phase'] for g in groups)==5,groups)

# Stable retry identity ignores changed problem wording for same file/kinds.
check('stable issue family signature',v._group_key('src-tauri/src/main.rs',['functional_bridge'])==v._group_key('src-tauri/src/main.rs',['functional_bridge']),'')

# A lower-layer issue prevents bridge attempts. Patch primitive is mocked at the
# V42.49 layer so no model call occurs in this regression.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/data.rs','pub fn x(){}\n')
    write(r/'src-tauri/src/main.rs','fn main(){}\n')
    audit={'issues':[
      {'file':'src-tauri/src/data.rs','kind':'persistence_returning','problem':'fix persistence'},
      {'file':'src-tauri/src/main.rs','kind':'functional_bridge','problem':'wire bridge'},
    ]}
    old=v._patch_only_repair; calls=[]
    try:
        def fake(g,req,manifest,root,group,progress_callback=None):
            calls.append(group['file']); return False,['no change']
        v._patch_only_repair=fake
        j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,1)
    finally:
        v._patch_only_repair=old
    check('bridge deferred while lower layer exists',calls==['src-tauri/src/data.rs'],calls)

# Unrelated source change does not reopen an unchanged exhausted target because
# the retry clock is target bytes + issue family, not repository token.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/data.rs','pub fn x(){}\n')
    write(r/'src/other.ts','export const n=1;\n')
    audit={'issues':[{'file':'src-tauri/src/data.rs','kind':'persistence_returning','problem':'fix persistence'}]}
    old=v._patch_only_repair; calls=[]
    try:
        def fake(g,req,manifest,root,group,progress_callback=None):
            calls.append(group['file']); return False,['no change']
        v._patch_only_repair=fake
        for n in range(v.MAX_GROUP_ATTEMPTS_SAME_TARGET):
            j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,n+1)
        write(r/'src/other.ts','export const n=2;\n')
        j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,99)
    finally:
        v._patch_only_repair=old
    check('unrelated accepted/source change cannot reopen hard target',len(calls)==v.MAX_GROUP_ATTEMPTS_SAME_TARGET,calls)

# Changing the target itself opens a new local repair budget.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/data.rs','pub fn x(){}\n')
    audit={'issues':[{'file':'src-tauri/src/data.rs','kind':'persistence_returning','problem':'fix persistence'}]}
    old=v._patch_only_repair; calls=[]
    try:
        def fake(g,req,manifest,root,group,progress_callback=None):
            calls.append(group['file']); return False,['no change']
        v._patch_only_repair=fake
        for n in range(v.MAX_GROUP_ATTEMPTS_SAME_TARGET):
            j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,n+1)
        write(r/'src-tauri/src/data.rs','pub fn x(){ /* real new accepted source */ }\n')
        j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,50)
    finally:
        v._patch_only_repair=old
    check('target change reopens local budget',len(calls)==v.MAX_GROUP_ATTEMPTS_SAME_TARGET+1,calls)

print(f'{passed}/{passed+failed} PASS')
raise SystemExit(1 if failed else 0)
