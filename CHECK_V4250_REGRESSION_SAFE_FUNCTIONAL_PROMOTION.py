from pathlib import Path
import tempfile
import local_qwen_project as j
import jarvis_v4250_repair as v
import jarvis_v4249_repair as p49

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
check('active version',ident.get('version')=='V42.63.0',ident)
check('active engine',ident.get('engine')=='VERIFIED_NATIVE_STARTUP_HYBRID_WORKFLOW_FACTORY',ident)
check('strategy generation',ident.get('repair_strategy_generation')==v.STRATEGY_GENERATION,ident)
check('marker',Path('JARVIS_ACTIVE_ENGINE.txt').read_text().strip()=='V42.63.0','')
check('disposable candidate advertised',ident.get('functional_candidate_disposable_until_proven') is True,ident)
check('green component regression forbidden',ident.get('previously_green_component_cannot_regress') is True,ident)

# Compiler/build failures outrank functional debt.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src-tauri/src/tools.rs','pub fn x(){}\n')
    calls=[]
    old=j._v4237_repair_component_failure
    try:
        j._v4237_repair_component_failure=lambda req,manifest,root,failure,callback=None: calls.append(failure) or True
        audit={'issues':[
            {'file':'src-tauri','kind':'component_validation','problem':'V36 COMPONENT FAILED [rust | rust | src-tauri]: error[E0308]: mismatch'},
            {'file':'src-tauri/src/tools.rs','kind':'persistence_null_semantics','problem':'bind real null'},
        ]}
        changed=j._v429_repair_audit_round('finish',{'components':[{'id':'rust','root':'src-tauri','toolchain_adapter':'rust'}]},r,audit,None,1)
    finally:
        j._v4237_repair_component_failure=old
    check('component regression repaired before functional debt',changed is True and len(calls)==1,calls)

# A candidate that changes source but fails component proof must never touch live bytes.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src-tauri/src/tools.rs','pub fn value() -> i32 { 1 }\n')
    manifest={'components':[{'id':'rust','root':'src-tauri','toolchain_adapter':'rust'}]}
    group={'file':'src-tauri/src/tools.rs','kinds':['persistence_null_semantics'],'phase':0,'problems':['fix null']}
    before=(r/'src-tauri/src/tools.rs').read_text()
    fake={
        '_v36_patch_repair_candidate': lambda *a,**k: ({'content':'pub fn value() -> String { 1 }\n'},''),
        '_copy_project_for_candidate_validation': j._copy_project_for_candidate_validation,
        '_v4216_language_syntax_error': lambda *a,**k: '',
        '_append_project_event': lambda *a,**k: None,
    }
    old=v._component_candidate_proof
    try:
        v._component_candidate_proof=lambda *a,**k:{'available':True,'ok':False,'kind':'synthetic_compile_fail','output':'error[E0308]'}
        changed,errs=v._patch_only_repair(fake,'finish',manifest,r,group,None)
    finally:
        v._component_candidate_proof=old
    check('compile-red functional candidate rejected',changed is False,errs)
    check('compile-red candidate never touches accepted source',(r/'src-tauri/src/tools.rs').read_text()==before,(r/'src-tauri/src/tools.rs').read_text())

# A build-green candidate still needs strict target-family functional improvement.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src/hooks/useX.ts','export const x=1;\n')
    manifest={}
    group={'file':'src/hooks/useX.ts','kinds':['functional_mock'],'phase':1,'problems':['replace mock']}
    fake={
        '_v36_patch_repair_candidate': lambda *a,**k: ({'content':'export const x=2;\n'},''),
        '_copy_project_for_candidate_validation': j._copy_project_for_candidate_validation,
        '_v4216_language_syntax_error': lambda *a,**k: '',
        '_append_project_event': lambda *a,**k: None,
    }
    oldp=v._component_candidate_proof; oldd=v._functional_delta
    try:
        v._component_candidate_proof=lambda *a,**k:{'available':False,'ok':True,'kind':'no_component','output':''}
        v._functional_delta=lambda *a,**k:{'before_total':1,'after_total':1,'before_group':1,'after_group':1,'improved':False}
        changed,errs=v._patch_only_repair(fake,'finish',manifest,r,group,None)
    finally:
        v._component_candidate_proof=oldp; v._functional_delta=oldd
    check('no functional delta rejected',changed is False,errs)
    check('no-delta source remains unchanged',(r/'src/hooks/useX.ts').read_text()=='export const x=1;\n','')

# A component-green candidate with strict functional delta is promoted and marked accepted.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src/hooks/useX.ts','export const x=1;\n')
    manifest={}
    group={'file':'src/hooks/useX.ts','kinds':['functional_mock'],'phase':1,'problems':['replace mock']}
    marks=[]
    fake={
        '_v36_patch_repair_candidate': lambda *a,**k: ({'content':'export const x=2;\n'},''),
        '_copy_project_for_candidate_validation': j._copy_project_for_candidate_validation,
        '_v4216_language_syntax_error': lambda *a,**k: '',
        '_append_project_event': lambda *a,**k: None,
        '_v413_mark_accepted': lambda root,rel,reason: marks.append((rel,reason)),
    }
    oldp=v._component_candidate_proof; oldd=v._functional_delta
    try:
        v._component_candidate_proof=lambda *a,**k:{'available':True,'ok':True,'kind':'synthetic_green','output':'PASS'}
        v._functional_delta=lambda *a,**k:{'before_total':2,'after_total':1,'before_group':1,'after_group':0,'improved':True}
        changed,errs=v._patch_only_repair(fake,'finish',manifest,r,group,None)
    finally:
        v._component_candidate_proof=oldp; v._functional_delta=oldd
    check('green plus strict functional delta promoted',changed is True,errs)
    check('promoted bytes are candidate bytes',(r/'src/hooks/useX.ts').read_text()=='export const x=2;\n','')
    check('promotion marked authoritative',bool(marks),marks)

check('component validation kind recognized',v._is_component_blocker({'kind':'component_validation'}))
check('functional mock is not compiler blocker',not v._is_component_blocker({'kind':'functional_mock'}))

# Exact GearTrack E0308 regression: String matched against enum arms returning Some(...).
import jarvis_v4241_repair as r41
failure = """error[E0308]: mismatched types
 --> src\tools.rs:27:9
this expression has type `std::string::String`
expected `String`, found `ToolCondition`
error: could not compile `geartrack` (lib) due to 3 previous errors
"""
source = """fn save(tool: Tool) {
    let condition_str = match tool.condition {
        ToolCondition::Good => Some(\"good\"),
        ToolCondition::Fair => Some(\"fair\"),
        ToolCondition::Poor => Some(\"poor\"),
    };
    query.bind(condition_str);
}
"""
candidate,reasons=r41.rust_compiler_candidate(source,failure,'src-tauri/src/tools.rs')
check('exact GearTrack String-vs-enum Option match repaired deterministically','tool.condition.as_str()' in candidate and 'ToolCondition::Good' not in candidate,(candidate,reasons))

print(f'{passed}/{passed+failed} PASS')
raise SystemExit(1 if failed else 0)
