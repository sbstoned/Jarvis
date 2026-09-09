from pathlib import Path
import json, tempfile
import local_qwen_project as l

results=[]
def check(name, cond, detail=''):
    results.append((name,bool(cond),str(detail)))
    print(('PASS' if cond else 'FAIL')+': '+name+((' :: '+str(detail)) if detail else ''))

def manifest_fixture():
    return {
      'components':[
        {'id':'ui','root':'.','purpose':'React UI','toolchain_adapter':'react'},
        {'id':'tauri-core','root':'src-tauri','purpose':'Rust backend','toolchain_adapter':'rust'}],
      'canonical_domain_contracts':{
        'entities':[
          {'name':'Category','fields':[{'name':'id','type':'string','required':True},{'name':'name','type':'string','required':True}]},
          {'name':'Tool','fields':[{'name':'id','type':'string','required':True},{'name':'name','type':'string','required':True},{'name':'condition','type':'ToolCondition','required':True}]},
          {'name':'CheckoutEvent','fields':[{'name':'id','type':'string','required':True},{'name':'event_type','type':'CheckoutEventType','required':True}]},
        ],
        'enums':[{'name':'ToolCondition','values':['NEW','GOOD','FAIR','POOR']},{'name':'CheckoutEventType','values':['CHECKOUT','CHECKIN']}],
        'shared_rules':[]},
      'files':[
        {'path':'src/contracts/category.ts','purpose':'Canonical Category and ToolCondition compatibility type','phase':'data','exports':['Category','ToolCondition'],'contracts':['interface Category','type ToolCondition']},
        {'path':'src/contracts/tool.ts','purpose':'Canonical Tool contract','phase':'data','exports':['Tool'],'contracts':['interface Tool']},
        {'path':'src/contracts/checkout_event.ts','purpose':'Canonical CheckoutEvent and CheckoutEventType','phase':'data','exports':['CheckoutEvent','CheckoutEventType'],'contracts':['interface CheckoutEvent','enum CheckoutEventType']},
        {'path':'src-tauri/src/models/category.rs','purpose':'Canonical Category model','phase':'data','exports':['Category'],'contracts':['struct Category']},
        {'path':'src-tauri/src/models/tool.rs','purpose':'Canonical Tool and compatibility ToolCondition','phase':'data','exports':['Tool','ToolCondition'],'contracts':['struct Tool','enum ToolCondition']},
        {'path':'src-tauri/src/models/tool_condition.rs','purpose':'Canonical ToolCondition enum','phase':'data','exports':['ToolCondition'],'contracts':['enum ToolCondition']},
        {'path':'src-tauri/src/models/checkout_event.rs','purpose':'Canonical CheckoutEvent and compatibility CheckoutEventType','phase':'data','exports':['CheckoutEvent','CheckoutEventType'],'contracts':['struct CheckoutEvent','enum CheckoutEventType']},
        {'path':'src-tauri/src/models/checkout_event_type.rs','purpose':'Canonical CheckoutEventType enum','phase':'data','exports':['CheckoutEventType'],'contracts':['enum CheckoutEventType']},
      ],
      'implementation_order':[]
    }

m0=manifest_fixture()
baseline=l._v428_prev_domain_owner_map(m0)
check('fixture reproduces bad UI ToolCondition owner', baseline.get(('ui','ToolCondition'))=='src/contracts/category.ts', baseline.get(('ui','ToolCondition')))
check('fixture reproduces bad UI CheckoutEventType aggregate owner', baseline.get(('ui','CheckoutEventType'))=='src/contracts/checkout_event.ts', baseline.get(('ui','CheckoutEventType')))

