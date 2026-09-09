from pathlib import Path
import tempfile, sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import local_qwen_project as m
import jarvis_v4251_repair as tx

passed=0
def ck(name,cond,detail=''):
    global passed
    if not cond: raise AssertionError(f'{name}: {detail}')
    passed+=1; print('PASS',name)


def make_project(root):
    hooks=root/'src'/'hooks'; hooks.mkdir(parents=True)
    names=['useCategories.ts','useCheckouts.ts','useCSVImportExport.ts','usePersons.ts']
    for name in names:
        (hooks/name).write_text(
            "// production integration uses invoke/backend service seam\nexport const value = 'mock';\n",
            encoding='utf-8')
    tests=root/'tests'; tests.mkdir()
    return names


def audit_for(names):
    issues=[]
    for name in names:
        issues.append({'file':'src/hooks/'+name,'kind':'functional_mock',
                       'problem':'Replace local/mock behavior with real invoke backend integration.'})
    issues.append({'file':'tests/application.integration.test.ts','kind':'functional_test_coverage',
                   'problem':'workflow test missing'})
    return {'issues':issues}

orig=tx.repair_transaction
try:
    # A four-owner connected cluster must begin as ONE owner, not one giant response.
    with tempfile.TemporaryDirectory(prefix='v4263_single_') as td:
        root=Path(td); names=make_project(root); calls=[]
        def repair(g,req,manifest,work,group,callback=None,prior_errors=None):
            calls.append(list(tx._cluster_owner_files(group)))
            return True, []
        tx.repair_transaction=repair
        changed=m._v429_repair_audit_round('finish',{'files':[]},root,audit_for(names),None,1)
        ck('single-owner fast path accepted',changed is True)
        ck('first transaction owns exactly one issue file',len(calls)==1 and len(calls[0])==1,calls)
        ck('no four-owner atomic response on fast path',all(len(x)<=2 for x in calls),calls)

    # If every solo owner fails twice, escalation may add ONE directly connected peer,
    # but must never serialize the full four-owner cluster.
    with tempfile.TemporaryDirectory(prefix='v4263_pair_') as td:
        root=Path(td); names=make_project(root); calls=[]
        def repair2(g,req,manifest,work,group,callback=None,prior_errors=None):
            calls.append(list(tx._cluster_owner_files(group)))
            return False, ['no improvement']
        tx.repair_transaction=repair2
        m._v429_repair_audit_round('finish',{'files':[]},root,audit_for(names),None,1)
        m._v429_repair_audit_round('finish',{'files':[]},root,audit_for(names),None,2)
        ck('all attempted batches stay at two owners or less',calls and all(1 <= len(x) <= 2 for x in calls),calls)
        ck('bounded direct-peer escalation occurs after solo exhaustion',any(len(x)==2 for x in calls),calls)
        ck('four-owner cluster is never a model batch',not any(len(x)>=3 for x in calls),calls)

    ident=m._v36_release_identity()
    ck('release is V42.64',ident.get('version')=='V42.64.0',ident)
    ck('connected graph is preserved',ident.get('connected_dependency_graph_preserved') is True,ident)
    ck('default batch is one owner',ident.get('default_issue_owners_per_transaction')==1,ident)
    ck('maximum atomic batch is two owners',ident.get('max_issue_owners_per_atomic_transaction')==2,ident)
    ck('V42.62 cache isolation remains advertised',ident.get('candidate_shared_cache_isolation_preserved') is True,ident)
    ck('27B hardware-fit context remains 40960',int(ident.get('qwen38_runtime_context_default',0))==40960,ident)
finally:
    tx.repair_transaction=orig

print(f'V42.63 minimal-atomic connected-evidence checks passed: {passed}/12')
