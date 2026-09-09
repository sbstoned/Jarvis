import importlib.util, json, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('jarvis_v362',HERE/'local_qwen_project.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
checks=[]
def check(name, condition, detail=''):
    checks.append((name,bool(condition),str(detail)))

prompt='''Build a complete production-quality local application named TaskForge.
TaskForge is a personal project and task management application for Windows.
Use this technology stack:
Frontend: React + TypeScript + Vite
Backend: Python 3 + FastAPI
Database: SQLite
The frontend and backend must be separate components in the same repository.
The application must work locally without cloud services, paid APIs, authentication providers, or external databases.

Core functionality
Users must be able to:
create projects
edit projects
delete projects
view projects
search projects
filter projects by status
filter projects by priority

Acceptance tests
Before declaring the project complete, verify:
Backend dependencies install successfully in a clean Python environment.
Frontend dependencies install successfully.
All Python files compile.
TypeScript compilation succeeds.
Backend automated tests pass.
Frontend automated tests pass when configured.
React production build succeeds.
FastAPI starts successfully.
SQLite initializes successfully.
A project can be created through the API.
The created project can be retrieved.
The project can be edited.
A task can be added to the project.
The task can be marked complete.
Dashboard statistics accurately reflect stored data.
Data remains after closing and reopening the database.
Invalid API requests return useful errors rather than crashing.
Frontend API contracts match backend API contracts.
No unfinished contract skeletons remain.
No TODO-only implementations, pass placeholders, fake success scripts, duplicate providers, or unfinished methods remain.

Repair behavior
If any test, compile, build, runtime, integration, contract, or acceptance check fails, determine the actual root cause.
Prefer the smallest targeted patch rather than rewriting entire working files.
After a repair, rerun the directly affected test first, then the broader relevant test suite.
Continue implementation and repair until every validation step that can be executed on the host passes.
'''

check('V37 identity',M.V36_VERSION=='37.0.0',M.V36_VERSION)
source=M._v361_extract_source_requirements(prompt)
check('frozen source ledger is nonempty',len(source)>=30,len(source))
check('all 20 plain acceptance lines are frozen',sum(x['category']=='acceptance' for x in source)>=20,sum(x['category']=='acceptance' for x in source))
check('repair behavior plain lines are frozen',sum('targeted patch' in x['text'].lower() for x in source)>=1,source[-8:])
check('explicit frontend stack frozen',any('React + TypeScript + Vite' in x['text'] for x in source),source[:8])
check('explicit backend stack frozen',any('Python 3 + FastAPI' in x['text'] for x in source),source[:8])

# JSONC must accept legal tsconfig comments/trailing commas while strict JSON remains strict.
ts='''{
  // TypeScript config comment
  "compilerOptions": {
    "target": "ES2022",
    /* bundler */
    "moduleResolution": "bundler",
  },
}'''
with tempfile.TemporaryDirectory(prefix='v362_jsonc_') as td:
    check('tsconfig JSONC comments/trailing commas accepted',M._v36_precommit_candidate_error(Path(td),'frontend/tsconfig.json',ts)=='',M._v36_precommit_candidate_error(Path(td),'frontend/tsconfig.json',ts))
    check('package.json remains strict JSON',bool(M._v36_precommit_candidate_error(Path(td),'frontend/package.json','{"scripts":{},}')))
    check('invalid JSONC still rejected',bool(M._v36_precommit_candidate_error(Path(td),'frontend/tsconfig.json','{"compilerOptions": { bad }}')))

# No vacuous coverage: even an unstructured one-line prompt gets a frozen source item.
simple=M._v361_extract_source_requirements('Make me a calculator')
check('unstructured prompt still has source ledger',len(simple)>=1,simple)

# Tiny complex manifests are rejected before implementation.
spec={'source_requirements':[{'id':f'UR-{i:03d}','category':'functional','text':f'req {i}'} for i in range(1,61)],'coverage_valid':True,'coverage_percent':100}
tiny={'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'},{'id':'backend','root':'backend','toolchain_adapter':'python'}],
      'files':[{'path':f'frontend/f{i}.ts','purpose':'x','phase':'ui','depends_on':[],'exports':[],'contracts':[]} for i in range(1,6)]+[{'path':f'backend/f{i}.py','purpose':'x','phase':'service','depends_on':[],'exports':[],'contracts':[]} for i in range(1,7)]}