m,changes=l._v428_reconcile_contract_manifest(m0,aggressive=False)
check('reconciliation inserts ToolCondition provider', l._manifest_file_item(m,'src/contracts/tool_condition.ts') is not None, changes)
check('reconciliation inserts CheckoutEventType provider', l._manifest_file_item(m,'src/contracts/checkout_event_type.ts') is not None, changes)
owners=l._v40_domain_owner_map(m)
check('ToolCondition owner corrected', owners.get(('ui','ToolCondition'))=='src/contracts/tool_condition.ts', owners.get(('ui','ToolCondition')))
check('CheckoutEventType owner corrected', owners.get(('ui','CheckoutEventType'))=='src/contracts/checkout_event_type.ts', owners.get(('ui','CheckoutEventType')))
cat=l._manifest_file_item(m,'src/contracts/category.ts')
check('old Category owner no longer exports ToolCondition', 'ToolCondition' not in (cat.get('exports') or []), cat.get('exports'))
reexp=m.get('_v428_compat_reexports') or {}
check('compatibility re-export recorded for category', any(x.get('symbol')=='ToolCondition' for x in reexp.get('src/contracts/category.ts',[])), reexp)

category_src=l._v428_render_contract_source(m,'src/contracts/category.ts')
tool_src=l._v428_render_contract_source(m,'src/contracts/tool.ts')
tool_cond_src=l._v428_render_contract_source(m,'src/contracts/tool_condition.ts')
check('deterministic Category source defines exact symbol', 'export interface Category' in category_src, category_src)
check('deterministic Category source re-exports moved enum', 'export { ToolCondition }' in category_src, category_src)
check('deterministic Tool source imports canonical enum', 'ToolCondition' in tool_src and 'from "./tool_condition"' in tool_src, tool_src)
check('deterministic Tool source re-exports canonical enum', 'export { ToolCondition }' in tool_src, tool_src)
check('deterministic enum contains frozen values', all(x in tool_cond_src for x in ('NEW','GOOD','FAIR','POOR')), tool_cond_src)

# Idiomatic Rust enum variants must match canonical wire values case-insensitively.
rust_enum='''#[derive(Debug, Clone)]\npub enum ToolCondition { New, Good, Fair, Poor }\n'''
check('idiomatic Rust enum values satisfy canonical enum meaning', not l._v381_candidate_domain_contract_error(m,'src-tauri/src/models/tool_condition.rs',rust_enum), l._v381_candidate_domain_contract_error(m,'src-tauri/src/models/tool_condition.rs',rust_enum))
rust_dup='''pub struct Tool { pub id: String, pub name: String, pub condition: ToolCondition }\npub enum ToolCondition { New, Good, Fair, Poor }'''
err=l._v381_candidate_domain_contract_error(m,'src-tauri/src/models/tool.rs',rust_dup)
check('competing Rust enum still rejected', 'defines competing ToolCondition' in err, err)

