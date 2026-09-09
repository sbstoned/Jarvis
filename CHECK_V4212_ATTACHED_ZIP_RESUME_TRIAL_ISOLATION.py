from pathlib import Path
import json, shutil, sys, tempfile, threading, time, zipfile

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as q

checks=[]
def check(name,cond,detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL')+f' | {name}'+(f' | {detail}' if detail else ''))

identity=q._v36_release_identity()

_ver=str(identity.get('version') or '').lstrip('Vv')
try:
    _parts=[int(x) for x in _ver.split('.')[:3]]
    while len(_parts)<3:_parts.append(0)
    _newer=tuple(_parts)>=(42,12,0)
except Exception:_newer=False
check('release version V42.12-compatible or newer', _newer, str(identity.get('version')))
check('attached ZIP resume enabled',identity.get('attached_zip_resume') is True)
check('trial source-only clone enabled',identity.get('resume_trial_source_only_clone') is True)
check('runtime cache clone isolation enabled',identity.get('runtime_cache_clone_isolation') is True)
check('true whole-project audit preserved',identity.get('true_every_component_whole_project_audit') is True)

with tempfile.TemporaryDirectory(prefix='v4212_resume_clone_') as td:
    td=Path(td); work=td/'working'; trial=td/'trial_01'
    (work/'src').mkdir(parents=True); (work/'src/main.ts').write_text('export const ok = true;\n',encoding='utf-8')
    (work/'src-tauri/src').mkdir(parents=True); (work/'src-tauri/src/lib.rs').write_text('pub fn ok() -> bool { true }\n',encoding='utf-8')
    (work/'package.json').write_text('{"scripts":{"build":"vite build"}}',encoding='utf-8')
    (work/'JARVIS_V33_ARCHITECTURE.json').write_text('{}',encoding='utf-8')
    # Reproduce the failing shape from the user's Windows trace.
    cache=work/'.jarvis_runtime/cache/npm/_cacache/content-v2/sha512/00/b1'
    cache.mkdir(parents=True); volatile=cache/('0'*120); volatile.write_text('volatile-cache',encoding='utf-8')
    (work/'.jarvis_failures/model_outputs').mkdir(parents=True); (work/'.jarvis_failures/model_outputs/x.txt').write_text('diagnostic')
    (work/'node_modules/pkg').mkdir(parents=True); (work/'node_modules/pkg/index.js').write_text('dependency')
    (work/'src-tauri/target/debug').mkdir(parents=True); (work/'src-tauri/target/debug/x').write_text('build')

    # Delete/cache-churn concurrently. A correct clone never even descends into this tree.
    stop=False
    def churn():
        nonlocal_stop=[False]
        for i in range(200):
            try:
                volatile.unlink(missing_ok=True)
                volatile.parent.mkdir(parents=True,exist_ok=True)
                volatile.write_text(str(i),encoding='utf-8')
            except Exception:
                pass
            time.sleep(0.001)
    t=threading.Thread(target=churn,daemon=True); t.start()
    try:
        q._copy_resume_workspace(work,trial)
        clone_ok=True
    except Exception as exc:
        clone_ok=False; clone_exc=exc
    t.join(timeout=2)
    check('working to trial clone survives active npm-cache churn',clone_ok,str(locals().get('clone_exc','')))
    check('authored frontend source copied',(trial/'src/main.ts').is_file())
    check('authored Rust source copied',(trial/'src-tauri/src/lib.rs').is_file())
    check('manifest copied',(trial/'package.json').is_file())
    check('compact Jarvis project state copied',(trial/'JARVIS_V33_ARCHITECTURE.json').is_file())
    check('.jarvis_runtime excluded from trial',not (trial/'.jarvis_runtime').exists())
    check('.jarvis_failures excluded from trial',not (trial/'.jarvis_failures').exists())
    check('node_modules excluded from trial',not (trial/'node_modules').exists())
    check('Cargo target excluded from trial',not (trial/'src-tauri/target').exists())

    # Checkpoint copies use the same stable clone path and must also avoid runtime caches.
    checkpoint=td/'checkpoint'
    q._copy_resume_workspace(work,checkpoint)
    check('checkpoint excludes runtime cache',not (checkpoint/'.jarvis_runtime').exists())
    check('checkpoint preserves authored source',(checkpoint/'src/main.ts').is_file())

# Candidate validation clone uses _ANALYSIS_IGNORE_DIRS, which must include volatile runtime trees.
check('analysis ignore contains .jarvis_runtime','.jarvis_runtime' in q._ANALYSIS_IGNORE_DIRS)
check('analysis ignore contains .jarvis_failures','.jarvis_failures' in q._ANALYSIS_IGNORE_DIRS)

source=(ROOT/'local_qwen_project.py').read_text(encoding='utf-8',errors='replace')
check('resume clone override present','def _v4212_resume_clone_ignore' in source)
check('resume clone prunes runtime','.jarvis_runtime' in source[source.rfind('V42.12 RESUME TRIAL'):])
check('V42.11 safe ZIP extraction preserved','V4211_ZIP_RESUME_IMPORT = True' in source)

passed=sum(1 for _,ok,_ in checks if ok)
print(f'RESULT {passed}/{len(checks)} PASS')
if passed != len(checks): raise SystemExit(1)
