from pathlib import Path
import json, tempfile, hashlib
import local_qwen_project as M

checks=[]
def check(name, ok, detail=''):
    checks.append((name,bool(ok),detail))

ident=M._v36_release_identity()
check('V37 identity', ident.get('version')=='V37.0.0', ident.get('version'))
check('small-model engine identity', ident.get('engine')=='SMALL_MODEL_SOFTWARE_FACTORY', ident.get('engine'))
check('semantic dependency resolution enabled', ident.get('semantic_dependency_resolution') is True)
check('read-before-edit enabled', ident.get('read_before_edit') is True)
check('repair loop detection enabled', ident.get('repair_loop_detection') is True)
check('large-file write guard enabled', ident.get('large_file_write_guard') is True)
check('focused context enabled', ident.get('focused_file_context') is True)
check('generate working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_GENERATE==32768, M.QWEN35_WORKING_CONTEXT_GENERATE)
check('plan working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_PLAN==32768, M.QWEN35_WORKING_CONTEXT_PLAN)
check('repair working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_REPAIR==32768, M.QWEN35_WORKING_CONTEXT_REPAIR)
check('file output budget is bounded', M.QWEN35_FILE_OUTPUT_TOKENS==6144 and M._qwen_file_output_limit()==6144, (M.QWEN35_FILE_OUTPUT_TOKENS,M._qwen_file_output_limit()))
check('continuation loop is bounded', M.FILE_CONTINUATION_ROUNDS==2, M.FILE_CONTINUATION_ROUNDS)
check('per-file wall clock is bounded', M.FILE_GENERATION_WALL_SECONDS==720, M.FILE_GENERATION_WALL_SECONDS)

# Exact V36.2 TaskForge failure pattern: package/tool deps and Python module:symbol notation.
manifest={
 'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react','entrypoint':'src/main.tsx'},
               {'id':'backend','root':'backend','toolchain_adapter':'python','entrypoint':'main.py'}],
 'files':[
 {'path':'frontend/package.json','purpose':'deps','phase':'foundation','depends_on':['frontend/node_modules'],'exports':[],'contracts':[]},
 {'path':'frontend/src/main.tsx','purpose':'entry','phase':'integration','depends_on':['frontend/node_modules','frontend/src/App.tsx'],'exports':[],'contracts':[]},
 {'path':'frontend/src/App.tsx','purpose':'app','phase':'ui','depends_on':['frontend/node_modules'],'exports':['App'],'contracts':[]},
 {'path':'backend/requirements.txt','purpose':'deps','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
 {'path':'backend/main.py','purpose':'entry','phase':'integration','depends_on':['backend/app:App'],'exports':[],'contracts':[]},
 {'path':'backend/app/__init__.py','purpose':'app','phase':'foundation','depends_on':['backend/app.routes:routes'],'exports':['App'],'contracts':[]},
 {'path':'backend/app/routes/__init__.py','purpose':'routes','phase':'integration','depends_on':['backend/app.routes.projects:project_router'],'exports':['routes'],'contracts':[]},
 {'path':'backend/app/routes/projects.py','purpose':'route','phase':'integration','depends_on':['backend/app.services.projects:project_service'],'exports':['project_router'],'contracts':[]},
 {'path':'backend/app/services/projects.py','purpose':'service','phase':'service','depends_on':['backend/app.repositories.projects:projects'],'exports':['project_service'],'contracts':[]},
 {'path':'backend/app/repositories/projects.py','purpose':'repo','phase':'data','depends_on':['sqlite3'],'exports':['projects'],'contracts':[]},
 ]}
M._v37_normalize_manifest_dependencies(manifest)
by={x['path']:x for x in manifest['files']}
check('node_modules is external metadata', by['frontend/package.json']['depends_on']==[], by['frontend/package.json']['depends_on'])
check('sqlite3 is external metadata', by['backend/app/repositories/projects.py']['depends_on']==[], by['backend/app/repositories/projects.py']['depends_on'])
check('backend/app:App resolves package init', by['backend/main.py']['depends_on']==['backend/app/__init__.py'], by['backend/main.py']['depends_on'])
check('dotted routes provider resolves', by['backend/app/__init__.py']['depends_on']==['backend/app/routes/__init__.py'], by['backend/app/__init__.py']['depends_on'])
check('dotted route symbol resolves', by['backend/app/routes/__init__.py']['depends_on']==['backend/app/routes/projects.py'], by['backend/app/routes/__init__.py']['depends_on'])
check('dotted service symbol resolves', by['backend/app/routes/projects.py']['depends_on']==['backend/app/services/projects.py'], by['backend/app/routes/projects.py']['depends_on'])
check('dotted repository symbol resolves', by['backend/app/services/projects.py']['depends_on']==['backend/app/repositories/projects.py'], by['backend/app/services/projects.py']['depends_on'])
check('no unresolved dependency noise', not manifest.get('_v37_unresolved_dependencies'), manifest.get('_v37_unresolved_dependencies'))
component_fixture={'components':[{'id':'frontend','root':'frontend','depends_on':['backend (via HTTP)','node_modules']},{'id':'backend','root':'backend','depends_on':['sqlite3','fastapi']}],'files':[]}
M._v37_normalize_manifest_dependencies(component_fixture)
check('component relation normalizes to component id', component_fixture['components'][0]['depends_on']==['backend'], component_fixture['components'][0]['depends_on'])
check('component package metadata removed', component_fixture['components'][1]['depends_on']==[], component_fixture['components'][1]['depends_on'])

spec={'source_requirements':[{'id':f'UR-{i:03d}','text':f'r{i}'} for i in range(1,6)],'coverage_valid':True,'coverage_percent':100}
issues=M._v362_manifest_completeness_issues(manifest,spec,'Frontend: React + Vite Backend: Python + FastAPI',80)
check('component-local entrypoints normalized', manifest['components'][0]['entrypoint']=='frontend/src/main.tsx' and manifest['components'][1]['entrypoint']=='backend/main.py', manifest['components'])
check('TaskForge-style dependency metadata no longer blocks architecture', not issues, issues)

bad={'components':[{'id':'app','root':'.','toolchain_adapter':'python','entrypoint':'main.py'}],
     'files':[{'path':'requirements.txt','purpose':'deps','phase':'foundation','depends_on':[],'exports':[],'contracts':[]},
              {'path':'main.py','purpose':'entry','phase':'integration','depends_on':['missing.py'],'exports':[],'contracts':[]},
              {'path':'tests/test_main.py','purpose':'test','phase':'test','depends_on':['main.py'],'exports':[],'contracts':[]}]}
badissues=M._v362_manifest_completeness_issues(bad,{'source_requirements':[{'id':'UR-001','text':'x'}],'coverage_valid':True,'coverage_percent':100},'Build a Python app',40)
check('real missing project dependency still blocks', any('missing.py' in x for x in badissues), badissues)

# Flattened prompt regression: transport may remove all newlines.
flat=('Build a complete production-quality local application named TaskForge. TaskForge is a personal project and task management application for Windows. '
      'Use this technology stack: Frontend: React + TypeScript + Vite Backend: Python 3 + FastAPI Database: SQLite '
      'The frontend and backend must be separate components in the same repository. The application must work locally without cloud services. '
      'Core functionality Users must be able to create projects. Each project must contain: unique ID project name description status priority created date updated date '
      'Users must be able to: create projects edit projects delete projects view projects search projects filter projects by status filter projects by priority '
      'Dashboard Create a dashboard showing: total projects total tasks Todo tasks In Progress tasks Completed tasks overdue tasks tasks due within 7 days '
      'Acceptance tests Before declaring the project complete, verify: Backend dependencies install successfully in a clean Python environment. '
      'Frontend dependencies install successfully. All Python files compile. TypeScript compilation succeeds. Backend automated tests pass. React production build succeeds. FastAPI starts successfully. '
      'Final project delivery The finished ZIP must include: complete frontend complete backend README BUILD_PROJECT.bat RUN_PROJECT.bat SETUP_AND_RUN.bat.')
ledger=M._v361_extract_source_requirements(flat)
check('flattened prompt yields many source requirements', len(ledger)>=20, len(ledger))
check('flattened frontend stack preserved', any('Frontend: React + TypeScript + Vite' in x['text'] for x in ledger), [x['text'] for x in ledger])
check('flattened backend stack preserved', any('Backend: Python 3 + FastAPI' in x['text'] for x in ledger), [x['text'] for x in ledger])
check('flattened database stack preserved', any('Database: SQLite' in x['text'] for x in ledger), [x['text'] for x in ledger])
accept=[x for x in ledger if x['category']=='acceptance']
check('flattened acceptance section recovered', len(accept)>=7, [(x['category'],x['text']) for x in ledger])

# Focused-context selection should remain bounded and relevant.
with tempfile.TemporaryDirectory(prefix='v37_req_') as td:
    r=Path(td)
    req={'project_summary':'Task manager','constraints':['Frontend: React + TypeScript + Vite','Backend: Python 3 + FastAPI','Windows local only'],
         'source_requirements':ledger,'acceptance_criteria':['Frontend build succeeds','Backend tests pass']}
    (r/M.V36_REQUIREMENTS_FILE).write_text(json.dumps(req),encoding='utf-8')
    item={'path':'frontend/src/App.tsx','purpose':'React project/task dashboard UI','contracts':['renders projects tasks dashboard'],'exports':['App']}
    focused=M._v37_focused_file_request(flat,{'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'}]},r,item)
    check('focused file request is bounded', len(focused)<12000, len(focused))
    check('focused file request carries frontend stack', 'React + TypeScript + Vite' in focused, focused[:1000])
    check('focused file request carries dashboard behavior', 'dashboard' in focused.lower(), focused[:1200])

