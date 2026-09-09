from __future__ import annotations
import json, tempfile, shutil
from pathlib import Path
import local_qwen_project as j
from jarvis_v4225_semantic import semantic_context

checks=[]
def ck(name,cond,detail=''):
    if not cond:
        raise AssertionError(f'{name}: {detail}')
    checks.append(name)

ident=j._v36_release_identity()
ck('release version', ident.get('version')=='V42.25.0', ident)
ck('engine semantic', ident.get('semantic_navigation_text_index') is True, ident)
ck('event projection', ident.get('durable_event_projection_from_project_journal') is True, ident)
ck('loop guard advertised', ident.get('global_same_revision_repair_fingerprint_guard') is True, ident)
ck('provisional gate advertised', ident.get('provisional_multifile_gate_defers_single_file_replay') is True, ident)
ck('spill advertised', ident.get('prompt_spill_retention') is True, ident)
ck('artifact separation advertised', ident.get('source_artifact_plane_separation') is True, ident)

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    (root/'src/hooks').mkdir(parents=True)
    (root/'src/components').mkdir(parents=True)
    (root/'src/types').mkdir(parents=True)
    (root/'src/App.tsx').write_text("import { View } from './components/View';\nexport default function App(){ return <View/> }\n",encoding='utf-8')
    (root/'src/components/View.tsx').write_text("import { useThing } from '../hooks/useThing';\nexport interface ViewProps { value: string }\nexport const View=({value}:ViewProps)=><div>{value}</div>;\n",encoding='utf-8')
    (root/'src/hooks/useThing.ts').write_text("export interface Thing { value: string }\nexport function useThing(): Thing { return {value:'x'} }\n",encoding='utf-8')
    (root/'src/types/stable.ts').write_text("export interface Stable { id: string }\n",encoding='utf-8')

    failure='\n'.join([
        "src/App.tsx(2,40): error TS2741: Property 'value' is missing in type '{}' but required in type 'ViewProps'.",
        "src/hooks/useThing.ts(2,10): error TS2339: Property 'missing' does not exist on type 'Thing'.",
        "src/hooks/useThing.ts(2,20): error TS2322: Type 'number' is not assignable to type 'string'.",
        "src/components/View.tsx(3,15): error TS6133: 'useThing' is declared but its value is never read.",
    ])
    manifest={'components':[{'id':'react','root':'.','toolchain_adapter':'react'}], 'files':[
        {'path':'src/App.tsx','purpose':'Main app consumer','contracts':[]},
        {'path':'src/components/View.tsx','purpose':'React view','contracts':['ViewProps']},
        {'path':'src/hooks/useThing.ts','purpose':'Hook producer','contracts':['Thing']},
        {'path':'src/types/stable.ts','purpose':'Canonical TypeScript definition','contracts':['Stable']},
    ]}
    cluster,grouped=j._v4224_select_ts_cluster(root,manifest,failure)
    ck('app is high leverage first', cluster and cluster[0]=='src/App.tsx', cluster)
    ck('hook promoted ahead of low-value component', cluster.index('src/hooks/useThing.ts') < cluster.index('src/components/View.tsx'), cluster)

    sem=semantic_context(root,'src/components/View.tsx',[{'line':2,'col':10}],use_lsp=False,max_chars=8000)
    ck('semantic imported contract', 'useThing.ts' in sem, sem[:500])
    ck('semantic reverse/contract evidence', 'READ-ONLY' in sem or 'SEMANTIC' in sem, sem[:500])

    # Event stream -> projection.
    j._append_project_event(root,'v4225_test_event','test projection',file='src/App.tsx',before=4,after=3)
    proj=json.loads((root/j.V4225_PROJECTION_FILE).read_text(encoding='utf-8'))
    ck('projection sequence', int(proj.get('seq') or 0)>=1, proj)
    ck('projection keeps delta', proj.get('before')==4 and proj.get('after')==3, proj)

    # Global same-revision action guard: first two allowed, third blocked.
    a=j._v4225_loop_guard_before(root,'src/App.tsx',['same strategy'],failure)
    b=j._v4225_loop_guard_before(root,'src/App.tsx',['same strategy'],failure)
    c=j._v4225_loop_guard_before(root,'src/App.tsx',['same strategy'],failure)
    ck('loop guard first allowed',a[0] is True,a)
    ck('loop guard second allowed',b[0] is True,b)
    ck('loop guard third blocked',c[0] is False,c)

    # Provisional multi-file gate must skip single-file no-progress replay while still
    # running base ownership + syntax + semantic checks.
    old_base=j._v4216_prev_candidate_transaction_error
    old_syn=j._v4216_language_syntax_error
    old_sem=j._v4221_semantic_role_error
    old_full=j._v4225_prev_candidate_transaction_error
    calls=[]
    try:
        j._v4216_prev_candidate_transaction_error=lambda *a,**k: (calls.append('base') or '')
        j._v4216_language_syntax_error=lambda *a,**k: (calls.append('syntax') or '')
        j._v4221_semantic_role_error=lambda *a,**k: (calls.append('semantic') or '')
        j._v4225_prev_candidate_transaction_error=lambda *a,**k: 'SINGLE_FILE_REPLAY_SHOULD_NOT_RUN'
        j._V4225_CTX.provisional_cluster=True
        err=j._candidate_transaction_error(root,manifest,'src/App.tsx',(root/'src/App.tsx').read_text(),validation_failure=failure)
        ck('provisional bypasses single-file replay',err=='',err)
        ck('provisional keeps safety gates',calls==['base','syntax','semantic'],calls)
        j._V4225_CTX.provisional_cluster=False
        err2=j._candidate_transaction_error(root,manifest,'src/App.tsx',(root/'src/App.tsx').read_text(),validation_failure=failure)
        ck('ordinary path still uses full gate',err2=='SINGLE_FILE_REPLAY_SHOULD_NOT_RUN',err2)
    finally:
        j._V4225_CTX.provisional_cluster=False
        j._v4216_prev_candidate_transaction_error=old_base
        j._v4216_language_syntax_error=old_syn
        j._v4221_semantic_role_error=old_sem
        j._v4225_prev_candidate_transaction_error=old_full

    # Candidate/artifact plane is outside authored working tree.
    td2,clone=j._v4224_clone_workspace(root)
    try:
        ck('cluster artifact outside source', not str(Path(td2).resolve()).startswith(str(root.resolve())+str(Path('/'))), td2)
        ck('artifact path named jarvis_artifacts','.jarvis_artifacts' in str(td2),td2)
        ck('source cloned',(clone/'src/App.tsx').is_file(),clone)
    finally:
        shutil.rmtree(td2,ignore_errors=True)

    # Existing context budget compaction now retains a spill artifact and diagnostic index.
    old_budget=j._v4225_prev_qwen_budget_prompt
    old_threshold=j.V4225_PROMPT_SPILL_CHARS
    try:
        j._v4225_prev_qwen_budget_prompt=lambda prompt,**kwargs: 'COMPACTED'
        j.V4225_PROMPT_SPILL_CHARS=12000
        j._V4225_CTX.prompt_work=root
        raw=('HEADER\n'+'src/App.tsx(1,1): error TS2741: Property x missing.\n')*700
        compact=j._qwen_budget_prompt(raw,stage='test')
        ck('spill marker returned','V42.25 CONTEXT SPILL' in compact,compact[:300])
        spills=list((j._v4225_artifact_root(root)/'spill').glob('prompt_*.txt'))
        ck('full prompt spill persisted',bool(spills),spills)
    finally:
        j._v4225_prev_qwen_budget_prompt=old_budget
        j.V4225_PROMPT_SPILL_CHARS=old_threshold
        j._V4225_CTX.prompt_work=None

print(f'V42.25 regression: {len(checks)}/{len(checks)} PASS')
