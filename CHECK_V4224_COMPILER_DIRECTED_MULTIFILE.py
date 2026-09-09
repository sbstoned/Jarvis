import tempfile
from pathlib import Path
import local_qwen_project as j

checks=[]
def ck(name,cond,detail=''):
    checks.append((name,bool(cond),detail))
    if not cond: raise AssertionError(f'{name}: {detail}')

ident=j._v36_release_identity()
ck('release version',ident.get('version')=='V42.24.0',ident)
ck('release engine',ident.get('engine')=='COMPILER_DIRECTED_MULTI_FILE_TRANSACTION_FACTORY',ident)
ck('cluster advertised',ident.get('compiler_connected_consumer_clusters') is True,ident)
ck('atomic commit advertised',ident.get('atomic_multifile_typescript_commit') is True,ident)
ck('delta required',ident.get('cluster_commit_requires_global_ts_error_reduction') is True,ident)
ck('leaf reentry blocked',ident.get('same_revision_exhausted_cluster_blocks_leaf_reentry') is True,ident)
ck('legacy blanket provider prepass disabled',j.V424_PROVIDER_FIRST is False,j.V424_PROVIDER_FIRST)
ck('cluster file cap bounded',2 <= j.V4224_MAX_CLUSTER_FILES <= 8,j.V4224_MAX_CLUSTER_FILES)
ck('attempt cap bounded',1 <= j.V4224_MAX_CLUSTER_ATTEMPTS <= 3,j.V4224_MAX_CLUSTER_ATTEMPTS)

with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/'src/components').mkdir(parents=True);(root/'src/hooks').mkdir(parents=True)
    (root/'src/App.tsx').write_text("import { InventoryView } from './components/InventoryView';\nimport { CheckoutHistoryView } from './components/CheckoutHistoryView';\nexport const App=()=> <><InventoryView/><CheckoutHistoryView/></>;\n")
    (root/'src/components/InventoryView.tsx').write_text("import { useTools } from '../hooks/useTools';\nexport const InventoryView=()=> <div/>;\n")
    (root/'src/components/CheckoutHistoryView.tsx').write_text("import { useCheckouts } from '../hooks/useCheckouts';\nexport const CheckoutHistoryView=()=> <div/>;\n")
    (root/'src/hooks/useTools.ts').write_text("export const useTools=()=>({tools:[]});\n")
    (root/'src/hooks/useCheckouts.ts').write_text("export const useCheckouts=()=>({records:[]});\n")
    failure="""src/App.tsx(3,24): error TS2741: Property 'tools' is missing in type '{}'.
src/components/InventoryView.tsx(2,35): error TS2345: Argument of type 'string' is not assignable.
src/components/CheckoutHistoryView.tsx(2,42): error TS2554: Expected 2 arguments, but got 0.
src/hooks/useTools.ts(1,30): error TS2339: Property 'data' does not exist.
src/hooks/useCheckouts.ts(1,30): error TS2304: Cannot find name 'useState'.
"""
    manifest={'files':[{'path':'src/App.tsx'},{'path':'src/components/InventoryView.tsx'},{'path':'src/components/CheckoutHistoryView.tsx'},{'path':'src/hooks/useTools.ts'},{'path':'src/hooks/useCheckouts.ts'}]}
    cluster,grouped=j._v4224_select_ts_cluster(root,manifest,failure)
    ck('App selected as cluster seed',cluster and cluster[0]=='src/App.tsx',cluster)
    ck('connected Inventory included','src/components/InventoryView.tsx' in cluster,cluster)
    ck('connected Checkout included','src/components/CheckoutHistoryView.tsx' in cluster,cluster)
    ck('connected hook included','src/hooks/useTools.ts' in cluster and 'src/hooks/useCheckouts.ts' in cluster,cluster)
    ck('diagnostics grouped',len(grouped)>=5,grouped)

print(f'V42.24 regression: {len(checks)}/{len(checks)} PASS')
