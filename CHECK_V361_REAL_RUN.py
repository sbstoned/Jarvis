import importlib.util, json, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('jarvis_v361',HERE/'local_qwen_project.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
checks=[]
def check(name, condition, detail=''):
    checks.append((name,bool(condition),str(detail)))

prompt='''Build a complete TaskForge application for Windows.\n- Frontend: React + TypeScript + Vite\n- Backend: Python 3 + FastAPI\n- The frontend and backend must be separate components in the same repository.\nA Windows user with Python and Node.js installed should be able to run it.\n\n## Acceptance requirements\n1. Backend tests pass.\n2. React production build succeeds.\n\n## Automated tests\n- create project\n- database persistence\n'''

check('V36.2 identity',M.V36_VERSION=='36.2.0',M.V36_VERSION)
locks=M._v361_explicit_component_locks(prompt)
check('two explicit components locked',len(locks)==2,locks)
check('frontend locked to React/Vite',any(x['id']=='frontend' and x['toolchain_adapter']=='react' for x in locks),locks)
check('backend locked to Python/FastAPI family',any(x['id']=='backend' and x['toolchain_adapter']=='python' for x in locks),locks)

bad_manifest={'toolchain_adapter':'expo','platform':'mobile','framework':'expo/react native','build_command':'npx expo export','run_command':'npx expo start','components':[
 {'id':'frontend','root':'frontend','purpose':'ui','toolchain_adapter':'vite','depends_on':[],'build_command':'cd frontend && npm run build'},
 {'id':'backend','root':'backend','purpose':'api','toolchain_adapter':'uvicorn','depends_on':[],'build_command':'cd backend && pip install -r requirements.txt'},
 {'id':'contracts','root':'shared/schemas','purpose':'schemas','toolchain_adapter':'json/jsonschema','depends_on':[],'build_command':'cat shared/schemas/*.json'},
 {'id':'database','root':'backend/data','purpose':'db','toolchain_adapter':'sqlite3/aiosqlite','depends_on':[],'build_command':'touch backend/data/taskforge.db'}],
 'shared_contracts':['SC-01: Project Schema: {id,name}','SC-01: Project Schema - { id, name }','SC-02: Task Schema: {id,title}','SC-02: Task Schema - {id,title}']}
fixed=M._v361_apply_explicit_component_locks(prompt,bad_manifest)
check('multi-stack manifest uses multi adapter',fixed.get('toolchain_adapter')=='multi',fixed)
check('Windows delivery platform preserved',fixed.get('platform')=='windows',fixed)
check('Expo substitution removed','expo' not in json.dumps(fixed).lower(),fixed)
check('support-only pseudo components removed',all(x.get('id') not in {'contracts','database'} for x in fixed.get('components',[])),fixed.get('components'))

check('Node.js prerequisite is not a requested file','Node.js' not in M._extract_explicit_requested_paths(prompt),M._extract_explicit_requested_paths(prompt))
check('explicitly named main.py remains a requested file','main.py' in M._extract_explicit_requested_paths('Create a file named main.py and implement it.'),M._extract_explicit_requested_paths('Create a file named main.py and implement it.'))

raw='def ok():\n    return 1\n===== END FILE backend/tests/test_api.py >>><source continuation only>\ndef broken(:\n'
clean=M._extract_single_file_response(raw,'backend/tests/test_api.py')
check('malformed END FILE continuation is truncated','source continuation' not in clean and 'broken' not in clean,repr(clean))
try: compile(clean,'x','exec'); compiled=True
except Exception: compiled=False
check('salvaged transport prefix is valid Python',compiled,repr(clean))

canon=M._v361_canonicalize_shared_contracts(bad_manifest['shared_contracts'])
check('duplicate schema contracts canonicalized',len(canon)==2,canon)
check('Windows touch command rejected',M._v361_windows_command_sanitize('touch backend/data/taskforge.db')=='')
check('Windows cat command rejected',M._v361_windows_command_sanitize('cat shared/schemas/*.json')=='')
check('python3 normalized for Windows',M._v361_windows_command_sanitize('python3 -m pytest')=='python -m pytest')
curl=M._v361_windows_command_sanitize("curl -H 'Content-Type: application/json' -d '{\"name\":\"x\"}' http://localhost:8000")
check('curl POSIX quotes normalized for Windows',"'" not in curl and 'Content-Type' in curl,curl)

bad_sql='''async def init(conn):\n    await conn.execute("""CREATE TABLE projects (id INTEGER PRIMARY KEY);""")\n    await conn.execute("""CREATE TABLE tasks (id INTEGER PRIMARY KEY, project_id INTEGER, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE; );""")\n'''
good_sql='''async def init(conn):\n    await conn.execute("""CREATE TABLE projects (id INTEGER PRIMARY KEY);""")\n    await conn.execute("""CREATE TABLE tasks (id INTEGER PRIMARY KEY, project_id INTEGER, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);""")\n'''
check('bad embedded SQLite DDL rejected',bool(M._v361_sqlite_ddl_error('backend/src/core/db.py',bad_sql)),M._v361_sqlite_ddl_error('backend/src/core/db.py',bad_sql))
check('valid embedded SQLite DDL accepted',not M._v361_sqlite_ddl_error('backend/src/core/db.py',good_sql),M._v361_sqlite_ddl_error('backend/src/core/db.py',good_sql))

with tempfile.TemporaryDirectory(prefix='v361_async_') as td:
    r=Path(td);(r/'backend/src/core').mkdir(parents=True);(r/'backend/src').mkdir(exist_ok=True)
    (r/'backend/src/core/db.py').write_text('async def get_db_session():\n    yield 1\n')
    (r/'backend/src/main.py').write_text('from backend.src.core.db import get_db_session\nasync def start():\n    async with get_db_session() as conn:\n        pass\n')
    mf={'files':[{'path':'backend/src/core/db.py'},{'path':'backend/src/main.py'}]}
    issues=M._v361_async_generator_context_issues(r,mf)
    check('async-generator used as context manager is detected',bool(issues),issues)
    (r/'backend/src/core/db.py').write_text('from contextlib import asynccontextmanager\n@asynccontextmanager\nasync def get_db_session():\n    yield 1\n')
    issues2=M._v361_async_generator_context_issues(r,mf)
    check('proper asynccontextmanager contract is accepted',not issues2,issues2)

source=M._v361_extract_source_requirements(prompt)
check('acceptance bullets preserved by deterministic extractor',sum(x['category']=='acceptance' for x in source)>=2,source)
check('test bullets preserved by deterministic extractor',sum(x['category']=='test' for x in source)>=2,source)
old=M._v361_base_generate_requirements
try:
    M._v361_base_generate_requirements=lambda req,work,progress_callback=None:{'project_summary':'x','functional_requirements':['Create projects'],'constraints':[],'acceptance_criteria':[],'suggested_test_scenarios':[],'nonfunctional_requirements':[]}
    with tempfile.TemporaryDirectory(prefix='v361_req_') as td:
        req=M._v36_generate_requirements(prompt,Path(td))
finally:
    M._v361_base_generate_requirements=old
check('requirements coverage gate reports 100 percent',req.get('coverage_percent')==100 and len(req.get('requirement_coverage') or [])==len(req.get('source_requirements') or []),req.get('requirement_coverage'))
check('planner prompt contains explicit multi-stack lock','EXPLICIT MULTI-COMPONENT TOOLCHAIN LOCK' in M._project_plan_prompt(prompt,80))
rec=M._v34_recovery_manifest(prompt,40)
check('recovery manifest preserves both buildable components',{x.get('id') for x in rec.get('components',[])} >= {'frontend','backend'},rec.get('components'))

with tempfile.TemporaryDirectory(prefix='v361_status_') as td:
    r=Path(td);(r/'main.py').write_text('print("ok")\n')
    mf={'files':[{'path':'main.py'}],'components':[{'id':'app','root':'.','purpose':'app','toolchain_adapter':'python','depends_on':[]}]}
    M._v33_write_build_status(r,mf,'implementing',implemented=1)
    data=json.loads((r/M.V33_BUILD_STATUS_FILE).read_text())
check('live status reports V36.2',data.get('version')=='V36.2.0' and data.get('real_run_hardening')=='V36.2',data)

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL')+' - '+name+(f' ({detail})' if detail and not ok else ''))
print(f'\nV36.1-derived real-run regression on V36.2: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
