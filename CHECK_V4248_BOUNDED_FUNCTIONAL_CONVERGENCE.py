from pathlib import Path
import tempfile
import json
import local_qwen_project as j
import jarvis_v4248_repair as v
import jarvis_v4249_repair as v49

passed=failed=0
def check(name,cond,detail=''):
    global passed,failed
    if cond:
        passed+=1; print('PASS',name)
    else:
        failed+=1; print('FAIL',name,detail)

def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
check('active version',ident.get('version')=='V42.50.0',ident.get('version'))
check('active engine',ident.get('engine')=='REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY',ident.get('engine'))
check('strategy generation',ident.get('repair_strategy_generation')==v.STRATEGY_GENERATION,ident.get('repair_strategy_generation'))
check('marker',Path('JARVIS_ACTIVE_ENGINE.txt').read_text().strip()=='V42.50.0','')

# Internal Jarvis source snapshots must never become live functional debt.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    bad='''use sqlx::{Pool,Sqlite};\npub async fn x(p:&Pool<Sqlite>)->Result<Row,sqlx::Error>{ let q="INSERT INTO things (id) VALUES (?)"; sqlx::query_as::<_,Row>(q).bind("1").fetch_one(p).await }\n'''
    write(r/'src-tauri/src/data.rs',bad)
    write(r/'.jarvis_backups/v36_checkpoints/files/old_data.rs',bad)
    issues=j._v4248_functional_acceptance_issues(r,'persistent app',{})
    check('backup tree excluded',all('.jarvis_backups' not in x.get('file','') for x in issues),issues)
    tok1=j._v4248_live_source_token(r)
    write(r/'.jarvis_backups/v36_checkpoints/files/new_data.rs',bad+'// historical copy')
    tok2=j._v4248_live_source_token(r)
    check('backup churn cannot reset revision budget',tok1==tok2,(tok1,tok2))

# Related issues in one file are one coherent repair transaction and attempts are bounded.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src-tauri/src/checkout.rs','pub fn x(){}\n')
    audit={'issues':[
        {'file':'src-tauri/src/checkout.rs','kind':'persistence_schema','problem':'fix schema mismatch'},
        {'file':'src-tauri/src/checkout.rs','kind':'persistence_returning','problem':'fix returning contract'},
        {'file':'.jarvis_backups/v36_checkpoints/files/old.rs','kind':'persistence_schema','problem':'ghost'},
    ]}
    old=v49._patch_only_repair; calls=[]
    try:
        def fake(g,req,manifest,root,group,progress_callback=None):
            calls.append((group['file'],list(group['problems']))); return False,['no change']
        v49._patch_only_repair=fake
        for n in range(1,5):
            j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,n)
    finally:
        v49._patch_only_repair=old
    check('same file issues grouped',bool(calls) and all(x[0]=='src-tauri/src/checkout.rs' for x in calls),calls)
    check('both problems supplied together',bool(calls) and len(calls[0][1])==2,calls)
    check('per-group retries bounded',len(calls)==v49.MAX_GROUP_ATTEMPTS_SAME_TARGET,calls)
    ledger=json.loads((r/v49.LEDGER_FILE).read_text())
    rec=next(iter(ledger['groups'].values()))
    check('ledger target-family scoped',rec.get('attempts')==v49.MAX_GROUP_ATTEMPTS_SAME_TARGET,rec)

# A successful grouped repair exits immediately and lets fresh validation take over.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src-tauri/src/lib.rs','pub fn run(){}\n')
    audit={'issues':[
        {'file':'src-tauri/src/lib.rs','kind':'functional_bridge','problem':'wire commands'},
        {'file':'src-tauri/src/lib.rs','kind':'functional_runtime_state','problem':'manage db state'},
    ]}
    old=v49._patch_only_repair; calls=[]
    try:
        def fake_ok(g,req,manifest,root,group,progress_callback=None):
            calls.append((group['file'],list(group['problems']))); (Path(root)/group['file']).write_text('pub fn run(){ /* wired */ }\n'); return True,[]
        v49._patch_only_repair=fake_ok
        changed=j._v429_repair_audit_round('finish',{'files':[]},r,audit,None,1)
    finally:
        v49._patch_only_repair=old
    check('accepted grouped repair returns progress',changed is True,calls)
    check('bridge and runtime state co-repaired',len(calls)==1 and len(calls[0][1])==2,calls)

check('pure cargo timeout classified infrastructure',v._is_validation_timeout_without_source_diagnostic('Command timed out after 180s: cargo build\nCompiling geartrack v0.1.0'))
check('timeout with compiler diagnostic stays source evidence',not v._is_validation_timeout_without_source_diagnostic('Command timed out after 180s: cargo build\nerror[E0277]: bad trait'))
check('cargo build recognized',v._cargo_action(['C:/Users/x/.cargo/bin/cargo.EXE','build'])=='build','')
check('cargo timeout floor expanded',ident.get('cargo_build_timeout_seconds',0)>=600,ident.get('cargo_build_timeout_seconds'))

print(f'{passed}/{passed+failed} PASS')
raise SystemExit(1 if failed else 0)