with tempfile.TemporaryDirectory() as td:
    providers=[]
    for row in l._v40_domain_owner_payload(m).get('owners',[]):
        p=l._v40_norm_rel(row.get('provider'))
        if p and p not in providers:providers.append(p)
    committed=[]
    for p in providers:
        if l._v428_commit_deterministic_provider(td,m,p):committed.append(p)
    check('deterministic provider materialization accepts synthetic UI contracts', 'src/contracts/tool_condition.ts' in committed and l._v413_is_accepted(td,'src/contracts/tool_condition.ts'), committed)
    check('deterministic provider materialization accepts Rust contracts', 'src-tauri/src/models/tool_condition.rs' in committed and l._v413_is_accepted(td,'src-tauri/src/models/tool_condition.rs'), committed)
    remaining=[p for p in providers if l._v424_provider_state_problem(td,m,p)]
    check('pure canonical provider set has zero provider-health debt', not remaining, remaining)

    # Accepted-state loop clock: rejected drafts do not count as progress.
    a,_=l._v428_register_provider_visit(td,m,'src/contracts/category.ts')
    b,_=l._v428_register_provider_visit(td,m,'src/contracts/tool.ts')
    c,vis=l._v428_register_provider_visit(td,m,'src/contracts/category.ts')
    check('provider rotation triggers graph escalation after no accepted progress', c is True, vis)
    # A new accepted revision resets the rotation clock.
    extra=Path(td)/'note.txt';extra.write_text('x',encoding='utf-8');l._v413_mark_accepted(td,'note.txt','test-progress')
    stalled,vis2=l._v428_register_provider_visit(td,m,'src/contracts/tool.ts')
    check('new accepted revision resets provider loop clock', stalled is False and len(vis2)==1, vis2)

    # Exact TS2688 regression.
    pkg={'dependencies':{'tauri-plugin-fs':'1','tauri-plugin-dialog':'1','tauri-plugin-shell':'1'},'devDependencies':{}}
    Path(td,'package.json').write_text(json.dumps(pkg),encoding='utf-8')
    Path(td,'tsconfig.json').write_text(json.dumps({'compilerOptions':{'types':['vite/client','tauri-plugin-fs/tauri-plugin-fs-api','tauri-plugin-dialog/tauri-plugin-dialog-api','tauri-plugin-shell/tauri-plugin-shell-api']}}),encoding='utf-8')
    mf={'components':[{'id':'ui','root':'.','toolchain_adapter':'react'}],'files':[{'path':'package.json'},{'path':'tsconfig.json'}]}
    failure="""TS2688: Cannot find type definition file for 'tauri-plugin-fs/tauri-plugin-fs-api'.\nTS2688: Cannot find type definition file for 'tauri-plugin-dialog/tauri-plugin-dialog-api'.\nTS2688: Cannot find type definition file for 'tauri-plugin-shell/tauri-plugin-shell-api'."""
    repaired=l._v428_repair_ts2688(td,mf,failure)
    types=json.loads(Path(td,'tsconfig.json').read_text()).get('compilerOptions',{}).get('types',[])
    check('TS2688 dependency module type-roots repaired deterministically', repaired and types==['vite/client'], types)

# AUTO contract-graph root cause is a specialist job; manual mode stays locked.
l.configure_project_qwen_routing('auto')
target,reason=l._v426_route_for_call('V42.8 contract graph root-cause reconciliation','audit','small')
check('AUTO contract graph reconciliation routes to new 27B Q2 specialist', target=='27b38q2', (target,reason))
l.configure_project_qwen_routing('9b35')
target,_=l._v426_route_for_call('V42.8 contract graph root-cause reconciliation','audit','small')
check('manual 9B remains strict during graph reconciliation', target=='9b35', target)
l.clear_project_qwen_routing()

# React requirement debt that may render UI must use TSX.
comp,path=l._v423_feature_owner_path(m0,'history')
check('React history debt owner uses TSX', path.endswith('.tsx'), path)

check('contract graph skill exists', (l.V36_SKILLS_DIR/'contract-graph-reconciliation.md').exists())
identity=l._v36_release_identity()
ver=str(identity.get('version') or '').lstrip('V'); parts=tuple(int(x) for x in ver.split('.') if x.isdigit()); check('release identity is V42.8-compatible or newer', parts >= (42,8), identity.get('version'))
check('release reports new 27B graph specialist takeover', identity.get('new_27b_contract_graph_specialist_takeover') is True, identity)
check('legacy 27B remains excluded from AUTO', identity.get('legacy_27b_auto_eligible') is False)
check('strict zero-debt publish gate preserved', identity.get('strict_zero_debt_publish_gate') is True)
check('skill registry expanded', len(list(l.V36_SKILLS_DIR.glob('*.md')))>=80, len(list(l.V36_SKILLS_DIR.glob('*.md'))))
check('universal toolchain registry preserved', len(l._v34_toolchain_catalog())>=73, len(l._v34_toolchain_catalog()))

passed=sum(1 for _,ok,_ in results if ok)
print(f'\nV42.8 contract graph reconciliation: {passed}/{len(results)} PASS')
if passed!=len(results):raise SystemExit(1)
