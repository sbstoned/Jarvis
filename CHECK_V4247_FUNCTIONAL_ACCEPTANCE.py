from pathlib import Path
import tempfile
import json
import local_qwen_project as j
import jarvis_v4249_repair as v49

passed=failed=0
def check(name, cond, detail=''):
    global passed,failed
    if cond:
        passed+=1; print('PASS',name)
    else:
        failed+=1; print('FAIL',name,detail)

def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
check('active version',ident.get('version')=='V42.50.0',ident)
check('active engine',ident.get('engine')=='REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY',ident)
check('functional gate advertised',ident.get('functional_acceptance_gate') is True,ident)
check('compiler not completion',ident.get('compile_success_is_not_project_completion') is True,ident)

# Bad cross-boundary app: should be rejected despite being perfectly parse/compile-shaped.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src/hooks/useApi.ts', '''import { invoke } from '@tauri-apps/api/core';\nexport async function load(){return invoke("items_get_all")}\n''')
    write(r/'src/hooks/usePeople.ts', '''// Simulate API call to backend\nexport async function createPerson(name:string){ return {id:"mock",name}; }\n''')
    write(r/'src-tauri/src/lib.rs', '''pub mod db; pub fn run(){tauri::Builder::default().run(tauri::generate_context!()).unwrap();}\n''')
    write(r/'src-tauri/src/db.rs', '''use sqlx::{Pool,Sqlite}; pub async fn init_db(_p:&Pool<Sqlite>){}\n''')
    write(r/'tests/application.integration.test.ts', '''import {expect,it} from 'vitest'; import {load} from '../src/hooks/useApi'; it('x',()=>expect(typeof load).toBe('function'));\n''')
    issues=j._v4247_functional_acceptance_issues(r,'build persistent app',{})
    kinds={x['kind'] for x in issues}
    check('unbound tauri bridge detected','functional_bridge' in kinds,issues)
    check('production mock detected','functional_mock' in kinds,issues)
    check('weak integration test detected','functional_test_coverage' in kinds,issues)

# SQL runtime contracts: compile-safe but runtime-broken patterns must be acceptance debt.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src-tauri/src/models.rs','''pub struct RowThing { pub id:String, pub name:String, pub owner_id:Option<String> }\n''')
    write(r/'src-tauri/src/data.rs', r'''use sqlx::{Pool,Sqlite};
pub async fn init(pool:&Pool<Sqlite>)->Result<(),sqlx::Error>{
 let q=r#"CREATE TABLE IF NOT EXISTS things (id TEXT PRIMARY KEY, name TEXT NOT NULL, owner_id TEXT)"#; sqlx::query(q).execute(pool).await?; Ok(()) }
pub async fn create(pool:&Pool<Sqlite>)->Result<RowThing,sqlx::Error>{
 let query="INSERT INTO things (id,name) VALUES (?,?)";
 sqlx::query_as::<_,RowThing>(query).bind("1").bind("x").fetch_one(pool).await }
pub async fn wrong(pool:&Pool<Sqlite>)->Result<(),sqlx::Error>{
 let q="UPDATE things SET missing_column = ? WHERE id = ?"; sqlx::query(q).bind("x").bind("1").execute(pool).await?; Ok(()) }
pub async fn clear(pool:&Pool<Sqlite>)->Result<(),sqlx::Error>{ let q="UPDATE things SET owner_id=? WHERE id=?"; sqlx::query(q).bind("null").bind("1").execute(pool).await?; Ok(()) }
pub async fn read(pool:&Pool<Sqlite>)->Result<RowThing,sqlx::Error>{ sqlx::query_as::<_,RowThing>("SELECT id, name FROM things WHERE id=?").bind("1").fetch_one(pool).await }
''')
    issues=j._v4247_functional_acceptance_issues(r,'persistent app',{})
    kinds={x['kind'] for x in issues}
    check('mutation returning detected','persistence_returning' in kinds,issues)
    check('schema mismatch detected','persistence_schema' in kinds,issues)
    check('string null detected','persistence_null_semantics' in kinds,issues)
    check('row projection detected','persistence_row_shape' in kinds,issues)

# Properly bound Tauri seam with meaningful test should not produce bridge/test debt.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src/api.ts','''import {invoke} from '@tauri-apps/api/core'; export const getItems=()=>invoke("items_get_all");\n''')
    write(r/'src-tauri/src/lib.rs',r'''#[tauri::command] async fn items_get_all()->Result<Vec<String>,String>{Ok(vec![])}
pub fn run(){tauri::Builder::default().invoke_handler(tauri::generate_handler![items_get_all]).run(tauri::generate_context!()).unwrap();}
''')
    write(r/'tests/items.test.ts','''import {describe,it,expect,vi} from 'vitest'; import {getItems} from '../src/api'; describe('items workflow',()=>it('loads items',async()=>{ await getItems(); expect(getItems).toBeDefined(); }));\n''')
    issues=j._v4247_functional_acceptance_issues(r,'simple desktop list',{})
    kinds={x['kind'] for x in issues}
    check('bound bridge accepted','functional_bridge' not in kinds,issues)
    check('nontrivial bridge test accepted','functional_test_coverage' not in kinds,issues)

# Audit wrapper must override an otherwise green inherited audit.
with tempfile.TemporaryDirectory() as td:
    r=Path(td)
    write(r/'src/api.ts','''import {invoke} from '@tauri-apps/api/core'; export const getItems=()=>invoke("items_get_all");\n''')
    write(r/'src-tauri/src/lib.rs','''pub fn run(){tauri::Builder::default().run(tauri::generate_context!()).unwrap();}\n''')
    payload=j._v429_whole_project_audit(r,'finish app',{'files':[]},run_components=False)
    check('functional debt forces audit unclean',payload.get('clean') is False,payload)
    check('functional report written',(r/'JARVIS_V4247_FUNCTIONAL_ACCEPTANCE.json').is_file(),'')

# Functional findings must bypass older stable-provider skipping and enter the
# active V42.49 patch-only functional dispatcher directly.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); write(r/'src/hooks/usePeople.ts','// Simulate API call to backend\nexport const x=()=>({id:"mock"});\n')
    old=v49._patch_only_repair; calls=[]
    try:
        def fake(g,req,manifest,root,group,progress_callback=None):
            calls.append((group['file'],list(group['problems']))); (Path(root)/group['file']).write_text('export const x=()=>({id:"real"});\n'); return True,[]
        v49._patch_only_repair=fake
        changed=j._v429_repair_audit_round('finish',{'files':[]},r,{'issues':[{'file':'src/hooks/usePeople.ts','kind':'functional_mock','problem':'replace production simulation'}]},None,1)
    finally:
        v49._patch_only_repair=old
    check('functional debt dispatches directly to repair',changed is True and calls and calls[0][0]=='src/hooks/usePeople.ts',calls)

print(f'{passed}/{passed+failed} PASS')
raise SystemExit(1 if failed else 0)
