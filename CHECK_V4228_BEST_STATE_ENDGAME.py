from pathlib import Path
import tempfile, json, shutil
import local_qwen_project as m

checks=[]
def ck(name, cond, detail=''):
    if not cond:
        raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=m._v36_release_identity()
ck('release identity', ident.get('version')=='V42.28.0', ident)
ck('compiler-count resume scoring enabled', ident.get('resume_score_uses_real_typescript_diagnostic_count') is True, ident)
ck('v4226 pipeline preserved', ident.get('v4226_dependency_first_global_compiler_proof_preserved') is True, ident)
ck('parser safety preserved', ident.get('v4227_parser_safe_changed_file_gate_preserved') is True, ident)

# The exact regression: two failed real builds must NOT score the same when one has
# dramatically fewer syntax-clean TypeScript diagnostics.
orig_det=m._deterministic_acceptance_issues
orig_real=m._run_real_project_validation
try:
    m._deterministic_acceptance_issues=lambda work,manifest: []
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/'src').mkdir(); (root/'src'/'App.tsx').write_text('export const App=()=>null;\n',encoding='utf-8')
        manifest={'project_name':'score-test','files':[{'path':'src/App.tsx'}]}
        def tsout(n, code='2322', msg="Type 'string' is not assignable to type 'number'."):
            return '\n'.join(f"src/App.tsx({i+1},1): error TS{code}: {msg}" for i in range(n))
        m._run_real_project_validation=lambda work,req,man:(False,tsout(37))
        s37=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        m._run_real_project_validation=lambda work,req,man:(False,tsout(3))
        s3=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        ck('37 semantic errors scored', s37['score'][0]==2 and s37['typescript_diagnostic_count']==37, s37)
        ck('3 semantic errors scored', s3['score'][0]==2 and s3['typescript_diagnostic_count']==3, s3)
        ck('37 to 3 is objective promotion', tuple(s3['score']) < tuple(s37['score']), (s37['score'],s3['score']))

        # A parser-blocked single-error state must not beat syntax-clean semantic progress.
        m._run_real_project_validation=lambda work,req,man:(False,tsout(1,'1128','Declaration or statement expected.'))
        sp=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        ck('parser debt separated', sp['score'][0]==3 and sp['typescript_syntax_diagnostic_count']==1, sp)
        ck('3 semantic outranks 1 parser', tuple(s3['score']) < tuple(sp['score']), (s3['score'],sp['score']))

        # Once parser syntax is fixed, newly revealed semantic debt is still forward progress.
        m._run_real_project_validation=lambda work,req,man:(False,tsout(10))
        s10=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        ck('10 semantic outranks parser', tuple(s10['score']) < tuple(sp['score']), (sp['score'],s10['score']))

        # Post-compile runtime failure is deeper progress than TS compile debt.
        m._run_real_project_validation=lambda work,req,man:(False,'Runtime smoke failed: window closed early')
        sr=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        ck('runtime phase', sr['score'][0]==1 and sr['typescript_diagnostic_count']==0, sr)
        ck('runtime outranks compiler debt', tuple(sr['score']) < tuple(s3['score']), (sr['score'],s3['score']))

        m._run_real_project_validation=lambda work,req,man:(True,'build/test/smoke green')
        sg=m._resume_validation_snapshot(root,manifest,'finish',include_real=True)
        ck('green phase', sg['score'][0]==0 and sg['real_ok'] is True, sg)
        summary=m._resume_snapshot_summary(s3)
        ck('snapshot summary exposes TS count', summary.get('typescript_diagnostics')==3, summary)
finally:
    m._deterministic_acceptance_issues=orig_det
    m._run_real_project_validation=orig_real

# Endgame deterministic transaction: simulate a small tail and prove that Jarvis only
# reports progress when the staged full TypeScript measurement strictly decreases.
orig_clone=m._v4224_clone_workspace
orig_bulk=m._v4223_bulk_ts_recovery
orig_diff=m._v4225_diff_source_files
orig_measure=m._v4224_measure_typescript
orig_commit=m._v4224_commit_cluster
try:
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/'src').mkdir(); (root/'src'/'a.ts').write_text('export const x=1;\n',encoding='utf-8')
        clone=root.parent/(root.name+'_clone')
        def fake_clone(work):
            if clone.exists(): shutil.rmtree(clone)
            shutil.copytree(root,clone)
            holder=clone.parent/(clone.name+'_holder'); holder.mkdir(exist_ok=True)
            return holder,clone
        m._v4224_clone_workspace=fake_clone
        m._v4223_bulk_ts_recovery=lambda work,man,failure,cb=None: [(Path(work)/'src'/'a.ts').write_text('export const x=2;\n',encoding='utf-8') or 'src/a.ts']
        m._v4225_diff_source_files=lambda work,cand:['src/a.ts']
        m._v4224_measure_typescript=lambda ow,cw,man,hint:(1,'src/a.ts(1,1): error TS6133: x is declared but its value is never read.')
        called={}
        def fake_commit(work,cand,man,changed,before,after):
            called.update(before=before,after=after,changed=list(changed)); return True,''
        m._v4224_commit_cluster=fake_commit
        issues=[{'problem':'src/a.ts(1,1): error TS6133: x is declared but its value is never read.'},
                {'problem':'src/a.ts(2,1): error TS2322: Type string is not assignable to type number.'}]
        ok=m._v4228_try_endgame_deterministic('finish',{},root,issues,None)
        ck('endgame deterministic commits strict delta', ok and called.get('before')==2 and called.get('after')==1, called)
finally:
    m._v4224_clone_workspace=orig_clone
    m._v4223_bulk_ts_recovery=orig_bulk
    m._v4225_diff_source_files=orig_diff
    m._v4224_measure_typescript=orig_measure
    m._v4224_commit_cluster=orig_commit

print(f'V42.28 regression: {len(checks)}/{len(checks)} PASS')

# Integration regression for the actual resume promotion path: a failed build that
# improves 37 -> 3 must replace `working`, not be thrown away as "still failed".
orig_det=m._deterministic_acceptance_issues
orig_real=m._run_real_project_validation
orig_accept=m._acceptance_repair_cycle
try:
    m._deterministic_acceptance_issues=lambda work,manifest: []
    def tsout(n):
        return '\n'.join(f"src/App.tsx({i+1},1): error TS2322: Type string is not assignable to type number." for i in range(n))
    def fake_real(work,req,man):
        return (False, tsout(3 if Path(work).name.startswith('trial_') else 37))
    m._run_real_project_validation=fake_real
    m._acceptance_repair_cycle=lambda req,man,work,cb=None:(False,[{'kind':'component_validation','problem':fake_real(work,req,man)[1]}])
    with tempfile.TemporaryDirectory() as td:
        job=Path(td); work=job/'working'; work.mkdir(); (work/'src').mkdir(); (work/'src'/'App.tsx').write_text('export const App=()=>null;\n',encoding='utf-8')
        manifest={'project_name':'promotion-test','files':[{'path':'src/App.tsx','purpose':'React App'}]}
        ok,issues,best=m._run_resume_sweeps('finish',manifest,work,job,None,generic_resume=True,max_sweeps=1)
        ck('resume path promotes failed-but-better compiler state', best.get('typescript_diagnostic_count')==3, best)
        ck('resume path keeps project resumable after promotion', ok is False and work.exists(), (ok,issues))
finally:
    m._deterministic_acceptance_issues=orig_det
    m._run_real_project_validation=orig_real
    m._acceptance_repair_cycle=orig_accept

print(f'V42.28 extended regression: {len(checks)}/{len(checks)} PASS')
