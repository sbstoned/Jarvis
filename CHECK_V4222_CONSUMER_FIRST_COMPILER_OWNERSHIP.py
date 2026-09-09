import json, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_qwen_project as M

passed=0;failed=0
def ck(name,cond,detail=''):
    global passed,failed
    if cond:
        passed+=1;print('PASS',name)
    else:
        failed+=1;print('FAIL',name,detail)

ident=M._v36_release_identity()
ck('release version',ident.get('version')=='V42.22.0',ident)
ck('consumer-first advertised',ident.get('fresh_compiler_location_is_primary_repair_owner') is True,ident)
ck('provider bias removed',ident.get('same_component_provider_bias_removed') is True,ident)
ck('fresh build after accepted TS repair advertised',ident.get('accepted_ts_repair_requires_fresh_build_before_next_edit') is True,ident)

manifest={
 '_original_user_request':'Finish the application completely.',
 'components':[{'id':'frontend','root':'.','toolchain_adapter':'react'}],
 'canonical_domain_contracts':{'entities':[{'name':'Category','fields':[{'name':'id','type':'string'},{'name':'name','type':'string'}]},{'name':'ToolCondition','fields':[]}]},
 'files':[
  {'path':'src/App.tsx','purpose':'React application root'},
  {'path':'src/types/category.ts','purpose':'Category TypeScript definition','exports':['Category'],'contracts':['canonical provider for Category','canonical provider for ToolCondition']},
  {'path':'src/components/InventoryView.tsx','purpose':'Inventory UI component','exports':['InventoryView']},
 ]
}

with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src/types').mkdir(parents=True);(w/'src/components').mkdir(parents=True)
    (w/'src/App.tsx').write_text("import { InventoryView } from './components/InventoryView';\nexport default function App(){ return <InventoryView />; }\n",encoding='utf-8')
    (w/'src/types/category.ts').write_text('export interface Category { id: string; name: string; }\n',encoding='utf-8')
    (w/'src/components/InventoryView.tsx').write_text("import type { Category } from '../types/category';\nexport interface InventoryViewProps { categories: Category[] }\nexport function InventoryView(_p:InventoryViewProps){return <div/>}\n",encoding='utf-8')
    for rel in ('src/App.tsx','src/types/category.ts','src/components/InventoryView.tsx'):
        M._v413_mark_accepted(w,rel,'test')
    ck('category recognized stable provider',M._v4222_provider_source_is_stable(w,manifest,'src/types/category.ts'))
    generic=["src/App.tsx(2,39): error TS2741: Property 'categories' is missing in type '{}' but required in type 'InventoryViewProps'."]
    paths=M._v424_provider_paths_for_consumer(manifest,'src/App.tsx',generic)
    ck('generic consumer prop error does not route to category provider','src/types/category.ts' not in paths,paths)
    explicit=["src/App.tsx(1,10): error TS2305: Module './types/category' has no exported member 'Category'."]
    paths2=M._v424_provider_paths_for_consumer(manifest,'src/App.tsx',explicit)
    ck('explicit missing export can route to provider','src/types/category.ts' in paths2,paths2)

    failure="""src/App.tsx(2,39): error TS2741: Property 'categories' is missing in type '{}' but required in type 'InventoryViewProps'.
src/components/InventoryView.tsx(8,12): error TS2345: Argument of type 'string' is not assignable to parameter of type 'Category[]'.
"""
    rows=M._v4222_parse_ts_diagnostics(w,failure)
    ck('parses tsc diagnostics',len(rows)==2,rows)
    targets=M._v4222_ts_consumer_targets(w,manifest,failure)
    ck('App consumer ranked before component',targets and targets[0][0]=='src/App.tsx',targets)
    ctx=M._v4222_ts_contract_context(w,'src/App.tsx')
    ck('read-only imported prop contract included','InventoryViewProps' in ctx,ctx)

src="""import { useState } from 'react';
import React, { useState, useEffect } from 'react';
export function X(){return <div/>}
"""
merged,did=M._v4222_merge_react_imports(src)
ck('duplicate React imports detected',did)
ck('React imports merged to one',merged.count("from 'react'")==1,merged)
ck('merged import preserves default and hooks','React' in merged and 'useState' in merged and 'useEffect' in merged,merged)

record="""export interface CheckoutRecord {
  id: string;
  metrics: Record<string, any>; // Added to satisfy DashboardViewProps requirement
}
"""
clean,did=M._v4222_remove_speculative_contract_fields(record)
ck('self-described cross-layer workaround detected',did)
ck('cross-layer workaround field removed','metrics:' not in clean,clean)

# Regression: a component build error must repair the exact compiler consumer, not a clean provider.
with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src/types').mkdir(parents=True);(w/'src/components').mkdir(parents=True)
    (w/'src/App.tsx').write_text("import { InventoryView } from './components/InventoryView';\nexport default function App(){ return <InventoryView />; }\n",encoding='utf-8')
    (w/'src/types/category.ts').write_text('export interface Category { id: string; name: string; }\n',encoding='utf-8')
    (w/'src/components/InventoryView.tsx').write_text("export interface InventoryViewProps { categories: {id:string;name:string}[] }\nexport function InventoryView(_p:InventoryViewProps){return <div/>}\n",encoding='utf-8')
    for rel in ('src/App.tsx','src/types/category.ts','src/components/InventoryView.tsx'):M._v413_mark_accepted(w,rel,'test')
    called=[]
    old=M._repair_file_for_issues
    oldfast=M._v4221_fast_static_recovery
    try:
        M._v4221_fast_static_recovery=lambda *a,**k: []
        def fake(user_request,man,work,rel,problems,progress_callback=None,validation_failure=None):
            called.append(rel);return rel=='src/App.tsx'
        M._repair_file_for_issues=fake
        got=M._v4222_repair_ts_component_failure('finish',manifest,w,"src/App.tsx(2,39): error TS2741: Property 'categories' is missing in type '{}' but required in type 'InventoryViewProps'.",None)
    finally:
        M._repair_file_for_issues=old;M._v4221_fast_static_recovery=oldfast
    ck('consumer repair accepted',got is True,got)
    ck('exact consumer repaired first',called and called[0]=='src/App.tsx',called)
    ck('stable category provider not touched','src/types/category.ts' not in called,called)

# Component-green cache: an unchanged Rust/Node component should not rebuild every audit round.
with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src').mkdir();(w/'src/a.ts').write_text('export const a=1;\n');(w/'package.json').write_text('{"scripts":{"build":"tsc"}}')
    comp={'id':'front','root':'.','toolchain_adapter':'react'}; man={'files':[{'path':'src/a.ts'}],'components':[comp]}
    calls={'n':0};old=M._v4222_prev_validate_component
    try:
        def fakeval(*a,**k):calls['n']+=1;return True,'green'
        M._v4222_prev_validate_component=fakeval
        a=M._v35_validate_component(w,man,comp,'')
        b=M._v35_validate_component(w,man,comp,'')
    finally:M._v4222_prev_validate_component=old
    ck('green component validator first call succeeds',a[0] is True,a)
    ck('unchanged green component build reused',calls['n']==1,calls)
    ck('cache result marked',b[0] is True and 'reused' in b[1].lower(),b)

print(f'RESULT {passed} passed / {failed} failed')
raise SystemExit(1 if failed else 0)
