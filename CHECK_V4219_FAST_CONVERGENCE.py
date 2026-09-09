import json, os, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('JARVIS_QWEN_MODEL','auto')
import local_qwen_project as j
import jarvis_v42_runtime as rt
PASS=0;FAIL=0

def ck(name,cond,detail=''):
    global PASS,FAIL
    if cond: PASS+=1;print('PASS',name)
    else: FAIL+=1;print('FAIL',name,detail)

def write(p,text='x'):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
ck('V42.19 identity',ident.get('version')=='V42.19.0',ident)
for key in ('routine_generation_on_fast_worker','acceptance_keyword_no_longer_promotes_generation','27b_reserved_for_evidence_backed_root_cause','persistent_topology_tombstones','project_root_issue_never_file_generated','strict_node_import_specifier_parser','deterministic_package_lock_reconciliation','conventional_tauri_asset_recovery','missing_soft_tests_not_hard_generation_debt','real_build_test_runtime_evidence_authoritative'):
    ck(key,bool(ident.get(key)),ident.get(key))

# Model routing: acceptance source emission is routine; true root cause remains specialist.
target,reason=j._v426_auto_target('Generating src-tauri/tests/acceptance_2.rs (1/1)','generate','write the file')
ck('acceptance test generation stays on 9B worker',target==j.V426_AUTO_WORKER,(target,reason))
target2,reason2=j._v426_auto_target('cross-component integration root-cause after cargo build failure','audit','compiler evidence')
ck('evidence-backed root cause can use 27B',target2==j.V426_AUTO_SPECIALIST,(target2,reason2))
ck('per-file LLM semantic audit off by default',j.QWEN_FILE_AUDIT is False,j.QWEN_FILE_AUDIT)
ck('acceptance rounds bounded',j.PROJECT_ACCEPTANCE_ROUNDS<=j.V4219_MAX_ACCEPTANCE_ROUNDS,j.PROJECT_ACCEPTANCE_ROUNDS)
ck('no-progress limit bounded',j.PROJECT_ACCEPTANCE_NO_PROGRESS_LIMIT<=2,j.PROJECT_ACCEPTANCE_NO_PROGRESS_LIMIT)

# Current Rust topology permanently retires stale flat alias from manifest debt.
with tempfile.TemporaryDirectory(prefix='v4219_topology_') as td:
    w=Path(td);write(w/'src-tauri/src/models/mod.rs','pub mod tool;\n')
    m={'_original_user_request':'finish app','files':[{'path':'src-tauri/src/models.rs','depends_on':[]},{'path':'src-tauri/src/models/mod.rs','depends_on':[]}], 'components':[{'id':'native','root':'src-tauri','toolchain_adapter':'tauri'}]}
    retired=j._v4219_reconcile_manifest_topology(w,m)
    paths=[x.get('path') for x in m.get('files') or []]
    ck('flat Rust alias retired','src-tauri/src/models.rs' not in paths,(retired,paths))
    ck('topology tombstone persisted',j._v4219_is_tombstoned(w,'src-tauri/src/models.rs'),j._v4219_tombstones(w))
    missing=j._missing_manifest_files(w,m)
    ck('tombstoned provider not re-required','src-tauri/src/models.rs' not in missing,missing)

# Project-root diagnostics must never hit file generation.
with tempfile.TemporaryDirectory(prefix='v4219_root_') as td:
    ok,wrote=j._generate_planned_file('finish',{},Path(td),{'path':'.','purpose':'project build issue'})
    ck('project root generation suppressed',not ok and wrote=='.',(ok,wrote))

# Strict import classification: relative/punctuation are never npm packages.
src='''import x from "./types";\nimport y from ".";\nimport React from "react";\nimport { invoke } from "@tauri-apps/api/core";\n'''
pkgs=j._v4219_strict_node_packages(src)
ck('strict imports keep real packages',pkgs==['react','@tauri-apps/api'],pkgs)
ck('strict imports drop dot/pipe artifacts','.' not in pkgs and '|' not in pkgs,pkgs)

# Missing soft tests do not block a normal project; explicit tests remain obligations.
with tempfile.TemporaryDirectory(prefix='v4219_tests_') as td:
    w=Path(td);m={'_original_user_request':'build an app','files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/acceptance.test.tsx','depends_on':[]}]} ;write(w/'src/main.ts','export {};\n')
    ck('planner-invented missing acceptance test is soft',j._missing_manifest_files(w,m)==[],j._missing_manifest_files(w,m))
    m['_original_user_request']='build an app and include tests'
    ck('explicitly requested missing test remains hard','tests/acceptance.test.tsx' in j._missing_manifest_files(w,m),j._missing_manifest_files(w,m))

# Every deterministic tsconfig.node writer must be project-reference compatible.
with tempfile.TemporaryDirectory(prefix='v4219_tsconfig_') as td:
    w=Path(td);write(w/'vite.config.ts','export default {};\n');j._v4210_write_tsconfig_node(w)
    d=json.loads((w/'tsconfig.node.json').read_text(encoding='utf-8'))
    opts=d.get('compilerOptions') or {}
    ck('tsconfig.node composite enabled',opts.get('composite') is True,opts)
    ck('tsconfig.node avoids noEmit reference conflict',opts.get('noEmit') is not True,opts)
    ck('tsconfig.node uses declaration-only emit',opts.get('emitDeclarationOnly') is True,opts)

