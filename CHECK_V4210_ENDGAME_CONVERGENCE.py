from pathlib import Path
import tempfile, json, sys, shutil
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as j
import jarvis_v42_runtime as rt

checks=[]
def ck(name,cond,detail=''):
    checks.append((name,bool(cond),detail))

# 1) Requirement owner can satisfy its own debt without weakening final acceptance.
with tempfile.TemporaryDirectory() as td:
    w=Path(td); (w/'tests').mkdir(parents=True)
    manifest={
      'components':[{'id':'ui','root':'.','toolchain_adapter':'react','test_command':'npm test'}],
      'files':[{'path':'tests/acceptance.test.tsx','purpose':'real tests','phase':'test','v423_requirement_debt':'tests','requirements':['tests'],'contracts':['V42.3 requirement debt owner for tests.']}]
    }
    (w/'tests/acceptance.test.tsx').write_text("import { describe, expect, it } from 'vitest';\nimport App from '../src/App';\ndescribe('x',()=>{it('y',()=>{expect(typeof App).toBe('function')})});\n",encoding='utf-8')
    # Ledger exists but this test is intentionally not accepted yet -> old V42.9 would circularly reject it.
    (w/'.jarvis_v413_accepted_revisions.json').write_text(json.dumps({'files':{'dummy.ts':{'sha256':'x'}}}),encoding='utf-8')
    issues=j._v361_current_file_foundation_issues(w,manifest,'tests/acceptance.test.tsx')
    ck('self debt issue filtered while evaluating its owner',not any('requirement debt unresolved' in str(x.get('problem','')).lower() for x in issues),issues)
    final=j._deterministic_acceptance_issues(w,manifest)
    ck('final acceptance still sees unaccepted test debt',any('requirement debt unresolved' in str(x.get('problem','')).lower() for x in final),final)

# 2) Conventional configs are deterministic and valid.
with tempfile.TemporaryDirectory() as td:
    w=Path(td)
    ck('tsconfig.node deterministic writer',j._v4210_write_tsconfig_node(w,'tsconfig.node.json'))
    cfg=json.loads((w/'tsconfig.node.json').read_text(encoding='utf-8'))
    ck('tsconfig.node valid json with noEmit',cfg.get('compilerOptions',{}).get('noEmit') is True,cfg)

# 3) Compatibility barrel resolves grouped type file rather than redefining canonical type.
with tempfile.TemporaryDirectory() as td:
    w=Path(td); (w/'src/types').mkdir(parents=True)
    manifest={
      'canonical_domain_contracts':{'entities':[{'name':'CheckoutRecord','fields':[{'name':'id','required':True}]}]},
      'components':[{'id':'ui','root':'.','toolchain_adapter':'react'}],
      'files':[
        {'path':'src/types/checkout_record.ts','purpose':'canonical CheckoutRecord model','phase':'data','exports':['CheckoutRecord'],'contracts':['CheckoutRecord']},
        {'path':'src/types/checkout.ts','purpose':'checkout-related type definitions','phase':'foundation','exports':[],'contracts':[]},
      ]
    }
    (w/'src/types/checkout_record.ts').write_text('export interface CheckoutRecord { id: string }\n',encoding='utf-8')
    ck('checkout compatibility barrel generated',j._v4210_write_ts_contract_barrel(w,manifest,'src/types/checkout.ts'))
    txt=(w/'src/types/checkout.ts').read_text(encoding='utf-8')
    ck('barrel reexports canonical CheckoutRecord','CheckoutRecord' in txt and 'checkout_record' in txt and 'interface CheckoutRecord' not in txt,txt)

# 4) Provider-safe Rust test seed imports production contracts and has a real assertion.
with tempfile.TemporaryDirectory() as td:
    w=Path(td); (w/'src-tauri/src/models').mkdir(parents=True); (w/'src-tauri/tests').mkdir(parents=True)
    manifest={
      'canonical_domain_contracts':{'entities':[{'name':'Tool','fields':[{'name':'id','required':True}]}]},
      'components':[{'id':'tauri-core','root':'src-tauri','toolchain_adapter':'rust','test_command':'cargo test'}],
      'files':[
        {'path':'src-tauri/src/models/tool.rs','purpose':'canonical Tool model','phase':'data','exports':['Tool'],'contracts':['Tool']},
        {'path':'src-tauri/src/models/mod.rs','purpose':'model module hub','phase':'foundation','exports':[],'contracts':[]},
        {'path':'src-tauri/tests/acceptance_2.rs','purpose':'real acceptance tests','phase':'test','v423_requirement_debt':'tests','requirements':['tests']},
      ]
    }
    (w/'src-tauri/src/models/tool.rs').write_text('#[derive(Debug)]\npub struct Tool { pub id: String }\n',encoding='utf-8')
    (w/'src-tauri/src/models/mod.rs').write_text('pub mod tool;\npub use tool::Tool;\n',encoding='utf-8')
    ck('provider-safe rust test seed created',j._v4210_write_provider_safe_test_seed(w,manifest,'src-tauri/tests/acceptance_2.rs'))
    txt=(w/'src-tauri/tests/acceptance_2.rs').read_text(encoding='utf-8')
    ck('rust seed does not redeclare Tool','struct Tool' not in txt and 'use models::{Tool}' in txt,txt)
    ck('rust seed has test and assertion','#[test]' in txt and 'assert!' in txt,txt)