issues=M._v362_manifest_completeness_issues(tiny,spec,prompt,160)
check('11-file complex emergency architecture rejected',any('suspiciously small' in x for x in issues),issues)

# depends_on closure must be proven.
mf={'components':[{'id':'app','root':'.','toolchain_adapter':'python','entrypoint':'main.py'}],
    'files':[{'path':'requirements.txt','purpose':'deps','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
             {'path':'main.py','purpose':'entry','phase':'integration','depends_on':['missing.py'],'exports':[],'contracts':[]},
             {'path':'tests/test_main.py','purpose':'test','phase':'test','depends_on':['main.py'],'exports':[],'contracts':[]}]}
issues=M._v362_manifest_completeness_issues(mf,{'source_requirements':[{'id':'UR-1','text':'x'}],'coverage_valid':True,'coverage_percent':100},'Build a Python app',40)
check('missing planned dependency detected',any(('missing planned provider' in x or 'unresolved internal project dependency' in x) for x in issues),issues)

# Candidate import closure catches the exact TaskForge pattern before source commit.
manifest={'components':[{'id':'backend','root':'backend','toolchain_adapter':'python'}],
          'files':[{'path':'backend/requirements.txt'},{'path':'backend/app/__init__.py'},{'path':'backend/app/main.py'}]}
py='from app.database import get_db\nfrom app.services.project_service import ProjectService\n'
check('Python unplanned internal providers rejected',bool(M._v362_candidate_internal_import_error('.',manifest,'backend/app/main.py',py)),M._v362_candidate_internal_import_error('.',manifest,'backend/app/main.py',py))
manifest_ts={'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'}],
             'files':[{'path':'frontend/package.json'},{'path':'frontend/src/App.tsx'},{'path':'frontend/src/main.tsx'}]}
ts_bad="import type { Project } from './types/api';\nimport './App.css';\n"
check('TypeScript unplanned relative providers rejected',bool(M._v362_candidate_internal_import_error('.',manifest_ts,'frontend/src/App.tsx',ts_bad)),M._v362_candidate_internal_import_error('.',manifest_ts,'frontend/src/App.tsx',ts_bad))
manifest_parent={'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'}],
                 'files':[{'path':'frontend/package.json'},{'path':'frontend/src/App.tsx'},{'path':'frontend/types/api.ts'}]}
check('TypeScript parent relative import normalization works',not M._v362_candidate_internal_import_error('.',manifest_parent,'frontend/src/App.tsx',"import type { Project } from '../types/api';\n"),M._v362_candidate_internal_import_error('.',manifest_parent,'frontend/src/App.tsx',"import type { Project } from '../types/api';\n"))
with tempfile.TemporaryDirectory(prefix='v362_node_dep_') as td:
    r=Path(td);(r/'frontend').mkdir();(r/'frontend/package.json').write_text(json.dumps({'dependencies':{'react':'1.0.0'}}))
    mfdep={'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'}],'files':[{'path':'frontend/package.json'},{'path':'frontend/src/App.tsx'}]}
    err=M._v362_candidate_internal_import_error(r,mfdep,'frontend/src/App.tsx',"import { useNavigate } from 'react-router-dom';\n")
    check('undeclared Node package import rejected',bool(err) and 'react-router-dom' in err,err)
    (r/'frontend/package.json').write_text(json.dumps({'dependencies':{'react':'1.0.0','react-router-dom':'1.0.0'}}))
    err2=M._v362_candidate_internal_import_error(r,mfdep,'frontend/src/App.tsx',"import { useNavigate } from 'react-router-dom';\n")
    check('declared Node package import accepted',not err2,err2)

