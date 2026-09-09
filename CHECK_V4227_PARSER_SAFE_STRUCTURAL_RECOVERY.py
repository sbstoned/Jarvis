from __future__ import annotations
import tempfile
from pathlib import Path
import local_qwen_project as j

checks=[]
def ck(name,cond,detail=''):
    if not cond: raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=j._v36_release_identity()
ck('release identity',ident.get('version')=='V42.27.0',ident)
ck('parser-safe delta advertised',ident.get('changed_ts_files_must_be_compiler_syntax_clean') is True,ident)
ck('structural recovery advertised',ident.get('orphan_top_level_fragment_compiler_proven_recovery') is True,ident)

failure='src/components/DashboardView.tsx(18,1): error TS1128: Declaration or statement expected.'
ck('TS1128 classified syntax',j._v4218_is_syntax_problem('src/components/DashboardView.tsx',[],failure))

broken='''\nimport React from 'react';\nimport { DashboardMetrics } from "../hooks/useDashboardStats";\n\ninterface ConditionBadgeProps {\n  condition: string;\n}\n\nconst colorClasses: Record<string, string> = {\n  "New": "bg-green-500 text-white",\n};\n\n  const color = colorClasses[condition] || defaultClass;\n\n  return (\n    <span className={color}>{condition}</span>\n  );\n};\n\ninterface DashboardViewProps { metrics: DashboardMetrics; }\nexport const DashboardView: React.FC<DashboardViewProps> = ({ metrics }) => <div>{metrics.totalTools}</div>;\n'''
rows=[{'file':'src/components/DashboardView.tsx','code':'1128','line':18,'col':1,'message':'Declaration or statement expected.','raw':failure}]
cand,changed,meta=j._v4227_orphan_top_level_fragment_candidate(broken,rows)
ck('orphan fragment detected',changed,meta)
ck('orphan top-level return removed','return (' not in cand,cand)
ck('public Dashboard preserved','export const DashboardView' in cand,cand)
ck('dead helper scaffold removed','ConditionBadgeProps' not in cand and 'colorClasses' not in cand,cand)

# Typed arrow cleanup must remove the entire balanced declaration, not the destructured
# parameter brace plus only part of the body.
typed='''interface XProps { x:string }\nconst Helper: React.FC<XProps> = ({ x }) => {\n  const y = {a:1};\n  return <span>{x}{y.a}</span>;\n};\nexport const Keep=()=> <div/>;\n'''
rr=[{'code':'6133','raw':"x.tsx(2,7): error TS6133: 'Helper' is declared but its value is never read."}]
out,reasons=j._v4226_remove_unused_function_or_local(typed,rr)
ck('typed arrow whole declaration removed','const Helper' not in out and 'return <span>' not in out,(out,reasons))
ck('following export preserved','export const Keep' in out,out)

with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/'src/components').mkdir(parents=True)
    target=root/'src/components/DashboardView.tsx';target.write_text(broken,encoding='utf-8')
    manifest={'components':[{'id':'react','root':'.','toolchain_adapter':'react'}], 'files':[{'path':'src/components/DashboardView.tsx','purpose':'React dashboard component','exports':['DashboardView']}]}

    # Prove the deterministic structural repair accepts syntax disappearance even if
    # semantic diagnostics remain/reappear after the parser blocker is removed.
    old_measure=j._v4224_measure_typescript;old_sem=j._v4221_semantic_role_error;old_mark=j._v413_mark_accepted
    try:
        def fake_measure(original_work,candidate_work,manifest,hint_rel):
            # Candidate compile has semantic debt but no syntax diagnostics.
            return 4,"src/components/DashboardView.tsx(30,9): error TS6133: 'x' is declared but its value is never read."
        j._v4224_measure_typescript=fake_measure
        j._v4221_semantic_role_error=lambda *a,**k:''
        j._v413_mark_accepted=lambda *a,**k:None
        ok=j._v4227_try_structural_ts_repair(root,manifest,'src/components/DashboardView.tsx',[],failure,None)
        ck('compiler-proven structural repair committed',ok)
        fixed=target.read_text(encoding='utf-8')
        ck('structural repair changed accepted file','ConditionBadgeProps' not in fixed and 'export const DashboardView' in fixed,fixed)
    finally:
        j._v4224_measure_typescript=old_measure;j._v4221_semantic_role_error=old_sem;j._v413_mark_accepted=old_mark

# Atomic cluster gate must reject a globally-improving candidate when a changed file
# has a real compiler parser diagnostic in the cached measurement.
with tempfile.TemporaryDirectory() as td:
    root=Path(td);clone=root/'clone';(root/'src').mkdir(parents=True);(clone/'src').mkdir(parents=True)
    (root/'src/a.tsx').write_text('export const A=()=> <div/>;\n',encoding='utf-8')
    (clone/'src/a.tsx').write_text('export const A=()=> { return <div/>;\n',encoding='utf-8')
    key=str(clone.resolve())
    j._V4227_MEASURE_CACHE[key]={'count':3,'output':'','rows':[{'file':'src/a.tsx','code':'1005','line':1,'col':34,'message':"'}' expected.",'raw':"src/a.tsx(1,34): error TS1005: '}' expected."}], 'at':0}
    old_commit=j._v4227_prev_commit_cluster
    called=[]
    try:
        j._v4227_prev_commit_cluster=lambda *a,**k:(called.append(True) or (True,''))
        ok,why=j._v4224_commit_cluster(root,clone,{},['src/a.tsx'],10,3)
        ck('new syntax regression blocks improving cluster',not ok,why)
        ck('legacy commit not reached',not called,called)
    finally:j._v4227_prev_commit_cluster=old_commit

# Syntax-clean cached candidate is allowed to reach the existing compiler-proof commit.
with tempfile.TemporaryDirectory() as td:
    root=Path(td);clone=root/'clone';(root/'src').mkdir(parents=True);(clone/'src').mkdir(parents=True)
    (root/'src/a.tsx').write_text('export const A=1;\n',encoding='utf-8');(clone/'src/a.tsx').write_text('export const A=2;\n',encoding='utf-8')
    j._V4227_MEASURE_CACHE[str(clone.resolve())]={'count':2,'output':'','rows':[{'file':'src/a.tsx','code':'2322','line':1,'col':1,'message':'semantic','raw':'semantic'}], 'at':0}
    old_commit=j._v4227_prev_commit_cluster
    try:
        j._v4227_prev_commit_cluster=lambda *a,**k:(True,'')
        ok,why=j._v4224_commit_cluster(root,clone,{},['src/a.tsx'],5,2)
        ck('syntax-clean improving cluster reaches commit',ok,why)
    finally:j._v4227_prev_commit_cluster=old_commit

print(f'V42.27 regression: {len(checks)}/{len(checks)} PASS')
