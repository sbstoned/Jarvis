from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('local_qwen_project_v413', ROOT / 'local_qwen_project.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+detail) if detail else ''))
    return ok

identity=M._v36_release_identity()
check('release identity is V41.3.2-compatible or newer', identity.get('version') == 'V41.3.2' or str(identity.get('version') or '').startswith('V42.'))
check('accepted revision guard enabled', identity.get('accepted_revision_guard') is True)
check('unaccepted draft regeneration enabled', identity.get('unaccepted_draft_regeneration') is True)
check('line-number patch normalization enabled', identity.get('line_number_patch_normalization') is True)
check('bounded no-commit regeneration enabled', identity.get('bounded_no_commit_regeneration') is True)
check('deterministic Foundation boot shells enabled', identity.get('deterministic_foundation_boot_shells') is True)
check('091222 missing-lib regression flag present', identity.get('geartrack_091222_missing_lib_regression_fixed') is True)

numbered='36: pub struct Tool {\n37:     pub id: i64,\n38: }'
check('display-line-number block detected', M._v413_numbered_block(numbered))
stripped=M._v413_strip_display_line_numbers(numbered)
check('display line numbers stripped', stripped=='pub struct Tool {\n    pub id: i64,\n}')
current='pub struct Tool {\n    pub id: i64,\n}\n'
patched,err=M._v36_apply_search_replace(current,[{'search':numbered,'replace':'36: pub struct Tool {\n37:     pub id: i64,\n38:     pub name: String,\n39: }'}])
check('malformed numbered SEARCH patch now applies', not err, err)
check('numbered REPLACE also normalized', 'pub name: String' in patched and '36:' not in patched, patched)
plain='match value {\n    36 => answer(),\n}'
check('normal source is not mistaken for display numbering', not M._v413_numbered_block(plain))

manifest={
    '_original_user_request':'Build a GearTrack desktop app in Tauri with React and Rust',
    'components':[
        {'id':'ui','root':'.','purpose':'React Vite UI','toolchain_adapter':'react'},
        {'id':'tauri','root':'src-tauri','purpose':'Tauri Rust desktop backend','toolchain_adapter':'rust'},
    ],
    'files':[
        {'path':'package.json','purpose':'Node manifest','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src/main.tsx','purpose':'React entry point','phase':'integration','depends_on':['src/App.tsx'],'exports':[]},
        {'path':'src/App.tsx','purpose':'Application UI','phase':'ui','depends_on':[],'exports':[]},
        {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
        {'path':'src-tauri/src/main.rs','purpose':'Tauri entry point','phase':'foundation','depends_on':['src-tauri/src/lib.rs'],'exports':[]},
        {'path':'src-tauri/src/lib.rs','purpose':'Tauri command registration and future service wiring','phase':'foundation','depends_on':['src-tauri/src/models/tool.rs'],'exports':[]},
        {'path':'src-tauri/src/models/tool.rs','purpose':'Canonical Tool model','phase':'data','depends_on':[],'exports':['Tool']},
    ]
}
check('Tauri topology detected', M._v413_is_tauri_manifest(manifest))
hardened=M._v413_harden_tauri_manifest(manifest)
paths={x['path'] for x in hardened['files']}
check('Tauri build.rs self-healed into plan', 'src-tauri/build.rs' in paths)
check('Tauri config self-healed into plan', 'src-tauri/tauri.conf.json' in paths)
check('Tauri main remains planned', 'src-tauri/src/main.rs' in paths)
check('Tauri lib remains planned', 'src-tauri/src/lib.rs' in paths)
miles=M._v39_build_milestones(hardened,manifest['_original_user_request'])
foundation=next((x for x in miles if x.get('kind')=='foundation'),{})
ff=set(foundation.get('files') or [])
check('Tauri main forced into Foundation', 'src-tauri/src/main.rs' in ff, str(sorted(ff)))
check('Tauri lib forced into Foundation', 'src-tauri/src/lib.rs' in ff)
check('Tauri build.rs forced into Foundation', 'src-tauri/build.rs' in ff)
check('Tauri config forced into Foundation', 'src-tauri/tauri.conf.json' in ff)
lib=M._v413_minimal_tauri_lib()
check('minimal lib shell excludes future canonical domain/service owners', all(x not in lib for x in ('Tool','Category','CheckoutLog','AppState','tool_service','db::')))
main=M._v413_minimal_tauri_main()
check('minimal main shell excludes future library/service imports', 'geartrack_lib' not in main and 'tool_service' not in main)

with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'src-tauri').mkdir(parents=True)
    cargo='''[package]\nname = "geartrack"\nversion = "0.1.0"\nedition = "2021"\n\n[build-dependencies]\ntauri-build = { version = "1.5", features = [] }\n\n[dependencies]\ntauri = { version = "1.5", features = ["all"] }\ntauri-plugin-shell = "1.0"\ntauri-plugin-dialog = "1.0"\ntauri-plugin-fs = "1.0"\nsqlx = { version = "0.7", features = ["runtime-tauri", "sqlite"] }\n'''
    cp=root/'src-tauri/Cargo.toml'; cp.write_text(cargo,encoding='utf-8')
    changed=M._v413_harden_tauri_cargo(root)
    fixed=cp.read_text(encoding='utf-8')
    check('Cargo coherence repair activates', changed)
    check('SQLx runtime-tauri repaired to runtime-tokio', 'runtime-tokio' in fixed and 'runtime-tauri' not in fixed)
    check('Tauri-2-style plugin mixture removed from Tauri 1 manifest', 'tauri-plugin-shell' not in fixed and 'tauri-plugin-dialog' not in fixed and 'tauri-plugin-fs' not in fixed)
    check('Tauri 1 all feature normalized to api-all', 'api-all' in fixed and 'features = ["all"]' not in fixed)
    f=root/'accepted.rs'; f.write_text('pub fn ok() {}\n',encoding='utf-8')
    M._v413_mark_accepted(root,'accepted.rs','regression')
    check('accepted ledger recognizes exact committed revision', M._v413_is_accepted(root,'accepted.rs'))
    f.write_text('pub fn changed() {}\n',encoding='utf-8')
    check('accepted ledger rejects stale/mutated revision', not M._v413_is_accepted(root,'accepted.rs'))

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
