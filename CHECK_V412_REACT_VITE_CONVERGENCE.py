from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('local_qwen_project_v412', ROOT / 'local_qwen_project.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+detail) if detail else ''))
    return ok

manifest={
    '_original_user_request':'Build me a Tauri React TypeScript GearTrack desktop app',
    'entrypoint':'src/main.tsx',
    'components':[
        {'id':'ui','root':'.','purpose':'Canonical React/TypeScript/Vite desktop UI','toolchain_adapter':'react','build_command':'npm run build'},
        {'id':'tauri-core','root':'src-tauri','purpose':'Rust/Tauri backend','toolchain_adapter':'rust','build_command':'cargo build'},
    ],
    'files':[
        {'path':'package.json','purpose':'Node package manifest','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'vite.config.ts','purpose':'Vite configuration','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'tsconfig.json','purpose':'TypeScript configuration','phase':'foundation','depends_on':['vite.config.ts'],'exports':[]},
        {'path':'src/main.tsx','purpose':'React entry point','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src/App.tsx','purpose':'Main application shell','phase':'ui','depends_on':['src/main.tsx'],'exports':[]},
        {'path':'src/index.css','purpose':'Global styles','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src/index.html','purpose':'HTML host','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
    ]
}
manifest=M._v412_harden_web_manifest(manifest, manifest['_original_user_request'], 160)
paths=[x['path'] for x in manifest['files']]
check('canonical Vite root index.html', 'index.html' in paths and 'src/index.html' not in paths)
check('tsconfig.node planned in Foundation substrate', 'tsconfig.node.json' in paths)

milestones=M._v39_build_milestones(manifest,manifest['_original_user_request'])
foundation=next((g for g in milestones if g.get('kind')=='foundation'),{})
ffiles=set(foundation.get('files') or [])
check('Foundation contains root index.html', 'index.html' in ffiles, str(sorted(ffiles)))
check('Foundation contains tsconfig.node.json', 'tsconfig.node.json' in ffiles)
check('Foundation keeps App.tsx future', 'src/App.tsx' not in ffiles)
check('Foundation keeps index.css future unless required', 'src/index.css' not in ffiles)

manifest['_v39_active_paths']=sorted(ffiles)
bad_main="""import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\nimport './index.css';\nReactDOM.createRoot(document.getElementById('root')!).render(<App />);\n"""
err=M._v412_current_slice_import_error('/tmp/v412',manifest,'src/main.tsx',bad_main)
check('future App/style import rejected before commit', 'current-slice JS/TS import gate' in err, err)

good_main=M._v412_minimal_react_boot_source()
check('minimal boot shell passes slice import gate', not M._v412_current_slice_import_error('/tmp/v412',manifest,'src/main.tsx',good_main))

with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'src').mkdir();
    (root/'src/main.tsx').write_text(bad_main,encoding='utf-8')
    (root/'tsconfig.json').write_text(json.dumps({'compilerOptions':{'target':'ES2020','module':'ESNext','moduleResolution':'bundler','noEmit':True},'include':['src'],'references':[]}),encoding='utf-8')
    failure="""src/main.tsx(3,17): error TS2307: Cannot find module './App' or its corresponding type declarations.\nsrc/main.tsx(4,8): error TS2307: Cannot find module './index.css' or its corresponding type declarations.\nsrc/main.tsx(5,62): error TS17004: Cannot use JSX unless the '--jsx' flag is provided."""
    repaired=M._v412_repair_react_vite_failure(manifest['_original_user_request'],manifest,root,failure)
    ts=json.loads((root/'tsconfig.json').read_text(encoding='utf-8'))
    main=(root/'src/main.tsx').read_text(encoding='utf-8')
    check('deterministic build-substrate repair activates', repaired)
    check('TS17004 deterministically sets react-jsx', ts.get('compilerOptions',{}).get('jsx')=='react-jsx')
    check('TS2307 future imports removed from bootstrap shell', './App' not in main and './index.css' not in main)
    check('root index.html deterministically materialized', (root/'index.html').exists())

identity=M._v36_release_identity()
ver=str(identity.get('version') or '').lstrip('Vv')
try:
    parts=tuple(int(x) for x in ver.split('.')[:2])
except Exception:
    parts=(0,0)
check('release identity is V41.2-compatible or newer', parts >= (41,2), identity.get('version'))
check('GearTrack regression flag present', identity.get('geartrack_20260830_regression_fixed') is True)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