# 5) Rust crate root exposes all planned top-level production modules.
with tempfile.TemporaryDirectory() as td:
    w=Path(td); (w/'src-tauri/src/models').mkdir(parents=True)
    (w/'src-tauri/src/lib.rs').write_text('pub fn run() {}\n',encoding='utf-8')
    (w/'src-tauri/src/db.rs').write_text('pub fn init() {}\n',encoding='utf-8')
    (w/'src-tauri/src/models/mod.rs').write_text('',encoding='utf-8')
    manifest={'components':[{'id':'core','root':'src-tauri','toolchain_adapter':'rust'}],'files':[
      {'path':'src-tauri/src/lib.rs','phase':'foundation'},{'path':'src-tauri/src/db.rs','phase':'service'},{'path':'src-tauri/src/models/mod.rs','phase':'data'}]}
    comp=manifest['components'][0]
    ck('rust module closure modifies crate root',j._v4210_harden_rust_crate_root(w,manifest,comp))
    lib=(w/'src-tauri/src/lib.rs').read_text(encoding='utf-8')
    ck('rust module closure exposes db and models','pub mod db;' in lib and 'pub mod models;' in lib,lib)

# 6) Command broker must allow safe cargo check with --message-format.
with tempfile.TemporaryDirectory() as td:
    b=rt.CommandBroker(Path(td))
    allowed,reason=b._policy(['cargo','check','--message-format','short'],Path(td))
    ck('cargo check message-format not falsely blocked',allowed,reason)

# 7) Test substrate closes React/Vite runner config and commands.
manifest={
 'components':[{'id':'ui','root':'.','toolchain_adapter':'react','test_command':''},{'id':'core','root':'src-tauri','toolchain_adapter':'rust','test_command':''}],
 'files':[{'path':'src/main.tsx','phase':'foundation'},{'path':'tests/acceptance.test.tsx','phase':'test','v423_requirement_debt':'tests'},
          {'path':'src-tauri/src/lib.rs','phase':'foundation'},{'path':'src-tauri/tests/acceptance_2.rs','phase':'test','v423_requirement_debt':'tests'}]
}
closed=j._v4210_close_test_substrate_plan(manifest)
ui=closed['components'][0];core=closed['components'][1]
ck('react test command restored',ui.get('test_command')=='npm test',ui)
ck('rust test command restored',core.get('test_command')=='cargo test',core)
ck('vitest config planned',any(x.get('path')=='vitest.config.ts' for x in closed['files']),[x.get('path') for x in closed['files']])

# 8) Exact 204118 regression shape: self-debt must not block acceptance_2.
SRC=ROOT.parent/'project_20260831_204118.zip'
if not SRC.exists(): SRC=Path('/mnt/data/project_20260831_204118.zip')
if SRC.exists():
    import zipfile
    with tempfile.TemporaryDirectory() as td:
        w=Path(td)
        with zipfile.ZipFile(SRC) as z:z.extractall(w)
        roots=[x for x in w.iterdir() if x.is_dir()]
        proj=roots[0] if len(roots)==1 else w
        arch=json.loads((proj/'JARVIS_V33_ARCHITECTURE.json').read_text(encoding='utf-8'))
        # Materialize the provider-safe seed and verify circular debt is absent from current-file gate.
        ok=j._v4210_write_provider_safe_test_seed(proj,arch,'src-tauri/tests/acceptance_2.rs')
        issues=j._v361_current_file_foundation_issues(proj,arch,'src-tauri/tests/acceptance_2.rs')
        ck('204118 exact test-debt deadlock removed',ok and not any('requirement debt unresolved: tests' in str(x.get('problem','')).lower() for x in issues),issues)
        # Conventional endgame files are repairable without Qwen.
        ck('204118 tsconfig.node can be generated deterministically',j._v4210_write_tsconfig_node(proj,'tsconfig.node.json'))
        ck('204118 checkout grouped type can become canonical barrel',j._v4210_write_ts_contract_barrel(proj,arch,'src/types/checkout.ts'))
else:
    ck('204118 regression workspace available',False,'missing uploaded replay zip')

# 9) Release identity.
r=j._v36_release_identity()
ck('release identity V42.10-compatible or newer',str(r.get('version') or '').startswith('V42.'),r.get('version'))
ck('true whole project audit advertised',r.get('true_every_component_whole_project_audit') is True,r)
ck('strict zero-debt publish gate preserved',r.get('strict_zero_debt_publish_gate') is True,r)
ck('new 27B remains AUTO specialist',r.get('auto_specialist_profile')=='27b38q2',r.get('auto_specialist_profile'))
ck('legacy 27B excluded from AUTO',r.get('legacy_27b_auto_eligible') is False,r.get('legacy_27b_auto_eligible'))

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL'),name,detail if detail else '')
print(f'RESULT {len(checks)-len(failed)}/{len(checks)} PASS')
if failed:raise SystemExit(1)
