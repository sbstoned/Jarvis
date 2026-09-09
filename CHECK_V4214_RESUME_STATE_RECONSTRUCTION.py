import json, os, re, shutil, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('JARVIS_QWEN_MODEL','auto')
import local_qwen_project as j

PASS=0;FAIL=0

def check(name, cond, detail=''):
    global PASS,FAIL
    if cond:
        PASS+=1; print('PASS',name)
    else:
        FAIL+=1; print('FAIL',name,detail)

source = Path('/mnt/data/project_20260831_204118.zip')
latest = Path('/mnt/data/latest_agent')
if not source.exists():
    raise SystemExit('missing replay checkpoint '+str(source))

with tempfile.TemporaryDirectory(prefix='v4214_') as td:
    td=Path(td); work=td/'working'; work.mkdir()
    rep=j._safe_extract_zip(source,work)
    check('safe extract has authored files', (work/'src/App.tsx').exists() and (work/'src-tauri/Cargo.toml').exists(), rep)

    # Reproduce the newest corrupted resume state seen in the user evidence.
    if latest.exists():
        for name in ('package.json','package-lock.json','JARVIS_V40_DOMAIN_OWNERS.json','JARVIS_V36_CONTRACT_REGISTRY.json'):
            p=latest/name
            if p.exists(): shutil.copy2(p,work/name)
    cargo=work/'src-tauri/Cargo.toml'
    text=cargo.read_text(encoding='utf-8')
    if 'default-run' not in text:
        text=text.replace('[package]\n','[package]\ndefault-run = "main"\n',1)
        cargo.write_text(text,encoding='utf-8')

    seed=j._resume_seed_from_workspace(work,source,'Finish this existing project completely.')
    m=seed['manifest']
    paths={j._v40_norm_rel(x.get('path')) for x in m.get('files') or [] if isinstance(x,dict)}
    comps={j._v40_norm_rel(x.get('root')) or '.':j._v361_normalize_component_adapter(x.get('toolchain_adapter')) for x in m.get('components') or []}
    owners=j._v40_domain_owner_payload(m).get('owners') or []
    owner_pairs={(x.get('scope'),x.get('symbol')):j._v40_norm_rel(x.get('provider')) for x in owners}
    providers=set(owner_pairs.values())

    check('current components reconstructed', '.' in comps and 'src-tauri' in comps, comps)
    check('frontend detected as node family', comps.get('.') in j._V4214_NODE_ADAPTERS, comps)
    check('rust component reconstructed', comps.get('src-tauri') in {'rust','tauri'}, comps)
    check('domain contracts rehydrated', len(j._v40_domain_definitions(m)) >= 5, j._v40_domain_definitions(m))
    check('domain owner map nonempty', len(owners) >= 8, owners)
    check('no stale flat TS provider', 'src/types.ts' not in paths and 'src/types.ts' not in providers, sorted(providers))
    check('no stale flat Rust provider', 'src-tauri/src/models.rs' not in paths and 'src-tauri/src/models.rs' not in providers, sorted(providers))
    check('TS semantic providers used', {'src/types/category.ts','src/types/tool.ts','src/types/person.ts','src/types/checkout_record.ts','src/types/tool_condition.ts'}.issubset(providers), sorted(providers))
    check('Rust semantic providers used', {'src-tauri/src/models/category.rs','src-tauri/src/models/tool.rs','src-tauri/src/models/person.rs','src-tauri/src/models/checkout_record.rs','src-tauri/src/models/tool_condition.rs'}.issubset(providers), sorted(providers))
    check('nested duplicate plan build.rs removed', 'src-tauri/src-tauri/build.rs' not in paths, sorted(x for x in paths if 'src-tauri/src-tauri' in x))
    check('nested duplicate plan tauri config removed', 'src-tauri/src-tauri/tauri.conf.json' not in paths, sorted(x for x in paths if 'src-tauri/src-tauri' in x))
    check('duplicate actual nested build removed', not (work/'src-tauri/src-tauri/build.rs').exists())
    check('duplicate actual nested tauri config removed', not (work/'src-tauri/src-tauri/tauri.conf.json').exists())
    check('duplicate src-tauri.conf removed', not (work/'src-tauri/src-tauri.conf.json').exists())

    pkg=json.loads((work/'package.json').read_text(encoding='utf-8'))
    check('Tauri API reconciled to v2', j._v4214_package_major((pkg.get('dependencies') or {}).get('@tauri-apps/api')) == 2, pkg)
    check('Tauri CLI reconciled to v2', j._v4214_package_major((pkg.get('devDependencies') or {}).get('@tauri-apps/cli')) == 2, pkg)
    ctext=cargo.read_text(encoding='utf-8')
    check('invalid cargo default-run removed', 'default-run' not in ctext, ctext[:500])

    op=json.loads((work/j.V40_OWNER_MEMORY_FILE).read_text(encoding='utf-8'))
    check('owner memory rewritten current', len(op.get('owners') or []) >= 8, op)
    cr=json.loads((work/j.V36_CONTRACT_REGISTRY_FILE).read_text(encoding='utf-8'))
    cproviders={j._v40_norm_rel(x.get('provider')) for x in cr.get('contracts') or [] if isinstance(x,dict)}
    check('contract registry no stale models.rs', 'src-tauri/src/models.rs' not in cproviders, sorted(cproviders))
    check('contract registry no stale types.ts', 'src/types.ts' not in cproviders, sorted(cproviders))
    check('migration report written', (work/j.V4214_MIGRATION_REPORT).exists())
    migration=json.loads((work/j.V4214_MIGRATION_REPORT).read_text(encoding='utf-8'))
    check('baseline hashes established', migration.get('baseline_accepted_files',0) >= 20, migration.get('baseline_accepted_files'))
    check('repo graph rebuilt', (work/j.V36_REPO_GRAPH_FILE).exists())
    check('project KB rebuilt', (work/j.V373_PROJECT_KB_FILE).exists())

    # A stale provider name from historical state must be suppressed rather than reaching Qwen.
    check('phantom types.ts topology recognized', bool(j._v4214_obsolete_topology_path(work,'src/types.ts',m.get('components') or [])))
    check('phantom models.rs topology recognized', bool(j._v4214_obsolete_topology_path(work,'src-tauri/src/models.rs',m.get('components') or [])))

print(f'V42.14 RESULT: {PASS} PASS / {FAIL} FAIL')
raise SystemExit(1 if FAIL else 0)
