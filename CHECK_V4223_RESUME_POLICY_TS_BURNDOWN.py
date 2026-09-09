import json, shutil, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_qwen_project as M

passed=failed=0
def ck(name,cond,detail=''):
    global passed,failed
    if cond:
        passed+=1;print('PASS',name)
    else:
        failed+=1;print('FAIL',name,detail)

ident=M._v36_release_identity()
ck('release version',ident.get('version')=='V42.23.0',ident)
ck('resume migration advertised',ident.get('resume_checkpoint_policy_is_migrated_to_current_engine') is True,ident)
ck('ts burndown advertised',ident.get('deterministic_typescript_burndown_before_model') is True,ident)
ck('progress continuation advertised',ident.get('progress_based_continuation_while_compiler_errors_decrease') is True,ident)

import jarvis_v42_runtime as RT
ck('runtime broker version',RT.V42_RUNTIME_VERSION=='42.23.0',RT.V42_RUNTIME_VERSION)
ck('runtime broker engine updated','V4223' in RT.V42_RUNTIME_ENGINE,RT.V42_RUNTIME_ENGINE)

old_manifest={
 'architecture_rules':['Tiered Hierarchy: Foundation -> Providers -> Consumers','Provider-First Repair: If a consumer fails, check if the canonical type definition exists. If not, create it before editing the consumer.'],
 'files':[],'components':[]
}
mig,removed=M._v4223_sanitize_resume_manifest(old_manifest)
ck('stale provider-first rule removed',all('provider-first' not in str(x).lower() for x in mig.get('architecture_rules',[])),mig)
ck('current consumer-first rule inserted',any('consumer-first compiler ownership' in str(x).lower() for x in mig.get('architecture_rules',[])),mig)
ck('migration records removed rule',bool(removed),removed)

# Synthetic old checkpoint metadata must migrate to current policy on resume.
with tempfile.TemporaryDirectory() as td:
    w=Path(td)/'w';w.mkdir();(w/'src').mkdir();(w/'src/App.tsx').write_text('export default function App(){return null}\n')
    checkpoint_meta={
      'schema_version':1,'status':'checkpoint_incomplete','resume_count':1,
      'original_request':'Finish the application completely.','latest_instruction':'finish this project',
      'manifest':old_manifest,'unresolved_issues':[]
    }
    (w/'.jarvis_resume.json').write_text(json.dumps(checkpoint_meta),encoding='utf-8')
    seed=M._resume_seed_from_workspace(w,Path(td)/'old_checkpoint.zip','finish this project')
    rules='\n'.join(str(x) for x in (seed.get('manifest') or {}).get('architecture_rules',[]))
    ck('old checkpoint provider-first policy retired','Provider-First Repair' not in rules,rules)
    ck('old checkpoint current policy active','Consumer-First Compiler Ownership' in rules,rules)
    arch=w/'JARVIS_V33_ARCHITECTURE.json'
    if arch.exists():
        arch_text=arch.read_text(encoding='utf-8',errors='replace')
        ck('derived architecture also drops provider-first policy','Provider-First Repair' not in arch_text,arch_text[:1200])
    else:
        ck('derived architecture written after migration',False,'missing architecture artifact')

