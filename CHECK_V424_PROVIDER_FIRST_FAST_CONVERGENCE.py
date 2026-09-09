import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as M

checks=[]
def check(name, cond, detail=''):
    checks.append((name,bool(cond),str(detail or '')))
    print(('PASS: ' if cond else 'FAIL: ')+name+((' -- '+str(detail)) if detail else ''))

manifest={
 'project_name':'geartrack','toolchain_adapter':'tauri','platform':'windows','language':'multi','framework':'Tauri',
 'components':[
  {'id':'ui','root':'.','toolchain_adapter':'react','purpose':'frontend ui','files':[]},
  {'id':'tauri-core','root':'src-tauri','toolchain_adapter':'tauri','purpose':'Rust backend','files':[]},
 ],
 'canonical_domain_contracts':{
  'version':'38.1.0',
  'entities':[
   {'name':'Tool','fields':[{'name':'id'},{'name':'name'},{'name':'category_id'},{'name':'condition'}]},
   {'name':'Category','fields':[{'name':'id'},{'name':'name'}]},
   {'name':'User','fields':[{'name':'id'},{'name':'name'}]},
   {'name':'CheckoutLog','fields':[{'name':'id'},{'name':'tool_id'},{'name':'user_id'},{'name':'checkout_date'}]},
  ],
  'enums':[{'name':'ConditionType','values':['New','Good','Fair','Poor']}],
  'shared_rules':[]
 },
 'shared_contracts':['DOMAIN_ENTITY Tool (id: String, name: String, category_id: String, condition: ConditionType)','DOMAIN_ENTITY Category (id: String, name: String)','DOMAIN_ENTITY User (id: String, name: String)','DOMAIN_ENTITY CheckoutLog (id: String, tool_id: String, user_id: String, checkout_date: DateTime)','DOMAIN_ENUM ConditionType (New, Good, Fair, Poor)'],
 'files':[
  {'path':'package.json','purpose':'frontend manifest','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'tsconfig.json','purpose':'TypeScript config','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'src/types.ts','purpose':'Canonical domain contracts Tool Category User CheckoutLog ConditionType','phase':'domain','depends_on':[],
   'exports':['Tool','Category','User','CheckoutLog','ConditionType'],
   'contracts':['Tool entity fields: id, name, category_id, condition','Category entity fields: id, name','User entity fields: id, name','CheckoutLog entity fields: id, tool_id, user_id, checkout_date','ConditionType enum values: New, Good, Fair, Poor']},
  {'path':'src/store/tool-store.ts','purpose':'Tool CRUD store consumer','phase':'feature','depends_on':['src/types.ts'],'exports':['useToolStore']},
  {'path':'src/store/category-store.ts','purpose':'Category CRUD store consumer','phase':'feature','depends_on':['src/types.ts'],'exports':['useCategoryStore']},
  {'path':'src/store/user-store.ts','purpose':'User CRUD store consumer','phase':'feature','depends_on':['src/types.ts'],'exports':['useUserStore']},
  {'path':'src/store/checkout-store.ts','purpose':'CheckoutLog store consumer','phase':'feature','depends_on':['src/types.ts'],'exports':['useCheckoutStore']},
  {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'src-tauri/src/contracts/mod.rs','purpose':'Canonical Rust domain models Tool Category User CheckoutLog ConditionType','phase':'domain','depends_on':[],
   'exports':['Tool','Category','User','CheckoutLog','ConditionType'],
   'contracts':['Tool entity fields: id, name, category_id, condition','Category entity fields: id, name','User entity fields: id, name','CheckoutLog entity fields: id, tool_id, user_id, checkout_date','ConditionType enum values: New, Good, Fair, Poor']},
 ]
}

owners=M._v40_domain_owner_payload(manifest).get('owners') or []
uiowners={x['symbol']:x['provider'] for x in owners if x.get('scope')=='ui'}
check('UI Tool canonical owner is src/types.ts',uiowners.get('Tool')=='src/types.ts',uiowners)
check('UI Category canonical owner is src/types.ts',uiowners.get('Category')=='src/types.ts',uiowners)
check('UI User canonical owner is src/types.ts',uiowners.get('User')=='src/types.ts',uiowners)
check('UI CheckoutLog canonical owner is src/types.ts',uiowners.get('CheckoutLog')=='src/types.ts',uiowners)

# Exact overnight failure shape: consumer errors should identify shared provider.
problems=["Type 'Tool[]' is not assignable to type 'Record<string, Tool>'.", "Property 'id' does not exist on type 'Omit<Tool, id>'."]
providers=M._v424_provider_paths_for_consumer(manifest,'src/store/tool-store.ts',problems)
check('consumer root cause includes canonical provider','src/types.ts' in providers,providers)

# Planned-but-missing provider must be injected even though it cannot appear in live repo graph.
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'src/store/tool-store.ts';p.parent.mkdir(parents=True);p.write_text('export const x = 1\n')
    selected,root,comp=M._v381_select_subsystem_files(td,manifest,'src/store/tool-store.ts',[])
    check('subsystem includes planned missing provider','src/types.ts' in selected,selected)
    check('provider ordered before consumer',('src/types.ts' in selected and 'src/store/tool-store.ts' in selected and selected.index('src/types.ts') < selected.index('src/store/tool-store.ts')),selected)

