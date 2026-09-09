from pathlib import Path
import json, tempfile, sys

import jarvis_v42_runtime as R
import local_qwen_project as M

checks=[]
def check(name, ok, detail=''):
    checks.append((name,bool(ok),detail))
    print(('PASS' if ok else 'FAIL')+': '+name+((' -- '+str(detail)) if detail else ''))

# Runtime discovery / summary
caps=R.discover_capabilities(probe_versions=False, only=['python','git','node','npm','cargo','rustc','docker','wsl'])
check('runtime identity',tuple(map(int, caps.get('version', '0.0.0').split('.'))) >= (42, 0, 0) and caps.get('engine')==R.V42_RUNTIME_ENGINE)
check('controlled native backend always available',(caps.get('sandbox_backends') or {}).get('native_controlled') is True)
check('capability inventory contains virtual compiler capabilities','c compiler' in (caps.get('tools') or {}) and 'c++ compiler' in (caps.get('tools') or {}))

# Deterministic readiness resolver independent of this Linux host.
fake_caps={'tools':{
    'node':{'available':True},'npm':{'available':True},'cargo':{'available':True},'rustc':{'available':True},
},'sandbox_backends':{'native_controlled':True,'docker':False,'wsl':False}}
toolchains=R.load_toolchains(Path(__file__).parent)
manifest={'toolchain_adapter':'tauri','components':[{'id':'ui','toolchain_adapter':'react'},{'id':'tauri-core','toolchain_adapter':'rust'}]}
ready=R.resolve_requirements(manifest,fake_caps,toolchains)
check('Tauri readiness derives Node/npm/Cargo/Rust',ready.get('status')=='READY' and not ready.get('missing'),ready)

fake_missing={'tools':{'node':{'available':True},'npm':{'available':True},'cargo':{'available':False},'rustc':{'available':False}},'sandbox_backends':{'native_controlled':True}}
not_ready=R.resolve_requirements(manifest,fake_missing,toolchains)
check('missing required tools are explicit',set(not_ready.get('missing') or []) >= {'cargo','rustc'},not_ready.get('missing'))

# Broker: direct no-shell success, structured log, destructive block.
with tempfile.TemporaryDirectory(prefix='jarvis_v42_broker_test_') as td:
    root=Path(td)
    broker=R.CommandBroker(root)
    result=broker.run([sys.executable,'-c','print("broker-ok")'],timeout=10)
    check('command broker executes direct compiler/tool process',result.ok and 'broker-ok' in result.combined,result.combined)
    check('command broker writes structured evidence',broker.log_path.exists() and 'returncode' in broker.log_path.read_text(encoding='utf-8'))
    blocked=broker.run(['format','C:'],timeout=2)
    check('command broker blocks destructive host-management command',blocked.blocked and not blocked.ok,blocked.reason)
    shellish=broker.run([sys.executable,'-c','print(1)','&&','echo','bad'],timeout=2)
    check('command broker rejects shell-control tokens',shellish.blocked and not shellish.ok,shellish.reason)

# Plan coverage regression from current GearTrack-style under-plan.
request=('Build GearTrack with React TypeScript Vite Tauri Rust SQLite. Add/edit/delete tools, organize categories, '
         'search and filter, check tools in and out, keep checkout history, dashboard, import/export CSV, and add real tests.')
under={'files':[
    {'path':'src/components/Dashboard.tsx','purpose':'Dashboard UI'},
    {'path':'src/components/ToolsList.tsx','purpose':'Search and filter tool inventory'},
    {'path':'src-tauri/src/domain/entities.rs','purpose':'Canonical Tool Category CheckoutEvent entities'},
    {'path':'src-tauri/src/domain/enums.rs','purpose':'Canonical checkout enums'},
]}
gaps=R.plan_coverage_gaps(request,under)
check('plan coverage catches missing CSV implementation','csv_import_export' in gaps,gaps)
check('plan coverage catches missing real tests','tests' in gaps,gaps)
check('domain CheckoutEvent does not falsely satisfy checkout behavior','checkout' in gaps,gaps)

covered={'files':under['files']+[
    {'path':'src-tauri/src/services/checkout.rs','purpose':'Implements check-out, check-in and checkout history workflows'},
    {'path':'src-tauri/src/services/csv_io.rs','purpose':'CSV import and export implementation'},
    {'path':'src-tauri/tests/checkout_tests.rs','purpose':'Real checkout and persistence tests'},
    {'path':'src/components/CategoryManager.tsx','purpose':'Organize categories'},
]}
gaps2=R.plan_coverage_gaps(request,covered)
check('covered plan clears CSV/tests/checkout gaps',not {'csv_import_export','tests','checkout'}.intersection(gaps2),gaps2)

# Canonical owner regression: exact enum provider must beat a type alias in entities.rs.
owner_manifest={
    'components':[{'id':'tauri-core','root':'src-tauri','toolchain_adapter':'rust','depends_on':[]}],
    'canonical_domain_contracts':{'entities':[{'name':'Tool','fields':[{'name':'id','required':True}]}], 'enums':[{'name':'ConditionType','values':['Good','Bad']}]},
    'files':[
      {'path':'src-tauri/src/domain/entities.rs','purpose':'Canonical Rust Tool entity','phase':'foundation','exports':[],'contracts':['pub struct Tool { id: String }','pub type ConditionType = String;']},
      {'path':'src-tauri/src/domain/enums.rs','purpose':'Canonical Rust enum definitions for ConditionType','phase':'foundation','exports':[],'contracts':['pub enum ConditionType { Good, Bad }']},
    ]
}
owners=M._v40_domain_owner_map(owner_manifest)
scope=M._v38_component_scope(owner_manifest,'src-tauri/src/domain/enums.rs')
check('exact enum provider wins canonical ownership',owners.get((scope,'ConditionType'))=='src-tauri/src/domain/enums.rs',owners)
reconciled=M._v42_reconcile_nonowner_contracts(owner_manifest)
entity_item=next(x for x in reconciled['files'] if x['path'].endswith('entities.rs'))
check('non-owner enum alias contract quarantined',not any('ConditionType' in str(x) and 'type' in str(x) for x in entity_item.get('contracts') or []),entity_item.get('contracts'))

# Integration identity and startup wiring.
identity=M._v36_release_identity()
check('Jarvis release identity V42+',str(identity.get('version') or '').startswith('V42.') and identity.get('controlled_command_broker') is True,identity)
plan_prompt=M._project_plan_prompt(request,80)
check('planner receives capability evidence','V42 HOST CAPABILITY EVIDENCE' in plan_prompt)
check('planner receives behavior coverage ledger','REQUESTED-BEHAVIOR COVERAGE LEDGER' in plan_prompt)
jarvis_text=(Path(__file__).parent/'jarvis.py').read_text(encoding='utf-8',errors='replace')
check('Jarvis startup launches background capability scan','start_background_startup_scan' in jarvis_text)
check('Jarvis online status surfaces developer runtime','Developer runtime:' in jarvis_text)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed==len(checks) else 1)
