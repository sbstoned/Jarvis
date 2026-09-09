from pathlib import Path
import sys,tempfile,time
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as q

checks=[]
def check(name,cond,detail=''):
    ok=bool(cond);checks.append((name,ok,detail));print(('PASS' if ok else 'FAIL')+f' | {name}'+(f' | {detail}' if detail else ''))

ident=q._v36_release_identity()
check('release version V42.13-compatible or newer', float(str(ident.get('version') or 'V0').lstrip('V').split('.',1)[0]+'.'+str(ident.get('version') or 'V0').lstrip('V').split('.')[1]) >= 42.13 if len(str(ident.get('version') or '').lstrip('V').split('.'))>1 else False, str(ident.get('version')))
check('accepted state is progress clock',ident.get('accepted_state_is_progress_clock') is True)
check('specialist response alone is not progress',ident.get('specialist_response_alone_is_not_progress') is True)
check('provider specialist budget is one by default',ident.get('provider_specialist_calls_per_accepted_state')==1,str(ident.get('provider_specialist_calls_per_accepted_state')))
check('global audit specialist budget is one by default',ident.get('whole_audit_specialist_calls_per_signature')==1,str(ident.get('whole_audit_specialist_calls_per_signature')))
check('overnight loop circuit breaker enabled',ident.get('overnight_loop_circuit_breaker') is True)
check('AUTO worker preserved',ident.get('auto_worker_profile')=='9b35',str(ident.get('auto_worker_profile')))
check('AUTO specialist is NEW 27B Q2',ident.get('auto_specialist_profile')=='27b38q2',str(ident.get('auto_specialist_profile')))
check('old 27B excluded from AUTO',ident.get('legacy_27b_auto_eligible') is False)
check('manual strict model lock preserved',ident.get('manual_model_selection_strict_lock') is True)
check('ZIP resume preserved',ident.get('robust_resume_zip_import') is True)
check('resume trial isolation preserved',ident.get('resume_trial_source_only_clone') is True)

with tempfile.TemporaryDirectory(prefix='v4213_state_') as td:
    work=Path(td)
    orig_token=q._v429_progress_token
    try:
        token=['A']
        q._v429_progress_token=lambda _w: token[0]
        s,t=q._v4213_state_for_token(work)
        s['provider_specialist_calls']={'x.rs':1};q._v4213_save_state(work,s)
        s2,t2=q._v4213_state_for_token(work)
        check('budget persists while accepted state unchanged',s2.get('provider_specialist_calls',{}).get('x.rs')==1)
        token[0]='B';s3,t3=q._v4213_state_for_token(work)
        check('budget resets on accepted-state progress',not s3.get('provider_specialist_calls'))
    finally:q._v429_progress_token=orig_token

with tempfile.TemporaryDirectory(prefix='v4213_provider_') as td:
    work=Path(td);manifest={'files':[],'components':[]}
    orig_token=q._v429_progress_token;orig_prev=q._v4213_prev_specialist_provider_takeover;orig_escape=q._v4213_deterministic_provider_escape;orig_problem=q._v424_provider_state_problem
    calls={'specialist':0,'escape':0}
    try:
        q._v429_progress_token=lambda _w:'STATIC'
        q._v424_provider_state_problem=lambda _w,_m,_p:'still bad'
        def fake_prev(*args,**kwargs):calls['specialist']+=1;return False
        def fake_escape(*args,**kwargs):calls['escape']+=1;return False
        q._v4213_prev_specialist_provider_takeover=fake_prev
        q._v4213_deterministic_provider_escape=fake_escape
        q._v429_specialist_provider_takeover('',manifest,work,'src/types/tool.ts','same error',None)
        q._v429_specialist_provider_takeover('',manifest,work,'src/types/tool.ts','same error',None)
        check('same provider gets only one specialist call per accepted state',calls['specialist']==1,str(calls))
        check('no-progress provider switches to deterministic escape',calls['escape']>=2,str(calls))
    finally:
        q._v429_progress_token=orig_token;q._v4213_prev_specialist_provider_takeover=orig_prev;q._v4213_deterministic_provider_escape=orig_escape;q._v424_provider_state_problem=orig_problem

with tempfile.TemporaryDirectory(prefix='v4213_audit_') as td:
    work=Path(td);manifest={};audit={'issues':[{'file':'a.ts','kind':'component_validation','problem':'same compiler error'}]}
    orig_token=q._v429_progress_token;orig_prev=q._v4213_prev_specialist_whole_audit
    calls={'global':0}
    try:
        q._v429_progress_token=lambda _w:'STATIC2'
        def fake_prev(*args,**kwargs):calls['global']+=1;return 'brief'
        q._v4213_prev_specialist_whole_audit=fake_prev
        q._v429_specialist_whole_audit('',manifest,work,audit,None,'repeat')
        second=q._v429_specialist_whole_audit('',manifest,work,audit,None,'repeat')
        check('identical whole-project signature gets one 27B clustering call',calls['global']==1,str(calls))
        check('repeated whole audit is suppressed explicitly','suppressed' in str(second).lower())
    finally:q._v429_progress_token=orig_token;q._v4213_prev_specialist_whole_audit=orig_prev

# Verify the bounded convergence circuit breaker without running compilers/models.
with tempfile.TemporaryDirectory(prefix='v4213_global_') as td:
    work=Path(td);manifest={'files':[],'components':[]};audit={'clean':False,'issues':[{'file':'a.ts','kind':'static','problem':'same'}]}
    saved={name:getattr(q,name) for name in ['_v429_whole_project_audit','_v429_repair_audit_round','_v429_specialist_whole_audit','_v428_reconcile_live_contract_graph','_v429_progress_token']}
    counts={'audit':0,'repair':0}
    try:
        def fake_audit(*args,**kwargs):counts['audit']+=1;return dict(audit)
        q._v429_whole_project_audit=fake_audit
        q._v429_repair_audit_round=lambda *a,**k: counts.__setitem__('repair',counts['repair']+1) or False
        q._v429_specialist_whole_audit=lambda *a,**k:'brief'
        q._v428_reconcile_live_contract_graph=lambda *a,**k:False
        q._v429_progress_token=lambda _w:'UNCHANGED'
        started=time.time();ok,issues=q._v429_whole_project_convergence('',manifest,work,None);elapsed=time.time()-started
        check('unchanged global convergence returns failure instead of looping',ok is False)
        check('global convergence is bounded',counts['audit']<=5,str(counts))
        check('global circuit returns consolidated issues',len(issues)==1,str(issues))
        check('bounded test completes quickly',elapsed<2.0,f'{elapsed:.3f}s')
    finally:
        for name,val in saved.items():setattr(q,name,val)

skill=(ROOT/'project_builder_skills/bounded-convergence.md')
check('bounded convergence skill exists',skill.exists())
source=(ROOT/'local_qwen_project.py').read_text(encoding='utf-8',errors='replace')
check('specialist budget overlay present','V42.13 BOUNDED SPECIALIST PROGRESS WATCHDOG' in source)
check('deterministic escape present','def _v4213_deterministic_provider_escape' in source)
check('global no-progress breaker present','v4213_global_no_progress_breaker' in source)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT {passed}/{len(checks)} PASS')
if passed!=len(checks):raise SystemExit(1)