# Mock the three-stage planner. It must merge complete frontend/backend plans rather than use recovery.
orig_call=M._qwen_call
def fake_call(prompt_text, progress_callback=None, stage='', profile='generate', max_tokens=None, thinking=False, response_schema=None, schema_name=None, strict_output=False, **kwargs):
    if schema_name=='v362_overview':
        obj={'project_name':'TaskForge','summary':'Task manager','project_type':'full-stack','platform':'windows','architecture_rules':['API contract is canonical'],'shared_contracts':['ProjectDTO(id,name)','TaskDTO(id,project_id,title)'],'components':[{'id':'frontend','root':'frontend','purpose':'React UI','toolchain_adapter':'react','depends_on':['backend']},{'id':'backend','root':'backend','purpose':'FastAPI API','toolchain_adapter':'python','depends_on':[]}]}
    elif schema_name in {'v362_component_plan','v362_component_retry'}:
        if '"id": "frontend"' in prompt_text:
            files=[
              {'path':'frontend/package.json','purpose':'deps','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
              {'path':'frontend/tsconfig.json','purpose':'ts config','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
              {'path':'frontend/vite.config.ts','purpose':'vite','phase':'foundation','depends_on':['frontend/package.json'],'exports':[],'contracts':[]},
              {'path':'frontend/index.html','purpose':'html','phase':'integration','depends_on':['frontend/src/main.tsx'],'exports':[],'contracts':[]},
              {'path':'frontend/src/types/api.ts','purpose':'api types','phase':'foundation','depends_on':[],'exports':['Project','Task'],'contracts':['Project and Task DTOs match backend']},
              {'path':'frontend/src/api/client.ts','purpose':'api client','phase':'service','depends_on':['frontend/src/types/api.ts'],'exports':['apiClient'],'contracts':[]},
              {'path':'frontend/src/App.css','purpose':'styles','phase':'ui','depends_on':[],'exports':[],'contracts':[]},
              {'path':'frontend/src/App.tsx','purpose':'ui','phase':'ui','depends_on':['frontend/src/api/client.ts','frontend/src/types/api.ts','frontend/src/App.css'],'exports':['App'],'contracts':[]},
              {'path':'frontend/src/main.tsx','purpose':'entry','phase':'integration','depends_on':['frontend/src/App.tsx'],'exports':[],'contracts':[]},
              {'path':'frontend/src/App.test.tsx','purpose':'tests','phase':'test','depends_on':['frontend/src/App.tsx'],'exports':[],'contracts':[]},
            ]
            obj={'component_id':'frontend','root':'frontend','entrypoint':'frontend/src/main.tsx','required_tools':['node','npm'],'dependency_command':'npm install','build_command':'npm run build','test_command':'npm test','run_command':'npm run dev','shared_contracts':['ProjectDTO(id,name)','TaskDTO(id,project_id,title)'],'files':files}
        else:
            files=[
              {'path':'backend/requirements.txt','purpose':'deps','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
              {'path':'backend/app/__init__.py','purpose':'pkg','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
              {'path':'backend/app/models.py','purpose':'models','phase':'foundation','depends_on':[],'exports':['Project','Task'],'contracts':[]},
              {'path':'backend/app/database.py','purpose':'db','phase':'data','depends_on':['backend/app/models.py'],'exports':['get_db','init_db'],'contracts':[]},
              {'path':'backend/app/schemas.py','purpose':'schemas','phase':'foundation','depends_on':[],'exports':['ProjectCreate','TaskCreate'],'contracts':['DTOs match frontend']},
              {'path':'backend/app/repositories.py','purpose':'repos','phase':'data','depends_on':['backend/app/database.py','backend/app/models.py'],'exports':['ProjectRepository','TaskRepository'],'contracts':[]},
              {'path':'backend/app/services.py','purpose':'services','phase':'service','depends_on':['backend/app/repositories.py'],'exports':['ProjectService','TaskService','DashboardService'],'contracts':[]},
              {'path':'backend/app/main.py','purpose':'api','phase':'integration','depends_on':['backend/app/services.py','backend/app/schemas.py','backend/app/database.py'],'exports':['app'],'contracts':[]},
              {'path':'backend/tests/test_api.py','purpose':'api tests','phase':'test','depends_on':['backend/app/main.py'],'exports':[],'contracts':[]},
              {'path':'backend/tests/test_persistence.py','purpose':'db tests','phase':'test','depends_on':['backend/app/database.py'],'exports':[],'contracts':[]},
            ]
            obj={'component_id':'backend','root':'backend','entrypoint':'backend/app/main.py','required_tools':['python'],'dependency_command':'python -m pip install -r requirements.txt','build_command':'python -m compileall -q .','test_command':'python -m pytest','run_command':'python -m uvicorn app.main:app','shared_contracts':['ProjectDTO(id,name)','TaskDTO(id,project_id,title)'],'files':files}
    elif schema_name=='v362_dependency_closure':
        obj={'complete':True,'issues':[],'add_files':[{'path':'README.md','purpose':'setup docs','phase':'docs','depends_on':[],'exports':[],'contracts':[]}],'shared_contracts':[]}
    else:
        return False,''
    return True,json.dumps(obj)
M._qwen_call=fake_call
try:
    mockspec={'project_summary':'TaskForge','functional_requirements':['projects','tasks'],'constraints':['Windows','React','FastAPI'],'acceptance_criteria':['builds'],
              'suggested_test_scenarios':['api'],'source_requirements':[{'id':f'UR-{i:03d}','category':'functional','text':f'requirement {i}'} for i in range(1,31)],'coverage_valid':True,'coverage_percent':100}
    planned,raw=M._v362_build_hierarchical_manifest(prompt,mockspec,80,None)
finally:
    M._qwen_call=orig_call
check('mock chunked planner returns manifest',isinstance(planned,dict),raw[-1000:] if not planned else '')
if planned:
    paths={x['path'] for x in planned['files']}
    check('chunked planner preserves both components',{x.get('id') for x in planned.get('components',[])}>={'frontend','backend'},planned.get('components'))
    check('chunked planner produces complete-sized graph',len(paths)>=20,len(paths))
    check('frontend API types are planned','frontend/src/types/api.ts' in paths,sorted(paths))
    check('backend database provider is planned','backend/app/database.py' in paths,sorted(paths))
    check('closure additions are merged','README.md' in paths,sorted(paths))
    check('no Expo substitution',all(str(x.get('toolchain_adapter') or '').lower()!='expo' for x in planned.get('components',[])) and 'expo' not in str(planned.get('framework') or '').lower(),planned.get('components'))

# Failed component planning must abort instead of returning V34 recovery.
orig_component=M._v362_plan_component
try:
    M._v362_plan_component=lambda *a,**k:(None,'forced failure')
    # Avoid a real overview call by temporarily replacing it.
    orig_overview=M._v362_plan_overview
    M._v362_plan_overview=lambda *a,**k:{'project_name':'x','summary':'x','project_type':'multi','platform':'windows','components':M._v361_explicit_component_locks(prompt),'architecture_rules':[],'shared_contracts':[],'_raw_overview':''}
    failed_plan,failed_raw=M._v362_build_hierarchical_manifest(prompt,mockspec,80,None)
finally:
    M._v362_plan_component=orig_component;M._v362_plan_overview=orig_overview
check('failed complex component plan aborts instead of tiny recovery',failed_plan is None and 'component planning failed' in failed_raw.lower(),failed_raw[-500:])

with tempfile.TemporaryDirectory(prefix='v362_status_') as td:
    r=Path(td);(r/'main.py').write_text('print("ok")\n')
    M._v33_write_build_status(r,{'files':[{'path':'main.py'}],'components':[{'id':'app','root':'.','toolchain_adapter':'python'}]},'implementing',implemented=1)
    status=json.loads((r/M.V33_BUILD_STATUS_FILE).read_text())
check('status reports V37 planner',status.get('version')=='V37.0.0' and status.get('planner_mode')=='bounded-component-semantic-closure-v37',status)

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL')+' - '+name+(f' ({detail})' if detail and not ok else ''))
print(f'\nV37 planner compatibility regression: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