# Tauri conventional icons should exist before a Cargo/Tauri build asks for them.
with tempfile.TemporaryDirectory(prefix='v4219_tauri_') as td:
    w=Path(td);write(w/'src-tauri/Cargo.toml','[package]\nname="x"\nversion="0.1.0"\n[dependencies]\ntauri="2"\n')
    write(w/'src-tauri/tauri.conf.json','{"$schema":"https://schema.tauri.app/config/2"}')
    changed=j._v4219_tauri_default_assets(w)
    ck('Tauri icon.ico deterministic recovery',(w/'src-tauri/icons/icon.ico').is_file(),changed)
    ck('Tauri PNG deterministic recovery',(w/'src-tauri/icons/128x128.png').is_file(),changed)

# Structural npm lock drift detection is deterministic and network-free.
with tempfile.TemporaryDirectory(prefix='v4219_lock_') as td:
    w=Path(td);write(w/'package.json',json.dumps({'dependencies':{'react':'^19.0.0'}}))
    write(w/'package-lock.json',json.dumps({'lockfileVersion':3,'packages':{'':{'dependencies':{}}}}))
    ck('stale lock detected structurally',j._v4219_node_lock_structurally_stale(w), '')
    write(w/'package-lock.json',json.dumps({'lockfileVersion':3,'packages':{'':{'dependencies':{'react':'^19.0.0'}},'node_modules/react':{'version':'19.0.0'}}}))
    ck('structurally synced lock accepted',not j._v4219_node_lock_structurally_stale(w), '')

# Sandbox: safe compiler formatting flag is allowed; external CWD/shell policy remains.
with tempfile.TemporaryDirectory(prefix='v4219_broker_') as td:
    w=Path(td);b=rt.CommandBroker(w)
    allowed,reason=b._policy(['cargo','check','--message-format','short'],w)
    ck('cargo --message-format is not destructive',allowed,reason)
    outside=w.parent.resolve();r=b.run(['python','--version'],cwd=outside,timeout=2)
    ck('sandbox still blocks external cwd',r.blocked,r.reason)

# Project-local executable resolution should outrank a random global tsc.
with tempfile.TemporaryDirectory(prefix='v4219_tools_') as td:
    w=Path(td);local=w/'node_modules/.bin/tsc';write(local,'shim')
    b=rt.CommandBroker(w);cmd=b._resolve_command(['tsc','--version'],w)
    ck('project-local tsc resolution',Path(cmd[0]).resolve()==local.resolve(),cmd)

# Fast defaults: routine leaves cannot consume the old 12-15 minute wall budgets.
ck('file generation wall capped',j.FILE_GENERATION_WALL_SECONDS<=480,j.FILE_GENERATION_WALL_SECONDS)
ck('file repair wall capped',j.FILE_REPAIR_WALL_SECONDS<=360,j.FILE_REPAIR_WALL_SECONDS)
ck('legacy 27B plan timeout capped',j.V427_27B_PLAN_TIMEOUT<=j.V4219_27B_MAX_SECONDS,j.V427_27B_PLAN_TIMEOUT)
ck('legacy 27B repair timeout capped',j.V427_27B_REPAIR_TIMEOUT<=j.V4219_27B_MAX_SECONDS,j.V427_27B_REPAIR_TIMEOUT)

# Planner-invented missing test files are pruned before expensive implementation;
# existing tests and explicitly requested tests remain intact.
with tempfile.TemporaryDirectory(prefix='v4219_manifest_fast_') as td:
    w=Path(td)
    m={'files':[{'path':'src/main.ts','depends_on':[]},{'path':'tests/acceptance.test.tsx','depends_on':['src/main.ts']}],
       'implementation_order':['src/main.ts','tests/acceptance.test.tsx'],
       'components':[{'id':'web','root':'.','toolchain_adapter':'vite','test_command':'npm test'}]}
    fast=j._v4219_prune_soft_missing_tests_from_manifest('build me an app',m,w)
    fpaths=[x.get('path') for x in fast.get('files') or []]
    ck('missing planner QA source pruned before implementation','tests/acceptance.test.tsx' not in fpaths,fpaths)
    ck('soft test command removed without test source',not str((fast.get('components') or [{}])[0].get('test_command') or '').strip(),fast.get('components'))
    write(w/'tests/existing.test.ts','export {};\n')
    m2={'files':[{'path':'tests/existing.test.ts','depends_on':[]}], 'components':[{'id':'web','root':'.','toolchain_adapter':'vite','test_command':'npm test'}]}
    kept=j._v4219_prune_soft_missing_tests_from_manifest('build me an app',m2,w)
    ck('existing tests preserved',[x.get('path') for x in kept.get('files') or []]==['tests/existing.test.ts'],kept)
    explicit=j._v4219_prune_soft_missing_tests_from_manifest('build me an app with tests',m,w)
    ck('explicit requested tests preserved','tests/acceptance.test.tsx' in [x.get('path') for x in explicit.get('files') or []],explicit)

safe,why=rt.CommandBroker._batch_payload_safe(['npm.cmd','install','--package-lock-only'])
ck('trusted Windows batch shim arguments accepted',safe,why)
unsafe,why2=rt.CommandBroker._batch_payload_safe(['npm.cmd','run','build&whoami'])
ck('batch shim shell metacharacters rejected',not unsafe,why2)

ck('runtime identity upgraded',rt.V42_RUNTIME_VERSION=='42.19.0',(rt.V42_RUNTIME_VERSION,rt.V42_RUNTIME_ENGINE))
print(f'RESULT {PASS}/{PASS+FAIL} PASS')
report={'version':'V42.19.0','pass':PASS,'fail':FAIL,'total':PASS+FAIL,'identity':ident}
(ROOT/'V42_19_VALIDATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(1 if FAIL else 0)