# JSONC and package manifest behavior remain distinct.
check('tsconfig JSONC comments accepted', not M._v36_precommit_candidate_error(Path('.'),'tsconfig.json','{"compilerOptions":{/*ok*/"strict":true,},}'))
check('package.json comments rejected', bool(M._v36_precommit_candidate_error(Path('.'),'package.json','{"scripts":{/*bad*/"test":"x"}}')))

# Import/dependency gates retained.
with tempfile.TemporaryDirectory(prefix='v37_imports_') as td:
    r=Path(td);(r/'frontend').mkdir();(r/'frontend/package.json').write_text(json.dumps({'dependencies':{'react':'1','react-router-dom':'1'}}))
    mf={'components':[{'id':'frontend','root':'frontend','toolchain_adapter':'react'}],
        'files':[{'path':'frontend/package.json'},{'path':'frontend/src/App.tsx'},{'path':'frontend/src/main.tsx'}]}
    err=M._v362_candidate_internal_import_error(r,mf,'frontend/src/App.tsx','import {x} from "./missing";\n')
    check('missing relative TypeScript provider rejected', 'not present' in err, err)
    err2=M._v362_candidate_internal_import_error(r,mf,'frontend/src/App.tsx','import {Link} from "react-router-dom";\n')
    check('declared Node dependency accepted', not err2, err2)

