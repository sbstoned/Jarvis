from pathlib import Path
import tempfile, json, shutil
import local_qwen_project as M

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+str(detail)) if detail else ''))

# Exact architecture pattern from project_20260830_183449: React root + nested Rust/Tauri,
# TypeScript source exists but planner omitted root tsconfig.
manifest={
 'components':[
   {'id':'ui','root':'.','toolchain_adapter':'react','depends_on':['tauri-core'],'build_command':'npm run build','test_command':'npm test'},
   {'id':'tauri-core','root':'src-tauri','toolchain_adapter':'rust','depends_on':[],'build_command':'cargo build','test_command':'cargo test'},
 ],
 'files':[
   {'path':'src/main.tsx','purpose':'React boot','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src/App.tsx','purpose':'Application shell','phase':'integration','depends_on':[],'exports':['App']},
   {'path':'package.json','purpose':'Node dependency/build manifest','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src-tauri/Cargo.toml','purpose':'Rust manifest','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src-tauri/src/main.rs','purpose':'Rust main','phase':'foundation','depends_on':[],'exports':[]},
   {'path':'src-tauri/src/lib.rs','purpose':'Rust lib','phase':'foundation','depends_on':[],'exports':[]},
 ]
}
closed=M._v422_close_component_substrate_plan(manifest)
paths={x['path'] for x in closed['files']}
check('React TypeScript component receives root-owned tsconfig before implementation','tsconfig.json' in paths,sorted(paths))
check('closure does not invent tsconfig inside nested Rust component','src-tauri/tsconfig.json' not in paths,sorted(paths))
check('Vite host remains component-root index.html','index.html' in paths,sorted(paths))

ui=next(c for c in closed['components'] if c['id']=='ui')
with tempfile.TemporaryDirectory(prefix='v422_exact_') as td:
    root=Path(td); (root/'src').mkdir(parents=True); (root/'src-tauri').mkdir()
    (root/'src/main.tsx').write_text("export {};\n",encoding='utf-8')
    (root/'package.json').write_text(json.dumps({
      'name':'geartrack','version':'1.0.0','scripts':{
        'build':'tsc -p src-tauri/tsconfig.json && vite build --outDir dist',
        'dev':'vite','tauri':'tauri dev'
      },'dependencies':{},'devDependencies':{}
    },indent=2),encoding='utf-8')
    issue_before=M._v422_component_command_issue(root,closed,ui)
    check('component-command gate detects cross-component compiler config before execution','nested component src-tauri' in issue_before,issue_before)
    changed=M._v422_prepare_component_substrate(root,closed,ui)
    check('deterministic substrate repair changed exact failed workspace shape',changed)
    check('deterministic repair materialized root tsconfig',(root/'tsconfig.json').exists())
    pkg=json.loads((root/'package.json').read_text(encoding='utf-8'))
    check('bad tsc project path rewritten to owning component config',pkg['scripts']['build'].startswith('tsc -p tsconfig.json'),pkg['scripts']['build'])
    check('component-command gate is clean after deterministic repair',not M._v422_component_command_issue(root,closed,ui),M._v422_component_command_issue(root,closed,ui))
    failure="error TS5058: The specified path does not exist: 'src-tauri/tsconfig.json'."
    check('TS5058 failure signature preserves exact missing config',M._validation_failure_signature(failure)=='component-missing-build-config:src-tauri/tsconfig.json',M._validation_failure_signature(failure))

