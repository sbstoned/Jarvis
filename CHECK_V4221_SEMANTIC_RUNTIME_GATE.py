import json, tempfile, shutil, sys, os
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

ck('release version',M._v36_release_identity().get('version')=='V42.21.0',M._v36_release_identity())
ck('semantic gate advertised',M._v36_release_identity().get('semantic_file_role_gate') is True)

bad_inv="""import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\nexport default defineConfig({plugins:[react()]})\n"""
manifest={'_original_user_request':'finish project','components':[{'id':'react','root':'.','toolchain_adapter':'react'}],'files':[{'path':'src/components/InventoryView.tsx','purpose':'UI component for viewing inventory','depends_on':['src/hooks/useTools.ts'],'exports':[]}]} 
with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src/components').mkdir(parents=True);(w/'src/hooks').mkdir(parents=True)
    (w/'src/components/InventoryView.tsx').write_text(bad_inv,encoding='utf-8')
    err=M._v4221_semantic_role_error(w,manifest,'src/components/InventoryView.tsx',bad_inv)
    ck('vite config rejected as React component',bool(err) and 'semantic-role' in err,err)
    good="""import { useTools } from '../hooks/useTools';\nexport function InventoryView(){ const tools=useTools(); return <div>{String(tools)}</div>; }\n"""
    ck('real InventoryView accepted by role gate',not M._v4221_semantic_role_error(w,manifest,'src/components/InventoryView.tsx',good),M._v4221_semantic_role_error(w,manifest,'src/components/InventoryView.tsx',good))

src='export interface Tool { id: string; }\nexport { Tool };\n'
fixed,did=M._v4221_redundant_ts_export_fix(src)
ck('redundant TS export detected',did)
ck('redundant TS export removed','export { Tool }' not in fixed,fixed)

src='import { useMemo } from "react";\nexport const x=()=>{ const [v,setV]=useState(0); return useMemo(()=>v,[v]); };\n'
fixed,did=M._v4221_react_hook_import_fix(src)
ck('missing hook import detected',did)
ck('useState inserted into React import','useState' in fixed.split('\n',1)[0],fixed)

with tempfile.TemporaryDirectory() as td:
    w=Path(td);(w/'src').mkdir();
    (w/'src/App.tsx').write_text('export default function App(){return <div>real app</div>}\n',encoding='utf-8')
    fake="""import React from 'react';\nimport ReactDOM from 'react-dom/client';\nReactDOM.createRoot(document.getElementById('root')!).render(React.createElement('div',null,'Application shell ready'));\n"""
    (w/'src/main.tsx').write_text(fake,encoding='utf-8')
    out,did=M._v4221_react_main_bootstrap_fix(w,'src/main.tsx',fake)
    ck('placeholder bootstrap detected',did)
    ck('real App mounted','<App />' in out and "from './App'" in out,out)
    ck('placeholder bootstrap rejected semantically',bool(M._v4221_semantic_role_error(w,{'files':[{'path':'src/main.tsx','purpose':'Root entry point that bootstraps the React application.'}]},'src/main.tsx',fake)))

# Exact stopped GearTrack regression if the supplied snapshot is available.
gear=Path('/mnt/data/v4221_gear_test')
if gear.exists():
    with tempfile.TemporaryDirectory() as td:
        w=Path(td)/'project';shutil.copytree(gear,w)
        manifest=json.loads((w/'JARVIS_V33_ARCHITECTURE.json').read_text(encoding='utf-8'))
        manifest['_original_user_request']='Finish this project completely.'
        before=M._v4221_semantic_repo_issues(w,manifest)
        ck('GearTrack wrong Inventory role found',any(x.get('file')=='src/components/InventoryView.tsx' for x in before),before)
        changed=M._v4221_fast_static_recovery(w,manifest,None)
        ck('GearTrack tool.ts fast-fixed','src/types/tool.ts' in changed,changed)
        ck('GearTrack useFiltering fast-fixed','src/hooks/useFiltering.ts' in changed,changed)
        ck('GearTrack main fast-fixed','src/main.tsx' in changed,changed)
        ck('GearTrack redundant export gone','export { Tool }' not in (w/'src/types/tool.ts').read_text(),(w/'src/types/tool.ts').read_text())
        ck('GearTrack useState imported','useState' in (w/'src/hooks/useFiltering.ts').read_text().split('\n',1)[0],(w/'src/hooks/useFiltering.ts').read_text()[:180])
        ck('GearTrack App mounted','<App />' in (w/'src/main.tsx').read_text(),(w/'src/main.tsx').read_text())
        after=M._v4221_semantic_repo_issues(w,manifest)
        ck('GearTrack Inventory remains only semantic-role blocker',any(x.get('file')=='src/components/InventoryView.tsx' for x in after),after)
        ck('GearTrack main no longer semantic blocker',not any(x.get('file')=='src/main.tsx' for x in after),after)

print(f'RESULT {passed} passed / {failed} failed')
raise SystemExit(1 if failed else 0)
