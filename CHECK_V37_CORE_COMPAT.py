import importlib.util, json, os, tempfile, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('jarvis_v36',HERE/'local_qwen_project.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
checks=[]
def check(name,condition,detail=''):
    checks.append((name,bool(condition),str(detail)))

check('V36 software factory enabled',getattr(M,'V36_SOFTWARE_FACTORY',False),getattr(M,'V36_VERSION','missing'))
check('V37 identity is current',getattr(M,'V36_VERSION','')=='37.0.0',getattr(M,'V36_VERSION',''))
ident=M._v36_release_identity()
for key in ('requirements_compiler','repo_map','machine_contracts','patch_repairs','green_checkpoints'):
    check(f'identity exposes {key}',bool(ident.get(key)),ident)

# Keep major V35.1 regressions protected.
for prompt,expected in [
    ('Build a Tauri desktop app','tauri'),('Build a SvelteKit website','sveltekit'),
    ('Build a Godot GDScript game','godot'),('Build a React Native app','react_native'),
    ('Build an Unreal Engine 5 game','unreal')]:
    actual=M._v34_infer_toolchain(prompt);check(f'toolchain {expected}',actual==expected,actual)
check('generic desktop is not Python locked',M._v35_explicit_toolchain('Build a desktop calculator')=='generic')
check('fake test command rejected',M._v35_is_noop_command('echo No tests configured'))

source='def ok():\n    return 1\n===== END FILE StockPilot/app/database.py =====\n'
clean=M._extract_single_file_response(source,'StockPilot/app/database.py')
try: compile(clean,'x','exec'); transport='END FILE' not in clean
except Exception: transport=False
check('StockPilot transport contamination salvaged',transport,clean[-100:])

with tempfile.TemporaryDirectory(prefix='v36_graph_') as td:
    r=Path(td);(r/'app').mkdir()
    (r/'app/models.py').write_text('class Item:\n    def __init__(self, sku): self.sku=sku\n',encoding='utf-8')
    (r/'app/db.py').write_text('from app.models import Item\nclass DB:\n    def insert(self, item: Item): return item\n',encoding='utf-8')
    (r/'app/service.py').write_text('from app.db import DB\nclass Service:\n    def __init__(self, db: DB): self.db=db\n    def add(self, item): return self.db.insert(item)\n',encoding='utf-8')
    (r/'unrelated.py').write_text('def lonely(): return 1\n',encoding='utf-8')
    manifest={'files':[
      {'path':'app/models.py','purpose':'models','exports':['Item'],'depends_on':[],'contracts':[]},
      {'path':'app/db.py','purpose':'database','exports':['DB'],'depends_on':['app/models.py'],'contracts':['DB.insert accepts Item']},
      {'path':'app/service.py','purpose':'service','exports':['Service'],'depends_on':['app/db.py'],'contracts':[]},
      {'path':'unrelated.py','purpose':'unrelated helper','exports':['lonely'],'depends_on':[],'contracts':[]},]}
    g=M._v36_build_repo_graph(r,manifest)
    edges={e['to'] for e in g['files']['app/service.py']['edges']}
    check('repo graph links service to DB','app/db.py' in edges,edges)
    check('repo graph persists to disk',(r/M.V36_REPO_GRAPH_FILE).exists())
    ranks=[float(v.get('rank',0)) for v in g['files'].values()]
    check('repo graph PageRank is normalized',0.98<=sum(ranks)<=1.02,sum(ranks))
    service_syms=[x['name'] for x in g['files']['app/service.py']['symbols']]
    check('repo map does not duplicate class methods as module functions',service_syms==['Service'],service_syms)
    reg=M._v36_build_contract_registry(r,manifest)
    sig=[x for x in reg['contracts'] if x.get('symbol')=='DB.insert']
    check('machine contract registry records real method signature',any(x.get('signature')=='insert(self, item)' for x in sig),sig)
    ctx=M._project_context_for_file(r,manifest,'app/service.py')
    check('dynamic context contains ranked repo map','V36 REPOSITORY MAP' in ctx)
    check('dynamic context contains machine contract registry','V36 MACHINE-OWNED CONTRACT REGISTRY' in ctx)
    check('dynamic context includes direct DB dependency','app/db.py' in ctx)

# Class-level constants must remain valid members.
with tempfile.TemporaryDirectory(prefix='v36_attrs_') as td:
    r=Path(td);(r/'app').mkdir();(r/'app/__init__.py').write_text('')
    (r/'app/ui.py').write_text('class InventoryView:\n    COLUMNS=("sku","name")\n')
    (r/'app/c.py').write_text('from app.ui import InventoryView\ndef use(): return InventoryView.COLUMNS\n')
    manifest={'files':[{'path':'app/ui.py','purpose':'ui','exports':['InventoryView'],'depends_on':[],'contracts':[]},{'path':'app/c.py','purpose':'consumer','exports':['use'],'depends_on':['app/ui.py'],'contracts':[]}]}
    req=M._python_method_contract_requirements(r,manifest)
    check('InventoryView.COLUMNS false positive stays fixed',not any(k[1]=='InventoryView' and k[2]=='COLUMNS' for k in req),req)

# StockPilot-shaped signature mismatch stays detectable.
with tempfile.TemporaryDirectory(prefix='v36_sig_') as td:
    r=Path(td);(r/'app').mkdir();(r/'app/__init__.py').write_text('')
    (r/'app/database.py').write_text('class DatabaseManager:\n    def insert_item(self, sku, name, qty): return 1\n')
    (r/'app/service.py').write_text('from app.database import DatabaseManager\nclass InventoryService:\n    def __init__(self, db: DatabaseManager): self.db=db\n    def add(self,item): return self.db.insert_item(item)\n')
    mf={'files':[{'path':'app/database.py','purpose':'db','exports':['DatabaseManager'],'depends_on':[],'contracts':[]},{'path':'app/service.py','purpose':'svc','exports':['InventoryService'],'depends_on':['app/database.py'],'contracts':[]}]}
    issues=M._python_local_call_signature_issues(r,mf)
    check('caller/provider arity drift detected',any('missing required argument' in str(x.get('problem','')).lower() for x in issues),issues)

# V36 bound-call checker handles nested project roots that older module mapping could miss.
with tempfile.TemporaryDirectory(prefix='v36_nested_contract_') as td:
    r=Path(td);(r/'StockPilot/app').mkdir(parents=True);(r/'StockPilot/app/__init__.py').write_text('')
    (r/'StockPilot/app/database.py').write_text('class DatabaseManager:\n    def insert_item(self, sku, name, qty): return 1\n')
    (r/'StockPilot/app/service.py').write_text('from app.database import DatabaseManager\nclass InventoryService:\n    def __init__(self, db_manager: DatabaseManager): self.db=db_manager\n    def create(self,item): return self.db.insert_item(item)\n')
    mf={'files':[{'path':'StockPilot/app/database.py','purpose':'db','exports':['DatabaseManager'],'depends_on':[],'contracts':[]},{'path':'StockPilot/app/service.py','purpose':'svc','exports':['InventoryService'],'depends_on':['StockPilot/app/database.py'],'contracts':[]}]}
    bound=M._v36_bound_member_call_issues(r,mf)
    check('V36 machine contract catches nested-root bound call mismatch',any('DatabaseManager.insert_item' in x.get('problem','') and 'with 1 positional' in x.get('problem','') for x in bound),bound)

# Patch primitives and precommit gates.
cur='def total(a, b):\n    return a - b\n'
cand,err=M._v36_apply_search_replace(cur,[{'search':'return a - b','replace':'return a + b'}])
check('exact search/replace patch applies',not err and 'a + b' in cand,err)
_,err2=M._v36_apply_search_replace('x=1\nx=1\n',[{'search':'x=1','replace':'x=2'}])
check('ambiguous patch search is rejected','exactly once' in err2,err2)
check('invalid Python rejected before commit',bool(M._v36_precommit_candidate_error(Path('.'),'x.py','def broken(:\n')))
check('invalid JSON rejected before commit',bool(M._v36_precommit_candidate_error(Path('.'),'x.json','{"a":')))
check('valid Python passes precommit',not M._v36_precommit_candidate_error(Path('.'),'x.py','x=1\n'))

# Failure localization.
with tempfile.TemporaryDirectory(prefix='v36_fail_') as td:
    r=Path(td)
    failure='Traceback (most recent call last):\n  File "'+str(r/'app/service.py')+'", line 42, in add\nTypeError: DatabaseManager.insert_item() missing 2 required positional arguments\n'
    loc=M._v36_localize_failure(r,failure)
    check('failure localizer extracts project file',any(str(x.get('file')).endswith('app/service.py') and x.get('line')==42 for x in loc['locations']),loc)
    check('failure localizer fingerprints exception',bool(loc.get('signature')),loc)

# Stack skill loading.
for adapter,needle in [('python_desktop','python'),('tauri','tauri'),('unreal','unreal'),('flutter','flutter')]:
    text=M._v36_stack_skill_context({'toolchain_adapter':adapter})
    check(f'{adapter} skill loads',needle.upper() in text.upper(),text[:150])

# Architecture collision detection stays active.
collision={'files':[{'path':'inventory_service.py','purpose':'Inventory service layer','exports':['InventoryService']},{'path':'app/service.py','purpose':'Inventory service layer','exports':['InventoryService']}]}
check('duplicate authoritative provider caught',bool(M._v351_architecture_collision_issues(collision)))

# JS test runner behavior.
for label,data,runner,token in [
    ('vitest',{'scripts':{'test':'vitest'},'devDependencies':{'vitest':'1'}},'vitest','run'),
    ('jest',{'scripts':{'test':'jest'},'devDependencies':{'jest':'29'}},'jest','--ci'),
    ('react',{'scripts':{'test':'react-scripts test'},'dependencies':{'react-scripts':'5'}},'react-scripts','--watchAll=false'),
    ('playwright',{'scripts':{'test':'playwright test'},'devDependencies':{'@playwright/test':'1'}},'playwright','--reporter=line')]:
    cmd,env,got=M._v351_node_test_strategy(HERE,data)
    check(f'{label} runner detected',got==runner,(got,cmd));check(f'{label} noninteractive',token in cmd and env.get('CI')=='true',cmd)

# Mixed toolchains remain discoverable.
with tempfile.TemporaryDirectory(prefix='v36_mixed_') as td:
    r=Path(td);(r/'package.json').write_text(json.dumps({'name':'x','version':'1','scripts':{'build':'vite build'},'dependencies':{'vite':'5'}}))
    (r/'src-tauri/src').mkdir(parents=True);(r/'src-tauri/Cargo.toml').write_text('[package]\nname="x"\nversion="0.1.0"\nedition="2021"\n');(r/'src-tauri/src/main.rs').write_text('fn main(){}\n')
    comps=M._v35_discover_components(r,{'toolchain_adapter':'tauri','components':[]})
    kinds={(x.get('root'),x.get('toolchain_adapter')) for x in comps}
    check('mixed project discovers Node',any(root=='.' and kind in {'node','vite','react'} for root,kind in kinds),kinds)
    check('mixed project discovers Rust',('src-tauri','rust') in kinds,kinds)

# V36 status reports current engine.
with tempfile.TemporaryDirectory(prefix='v36_status_') as td:
    r=Path(td);(r/'main.py').write_text('print("ok")\n')
    mf={'files':[{'path':'main.py'}],'components':[{'id':'app','root':'.','purpose':'app','toolchain_adapter':'python','depends_on':[]}]}
    old=M.qwen_runtime_context_tokens;M.qwen_runtime_context_tokens=lambda:262144
    try:M._v33_write_build_status(r,mf,'implementing',implemented=1)
    finally:M.qwen_runtime_context_tokens=old
    data=json.loads((r/M.V33_BUILD_STATUS_FILE).read_text())
    check('status reports V37',data.get('version')=='V37.0.0',data)
    check('status reports software factory engine',data.get('engine')=='SMALL_MODEL_SOFTWARE_FACTORY',data)
    check('status reports repo map',data.get('repo_map')=='pagerank-symbol-graph',data)

# Internal graph/contract files must not leak into generated user project ZIP.
with tempfile.TemporaryDirectory(prefix='v36_package_') as td:
    root=Path(td);(root/'main.py').write_text('print("ok")\n');(root/M.V36_REPO_GRAPH_FILE).write_text('{}');(root/M.V36_CONTRACT_REGISTRY_FILE).write_text('{}')
    oldgen=M.GENERATED_DIR
    try:
        M.GENERATED_DIR=root/'out';M.GENERATED_DIR.mkdir()
        out,count=M._package_workspace_zip(root,'demo','test')
        with zipfile.ZipFile(out) as z:names=set(z.namelist())
    finally:M.GENERATED_DIR=oldgen
    check('user ZIP keeps source','main.py' in names,names)
    check('user ZIP excludes internal repo graph',M.V36_REPO_GRAPH_FILE not in names,names)
    check('user ZIP excludes internal contract registry',M.V36_CONTRACT_REGISTRY_FILE not in names,names)

# File checkpoint primitive.
with tempfile.TemporaryDirectory(prefix='v36_checkpoint_') as td:
    r=Path(td);M._v36_checkpoint_file(r,'app/x.py','x=1\n','test')
    saved=list((r/'.jarvis_backups/v36_checkpoints/files').glob('*'))
    check('per-file rollback checkpoint is created',len(saved)==1,saved)

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL')+' - '+name+(f' ({detail})' if detail and not ok else ''))
print(f'\nV37 core compatibility: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
