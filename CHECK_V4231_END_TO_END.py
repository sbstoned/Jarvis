import sys, types, importlib.util, pathlib, shutil, tempfile, json

ROOT = pathlib.Path('/mnt/data')
SRC = ROOT / 'local_qwen_project_V42_31.py'
GEAR = ROOT / 'v4231_gear'

def load_module():
    m=types.ModuleType('multi_provider')
    m.ask_qwen=lambda *a,**k:(False,'stub')
    m.qwen_status=lambda *a,**k:{}
    m.qwen_runtime_context_tokens=lambda fallback,*a,**k:fallback
    m.ProjectTools=object
    sys.modules['multi_provider']=m
    q=types.ModuleType('qwen_model_manager')
    q.ensure_qwen_profile=lambda *a,**k:True
    q.normalize_profile=lambda x='auto':x
    q.active_profile=lambda:'9b35'
    q._runtime_context_tokens=lambda *a,**k:32768
    sys.modules['qwen_model_manager']=q
    spec=importlib.util.spec_from_file_location('lqp_v4231',SRC)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

mod=load_module();tests=[]
def check(name,cond,detail=''):
    tests.append((name,bool(cond),detail))

check('release identity',mod._v36_release_identity().get('version')=='V42.31.0',str(mod._v36_release_identity()))
check('universal engine name','END_TO_END' in mod._v36_release_identity().get('engine',''))

failure='''src/App.tsx(7,54): error TS2741: Property 'metrics' is missing in type '{}' but required in type 'DashboardViewProps'.
src/App.tsx(8,54): error TS2739: Type '{}' is missing the following properties from type 'InventoryViewProps': tools, categories
src/App.tsx(9,68): error TS2739: Type '{}' is missing the following properties from type 'CheckoutHistoryViewProps': tools, persons
src/hooks/useCSVImportExport.ts(66,24): error TS2322: Type '{ id: string; is_checked_out: string; }[]' is not assignable to type 'CSVRow[]'. Types of property 'is_checked_out' are incompatible. Type 'string' is not assignable to type 'boolean'.
src/hooks/useCSVImportExport.ts(138,19): error TS2345: Argument of type 'Partial<CSVRow>' is not assignable to parameter of type 'CSVRow'.
src/hooks/useCSVImportExport.ts(145,17): error TS2345: Argument of type 'Partial<CSVRow>' is not assignable to parameter of type 'CSVRow'.
src/hooks/useTools.ts(14,52): error TS2339: Property 'updateToolCommand' does not exist on type '{}'.
src/hooks/useTools.ts(14,71): error TS2339: Property 'deleteToolCommand' does not exist on type '{}'.'''
rows=mod._v4222_parse_ts_diagnostics(GEAR,failure)
check('8-error fixture parsed',len(rows)==8,str(rows))

td=pathlib.Path(tempfile.mkdtemp())/'p';shutil.copytree(GEAR,td)
changed,reasons=mod._v4231_apply_small_tail_source_fixes(td,rows)
app=(td/'src/App.tsx').read_text();tools=(td/'src/hooks/useTools.ts').read_text();csv=(td/'src/hooks/useCSVImportExport.ts').read_text()
check('small-tail edits exact root files',set(changed)=={'src/App.tsx','src/hooks/useTools.ts','src/hooks/useCSVImportExport.ts'},str(changed))
check('react metrics wired','DashboardView metrics={metrics}' in app)
check('inventory props wired','InventoryView tools={tools} categories={categories}' in app)
check('checkout props wired','CheckoutHistoryView tools={tools} persons={persons}' in app)
check('update alias repaired','updateTool: updateToolCommand' in tools)
check('delete alias repaired','deleteTool: deleteToolCommand' in tools)
check('csv boolean preserved','is_checked_out: tool.is_checked_out ? "true" : "false"' not in csv)
check('csv partial parser removed','Partial<CSVRow>' not in csv)

issues0=mod._v4231_end_to_end_issues(td,{})
kinds0={x['kind'] for x in issues0}
check('rust reachability detected','v4231_rust_reachability' in kinds0,str(issues0))
check('tauri commands detected missing','v4231_tauri_commands_missing' in kinds0,str(issues0))
check('db lifecycle detected','v4231_database_lifecycle' in kinds0,str(issues0))
check('mock integration detected','v4231_mock_integration' in kinds0,str(issues0))
check('navigation defect detected','v4231_navigation_state' in kinds0,str(issues0))

mods=mod._v4231_expose_tauri_modules(td,{})
lib=(td/'src-tauri/src/lib.rs').read_text()
check('filesystem modules exposed',bool(mods) and 'pub mod tools;' in lib and 'pub mod models;' in lib,str(mods))
issues1=mod._v4231_end_to_end_issues(td,{})
check('reachability clears after exposure','v4231_rust_reachability' not in {x['kind'] for x in issues1},str(issues1))

plain=pathlib.Path(tempfile.mkdtemp())
(plain/'src').mkdir();(plain/'src/main.py').write_text('print("hi")\n')
check('non-tauri project not overfit',mod._v4231_end_to_end_issues(plain,{})==[],str(mod._v4231_end_to_end_issues(plain,{})))

shutil.rmtree(td.parent,ignore_errors=True);shutil.rmtree(plain,ignore_errors=True)
passed=sum(1 for _,ok,_ in tests if ok)
for name,ok,detail in tests:
    print(('PASS' if ok else 'FAIL'),name,('' if ok else detail))
print(f'RESULT {passed}/{len(tests)}')
if passed!=len(tests):raise SystemExit(1)
