from pathlib import Path
import importlib.util
import json
import tempfile

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m',ROOT/'local_qwen_project.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+detail) if detail else ''))

manifest={
    '_original_user_request':'Build GearTrack as a React TypeScript Vite Tauri Rust SQLite desktop app',
    'components':[
        {'id':'ui','root':'.','purpose':'React TypeScript Vite UI','toolchain_adapter':'react'},
        {'id':'tauri-core','root':'src-tauri','purpose':'Rust Tauri backend','toolchain_adapter':'rust'},
    ],
    'files':[
        {'path':'package.json','purpose':'Node manifest','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'tsconfig.json','purpose':'TypeScript configuration','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src/main.tsx','purpose':'React entry point','phase':'integration','depends_on':['src/App.tsx'],'exports':[]},
        {'path':'src/App.tsx','purpose':'Application UI','phase':'integration','depends_on':['src/index.css'],'exports':[]},
        {'path':'src/index.css','purpose':'Global styles','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'index.html','purpose':'Vite HTML host','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'vite.config.ts','purpose':'Vite config','phase':'foundation','depends_on':['package.json'],'exports':[]},
        {'path':'tsconfig.node.json','purpose':'Vite TS config','phase':'foundation','depends_on':['vite.config.ts'],'exports':[]},
        {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src-tauri/src/main.rs','purpose':'Tauri entry point','phase':'foundation','depends_on':['src-tauri/Cargo.toml'],'exports':[]},
        {'path':'src-tauri/src/lib.rs','purpose':'Tauri library and command registration','phase':'foundation','depends_on':['src-tauri/src/models/tool.rs'],'exports':[]},
        {'path':'src-tauri/src/db.rs','purpose':'SQLite database','phase':'data','depends_on':['src-tauri/Cargo.toml'],'exports':[]},
        {'path':'src-tauri/src/models/tool.rs','purpose':'Canonical Tool model','phase':'data','depends_on':['src-tauri/Cargo.toml'],'exports':['Tool']},
    ]
}
manifest=m._v413_harden_tauri_manifest(m._v412_harden_web_manifest(manifest,manifest['_original_user_request'],160))
milestones=m._v39_build_milestones(manifest,manifest['_original_user_request'])
foundation=next(x for x in milestones if x.get('kind')=='foundation')
ff=set(foundation['files'])
check('091222 replay keeps React boot in Foundation', 'src/main.tsx' in ff)
check('091222 replay keeps Tauri lib in Foundation', 'src-tauri/src/lib.rs' in ff)
check('091222 replay adds required Tauri build substrate', {'src-tauri/build.rs','src-tauri/tauri.conf.json'}.issubset(ff))
check('091222 replay does not drag Tool model into Foundation', 'src-tauri/src/models/tool.rs' not in ff)

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    # Materialize conservative Foundation substrate exactly as the deterministic path would.
    for rel in foundation['files']:
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True)
        if rel=='src/main.tsx': text=m._v413_minimal_react_main()
        elif rel=='src-tauri/src/main.rs': text=m._v413_minimal_tauri_main()
        elif rel=='src-tauri/src/lib.rs': text=m._v413_minimal_tauri_lib()
        elif rel=='src-tauri/build.rs': text=m._v413_tauri_build_rs()
        elif rel=='src-tauri/Cargo.toml':
            text='''[package]\nname="geartrack"\nversion="0.1.0"\nedition="2021"\n\n[build-dependencies]\ntauri-build={version="1.5",features=[]}\n\n[dependencies]\ntauri={version="1.5",features=["all"]}\nsqlx={version="0.7",features=["runtime-tauri","sqlite"]}\n'''
        elif rel=='src-tauri/tauri.conf.json':
            # Cargo must exist before deterministic config derivation.
            text=m._v413_tauri_conf(root)
        elif rel=='package.json': text=json.dumps({'scripts':{'build':'tsc -b && vite build'},'dependencies':{'react':'^18.0.0','react-dom':'^18.0.0'},'devDependencies':{'typescript':'^5.0.0','vite':'^5.0.0'}},indent=2)
        elif rel=='tsconfig.json': text=json.dumps({'compilerOptions':{'target':'ES2020','module':'ESNext','moduleResolution':'bundler','jsx':'react-jsx','noEmit':True},'include':['src']},indent=2)
        elif rel=='tsconfig.node.json': text=json.dumps({'compilerOptions':{'module':'ESNext','moduleResolution':'bundler','noEmit':True},'include':['vite.config.ts']},indent=2)
        elif rel=='vite.config.ts': text="import { defineConfig } from 'vite';\nexport default defineConfig({});\n"
        elif rel=='index.html': text=m._v412_root_index_html('src/main.tsx')
        else: text='// foundation\n'
        p.write_text(text,encoding='utf-8')
        if rel=='src-tauri/Cargo.toml': m._v413_harden_tauri_cargo(root)
        m._v413_mark_accepted(root,rel,'replay')
    issues=m._v39_milestone_issues(root,manifest,foundation['files'])
    check('091222 replay Foundation has no missing lib.rs issue', not any(x.get('file')=='src-tauri/src/lib.rs' and x.get('kind')=='missing' for x in issues),str(issues))
    check('091222 replay lib.rs is accepted exact revision', m._v413_is_accepted(root,'src-tauri/src/lib.rs'))
    cargo=(root/'src-tauri/Cargo.toml').read_text(encoding='utf-8')
    check('091222 replay Cargo invalid runtime removed', 'runtime-tauri' not in cargo and 'runtime-tokio' in cargo)

passed=sum(ok for _,ok,_ in checks)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
