import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as M
import jarvis_v42_runtime as R

checks=[]
def check(name,cond,detail=''):
    checks.append((name,bool(cond),str(detail or '')))
    print(('PASS: ' if cond else 'FAIL: ')+name+((' -- '+str(detail)) if detail else ''))

req='''Build me a complete Windows desktop GearTrack app using React TypeScript Vite Tauri Rust and SQLite. Add edit delete tools, organize categories, search and filter, check tools in and out, keep checkout history, show a dashboard, import and export CSV files, add real tests, and keep fixing anything that fails until it builds and tests pass.'''
manifest={
 'project_name':'geartrack','toolchain_adapter':'tauri','platform':'windows','language':'multi','framework':'Tauri',
 'components':[
   {'id':'ui','root':'.','toolchain_adapter':'react','purpose':'frontend ui','files':[]},
   {'id':'tauri-core','root':'src-tauri','toolchain_adapter':'tauri','purpose':'Rust backend core','files':[]},
 ],
 'files':[
   {'path':'package.json','purpose':'frontend manifest','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'tsconfig.json','purpose':'TypeScript config','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src/main.tsx','purpose':'React boot','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src/App.tsx','purpose':'Dashboard search filter category management checkout UI','phase':'ui','depends_on':[],'exports':[]},
   {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src-tauri/src/lib.rs','purpose':'Tauri integration','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src-tauri/src/db.rs','purpose':'SQLite database persistence repository and checkout history storage','phase':'data','depends_on':[],'exports':[]},
   {'path':'src-tauri/src/services/tool_service.rs','purpose':'tool add edit delete checkout category search service','phase':'service','depends_on':[],'exports':[]},
 ]
}
base_gaps=M._v422_plan_gaps(req,manifest)
check('replay starts with V42.2 CSV gap','csv_import_export' in base_gaps,base_gaps)
check('replay starts with V42.2 tests gap','tests' in base_gaps,base_gaps)
aug,added,remaining=M._v423_autoaugment_manifest(req,manifest)
check('V42.3 auto-augments rather than aborts',bool(added),added)
check('CSV gap cleared by real planned owner','csv_import_export' not in remaining,remaining)
check('tests gap cleared by real planned test files','tests' not in remaining,remaining)
check('Tauri CSV owner is Rust',any(p.startswith('src-tauri/') and p.endswith('.rs') and 'csv' in p for p in added),added)
check('mixed repo gets executable test ownership',any('test' in Path(p).name.lower() or '/tests/' in '/'+p for p in added),added)
check('synthetic owners are marked as requirement debt',all(any(x.get('path')==p and x.get('v423_requirement_debt') for x in aug['files']) for p in added))

# Verify the top-level executor hands an augmented plan to the previous chain.
with tempfile.TemporaryDirectory() as td:
    captured={}; old=M._v423_prev_execute_manifest
    def stub(user_request,man,work,max_files,progress_callback=None,raw_plan=''):
        captured['manifest']=man
        # Materialize one source so the return resembles a successful executor.
        p=Path(work)/'src/main.tsx';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('export const ready = true;')
        return True,man,[('src/main.tsx',p.read_text())],raw_plan
    M._v423_prev_execute_manifest=stub
    try: result=M._v362_execute_manifest(req,manifest,td,160,None,'plan')
    finally:M._v423_prev_execute_manifest=old
    check('executor no longer rejects coverage before source',result[0] is True)
    passed=M._v422_plan_gaps(req,captured.get('manifest') or {})
    check('executor passes corrected plan downstream','csv_import_export' not in passed and 'tests' not in passed,passed)
    debt=Path(td)/M.V423_DEBT_FILE
    check('requirement debt ledger is persisted',debt.exists())

# Verify build-debt continuation can materialize future files and then return to
# the outer strict acceptance pipeline rather than publishing immediately.
with tempfile.TemporaryDirectory() as td:
    m={'project_name':'x','toolchain_adapter':'python','components':[{'id':'root','root':'.','toolchain_adapter':'python','purpose':'core'}],
       'files':[{'path':'main.py','purpose':'entry','phase':'foundation','depends_on':[],'exports':[]},{'path':'feature.py','purpose':'future feature','phase':'service','depends_on':[],'exports':[]}]}
    oldgen=M._generate_planned_file
    def fakegen(user_request,man,work,item,progress_callback=None):
        rel=item['path'];p=Path(work)/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('VALUE = 1\n',encoding='utf-8');M._v413_mark_accepted(work,rel,'v423-test');return True,rel
    M._generate_planned_file=fakegen
    try: ok,mm,visible,raw=M._v423_continue_with_build_debt('build it',m,td,'V39 current vertical slice failed real build/test',None)
    finally:M._generate_planned_file=oldgen
    check('recoverable intermediate build failure continues',ok)
    check('future planned file materialized after debt',Path(td,'feature.py').exists())
    payload=json.loads((Path(td)/M.V423_DEBT_FILE).read_text())
    check('build debt retained for global convergence',payload.get('status')=='ready_for_global_convergence' and payload.get('build_debt'),payload.get('status'))

# Debt owner is a hard final acceptance obligation until it becomes real.
with tempfile.TemporaryDirectory() as td:
    debt_manifest={'files':[{'path':'src/csv_import_export.py','purpose':'CSV implementation','v423_requirement_debt':'csv_import_export'}]}
    issues=M._deterministic_acceptance_issues(td,debt_manifest)
    check('unmaterialized requirement debt blocks final acceptance',any('requirement debt unresolved' in str(x.get('problem','')).lower() for x in issues),issues)

reg=json.loads((ROOT/'project_builder_skills'/'toolchains.json').read_text())
skills=list((ROOT/'project_builder_skills').glob('*.md'))
check('expanded adapter registry',len(reg.get('adapters') or {})>=72,len(reg.get('adapters') or {}))
check('expanded skill library',len(skills)>=76,len(skills))
for adapter in ('deno','bun','powershell','shell_bash','docker_compose','kubernetes_helm','clojure','fsharp','crystal','racket','fortran_cmake','cuda_cmake','wasm_rust'):
    check('adapter:'+adapter,adapter in reg.get('adapters',{}))
check('Crystal routes to registered adapter',M._v34_infer_toolchain('Build this in Crystal',{})=='crystal',M._v34_infer_toolchain('Build this in Crystal',{}))
check('Deno routes to registered adapter',M._v34_infer_toolchain('Build a Deno TypeScript API',{})=='deno',M._v34_infer_toolchain('Build a Deno TypeScript API',{}))
check('F# routes to registered adapter',M._v34_infer_toolchain('Build a desktop utility in F#',{})=='fsharp',M._v34_infer_toolchain('Build a desktop utility in F#',{}))
check('capability scanner knows extended tools',all(x in R._TOOL_ALIASES for x in ('deno','pwsh','kubectl','helm','uv','poetry','clojure','crystal','racket','nvcc','gfortran','wasm-pack')))
check('planning context gets more headroom',M.QWEN35_WORKING_CONTEXT_PLAN>=49152,M.QWEN35_WORKING_CONTEXT_PLAN)
check('repair context gets more headroom',M.QWEN35_WORKING_CONTEXT_REPAIR>=49152,M.QWEN35_WORKING_CONTEXT_REPAIR)
check('audit context gets more headroom',M.QWEN35_WORKING_CONTEXT_AUDIT>=49152,M.QWEN35_WORKING_CONTEXT_AUDIT)
identity=M._v36_release_identity()
check('release identity V42.3',str(identity.get('version') or '').startswith('V42.') and identity.get('progressive_build_debt') is True,identity.get('version'))
check('identity reports live registry counts',identity.get('registered_toolchain_adapters')>=72 and identity.get('skill_cards')>=76,(identity.get('registered_toolchain_adapters'),identity.get('skill_cards')))
setup=(ROOT/'V42_SETUP_DEV_TOOLS.ps1').read_text(encoding='utf-8')
check('extended optional tool installer exists','InstallExtended' in setup and 'DenoLand.Deno' in setup and 'Microsoft.PowerShell' in setup)

failed=[n for n,ok,_ in checks if not ok]
print(f'RESULT: {len(checks)-len(failed)}/{len(checks)} PASS')
if failed:
    print('FAILED:',*failed,sep='\n- ')
    raise SystemExit(1)
