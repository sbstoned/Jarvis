from pathlib import Path
import tempfile, json
import local_qwen_project as M

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+str(detail)) if detail else ''))

# 1-6: exact Cargo failure from project_20260830_171300.
cargo='''[package]\nname = "geartrack"\nversion = "0.1.0"\nedition = "2021"\n\n[build-dependencies]\ntauri-build = { version = "2", features = [] }\nsqlx-build = { version = "0.7", features = ["sqlite"] }\n\n[dependencies]\ntauri = { version = "2.0", features = ["shell-open", "custom-protocol"] }\ntauri-plugin-shell = "2.0"\nsqlx = { version = "0.7", features = ["runtime-tokio-native-tls", "sqlite", "uuid", "chrono"] }\n'''
fixed,changed=M._v421_static_tauri_cargo_text(cargo)
check('Tauri-2 static hardener changes broken Cargo manifest',changed)
check('removed obsolete shell-open core feature','shell-open' not in fixed,fixed)
check('preserved valid custom-protocol feature','custom-protocol' in fixed,fixed)
check('preserved Tauri-2 shell plugin dependency','tauri-plugin-shell' in fixed,fixed)
check('removed nonexistent sqlx-build pseudo crate','sqlx-build' not in fixed,fixed)
check('preserved real sqlx dependency','sqlx = ' in fixed,fixed)

failure='''error: failed to select a version for `tauri`.\npackage `geartrack` depends on `tauri` with feature `shell-open` but `tauri` does not have that feature.\nfailed to select a version for `tauri` which could resolve this conflict'''
check('Cargo invalid-feature signature is semantic',M._validation_failure_signature(failure)=='cargo-invalid-feature:tauri:shell-open',M._validation_failure_signature(failure))

# Generic exact-feature diagnostic repair (not a hard-coded shell-open-only rule).
with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'src-tauri').mkdir()
    cp=root/'src-tauri'/'Cargo.toml'
    cp.write_text('[package]\nname="x"\nversion="0.1.0"\n\n[dependencies]\ntauri = { version = "2", features = ["made-up-old-feature", "custom-protocol"] }\n',encoding='utf-8')
    f='package `x` depends on `tauri` with feature `made-up-old-feature` but `tauri` does not have that feature.'
    ok=M._v421_repair_cargo_resolution_failure(root,f)
    now=cp.read_text(encoding='utf-8')
    check('exact Cargo feature diagnostic repairs manifest without Qwen',ok,now)
    check('diagnostic repair removes exact invalid feature','made-up-old-feature' not in now,now)
    check('diagnostic repair keeps unrelated valid feature','custom-protocol' in now,now)

# Live architecture pattern: wrong-language files under Rust source root.
manifest={
 'components':[{'id':'ui','root':'.','toolchain_adapter':'react','depends_on':['tauri-core']},{'id':'tauri-core','root':'src-tauri','toolchain_adapter':'rust','depends_on':[]}],
 'canonical_domain_contracts':{
   'entities':[
    {'name':'Tool','fields':[{'name':'id','required':True},{'name':'name','required':True}]},
    {'name':'Category','fields':[{'name':'id','required':True},{'name':'name','required':True}]},
    {'name':'CheckoutEvent','fields':[{'name':'id','required':True},{'name':'tool_id','required':True}]},
   ],
   'enums':[{'name':'ToolCondition','values':['Good','Fair','Needs Maintenance','Broken']}]
 },
 'files':[
  {'path':'package.json','purpose':'Vite manifest','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'src/main.tsx','purpose':'React boot','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'src-tauri/Cargo.toml','purpose':'Rust/Tauri manifest','phase':'foundation','depends_on':[],'exports':[],'contracts':['ToolCondition']},
  {'path':'src-tauri/src/lib.rs','purpose':'Tauri lib','phase':'foundation','depends_on':['src-tauri/Cargo.toml'],'exports':[]},
  {'path':'src-tauri/src/main.rs','purpose':'Tauri main','phase':'foundation','depends_on':['src-tauri/Cargo.toml'],'exports':[]},
  {'path':'src-tauri/src/models/Tool.ts','purpose':'TypeScript interface for Tool entity','phase':'foundation','depends_on':[],'exports':['ITool'],'contracts':['Tool']},
  {'path':'src-tauri/src/models/Category.ts','purpose':'TypeScript interface for Category entity','phase':'foundation','depends_on':[],'exports':['ICategory'],'contracts':['Category']},
  {'path':'src-tauri/src/models/CheckoutEvent.ts','purpose':'TypeScript interface for CheckoutEvent entity','phase':'foundation','depends_on':[],'exports':['ICheckoutEvent'],'contracts':['CheckoutEvent']},
  {'path':'src-tauri/src/db/migrations/00001_create_tools.sql','purpose':'SQL migration','phase':'foundation','depends_on':[],'exports':[]},
  {'path':'src-tauri/src/db/mod.rs','purpose':'Database schema and repositories for Tool, Category, CheckoutEvent','phase':'foundation','depends_on':[],'exports':['ToolRepository'],'contracts':['Tool','Category','CheckoutEvent']},
  {'path':'src-tauri/src/commands/mod.rs','purpose':'Commands for CheckoutEvent and Tool','phase':'data','depends_on':[],'exports':[],'contracts':['CheckoutEvent']},
 ]
}
clean=M._v421_sanitize_tauri_manifest(manifest)
paths={x['path'] for x in clean['files']}
check('backend Tool TypeScript path normalized to Rust','src-tauri/src/models/tool.rs' in paths,sorted(paths))
check('backend Category TypeScript path normalized to Rust','src-tauri/src/models/category.rs' in paths,sorted(paths))
check('backend CheckoutEvent TypeScript path normalized to Rust','src-tauri/src/models/checkout_event.rs' in paths,sorted(paths))
check('missing canonical ToolCondition Rust provider added','src-tauri/src/models/tool_condition.rs' in paths,sorted(paths))
check('SQLx migration moved to crate migration root','src-tauri/migrations/00001_create_tools.sql' in paths,sorted(paths))
check('wrong-language backend source removed',not any(p.startswith('src-tauri/src/') and Path(p).suffix.lower() in {'.ts','.tsx','.js','.jsx'} for p in paths),sorted(paths))

