import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('jarvis_local_qwen_project', HERE / 'local_qwen_project.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

checks = []
def check(name, condition, detail=''):
    checks.append((name, bool(condition), str(detail)))

check('V35.1 engine enabled', getattr(MOD, 'V351_REAL_RUN_HARDENING', False), getattr(MOD, 'V35_VERSION', 'missing'))
check('V35.1 version identity', getattr(MOD, 'V35_VERSION', '') == '35.1.0', getattr(MOD, 'V35_VERSION', 'missing'))

for prompt, expected in [
    ('Build a Tauri desktop app', 'tauri'),
    ('Build a SvelteKit website', 'sveltekit'),
    ('Build a Godot GDScript game', 'godot'),
    ('Build a React Native app', 'react_native'),
    ('Build an Unreal Engine 5 game', 'unreal'),
]:
    actual = MOD._v34_infer_toolchain(prompt)
    check(f'toolchain: {prompt}', actual == expected, f'expected={expected}, actual={actual}')

check('generic desktop request is not an explicit Python lock', MOD._v35_explicit_toolchain('Build a desktop calculator') == 'generic')
check('no-op test scripts are rejected', MOD._v35_is_noop_command('echo No tests configured'))

# Regression: salvage the exact V34.1 transport artifact seen after a valid Python candidate.
source = 'def ok():\n    return 1\n===== END FILE StockPilot/app/database.py =====\n'
cleaned = MOD._extract_single_file_response(source, 'StockPilot/app/database.py')
try:
    compile(cleaned, 'StockPilot/app/database.py', 'exec')
    transport_ok = 'END FILE' not in cleaned
except Exception:
    transport_ok = False
check('legacy END FILE contamination is salvaged', transport_ok, cleaned[-120:])

wrapped = '===== BEGIN FILE StockPilot/app/database.py =====\n' + source
cleaned2 = MOD._extract_single_file_response(wrapped, 'StockPilot/app/database.py')
try:
    compile(cleaned2, 'StockPilot/app/database.py', 'exec')
    begin_end_ok = 'BEGIN FILE' not in cleaned2 and 'END FILE' not in cleaned2
except Exception:
    begin_end_ok = False
check('legacy BEGIN/END transport envelope is salvaged', begin_end_ok, cleaned2[-120:])

# Regression: duplicate service providers should be caught before implementation.
collision_manifest = {'files': [
    {'path':'inventory_service.py','purpose':'Inventory service layer','exports':['InventoryService']},
    {'path':'StockPilot/app/service.py','purpose':'Inventory service layer','exports':['InventoryService']},
]}
collisions = MOD._v351_architecture_collision_issues(collision_manifest)
check('duplicate InventoryService provider is detected', bool(collisions), collisions)

safe_manifest = {'files': [
    {'path':'frontend/parser.py','purpose':'CSV parser','exports':['parse']},
    {'path':'backend/url_tools.py','purpose':'URL tokenizer','exports':['parse']},
]}
check('legal unrelated duplicate helper name is not over-collapsed', not MOD._v351_architecture_collision_issues(safe_manifest))

with tempfile.TemporaryDirectory(prefix='jarvis_v351_selftest_') as td:
    root = Path(td)
    (root / 'package.json').write_text(json.dumps({'name':'mixed','version':'1.0.0','scripts':{'build':'vite build'},'dependencies':{'@tauri-apps/api':'1','vite':'5'}}), encoding='utf-8')
    native = root / 'src-tauri'
    (native / 'src').mkdir(parents=True)
    (native / 'Cargo.toml').write_text('[package]\nname="mixed_native"\nversion="0.1.0"\nedition="2021"\n', encoding='utf-8')
    (native / 'src' / 'main.rs').write_text('fn main() {}\n', encoding='utf-8')
    comps = MOD._v35_discover_components(root, {'toolchain_adapter':'tauri', 'components':[]})
    kinds = {(c['root'], c['toolchain_adapter']) for c in comps}
    check('mixed repo discovers Node component', any(a in {'node','vite','react','nextjs','sveltekit','nuxt'} and r == '.' for r,a in kinds), sorted(kinds))
    check('mixed repo discovers Rust component', ('src-tauri','rust') in kinds, sorted(kinds))

# Regression: class-level constants such as InventoryView.COLUMNS are valid members.
with tempfile.TemporaryDirectory(prefix='jarvis_v351_classattrs_') as td:
    root = Path(td)
    app = root / 'app'; app.mkdir()
    (app / '__init__.py').write_text('', encoding='utf-8')
    (app / 'ui.py').write_text('class InventoryView:\n    COLUMNS = ("sku", "name")\n', encoding='utf-8')
    (app / 'consumer.py').write_text('from app.ui import InventoryView\n\ndef use():\n    view = InventoryView()\n    return view.COLUMNS\n', encoding='utf-8')
    manifest = {'entrypoint':'app/consumer.py','files':[
        {'path':'app/ui.py','purpose':'UI','exports':['InventoryView'],'depends_on':[],'contracts':[]},
        {'path':'app/consumer.py','purpose':'Consumer','exports':['use'],'depends_on':['app/ui.py'],'contracts':[]},
    ]}
    reqs = MOD._python_method_contract_requirements(root, manifest)
    false_columns = [k for k in reqs if k[1] == 'InventoryView' and k[2] == 'COLUMNS']
    check('class constant COLUMNS is not a false missing-member contract', not false_columns, false_columns)

# Regression: concrete service/database arity drift should be caught before wasting semantic repair calls.
with tempfile.TemporaryDirectory(prefix='jarvis_v351_signature_') as td:
    root = Path(td)
    app = root / 'app'; app.mkdir()
    (app / '__init__.py').write_text('', encoding='utf-8')
    (app / 'database.py').write_text(
        'class DatabaseManager:\n'
        '    def insert_item(self, sku, name, description, category, quantity, reorder_level, unit_cost, selling_price, supplier):\n'
        '        return 1\n', encoding='utf-8')
    (app / 'service.py').write_text(
        'from app.database import DatabaseManager\n'
        'class InventoryService:\n'
        '    def __init__(self, db: DatabaseManager):\n'
        '        self.db = db\n'
        '    def add(self, item):\n'
        '        return self.db.insert_item(item)\n', encoding='utf-8')
    manifest = {'entrypoint':'app/service.py','files':[
        {'path':'app/database.py','purpose':'database','exports':['DatabaseManager'],'depends_on':[],'contracts':[]},
        {'path':'app/service.py','purpose':'service','exports':['InventoryService'],'depends_on':['app/database.py'],'contracts':[]},
    ]}
    sig_issues = MOD._python_local_call_signature_issues(root, manifest)
    check('StockPilot-shaped DatabaseManager.insert_item signature drift is detected',
          any('missing required argument' in str(x.get('problem','')).lower() for x in sig_issues), sig_issues)

# Status must identify the actual V35.1 engine and derive progress from disk rather than stale counters.
with tempfile.TemporaryDirectory(prefix='jarvis_v351_status_') as td:
    root = Path(td)
    (root / 'main.py').write_text('print("ok")\n', encoding='utf-8')
    (root / 'later.py').write_text(f'# {MOD.V33_SKELETON_MARKER}\n', encoding='utf-8')
    manifest = {'files':[{'path':'main.py'},{'path':'later.py'}], 'components':[{'id':'app','root':'.','purpose':'app','toolchain_adapter':'python','depends_on':[]}]}
    old_ctx = MOD.qwen_runtime_context_tokens
    MOD.qwen_runtime_context_tokens = lambda: 262144
    try:
        MOD._v33_write_build_status(root, manifest, 'implementing', implemented=0)
    finally:
        MOD.qwen_runtime_context_tokens = old_ctx
    status = json.loads((root / MOD.V33_BUILD_STATUS_FILE).read_text(encoding='utf-8'))
    check('status reports V35.1 instead of legacy V34.1', status.get('version') == 'V35.1.0', status)
    check('status derives implemented file count from filesystem', status.get('implemented_source_files') == 1, status)
    check('status exposes 262K context capacity', status.get('context_capacity') == 262144, status.get('context_capacity'))

# Framework-aware noninteractive JS test commands.
for label, data, expected_runner, required_token in [
    ('Vitest', {'scripts':{'test':'vitest'}, 'devDependencies':{'vitest':'1'}}, 'vitest', 'run'),
    ('Jest', {'scripts':{'test':'jest'}, 'devDependencies':{'jest':'29'}}, 'jest', '--ci'),
    ('React Scripts', {'scripts':{'test':'react-scripts test'}, 'dependencies':{'react-scripts':'5'}}, 'react-scripts', '--watchAll=false'),
    ('Playwright', {'scripts':{'test':'playwright test'}, 'devDependencies':{'@playwright/test':'1'}}, 'playwright', '--reporter=line'),
    ('Mocha', {'scripts':{'test':'mocha'}, 'devDependencies':{'mocha':'10'}}, 'mocha', 'test'),
]:
    cmd, env, runner = MOD._v351_node_test_strategy(HERE, data)
    check(f'{label} runner is detected', runner == expected_runner, (runner, cmd))
    check(f'{label} command is noninteractive/CI-safe', required_token in cmd and env.get('CI') == 'true', cmd)

# Component ownership used by hierarchical refinement should keep nested native files with native component.
ownership_manifest = {
    'components': [
        {'id':'frontend','root':'.','purpose':'front','toolchain_adapter':'node','depends_on':[]},
        {'id':'native','root':'src-tauri','purpose':'native','toolchain_adapter':'rust','depends_on':['frontend']},
    ],
    'files': [
        {'path':'package.json'}, {'path':'src/main.ts'}, {'path':'src-tauri/Cargo.toml'}, {'path':'src-tauri/src/main.rs'}
    ]
}
owners = MOD._v351_component_owner_map(ownership_manifest)
check('hierarchical ownership keeps frontend root files in frontend', owners.get('src/main.ts') == 'frontend', owners)
check('hierarchical ownership keeps nested Rust files in native component', owners.get('src-tauri/src/main.rs') == 'native', owners)

# Evidence-first runtime preflight: when only speculative method-contract issues remain, an executed
# failure must be repaired before the legacy acceptance loop begins.
old_det = MOD._deterministic_acceptance_issues
old_real = MOD._run_real_project_validation
old_repair = MOD._repair_real_validation_failure
old_base = MOD._v351_base_acceptance_repair_cycle
old_status = MOD._v33_write_build_status
calls = []
state = {'real':0}
try:
    MOD._deterministic_acceptance_issues = lambda work, manifest: [{'file':'ui.py','kind':'method_contract','problem':'speculative member'}]
    def fake_real(work, request, manifest):
        state['real'] += 1
        if state['real'] == 1:
            calls.append('real-fail')
            return False, 'TypeError: DatabaseManager.insert_item() missing 8 required positional arguments'
        calls.append('real-pass')
        return True, 'ok'
    MOD._run_real_project_validation = fake_real
    MOD._repair_real_validation_failure = lambda *a, **k: calls.append('repair-runtime') or True
    MOD._v351_base_acceptance_repair_cycle = lambda *a, **k: calls.append('legacy-cycle') or (True, [])
    MOD._v33_write_build_status = lambda *a, **k: None
    ok, _ = MOD._acceptance_repair_cycle('request', {}, Path('.'), None)
finally:
    MOD._deterministic_acceptance_issues = old_det
    MOD._run_real_project_validation = old_real
    MOD._repair_real_validation_failure = old_repair
    MOD._v351_base_acceptance_repair_cycle = old_base
    MOD._v33_write_build_status = old_status
check('real runtime failure is prioritized before speculative static member repair', ok and calls[:3] == ['real-fail','repair-runtime','real-pass'], calls)
check('legacy acceptance loop still runs after evidence-first preflight', calls and calls[-1] == 'legacy-cycle', calls)

failed = [x for x in checks if not x[1]]
for name, ok, detail in checks:
    print(('PASS' if ok else 'FAIL') + ' - ' + name + (f' ({detail})' if detail else ''))
print()
print(f'V35.1 self-test: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