# Provider prepass should regenerate an unaccepted canonical provider before consumers.
with tempfile.TemporaryDirectory() as td:
    old=M._generate_planned_file
    calls=[]
    def fakegen(user_request,man,work,item,progress_callback=None):
        rel=item['path'];calls.append(rel);p=Path(work)/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if rel=='src/types.ts':
            p.write_text("export interface Tool { id:string; name:string; category_id:string; condition:ConditionType }\nexport interface Category { id:string; name:string }\nexport interface User { id:string; name:string }\nexport interface CheckoutLog { id:string; tool_id:string; user_id:string; checkout_date:string }\nexport type ConditionType='New'|'Good'|'Fair'|'Poor';\n")
        else:p.write_text('export const ok=true;\n')
        M._v413_mark_accepted(work,rel,'v424-test')
        return True,rel
    M._generate_planned_file=fakegen
    try:
        changed=M._v424_provider_health_prepass('build geartrack',manifest,td,None,'src/store/tool-store.ts',problems)
    finally:M._generate_planned_file=old
    check('provider prepass changes missing canonical provider',changed,calls)
    check('provider generated before consumer repair',calls and calls[0]=='src/types.ts',calls)
    check('provider accepted after prepass',M._v413_is_accepted(td,'src/types.ts'))

# TS emitted .js import specifier must resolve to planned .ts provider.
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'src/store/tool-store.ts';p.parent.mkdir(parents=True);p.write_text("import type { Tool } from '../types.js';\nexport const x=1;\n")
    err=M._v362_candidate_internal_import_error(td,manifest,'src/store/tool-store.ts',p.read_text())
    check('TS .js specifier maps to planned .ts source',err=='',err)
    check('alias resolver returns src/types.ts',M._v424_planned_source_alias(manifest,'src/types.js')=='src/types.ts',M._v424_planned_source_alias(manifest,'src/types.js'))

# Genuine unplanned import remains blocked.
with tempfile.TemporaryDirectory() as td:
    err=M._v362_candidate_internal_import_error(td,manifest,'src/store/tool-store.ts',"import { X } from '../never-planned.js';\n")
    check('genuine unplanned internal provider still blocked',bool(err) and 'provider' in err.lower(),err)

# Fast convergence defaults.
check('leaf patch candidates reduced to two',M.V37_PATCH_CANDIDATES<=2,M.V37_PATCH_CANDIDATES)
check('V36 patch candidates reduced to two',M.V36_REPAIR_CANDIDATES<=2,M.V36_REPAIR_CANDIDATES)
check('runtime repair fanout bounded to three',M.PROJECT_RUNTIME_REPAIR_TARGETS<=3,M.PROJECT_RUNTIME_REPAIR_TARGETS)
check('per-file repair wall bounded',M.FILE_REPAIR_WALL_SECONDS<=480,M.FILE_REPAIR_WALL_SECONDS)
check('provider prepass bounded',M.V424_PROVIDER_PREPASS_MAX<=16,M.V424_PROVIDER_PREPASS_MAX)

# Prompt compaction only needs to prove it focuses an oversized repair prompt.
big=('HEAD instruction\n'*2000)+('middle evidence\n'*6000)+('TAIL source\n'*2000)
trim=M._v424_trim_repair_prompt(big,14000)
check('repair prompt compaction reduces oversized prompt',len(trim)<len(big),(len(big),len(trim)))
check('repair prompt compaction preserves head',trim.startswith('HEAD instruction'))
check('repair prompt compaction preserves tail',trim.rstrip().endswith('TAIL source'))

for skill in ('dependency-graph-repair.md','type-contracts.md','fast-convergence.md'):
    check('skill exists:'+skill,(ROOT/'project_builder_skills'/skill).exists())

identity=M._v36_release_identity()
check('release identity is V42.4',str(identity.get('version') or '').startswith('V42.'),identity.get('version'))
check('provider-first advertised',identity.get('provider_first_global_convergence') is True)
check('strict zero-debt gate preserved',identity.get('strict_zero_debt_publish_gate') is True)
check('registry breadth preserved',identity.get('registered_toolchain_adapters',0)>=72,identity.get('registered_toolchain_adapters'))
check('skill library expanded',identity.get('skill_cards',0)>=79,identity.get('skill_cards'))

readme=(ROOT/'V42_4_PROVIDER_FIRST_FAST_CONVERGENCE_README.txt').read_text(encoding='utf-8')
check('readme documents universal provider-first design','C/C++ headers' in readme and 'Rust model modules' in readme)
check('readme documents speed controls','JARVIS_V424_FAST_REPAIR' in readme)

failed=[n for n,ok,_ in checks if not ok]
print(f'RESULT: {len(checks)-len(failed)}/{len(checks)} PASS')
if failed:
    print('FAILED:',*failed,sep='\n- ')
    raise SystemExit(1)
