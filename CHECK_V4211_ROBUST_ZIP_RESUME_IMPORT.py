from pathlib import Path
import json, os, shutil, stat, sys, tempfile, zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import local_qwen_project as q

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+f' | {name}'+(f' | {detail}' if detail else ''))

check('V4211 flag enabled', getattr(q,'V4211_ZIP_RESUME_IMPORT',False))
identity=q._v36_release_identity()
ver=str(identity.get('version') or '')
try:
    parts=[int(x) for x in ver.lstrip('Vv').split('.')[:2]]
    newer=(parts[0],parts[1]) >= (42,11)
except Exception:
    newer=False
check('release version V42.11-compatible or newer', newer, ver)
check('robust resume identity enabled', identity.get('robust_resume_zip_import') is True)
check('safe extractor callable', callable(getattr(q,'_safe_extract_zip',None)))

with tempfile.TemporaryDirectory(prefix='v4211_zip_test_') as td:
    td=Path(td); z=td/'wrapped.zip'; out=td/'very'/'deep'/'generated_projects'/'resume_job'/'working'
    long_diag='project/.jarvis_failures/model_outputs/'+'x'*180+'_src-tauri__src__models__category.rs.txt'
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as a:
        a.writestr('project/package.json','{"scripts":{"build":"vite build"}}')
        a.writestr('project/src/main.ts','export const ok = true;\n')
        a.writestr('project/src-tauri/src/models/category.rs','pub struct Category { pub id: String }\n')
        a.writestr('project/node_modules/pkg/index.js','cache')
        a.writestr('project/src-tauri/target/debug/cache.bin',b'1234')
        a.writestr('project/.jarvis_runtime/cache/npm/blob','cache')
        a.writestr('project/.jarvis_backups/v36/file.txt','backup')
        a.writestr(long_diag,'diagnostic')
    report=q._safe_extract_zip(z,out)
    check('single wrapper stripped', report.get('wrapper_stripped')=='project', str(report.get('wrapper_stripped')))
    check('package lands at project root', (out/'package.json').is_file())
    check('authored TS source extracted', (out/'src/main.ts').is_file())
    check('authored Rust source extracted', (out/'src-tauri/src/models/category.rs').is_file())
    check('node_modules pruned', not (out/'node_modules').exists())
    check('Cargo target pruned', not (out/'src-tauri/target').exists())
    check('Jarvis runtime cache pruned', not (out/'.jarvis_runtime').exists())
    check('Jarvis backups pruned', not (out/'.jarvis_backups').exists())
    check('long malformed-output mirror pruned', not (out/'.jarvis_failures/model_outputs').exists())
    check('import report written', (out/'JARVIS_V4211_IMPORT_REPORT.json').is_file())
    check('rebuildable skip count recorded', int(report.get('skipped_rebuildable',0)) >= 5, str(report.get('skipped_rebuildable')))

    # Symlinks in ZIPs are ignored rather than materialized.
    z2=td/'symlink.zip'; out2=td/'symlink_out'
    zi=zipfile.ZipInfo('project/link')
    zi.create_system=3
    zi.external_attr=(stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(z2,'w') as a:
        a.writestr('project/src/main.py','print("ok")\n')
        a.writestr(zi,'../../outside')
    r2=q._safe_extract_zip(z2,out2)
    check('ZIP symlink rejected', int(r2.get('rejected_symlinks',0))==1)
    check('ZIP symlink not materialized', not (out2/'link').exists())

    # Traversal and drive-absolute members remain hard failures.
    z3=td/'traversal.zip'
    with zipfile.ZipFile(z3,'w') as a: a.writestr('../escape.txt','bad')
    try:
        q._safe_extract_zip(z3,td/'traversal_out'); traversal_rejected=False
    except Exception: traversal_rejected=True
    check('path traversal remains rejected', traversal_rejected)

    z4=td/'drive_absolute.zip'
    with zipfile.ZipFile(z4,'w') as a: a.writestr('C:/escape.txt','bad')
    try:
        q._safe_extract_zip(z4,td/'drive_out'); drive_rejected=False
    except Exception: drive_rejected=True
    check('drive-absolute ZIP member rejected', drive_rejected)

    # Final package must not re-ship internal build/runtime/failure caches.
    pkgroot=td/'pkgroot'; (pkgroot/'src').mkdir(parents=True); (pkgroot/'src/main.py').write_text('print("ok")\n')
    (pkgroot/'.jarvis_runtime/cache').mkdir(parents=True); (pkgroot/'.jarvis_runtime/cache/x').write_text('x')
    (pkgroot/'.jarvis_failures/model_outputs').mkdir(parents=True); (pkgroot/'.jarvis_failures/model_outputs/x.txt').write_text('x')
    oldgen=q.GENERATED_DIR; q.GENERATED_DIR=td/'generated'; q.GENERATED_DIR.mkdir()
    try:
        packaged,count=q._package_workspace_zip(pkgroot,'test_package','4211')
        with zipfile.ZipFile(packaged) as a: names=set(a.namelist())
        check('packager keeps authored source', 'src/main.py' in names)
        check('packager excludes .jarvis_runtime', not any(n.startswith('.jarvis_runtime/') for n in names))
        check('packager excludes .jarvis_failures', not any(n.startswith('.jarvis_failures/') for n in names))
        check('packaged ZIP integrity', zipfile.ZipFile(packaged).testzip() is None)
    finally:
        q.GENERATED_DIR=oldgen

source=(ROOT/'local_qwen_project.py').read_text(encoding='utf-8',errors='replace')
check('existing-project editor consumes extraction report', 'import_report = _safe_extract_zip(source_zip, work)' in source)
check('resume import reports pruning progress', 'pruned' in source and 'rebuildable/cache artifacts' in source)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT {passed}/{len(checks)} PASS')
if passed != len(checks): raise SystemExit(1)