owners=M._v40_domain_owner_map(clean)
scope=M._v38_component_scope(clean,'src-tauri/src/models/tool.rs')
expected={
 'Tool':'src-tauri/src/models/tool.rs',
 'Category':'src-tauri/src/models/category.rs',
 'CheckoutEvent':'src-tauri/src/models/checkout_event.rs',
 'ToolCondition':'src-tauri/src/models/tool_condition.rs',
}
for sym,path in expected.items():
    check(f'exact Rust owner stable for {sym}',owners.get((scope,sym))==path,owners)

# The repaired plan keeps Foundation small rather than promoting backend domain models.
ms=M._v39_build_milestones(clean,'')
foundation=set(next(x for x in ms if x['id']=='foundation')['files'])
check('normalized Rust models stay out of Foundation',not any('/models/' in p for p in foundation),foundation)
check('Tauri boot roots remain in Foundation',{'src-tauri/Cargo.toml','src-tauri/src/lib.rs','src-tauri/src/main.rs'}.issubset(foundation),foundation)

# Safety net rejects a future planner/wrapper regression.
wrong='export interface Tool { id: string }'
err=M._candidate_transaction_error(Path('.'),clean,'src-tauri/src/models/tool.ts',wrong,user_request='',validation_failure='',target_problems=[])
check('Rust-root language gate rejects TypeScript backend source','root-language gate' in str(err),err)

# Existing explicit generic enum provider should not be replaced by an invented model file.
explicit={
 'components':[{'id':'tauri-core','root':'src-tauri','toolchain_adapter':'rust','depends_on':[]}],
 'canonical_domain_contracts':{'entities':[],'enums':[{'name':'ConditionType','values':['Good','Bad']}]},
 'files':[{'path':'src-tauri/Cargo.toml','purpose':'manifest','phase':'foundation','exports':[]},
          {'path':'src-tauri/src/domain/enums.rs','purpose':'Canonical Rust enum definitions for ConditionType','phase':'data','exports':[],'contracts':['pub enum ConditionType { Good, Bad }']}]
}
exp_clean=M._v421_sanitize_tauri_manifest(explicit)
exp_paths={x['path'] for x in exp_clean['files']}
check('explicit enum provider is preserved without duplicate invented owner','src-tauri/src/models/condition_type.rs' not in exp_paths,exp_paths)
exp_owners=M._v40_domain_owner_map(exp_clean); exp_scope=M._v38_component_scope(exp_clean,'src-tauri/src/domain/enums.rs')
check('generic explicit enum provider remains canonical',exp_owners.get((exp_scope,'ConditionType'))=='src-tauri/src/domain/enums.rs',exp_owners)

identity=M._v36_release_identity()
check('release identity V42.1',str(identity.get('version') or '').startswith('V42.') and identity.get('cargo_diagnostic_repair') is True,identity)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