# Agent loop memory catches repeated candidate fingerprints.
with tempfile.TemporaryDirectory(prefix='v37_state_') as td:
    r=Path(td)
    fp=M._v37_record_patch_attempt(r,'app.py','print(1)','failed')
    hist=M._v37_recent_patch_history(r,'app.py')
    check('patch history persists', bool(hist) and hist[-1]['fingerprint']==fp, hist)
    check('patch fingerprint stable', fp==hashlib.sha256(b'print(1)').hexdigest()[:20], fp)

# Repo-map and machine contracts remain active.
with tempfile.TemporaryDirectory(prefix='v37_graph_') as td:
    r=Path(td);(r/'db.py').write_text('class DB:\n    def save(self, item):\n        return item\n')
    (r/'service.py').write_text('from db import DB\nclass Service:\n    def add(self,x):\n        return DB().save(x)\n')
    mf={'files':[{'path':'db.py','depends_on':[],'exports':['DB']},{'path':'service.py','depends_on':['db.py'],'exports':['Service']}], 'components':[{'id':'app','root':'.','toolchain_adapter':'python'}]}
    graph=M._v36_build_repo_graph(r,mf,write=True);reg=M._v36_build_contract_registry(r,mf,write=True)
    check('repo graph persisted', (r/M.V36_REPO_GRAPH_FILE).exists())
    check('contract registry persisted', (r/M.V36_CONTRACT_REGISTRY_FILE).exists())
    check('method signature recorded', any('save' in str(x) for x in reg.get('contracts',[]) if isinstance(x,dict)), reg.get('contracts',[])[:5])

# Live status identity.
with tempfile.TemporaryDirectory(prefix='v37_status_') as td:
    r=Path(td);(r/'main.py').write_text('print("ok")\n')
    M._v33_write_build_status(r,{'files':[{'path':'main.py'}],'components':[{'id':'app','root':'.','toolchain_adapter':'python'}]},'implementing',implemented=1)
    status=json.loads((r/M.V33_BUILD_STATUS_FILE).read_text())
    check('status reports V37',status.get('version')=='V37.0.0',status)
    check('status reports small-model engine',status.get('engine')=='SMALL_MODEL_SOFTWARE_FACTORY',status)
    check('status reports focused context',status.get('focused_context') is True,status)

# Architecture-blocked result is marked so outer packaging can report the right failure class.
# (No Qwen call needed; validate the convention used by V37 direct bootstrap.)
check('architecture blocked marker convention present', '_jarvis_architecture_blocked' in Path(M.__file__).read_text(encoding='utf-8'))
check('generic bootstrap error replacement present', 'Project architecture/preflight did not converge' in Path(M.__file__).read_text(encoding='utf-8'))

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL')+' - '+name+(f' ({detail})' if detail and not ok else ''))
print(f'\nV37 small-model regression: {len(checks)-len(failed)}/{len(checks)} passed')
raise SystemExit(1 if failed else 0)
# Research-informed bounded operating profile: native server context remains available, ordinary turns stay compact.
check('generate working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_GENERATE==32768, M.QWEN35_WORKING_CONTEXT_GENERATE)
check('plan working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_PLAN==32768, M.QWEN35_WORKING_CONTEXT_PLAN)
check('repair working context defaults to 32K', M.QWEN35_WORKING_CONTEXT_REPAIR==32768, M.QWEN35_WORKING_CONTEXT_REPAIR)
check('file output budget is bounded', M.QWEN35_FILE_OUTPUT_TOKENS==6144 and M._qwen_file_output_limit()==6144, (M.QWEN35_FILE_OUTPUT_TOKENS,M._qwen_file_output_limit()))
check('continuation loop is bounded', M.FILE_CONTINUATION_ROUNDS==2, M.FILE_CONTINUATION_ROUNDS)