# Universal/mixed-repo regression: the same rule is not Tauri-specific. A root React
# component may not compile against a nested Go service's config path either.
generic={
 'components':[
   {'id':'web','root':'.','toolchain_adapter':'react','depends_on':['api']},
   {'id':'api','root':'server','toolchain_adapter':'go','depends_on':[]},
 ],
 'files':[
   {'path':'package.json','purpose':'web manifest','phase':'foundation','exports':[]},
   {'path':'src/main.tsx','purpose':'web boot','phase':'foundation','exports':[]},
   {'path':'server/go.mod','purpose':'Go API manifest','phase':'foundation','exports':[]},
   {'path':'server/main.go','purpose':'Go API','phase':'integration','exports':[]},
 ]
}
generic=M._v422_close_component_substrate_plan(generic)
web=next(c for c in generic['components'] if c['id']=='web')
with tempfile.TemporaryDirectory(prefix='v422_generic_') as td:
    root=Path(td); (root/'server').mkdir(); (root/'src').mkdir()
    (root/'package.json').write_text(json.dumps({'scripts':{'build':'tsc -p server/tsconfig.json && vite build'}}),encoding='utf-8')
    problem=M._v422_component_command_issue(root,generic,web)
    check('component boundary rule works for non-Tauri mixed repositories','nested component server' in problem,problem)

# Legitimate component-local config refs remain untouched.
with tempfile.TemporaryDirectory(prefix='v422_local_') as td:
    root=Path(td); (root/'src').mkdir(); (root/'vite.config.ts').write_text('export default {}\n',encoding='utf-8')
    local_manifest={
      'components':[{'id':'web','root':'.','toolchain_adapter':'vite','depends_on':[]}],
      'files':[{'path':'package.json','phase':'foundation'},{'path':'src/main.ts','phase':'foundation'},{'path':'vite.config.ts','phase':'foundation'}]
    }
    comp=local_manifest['components'][0]
    (root/'package.json').write_text(json.dumps({'scripts':{'build':'vite --config vite.config.ts'}}),encoding='utf-8')
    check('legitimate local config reference is allowed',not M._v422_component_command_issue(root,local_manifest,comp),M._v422_component_command_issue(root,local_manifest,comp))

# Direct self-import from the live failed workspace must be rejected before commit.
self_bad="import React from 'react';\nimport { App as RootApp } from './App';\nexport default function App(){ return null; }\n"
err=M._v422_direct_self_reference_error('src/App.tsx',self_bad)
check('direct JS/TS self-import rejected before compiler','imports itself' in err,err)
check('normal sibling import is not rejected',not M._v422_direct_self_reference_error('src/App.tsx',"import X from './components/X';\nexport default X;"))

# Registry-driven path-flag rules remain data extensible and do not reduce adapter breadth.
reg=M._v422_registry()
check('toolchain registry still has 59 adapters',len(reg.get('adapters') or {})>=59,len(reg.get('adapters') or {}))
check('config path rules loaded from registry','tsc' in (reg.get('command_path_rules') or {}),reg.get('command_path_rules'))

# Plan sanitizer leaves unrelated ecosystems alone.
rust_only={'components':[{'id':'core','root':'.','toolchain_adapter':'rust','depends_on':[]}], 'files':[{'path':'Cargo.toml','phase':'foundation'},{'path':'src/main.rs','phase':'integration'}]}
rust_closed=M._v422_close_component_substrate_plan(rust_only)
check('Rust-only plan not polluted with JS/TS substrate',not any(Path(x['path']).name=='tsconfig.json' for x in rust_closed['files']),rust_closed['files'])

# Final coverage barrier regression: tests requested must survive all later plan merges.
coverage_request='Build a cross-platform app with import/export CSV and add real tests.'
coverage_manifest={'files':[{'path':'src/csv_io.py','purpose':'CSV import and export implementation'}]}
check('final plan gap recomputation catches dropped tests','tests' in M._v422_plan_gaps(coverage_request,coverage_manifest),M._v422_plan_gaps(coverage_request,coverage_manifest))
spec_manifest={'files':[{'path':'src/csv_io.py','purpose':'CSV import and export implementation'},{'path':'spec/csv_io_spec.rb','purpose':'RSpec behavior spec'}]}
check('spec-style test ownership satisfies generic test coverage','tests' not in M._v422_plan_gaps(coverage_request,spec_manifest),M._v422_plan_gaps(coverage_request,spec_manifest))

identity=M._v36_release_identity()
check('release identity V42.2',str(identity.get('version') or '').startswith('V42.') and identity.get('component_command_boundary_gate') is True and identity.get('final_plan_coverage_barrier') is True,identity)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
