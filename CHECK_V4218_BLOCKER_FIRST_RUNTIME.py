import json, os, socket, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('JARVIS_QWEN_MODEL','auto')
import local_qwen_project as j
import jarvis_v42_runtime as rt
PASS=0;FAIL=0

def check(name,cond,detail=''):
    global PASS,FAIL
    if cond:
        PASS+=1;print('PASS',name)
    else:
        FAIL+=1;print('FAIL',name,detail)

def write(p,text):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

ident=j._v36_release_identity()
check('V42.18 identity',ident.get('version')=='V42.18.0',ident)
for key in (
    'deterministic_syntax_before_model','raw_unnumbered_patch_windows','numbered_patch_transport_recovery',
    'authoritative_current_blocker','error_delta_tracking','repair_strategy_ledger',
    'successful_production_check_cache_by_repo_state','deterministic_build_substrate_closure',
    'runtime_smoke_after_build','acceptance_contract_from_user_request','sandbox_project_root_enforcement',
    'sandbox_provider_secret_scrubbing','sandbox_process_tree_timeout_kill','strict_all_language_source_syntax_gate',
    'atomic_multifile_direct_edits','whole_project_build_audit_authoritative_at_endgame','project_local_toolchain_discovery',
    'generated_acceptance_tests_from_original_request','acceptance_tests_are_consumers_not_api_authorities'):
    check(key,bool(ident.get(key)),ident.get(key))

# Exact GearTrack corruption reproduced from the uploaded runtime snapshot.
malformed='''export function InventoryView(){return (<div>\n<input\n  type="text"\n  type="text"\n  value={searchQuery}\n  onChange={(e) => setSearchQuery(e.target.value)}\n  className="search"\n/>\n  value={searchQuery}\n  onChange={(e) => setSearchQuery(e.target.value)}\n  className="search"\n/>\n</div>)}\n'''
fixed,did=j._v4217_mechanical_jsx_candidate(malformed)
check('Inventory loop shape recognized mechanically',did,fixed)
check('Inventory duplicate type removed',fixed.count('type="text"')==1,fixed)
check('Inventory dangling duplicate tail removed',fixed.count('value={searchQuery}')==1 and fixed.count('className="search"')==1,fixed)

# Blocker-first wrapper must not invoke model/subsystem repair when deterministic repair succeeds.
with tempfile.TemporaryDirectory(prefix='v4218_blocker_first_') as td:
    w=Path(td);rel='src/InventoryView.tsx';write(w/rel,malformed)
    old_mech=j._v4217_try_mechanical_source_repair;old_prev=j._v4218_prev_repair_file_for_issues
    calls={'model':0}
    try:
        j._v4217_try_mechanical_source_repair=lambda *a,**k: True
        def should_not_run(*a,**k): calls['model']+=1; return False
        j._v4218_prev_repair_file_for_issues=should_not_run
        ok=j._repair_file_for_issues('build app',{},w,rel,['language_syntax parse failure'],validation_failure='parse failure')
        check('deterministic syntax gets first refusal',ok and calls['model']==0,calls)
    finally:
        j._v4217_try_mechanical_source_repair=old_mech;j._v4218_prev_repair_file_for_issues=old_prev


# Unchanged failed transactional family must rotate instead of re-entering the same model path.
with tempfile.TemporaryDirectory(prefix='v4218_rotate_') as td:
    w=Path(td);rel='src/x.ts';write(w/rel,'const x = broken;\n')
    old_prev=j._v4218_prev_repair_file_for_issues;old_fresh=j._v4217_fresh_exhausted_recovery;old_mech=j._v4217_try_mechanical_source_repair
    calls={'model':0,'fresh':0}
    try:
        j._v4217_try_mechanical_source_repair=lambda *a,**k: False
        def fail_model(*a,**k): calls['model']+=1; return False
        def fresh(*a,**k): calls['fresh']+=1; return True
        j._v4218_prev_repair_file_for_issues=fail_model;j._v4217_fresh_exhausted_recovery=fresh
        args=('build app',{},w,rel,['contract failure'])
        first=j._repair_file_for_issues(*args,validation_failure='same compiler failure')
        second=j._repair_file_for_issues(*args,validation_failure='same compiler failure')
        check('first transactional family can fail boundedly',not first and calls['model']==1,calls)
        check('same revision rotates repair strategy',second and calls['model']==1 and calls['fresh']==1,calls)
    finally:
        j._v4218_prev_repair_file_for_issues=old_prev;j._v4217_fresh_exhausted_recovery=old_fresh;j._v4217_try_mechanical_source_repair=old_mech

# Raw edit windows must not inject line-number prefixes.
with tempfile.TemporaryDirectory(prefix='v4218_raw_') as td:
    w=Path(td);rel='src/a.tsx';write(w/rel,'\n'.join(f'const value{i} = {i};' for i in range(1,120)))
    window=j._v4218_raw_edit_window(w,rel,{'locations':[{'file':rel,'line':74}]},max_lines=20)
    check('raw edit window contains target source','const value74 = 74;' in window,window)
    check('raw edit window has no viewer prefixes',not any(line.lstrip().startswith(('73:','74:','75:')) for line in window.splitlines()),window)

