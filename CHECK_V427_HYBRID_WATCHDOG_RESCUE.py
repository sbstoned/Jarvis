from pathlib import Path
import local_qwen_project as l

results=[]
def check(name, cond, detail=''):
    results.append((name,bool(cond),str(detail)))
    print(('PASS' if cond else 'FAIL')+': '+name+((' :: '+str(detail)) if detail else ''))

# AUTO role split: 27B remains the architect, 9B serializes the heavy component JSON.
l.configure_project_qwen_routing('auto')
t,r=l._v426_route_for_call('V42.7 compiling frozen requirements','plan','small')
check('AUTO high-level requirements still use new 27B', t=='27b38q2', (t,r))
t,r=l._v426_route_for_call('V37 component plan 1/2: ui','plan','small')
check('AUTO detailed component plan uses 9B serializer', t=='9b35', (t,r))
t,r=l._v426_route_for_call('V37 component plan retry: backend','plan','small')
check('AUTO component plan retry stays on fast 9B', t=='9b35', (t,r))
t,r=l._v426_route_for_call('V42.7 architecture collision repair 1/2','repair','small')
check('AUTO architecture collision still uses new 27B', t=='27b38q2', (t,r))

# Manual choices remain absolute locks even for component planning.
for mode in ('9b35','27b38q2','27b','8b'):
    l.configure_project_qwen_routing(mode)
    t,_=l._v426_route_for_call('V37 component plan 1/2: ui','plan','small')
    check(f'manual {mode} component planning remains strict', t==mode, t)

# V42.57 supersedes the old active-stream wall clock. Older releases keep the
# historical bounded stage-specific watchdog expectations.
orig_active=l._v426_active_profile
try:
    l._v426_active_profile=lambda:'27b38q2'
    current=l._v36_release_identity()
    if current.get('active_stream_wall_clock_unbounded'):
        check('27B plan hard wall disabled by current release', l._qwen_profile_hard_timeout('plan')==0, l._qwen_profile_hard_timeout('plan'))
        check('27B repair hard wall disabled by current release', l._qwen_profile_hard_timeout('repair')==0, l._qwen_profile_hard_timeout('repair'))
    else:
        check('27B plan watchdog > old six-minute limit', l._qwen_profile_hard_timeout('plan')>=720, l._qwen_profile_hard_timeout('plan'))
        check('27B repair watchdog bounded and >= plan', 720 <= l._qwen_profile_hard_timeout('repair') <= 1800, l._qwen_profile_hard_timeout('repair'))
finally:
    l._v426_active_profile=orig_active

# AUTO hard-watchdog rescue is historical once V42.57 removes the hard wall.
current_identity=l._v36_release_identity()
if current_identity.get('active_stream_wall_clock_unbounded'):
    check('AUTO hard-watchdog rescue superseded by unbounded active stream', True)
    check('manual model lock preserved without hard wall', current_identity.get('manual_model_selection_strict_lock') is True)
else:
    # AUTO watchdog rescue retries exactly once on peer model and bypasses re-routing.
    orig_first=l._v427_prev_qwen_call
    orig_switch=l._v426_switch_for_call
    orig_rescue=l._v426_prev_qwen_call
    orig_ctx=l._v427_runtime_context_tokens
    try:
        l.configure_project_qwen_routing('auto')
        l._V426_ROUTE.last_target='27b38q2'
        calls={'rescue':0,'switch':[]}
        l._v427_prev_qwen_call=lambda *a,**k:(False,'Local Qwen exceeded the configured 6-minute hard watchdog.')
        def fake_switch(target, reason, progress_callback=None):
            calls['switch'].append(target); l._V426_ROUTE.last_target=target; return True,'ok'
        l._v426_switch_for_call=fake_switch
        def fake_rescue(*a,**k):
            calls['rescue']+=1; return True,'rescued-output'
        l._v426_prev_qwen_call=fake_rescue
        l._v427_runtime_context_tokens=lambda timeout=1.2:6144
        out=l._qwen_call('x',None,'V37 component plan 1/2: ui',profile='plan')
        check('AUTO watchdog rescues successful peer output', out==(True,'rescued-output'), out)
        check('AUTO watchdog switches 27B timeout to 9B peer', calls['switch']==['9b35'], calls['switch'])
        check('AUTO watchdog rescue is a single peer call', calls['rescue']==1, calls['rescue'])

        l.configure_project_qwen_routing('27b38q2')
        calls['switch'].clear(); calls['rescue']=0
        out=l._qwen_call('x',None,'V37 component plan 1/2: ui',profile='plan')
        check('manual 27B timeout does not cross-fallback', not out[0] and 'hard watchdog' in out[1], out)
        check('manual timeout performs no peer switch', calls['switch']==[] and calls['rescue']==0, (calls['switch'],calls['rescue']))
    finally:
        l._v427_prev_qwen_call=orig_first
        l._v426_switch_for_call=orig_switch
        l._v426_prev_qwen_call=orig_rescue
        l._v427_runtime_context_tokens=orig_ctx
        l.clear_project_qwen_routing()

identity=l._v36_release_identity()
check('release identity preserves V42.7 watchdog behavior in V42.7+', str(identity.get('version') or '').startswith('V42.') and identity.get('auto_cross_model_watchdog_rescue') is True, identity.get('version'))
check('release reports watchdog rescue', identity.get('auto_cross_model_watchdog_rescue') is True)
check('release keeps legacy 27B out of AUTO', identity.get('legacy_27b_auto_eligible') is False)
check('release keeps zero-debt publication gate', identity.get('strict_zero_debt_publish_gate') is True)

passed=sum(1 for _,ok,_ in results if ok)
print(f'\nV42.7 hybrid watchdog rescue: {passed}/{len(results)} PASS')
if passed != len(results): raise SystemExit(1)
