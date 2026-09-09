from pathlib import Path
import tempfile, zipfile, json, sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import local_qwen_project as m

passed=0

def ck(name, cond, detail=''):
    global passed
    if not cond: raise AssertionError(f'{name}: {detail}')
    passed += 1
    print('PASS',name)

with tempfile.TemporaryDirectory(prefix='v4261_clone_') as td:
    root=Path(td); work=root/'working'; trial=root/'trial_01'
    (work/'src').mkdir(parents=True)
    (work/'src'/'main.ts').write_text('export const ok = true;\n',encoding='utf-8')
    blob=work/'.jarvis_shared_build_cache'/'cache'/'npm'/'_cacache'/'content-v2'/'sha512'/'00'/'aa'/'blob'
    blob.parent.mkdir(parents=True); blob.write_text('volatile',encoding='utf-8')
    m._copy_resume_workspace(work,trial)
    ck('authored source cloned', (trial/'src'/'main.ts').exists())
    ck('shared cache excluded from trial', not (trial/'.jarvis_shared_build_cache').exists())

with tempfile.TemporaryDirectory(prefix='v4261_import_') as td:
    root=Path(td); z=root/'checkpoint.zip'; out=root/'out'
    with zipfile.ZipFile(z,'w') as f:
        f.writestr('project/src/main.ts','export {};\n')
        f.writestr('project/.jarvis_shared_build_cache/cache/npm/_cacache/content-v2/blob','volatile')
    report=m._safe_extract_zip(z,out)
    ck('resume ZIP source extracted', (out/'src'/'main.ts').exists())
    ck('resume ZIP shared cache skipped', not (out/'.jarvis_shared_build_cache').exists(), report)
    ck('resume import reports rebuildable skip', int(report.get('skipped_rebuildable',0)) >= 1, report)

with tempfile.TemporaryDirectory(prefix='v4261_prune_') as td:
    root=Path(td); (root/'src').mkdir(); (root/'src'/'a.py').write_text('x=1\n')
    cache=root/'.jarvis_shared_build_cache'/'cache'/'npm'; cache.mkdir(parents=True); (cache/'blob').write_text('x')
    removed=m._v4220_prune_rebuildable_tree(root)
    ck('pre-package prune removes nested shared cache', not (root/'.jarvis_shared_build_cache').exists(), removed)
    ck('pre-package prune preserves source', (root/'src'/'a.py').exists())

ident=m._v36_release_identity()
ck('active release is V42.63', ident.get('version')=='V42.63.0', ident)
ck('identity advertises shared-cache isolation', ident.get('volatile_shared_build_cache_isolated') is True, ident)
ck('27B hardware-fit context preserved', int(ident.get('qwen38_runtime_context_default',0))==40960, ident)

print(f'V42.61 volatile shared cache isolation checks passed: {passed}/10')