# Legacy numbered SEARCH/REPLACE output should be normalized before exact application.
numbered='''<<<<<<< SEARCH\n73: <input\n74:   type="text"\n75:   type="text"\n76: />\n=======\n73: <input\n74:   type="text"\n75: />\n>>>>>>> REPLACE\n'''
reps,err=j._v38_parse_search_replace_blocks(numbered)
check('numbered patch transport detected',j._v4218_search_looks_viewer_numbered(numbered),numbered)
check('numbered SEARCH normalized before parser',bool(reps) and reps[0].get('search','').startswith('<input') and not reps[0].get('search','').startswith('73:'),(reps,err))

# Missing Vite TS config is restored deterministically.
with tempfile.TemporaryDirectory(prefix='v4218_substrate_') as td:
    w=Path(td)
    write(w/'package.json',json.dumps({'scripts':{'build':'tsc -p tsconfig.node.json && tsc -p tsconfig.json && vite build'},'devDependencies':{'vite':'1'}}))
    write(w/'tsconfig.json',json.dumps({'references':[{'path':'./tsconfig.node.json'}]}))
    write(w/'vite.config.ts','export default {};\n');write(w/'src/main.tsx','console.log("ok")\n')
    changed=j._v4218_recover_build_substrate(w,{'components':[{'id':'web','root':'.','toolchain_adapter':'vite'}]})
    check('tsconfig.node.json deterministically restored',(w/'tsconfig.node.json').is_file(),changed)
    check('missing Vite index deterministically restored',(w/'index.html').is_file(),changed)
    changed2=j._v4218_recover_build_substrate(w,{'components':[{'id':'web','root':'.','toolchain_adapter':'vite'}]})
    check('build substrate recovery is idempotent',not any(x in {'tsconfig.node.json','index.html'} for x in changed2),changed2)

# Error-delta/current-blocker state must reflect the authoritative audit.
with tempfile.TemporaryDirectory(prefix='v4218_delta_') as td:
    w=Path(td)
    a1={'clean':False,'issues':[{'file':'src/a.ts','category':'syntax','message':'bad'},{'file':'src/b.ts','category':'syntax','message':'bad2'}],'components':[]}
    r1=j._v4218_record_audit_state(w,{},a1)
    a2={'clean':False,'issues':[{'file':'src/a.ts','category':'syntax','message':'bad'}],'components':[]}
    r2=j._v4218_record_audit_state(w,{},a2)
    check('current blocker is singular and authoritative',r2.get('current_blocker',{}).get('file')=='src/a.ts',r2)
    check('error delta records improvement',r2.get('error_delta')==1,r2)
    r3=j._v4218_record_audit_state(w,{},a2)
    check('unchanged audit marks stalled',r3.get('unchanged_repeats')>=1 and j._v4218_state(w).get('stalled'),r3)

# Runtime command broker safety controls.
with tempfile.TemporaryDirectory(prefix='v4218_broker_') as td:
    w=Path(td);broker=rt.CommandBroker(w)
    shell=broker.run(['bash','-c','echo bad'],cwd=w,timeout=2) if os.name!='nt' else broker.run(['cmd','/c','echo bad'],cwd=w,timeout=2)
    check('direct shell payload blocked',shell.blocked,shell.reason)
    outside=Path(tempfile.gettempdir()).resolve()
    if outside==w.resolve(): outside=w.parent
    escape=broker.run([sys.executable,'--version'],cwd=outside,timeout=2)
    check('external cwd blocked',escape.blocked,escape.reason)
    old=os.environ.get('OPENAI_API_KEY');os.environ['OPENAI_API_KEY']='test-secret-should-not-pass'
    try: env=broker._prepare_env();check('provider secret scrubbed','OPENAI_API_KEY' not in env,env.get('OPENAI_API_KEY'))
    finally:
        if old is None: os.environ.pop('OPENAI_API_KEY',None)
        else: os.environ['OPENAI_API_KEY']=old

# Local project tools: wrappers/venvs/package CLIs count when their host runtime exists.
with tempfile.TemporaryDirectory(prefix='v4218_tools_') as td:
    w=Path(td);write(w/'gradlew','wrapper');write(w/'node_modules/.bin/vite','shim')
    caps={'tools':{'java':{'available':True},'node':{'available':True}}}
    local=rt.discover_project_tools(w,{},caps)
    check('Gradle wrapper discovered',local.get('gradle',{}).get('available'),local)
    check('package-local Vite discovered',local.get('vite',{}).get('available'),local)
    readiness={'requirements':[{'requirement':'gradle/gradlew','available':False,'providers':[]}],'missing':['gradle/gradlew'],'status':'HOST_MISSING_TOOLS'}
    readiness=rt._apply_project_local_tools(readiness,local)
    check('local wrapper satisfies readiness',readiness.get('status')=='READY' and not readiness.get('missing'),readiness)

# Startup smoke: prove a launched local server answers, then broker tears it down.
with tempfile.TemporaryDirectory(prefix='v4218_smoke_') as td:
    w=Path(td);sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    broker=rt.CommandBroker(w)
    r=broker.startup_smoke([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1'],cwd=w,timeout=6,probe_url=f'http://127.0.0.1:{port}/')
    check('bounded runtime HTTP smoke passes',r.ok,(r.reason,r.combined[-1000:]))

print(f'RESULT {PASS}/{PASS+FAIL} PASS')
report={'version':'V42.18.0','pass':PASS,'fail':FAIL,'total':PASS+FAIL,'identity':ident}
(ROOT/'V42_18_VALIDATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(1 if FAIL else 0)