manifest={
 '_original_user_request':'Finish the application completely.',
 'files':[
  {'path':'src/App.tsx','purpose':'React application root'},
  {'path':'src/hooks/useCheckouts.ts','purpose':'checkout hook'},
  {'path':'src/hooks/useFiltering.ts','purpose':'filter hook'},
  {'path':'src/hooks/useTauriCommands.ts','purpose':'Tauri commands'},
  {'path':'src/hooks/useTools.ts','purpose':'tools hook'},
 ],
 'components':[{'id':'frontend','root':'.','toolchain_adapter':'react'}]
}
with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src/hooks').mkdir(parents=True)
    (w/'package.json').write_text(json.dumps({'dependencies':{'@tauri-apps/api':'^2.0.0','react':'^18.0.0'}}),encoding='utf-8')
    (w/'src/App.tsx').write_text("import React from 'react';\nimport './App.css';\nexport default function App(){return <div/>}\n",encoding='utf-8')
    (w/'src/hooks/useCheckouts.ts').write_text("export function useCheckouts(){\n  const [items, setItems] = useState<string[]>([]);\n  const x: string | undefined = null;\n  return {items,setItems,x};\n}\n",encoding='utf-8')
    (w/'src/hooks/useFiltering.ts').write_text("export interface FilterState { q:string }\nexport type { FilterState };\n",encoding='utf-8')
    (w/'src/hooks/useTauriCommands.ts').write_text("export const cmd=(n:string)=>window.__TAURI__.invoke(n);\n",encoding='utf-8')
    (w/'src/hooks/useTools.ts').write_text("export const useTools=()=>({tools:[]});\n",encoding='utf-8')
    for rel in [x['path'] for x in manifest['files']]:M._v413_mark_accepted(w,rel,'test')
    failure="""src/App.tsx(1,1): error TS6133: 'React' is declared but its value is never read.
src/App.tsx(2,8): error TS2307: Cannot find module './App.css' or its corresponding type declarations.
src/hooks/useCheckouts.ts(2,29): error TS2304: Cannot find name 'useState'.
src/hooks/useCheckouts.ts(3,9): error TS2322: Type 'null' is not assignable to type 'string | undefined'.
src/hooks/useFiltering.ts(2,15): error TS2484: Export declaration conflicts with exported declaration of 'FilterState'.
src/hooks/useTauriCommands.ts(1,37): error TS2339: Property '__TAURI__' does not exist on type 'Window & typeof globalThis'.
"""
    rows=M._v4222_parse_ts_diagnostics(w,failure)
    ck('diagnostics parsed',len(rows)==6,rows)
    changed=M._v4223_bulk_ts_recovery(w,manifest,failure,None)
    ck('bulk recovery changed multiple files',len(changed)>=4,changed)
    ck('missing local stylesheet created',(w/'src/App.css').exists(),changed)
    app=(w/'src/App.tsx').read_text()
    ck('unused React default import removed',"import React from 'react'" not in app,app)
    uc=(w/'src/hooks/useCheckouts.ts').read_text()
    ck('missing useState import fixed','useState' in uc.splitlines()[0],uc)
    ck('null undefined mismatch fixed',' = undefined;' in uc,uc)
    uf=(w/'src/hooks/useFiltering.ts').read_text()
    ck('duplicate exported type fixed','export type { FilterState }' not in uf,uf)
    ta=(w/'src/hooks/useTauriCommands.ts').read_text()
    ck('Tauri2 invoke import added',"@tauri-apps/api/core" in ta and 'window.__TAURI__.invoke' not in ta,ta)

    # Producer context should reveal nearby hook APIs for App/component wiring.
    ctx=M._v4223_nearby_producer_context(w,'src/App.tsx',[{'raw':"src/App.tsx(3,1): error TS2741: Property 'tools' is missing",'code':'2741'}])
    ck('nearby producer context includes hook','useTools' in ctx,ctx)

# Progress policy: decreasing compiler counts continue to zero; identical counts stop boundedly.
def audit_with(n):
    if n<=0:return {'clean':True,'issues':[],'components':[]}
    lines=[]
    for i in range(n):lines.append(f"src/App.tsx({i+1},1): error TS2304: Cannot find name 'X{i}'.")
    return {'clean':False,'issues':[{'file':'.','kind':'component_validation','problem':'\n'.join(lines)}],'components':[]}

with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src').mkdir();(w/'src/App.tsx').write_text('export default function App(){return null}\n')
    man={'files':[{'path':'src/App.tsx'}],'components':[{'id':'front','root':'.','toolchain_adapter':'react'}]}
    seq=[3,2,1,0];idx={'i':0};rep={'n':0}
    olda=M._v429_whole_project_audit;oldr=M._v429_repair_audit_round;oldtok=M._v429_progress_token
    try:
        def fa(*a,**k):return audit_with(seq[min(idx['i'],len(seq)-1)])
        def fr(*a,**k):rep['n']+=1;idx['i']+=1;return True
        M._v429_whole_project_audit=fa;M._v429_repair_audit_round=fr;M._v429_progress_token=lambda _w: str(idx['i'])
        ok,issues=M._v429_whole_project_convergence('finish',man,w,None)
    finally:
        M._v429_whole_project_audit=olda;M._v429_repair_audit_round=oldr;M._v429_progress_token=oldtok
    ck('decreasing compiler errors continue to green',ok is True,(ok,issues,rep))
    ck('decreasing path allowed multiple repair/build cycles',rep['n']>=3,rep)

with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src').mkdir();(w/'src/App.tsx').write_text('export default function App(){return null}\n')
    man={'files':[{'path':'src/App.tsx'}],'components':[{'id':'front','root':'.','toolchain_adapter':'react'}]}
    rep={'n':0};tok={'n':0}
    olda=M._v429_whole_project_audit;oldr=M._v429_repair_audit_round;oldtok=M._v429_progress_token
    try:
        M._v429_whole_project_audit=lambda *a,**k:audit_with(3)
        def fr(*a,**k):rep['n']+=1;tok['n']+=1;return True
        M._v429_repair_audit_round=fr;M._v429_progress_token=lambda _w:str(tok['n'])
        ok,issues=M._v429_whole_project_convergence('finish',man,w,None)
    finally:
        M._v429_whole_project_audit=olda;M._v429_repair_audit_round=oldr;M._v429_progress_token=oldtok
    ck('identical compiler blocker set stops boundedly',ok is False,(ok,rep))
    ck('identical blocker does not consume many cycles',rep['n']<=3,rep)

print(f'RESULT {passed} passed / {failed} failed')
raise SystemExit(1 if failed else 0)
