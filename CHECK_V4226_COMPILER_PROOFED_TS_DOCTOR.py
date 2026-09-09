from __future__ import annotations
import tempfile
from pathlib import Path
import local_qwen_project as j

checks=[]
def ck(name, cond, detail=''):
    if not cond:
        raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=j._v36_release_identity()
ck('release identity', ident.get('version')=='V42.26.0', ident)
ck('compiler proof advertised', ident.get('cluster_final_commit_uses_global_compiler_proof') is True, ident)
ck('dependency first advertised', ident.get('dependency_first_cluster_execution') is True, ident)
ck('six-file cluster default', int(ident.get('cluster_model_files') or 0)>=6, ident)

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    (root/'src/hooks').mkdir(parents=True)
    (root/'src/components').mkdir(parents=True)
    (root/'src/types').mkdir(parents=True)
    (root/'src/App.tsx').write_text("import { View } from './components/View';\nexport default function App(){ return <View/> }\n",encoding='utf-8')
    (root/'src/components/View.tsx').write_text("import { useThing } from '../hooks/useThing';\nexport interface ViewProps { value: string }\nexport const View=({value}:ViewProps)=><div>{value}</div>;\n",encoding='utf-8')
    (root/'src/hooks/useThing.ts').write_text("export function useThing(value: string, items: Item[]){ return {value,items}; }\nimport type { Item } from '../types/item';\n",encoding='utf-8')
    (root/'src/types/item.ts').write_text("export interface Item { id: string }\n",encoding='utf-8')
    order=j._v4226_dependency_order(root,['src/App.tsx','src/components/View.tsx','src/hooks/useThing.ts'])
    ck('dependency hook before view',order.index('src/hooks/useThing.ts') < order.index('src/components/View.tsx'),order)
    ck('integration root last',order[-1]=='src/App.tsx',order)

    # Signature-directed TS2554 and TS2345 call repair.
    caller=root/'src/components/Caller.tsx'
    caller.write_text("import { useThing } from '../hooks/useThing';\nexport function Caller({value,items}:{value:string;items:Item[]}){\n const x=useThing();\n const y=useThing(value, value);\n return null;\n}\nimport type { Item } from '../types/item';\n",encoding='utf-8')
    original=caller.read_text()
    rows=[
      {'code':'2554','line':3,'raw':"src/components/Caller.tsx(3,10): error TS2554: Expected 2 arguments, but got 0."},
      {'code':'2345','line':4,'raw':"src/components/Caller.tsx(4,28): error TS2345: Argument of type 'string' is not assignable to parameter of type 'Item[]'."},
    ]
    out,rs=j._v4226_fix_call_arguments(root,'src/components/Caller.tsx',original,original,rows)
    ck('missing args synthesized','useThing(value, items)' in out,(out,rs))
    ck('wrong typed arg replaced',out.count('useThing(value, items)')==2,(out,rs))

    # Stale TS6133 must not delete a symbol another diagnostic proves is needed.
    rescued=j._v4226_rescued_symbols_for_call_fixes(root,'src/components/Caller.tsx',original,rows)
    ck('required producer rescued','items' in rescued,rescued)

    # Missing member aliases reconcile producer API without rewriting the provider.
    text="const { createThingCommand, updateThingCommand } = useApi();\n"
    rows_alias=[
      {'code':'2339','raw':"error TS2339: Property 'createThingCommand' does not exist on type '{ createThing: () => void; updateThing: () => void; }'."},
      {'code':'2339','raw':"error TS2339: Property 'updateThingCommand' does not exist on type '{ createThing: () => void; updateThing: () => void; }'."},
    ]
    out,rs=j._v4226_fix_missing_member_aliases(text,rows_alias)
    ck('create alias','createThing: createThingCommand' in out,(out,rs))
    ck('update alias','updateThing: updateThingCommand' in out,(out,rs))

    # Response wrappers with data are unwrapped before React state assignment.
    (root/'src/hooks/api.ts').write_text("export interface ApiResponse<T>{ data: T | null; error: string | null }\n",encoding='utf-8')
    text="setItems(response);\n"
    row={'code':'2345','line':1,'raw':"x.ts(1,1): error TS2345: Argument of type 'ApiResponse<Item[]>' is not assignable to parameter of type 'SetStateAction<Item[]>'."}
    out,rs=j._v4226_fix_response_unwrap(root,text,text,[row])
    ck('response data unwrapped','setItems(response.data ?? [])' in out,(out,rs))

    # Unused function locals are safely removed; call initializers keep side effects.
    text="const unused = () => { console.log('x'); };\nconst url = URL.createObjectURL(blob);\n"
    rr=[
      {'code':'6133','raw':"x.ts(1,7): error TS6133: 'unused' is declared but its value is never read."},
      {'code':'6133','raw':"x.ts(2,7): error TS6133: 'url' is declared but its value is never read."},
    ]
    out,rs=j._v4226_remove_unused_function_or_local(text,rr)
    ck('unused arrow removed','const unused' not in out,(out,rs))
    ck('side effect preserved','void URL.createObjectURL(blob);' in out,(out,rs))

    # Boolean string ternary is corrected from exact structural compiler evidence.
    text='const row = { is_checked_out: tool.is_checked_out ? "true" : "false" };\n'
    row={'code':'2322','raw':"Types of property 'is_checked_out' are incompatible. Type 'string' is not assignable to type 'boolean'."}
    out,rs=j._v4226_fix_boolean_property_mismatch(text,[row])
    ck('boolean object property repaired','is_checked_out: tool.is_checked_out' in out,(out,rs))

    # Final cluster commit must not call inherited per-file whole-project replay once
    # the global compiler delta already proved improvement.
    source=root/'src/simple.ts'; source.write_text('export const x = 1;\n',encoding='utf-8')
    clone=root/'clone'; (clone/'src').mkdir(parents=True); (clone/'src/simple.ts').write_text('export const x = 2;\n',encoding='utf-8')
    old_sem=j._v4221_semantic_role_error
    old_tx=j._v4221_prev_candidate_transaction_error
    old_mark=j._v413_mark_accepted
    called=[]
    try:
        j._v4221_semantic_role_error=lambda *a,**k:''
        j._v4221_prev_candidate_transaction_error=lambda *a,**k: (_ for _ in ()).throw(AssertionError('legacy leaf replay invoked'))
        j._v413_mark_accepted=lambda *a,**k: called.append(a[1] if len(a)>1 else 'x')
        ok,why=j._v4224_commit_cluster(root,clone,{},['src/simple.ts'],5,4)
        ck('compiler-proved cluster committed',ok,why)
        ck('candidate promoted',(source.read_text()=='export const x = 2;\n'),source.read_text())
    finally:
        j._v4221_semantic_role_error=old_sem
        j._v4221_prev_candidate_transaction_error=old_tx
        j._v413_mark_accepted=old_mark

print(f'V42.26 regression: {len(checks)}/{len(checks)} PASS')
