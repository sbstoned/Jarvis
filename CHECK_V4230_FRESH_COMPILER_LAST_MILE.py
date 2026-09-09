from pathlib import Path
import tempfile, json
import local_qwen_project as m

checks=[]
def ck(name,cond,detail=''):
    if not cond: raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=m._v36_release_identity()
ck('release identity',ident.get('version')=='V42.30.0',ident)
ck('engine identity',ident.get('engine')==m.V4230_ENGINE,ident)
ck('pre-sweep activation advertised',ident.get('fresh_compiler_last_mile_pre_sweep') is True)
ck('post-acceptance activation advertised',ident.get('fresh_compiler_last_mile_post_acceptance') is True)
ck('eight-error tail eligible',m.V4230_ENDGAME_MAX_DIAGNOSTICS>=8,m.V4230_ENDGAME_MAX_DIAGNOSTICS)
ck('engine marker matches',m._v4230_engine_disk_guard()[0] is True,m._v4230_engine_disk_guard())

with tempfile.TemporaryDirectory(prefix='v4230_') as td:
    root=Path(td)
    # Fresh compiler parsing must deduplicate repeated audit echoes rather than letting
    # a noisy issue list push an 8-error project above the small-tail limit.
    (root/'src').mkdir()
    lines=[]
    for i in range(1,9):
        (root/f'src/File{i}.ts').write_text(f'export const x{i} = 1;\n')
        lines.append(f"src/File{i}.ts({i},1): error TS2339: Property 'x{i}' does not exist on type 'Y'.")
    output='\n'.join(lines+lines)
    snap={'real_output':output,'typescript_diagnostic_count':8,'typescript_syntax_diagnostic_count':0}
    rows=m._v4230_fresh_ts_rows(root,snap)
    ck('fresh compiler diagnostics deduplicated',len(rows)==8,len(rows))
    ck('small semantic tail recognized',len(m._v4230_small_semantic_tail(root,snap))==8)

    # TS2322 continuation detail is often lost by the one-line parser.  The declared
    # target interface plus object-shape error is enough to repair a boolean string.
    csv='''interface CSVRow {\n  id: string;\n  enabled: boolean;\n}\nconst rows = source.map(item => ({ id: item.id, enabled: item.enabled ? "true" : "false" }));\n'''
    r=[{'code':'2322','raw':"src/useCSV.ts(4,1): error TS2322: Type '{ id: string; enabled: string; }[]' is not assignable to type 'CSVRow[]'."}]
    fixed,why=m._v4230_fix_boolean_shape_fields(csv,r)
    ck('boolean shape solver fired',bool(why),why)
    ck('boolean shape solver preserves boolean','enabled: item.enabled' in fixed and '? "true"' not in fixed,fixed)

# Prove the real resume wrapper invokes the V42.30 preflight before inherited sweeps.
orig_pre=m._v4230_try_preflight_last_mile
orig_prev=m._v4230_prev_run_resume_sweeps
calls=[]
try:
    m._v4230_try_preflight_last_mile=lambda *a,**k: calls.append('preflight') or False
    m._v4230_prev_run_resume_sweeps=lambda *a,**k: calls.append('inherited') or (False,['x'],{})
    with tempfile.TemporaryDirectory(prefix='v4230_wrap_') as td:
        root=Path(td);work=root/'working';work.mkdir();job=root/'job';job.mkdir()
        m._run_resume_sweeps('finish',{},work,job,generic_resume=True,prior_issues=[],max_sweeps=1)
    ck('resume preflight runs before inherited sweeps',calls[:2]==['preflight','inherited'],calls)
finally:
    m._v4230_try_preflight_last_mile=orig_pre
    m._v4230_prev_run_resume_sweeps=orig_prev

# Prove the post-acceptance fallback uses fresh compiler output rather than the mixed
# legacy issue list and is intrinsically bounded to one inherited retry.
orig_acc=m._v4230_prev_acceptance
orig_snap=m._resume_validation_snapshot
orig_lm=m._v4229_last_mile_transaction
calls=[]
try:
    def fake_acc(*a,**k):
        calls.append('acceptance')
        return False,['legacy audit prose with no TS rows']
    m._v4230_prev_acceptance=fake_acc
    m._resume_validation_snapshot=lambda *a,**k:{
        'real_output':"src/App.tsx(1,1): error TS2741: Property 'metrics' is missing in type '{}' but required in type 'Props'.",
        'typescript_diagnostic_count':1,'typescript_syntax_diagnostic_count':0,
    }
    def fake_lm(*a,**k):
        calls.append('last-mile')
        return True
    m._v4229_last_mile_transaction=fake_lm
    with tempfile.TemporaryDirectory(prefix='v4230_acc_') as td:
        r=Path(td);(r/'src').mkdir();(r/'src/App.tsx').write_text('export default function App(){ return null; }\n')
        m._acceptance_repair_cycle('finish',{},r,None)
    ck('post acceptance fresh compiler last-mile activated','last-mile' in calls,calls)
    ck('post acceptance retry bounded',calls.count('acceptance')==2,calls)
finally:
    m._v4230_prev_acceptance=orig_acc
    m._resume_validation_snapshot=orig_snap
    m._v4229_last_mile_transaction=orig_lm


# Current-engine identity must survive durable-event/progress wrapper chains.
with tempfile.TemporaryDirectory(prefix='v4230_identity_') as td:
    r=Path(td)
    ev=m._append_project_event(r,'identity_probe','probe')
    ck('journal event stamped current engine',ev.get('engine_version')=='V42.30.0',ev)
    proj=json.loads((r/m.V4225_PROJECTION_FILE).read_text())
    ck('event projection stamped current engine',proj.get('version')=='V42.30.0' and proj.get('engine')==m.V4230_ENGINE,proj)
seen=[]
m._progress(lambda payload: seen.append(payload),'V42.27 old label',stage='probe')
ck('progress callback stamped current engine',seen and seen[-1].get('engine_version')=='V42.30.0',seen)
ck('progress label normalized once',seen and 'V42.30 old label' in seen[-1].get('message',''),seen)

print(f'V42.30 regression: {len(checks)}/{len(checks)} PASS')
