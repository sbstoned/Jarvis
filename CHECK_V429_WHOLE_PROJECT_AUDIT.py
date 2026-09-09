from pathlib import Path
import json, tempfile, shutil, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as j

checks=[]
def ck(name,cond,detail=''):
    checks.append((name,bool(cond),detail))

# Synthetic manifest with a canonical provider and two components.
with tempfile.TemporaryDirectory() as td:
    w=Path(td)
    manifest={
      'project_name':'AuditDemo',
      'canonical_domain_contracts':{
        'ui':{'ToolCondition':{'kind':'enum','values':['NEW','GOOD','FAIR','POOR']}},
      },
      'components':[
        {'id':'ui','root':'.','toolchain_adapter':'react','files':[]},
        {'id':'backend','root':'backend','toolchain_adapter':'rust','files':[]},
      ],
      'files':[
        {'path':'src/contracts/tool_condition.ts','purpose':'Canonical ToolCondition contract','phase':'foundation','exports':['ToolCondition'],'contracts':['ToolCondition'],'v428_contract_provider':True},
        {'path':'src/main.tsx','purpose':'Foundation UI entry','phase':'foundation','exports':[]},
        {'path':'backend/src/lib.rs','purpose':'Backend root','phase':'foundation','exports':[]},
      ]
    }
    # Force owner mapping in the manifest-style payload used by V40.
    manifest['canonical_domain_owners']=[{'scope':'ui','symbol':'ToolCondition','provider':'src/contracts/tool_condition.ts'}]
    # Missing provider should be found by audit.
    aud=j._v429_whole_project_audit(w,'build a tool app with tests',manifest,run_components=False)
    ck('audit detects missing planned provider',any(x.get('file')=='src/contracts/tool_condition.ts' for x in aud['issues']))
    ck('audit detects missing foundation files',sum(1 for x in aud['issues'] if x.get('kind')=='missing')>=3)

    # Same-provider counter escalates at exactly configured threshold.
    c1,_=j._v429_register_provider_failure(w,'src/contracts/tool_condition.ts')
    c2,_=j._v429_register_provider_failure(w,'src/contracts/tool_condition.ts')
    ck('same provider counter increments',c1==1 and c2==2,(c1,c2))
    j._v429_quarantine_provider(w,'src/contracts/tool_condition.ts','repeat')
    ck('provider quarantine tied to accepted token',j._v429_is_quarantined(w,'src/contracts/tool_condition.ts'))

    # Independent component validation: monkeypatch so both failures are collected.
    old_disc=j._v35_discover_components; old_val=j._v35_validate_component
    try:
        j._v35_discover_components=lambda work,m:[
            {'id':'ui','root':'.','toolchain_adapter':'react'},
            {'id':'backend','root':'backend','toolchain_adapter':'rust'},
        ]
        j._v35_validate_component=lambda work,m,c,user_request='':(False,f"FAIL-{c['id']}")
        aud2=j._v429_whole_project_audit(w,'demo',manifest,run_components=True)
        fails=[x for x in aud2['issues'] if x.get('kind')=='component_validation']
        ck('whole audit collects both component failures',len(fails)==2,[x.get('component') for x in fails])
        ck('audit writes consolidated report',(w/j.V429_AUDIT_FILE).exists())
    finally:
        j._v35_discover_components=old_disc;j._v35_validate_component=old_val


# Continuous IDE-style diagnostics: accepted saves get an immediate report and
# bounded real analyzers can record component errors without waiting for final audit.
with tempfile.TemporaryDirectory() as td:
    w=Path(td)
    (w/'src').mkdir(parents=True,exist_ok=True)
    (w/'src/main.ts').write_text('export const answer: number = 42;\n',encoding='utf-8')
    manifest_live={
      'components':[{'id':'ui','root':'.','toolchain_adapter':'typescript'}],
      'files':[{'path':'src/main.ts','purpose':'main source','phase':'foundation','exports':['answer']}],
    }
    j._v413_mark_accepted(w,'src/main.ts','test')
    issues=j._v429_after_accepted_edit('demo',manifest_live,w,'src/main.ts',None,'test')
    ck('live diagnostics writes report',(w/j.V429_LIVE_DIAGNOSTICS_FILE).exists())
    live=json.loads((w/j.V429_LIVE_DIAGNOSTICS_FILE).read_text(encoding='utf-8'))
    ck('live diagnostics tracks accepted file','src/main.ts' in (live.get('files') or {}),live.get('files'))

    old_cmd=j._v429_live_component_command; old_run=j._run_command
    try:
        j._v429_live_component_command=lambda work,m,c:(['fake-analyzer'],Path(work))
        j._run_command=lambda cmd,cwd,timeout,env=None:(False,'FAKE TYPE ERROR in src/main.ts')
        result=j._v429_run_live_component_diagnostic('demo',manifest_live,w,'src/main.ts',None,force=True)
        ck('live real analyzer records failure',bool(result) and result[0] is False,result)
        live2=json.loads((w/j.V429_LIVE_DIAGNOSTICS_FILE).read_text(encoding='utf-8'))
        comp=(live2.get('components') or {}).get('ui') or {}
        ck('live real analyzer persists evidence',comp.get('last_ok') is False and 'FAKE TYPE ERROR' in str(comp.get('last_output') or ''),comp)
    finally:
        j._v429_live_component_command=old_cmd;j._run_command=old_run

# AUTO model routing must choose the NEW 27B specialist for V42.9 root cause stages.
try:
    j.configure_project_qwen_routing('auto')
    target,reason=j._v426_route_for_call('V42.9 quarantined provider root-cause specialist','audit','small prompt')
    ck('V42.9 quarantine route targets new 27B',target=='27b38q2',(target,reason))
    target2,reason2=j._v426_route_for_call('V42.9 whole-project root-cause global convergence','audit','small prompt')
    ck('whole-project root cause targets new 27B',target2=='27b38q2',(target2,reason2))
finally:
    try:j.clear_project_qwen_routing()
    except Exception:pass

# Final release identity advertises new engine and preserves strict gate.
r=j._v36_release_identity()
ver=str(r.get('version') or '').lstrip('V'); parts=tuple(int(x) for x in ver.split('.') if x.isdigit()); ck('release version V42.9 or newer',parts >= (42,9),r.get('version'))
ck('whole project audit enabled',r.get('whole_project_audit') is True)
ck('continuous IDE diagnostics enabled',r.get('continuous_ide_diagnostics') is True)
ck('live real component diagnostics enabled',r.get('live_real_component_diagnostics') is True)
ck('strict publish gate preserved',r.get('strict_zero_debt_publish_gate') is True)
ck('legacy 27B excluded from AUTO',r.get('legacy_27b_auto_eligible') is False)

failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL'),name,detail if detail else '')
print(f"RESULT {len(checks)-len(failed)}/{len(checks)} PASS")
if failed: raise SystemExit(1)
