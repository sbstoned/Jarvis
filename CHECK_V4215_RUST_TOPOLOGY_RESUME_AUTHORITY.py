import json, os, shutil, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ.setdefault('JARVIS_QWEN_MODEL','auto')
import local_qwen_project as j

PASS=0;FAIL=0

def check(name,cond,detail=''):
    global PASS,FAIL
    if cond:
        PASS+=1;print('PASS',name)
    else:
        FAIL+=1;print('FAIL',name,detail)

def write(p,text):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

# 1) The exact false-lock phrase that contaminated GearTrack must stay stack-neutral.
phrase='Do not endlessly retry the same unchanged problem. If state is not improving, escalate or switch repair strategy.'
check('escalate is not Scala', j._v35_explicit_toolchain(phrase)!='scala_sbt', j._v35_explicit_toolchain(phrase))
check('explicit Scala still works', j._v35_explicit_toolchain('Build this service in Scala with sbt')=='scala_sbt')
check('trust prose is not Rust', j._v35_explicit_toolchain('Do not trust stale generated metadata')!='rust', j._v35_explicit_toolchain('Do not trust stale generated metadata'))
check('explicit Rust still works', j._v35_explicit_toolchain('Build the backend in Rust with Cargo')=='rust')

with tempfile.TemporaryDirectory(prefix='v4215_') as td:
    w=Path(td)
    # React + Rust/Tauri-shaped repo with directory module topology.
    write(w/'package.json',json.dumps({'scripts':{'build':'tsc --noEmit'},'dependencies':{'react':'^18.0.0'},'devDependencies':{'typescript':'^5.5.0'}},indent=2))
    write(w/'src/App.tsx','export default function App(){ return null; }\n')
    write(w/'src/types/tool.ts','export interface Tool { id: string; name: string }\n')
    write(w/'src/types/category.ts','export interface Category { id: string; name: string }\n')
    write(w/'src-tauri/Cargo.toml','''[package]\nname = "geartrack"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\nserde = { version = "1", features=["derive"] }\n''')
    write(w/'src-tauri/src/lib.rs','pub mod models;\npub mod checkout;\n')
    write(w/'src-tauri/src/models/mod.rs','pub mod tool;\npub mod category;\npub use tool::Tool;\npub use category::Category;\n')
    write(w/'src-tauri/src/models/tool.rs','pub struct Tool { pub id: String, pub name: String }\n')
    write(w/'src-tauri/src/models/category.rs','pub struct Category { pub id: String, pub name: String }\n')
    write(w/'src-tauri/src/checkout.rs','use crate::models::tool::Tool;\nuse crate::models::{Category};\npub fn f(_: Tool, _: Category){}\n')
    # Simulate the bad repair having already materialized a competing flat aggregate.
    write(w/'src-tauri/src/models.rs','pub struct Tool { pub id: String }\n')
    # Simulate the Scala contamination observed in the latest state.
    write(w/'build.sbt','scalaVersion := "3.3.1"\n')
    write(w/'src/main/scala/com/jarvis/core/Main.scala','object Main extends App {}\n')

    historical={
      'project_name':'geartrack','components':[
        {'id':'react','root':'.','toolchain_adapter':'react','depends_on':['rust']},
        {'id':'rust','root':'src-tauri','toolchain_adapter':'rust','depends_on':[]},
      ],
      'files':[
        {'path':'package.json'},{'path':'src/App.tsx'},{'path':'src/types/tool.ts','exports':['Tool']},{'path':'src/types/category.ts','exports':['Category']},
        {'path':'src-tauri/Cargo.toml'},{'path':'src-tauri/src/lib.rs'},{'path':'src-tauri/src/models/mod.rs'},
        {'path':'src-tauri/src/models/tool.rs','exports':['Tool']},{'path':'src-tauri/src/models/category.rs','exports':['Category']},{'path':'src-tauri/src/checkout.rs'},
      ],
      'canonical_domain_contracts':{'entities':{'Tool':{'fields':['id','name']},'Category':{'fields':['id','name']}},'enums':{}},
    }
    write(w/j.V33_ARCHITECTURE_FILE,json.dumps(historical,indent=2))
    # Old KB explicitly knew the Scala files were unplanned.
    write(w/j.V373_PROJECT_KB_FILE,json.dumps({'files':{
      'build.sbt':{'status':'unplanned_source'},
      'src/main/scala/com/jarvis/core/Main.scala':{'status':'unplanned_source'},
    }},indent=2))
    # Ledger contains real + stale entries.
    write(w/j.V413_ACCEPTED_LEDGER,json.dumps({'files':{
      'src/App.tsx':{'sha256':'bad','revision':1},
      'src-tauri/src/models.rs':{'sha256':'bad','revision':1},
      'src-tauri/src-tauri/build.rs':{'sha256':'bad','revision':1},
      'build.sbt':{'sha256':'bad','revision':1},
    }},indent=2))

    contaminated='''Finish this existing project completely. If accepted state is not improving, escalate or switch strategy.\n\nEXPLICIT USER TOOLCHAIN LOCK (preserve it):\n- Adapter: scala_sbt\n- Language: scala\n- Framework/toolchain:  / sbt\n- Do not substitute an unrelated language/framework.\n\nRebuild the correct project from these requirements. Delete or ignore any existing files that use the wrong language or domain.'''
    clean=j._v4215_strip_injected_toolchain_lock(contaminated,['react','rust'])
    check('generated Scala lock stripped','scala_sbt' not in clean and 'Language: scala' not in clean,clean)

    m,rep=j._v4214_rebuild_current_state(w,historical,contaminated,None)
    paths={j._v40_norm_rel(x.get('path')) for x in m.get('files') or [] if isinstance(x,dict)}
    comps={j._v361_normalize_component_adapter(x.get('toolchain_adapter')) for x in m.get('components') or [] if isinstance(x,dict)}
    check('Scala marker quarantined',not (w/'build.sbt').exists())
    check('Scala source quarantined',not (w/'src/main/scala/com/jarvis/core/Main.scala').exists())
    check('Scala not detected as component','scala_sbt' not in comps,comps)
    check('Rust directory module retained','src-tauri/src/models/mod.rs' in paths,sorted(paths))
    check('flat models.rs removed',not (w/'src-tauri/src/models.rs').exists() and 'src-tauri/src/models.rs' not in paths,sorted(paths))

    ledger=j._v413_load_accepted(w).get('files') or {}
    check('stale nested accepted entry pruned','src-tauri/src-tauri/build.rs' not in ledger,ledger.keys())
    check('Scala accepted entry pruned','build.sbt' not in ledger,ledger.keys())
    check('flat models accepted entry pruned','src-tauri/src/models.rs' not in ledger,ledger.keys())

    graph=j._v36_build_repo_graph(w,m,write=True)
    gf=graph.get('files') or {}
    check('graph suppresses flat models.rs','src-tauri/src/models.rs' not in gf,gf.keys())
    edges={x.get('to') for x in (gf.get('src-tauri/src/checkout.rs') or {}).get('edges') or []}
    check('crate models tool resolves child module','src-tauri/src/models/tool.rs' in edges,edges)
    check('crate models brace import resolves mod.rs','src-tauri/src/models/mod.rs' in edges,edges)
    check('checkout graph does not point to flat models.rs','src-tauri/src/models.rs' not in edges,edges)

    # Current planned repo accepted => a phantom unplanned provider is not a valid specialist target.
    for rel in paths:
        p=w/rel
        if p.exists() and p.is_file():j._v413_mark_accepted(w,rel,'test')
    write(w/'src-tauri/src/models.rs','pub struct Ghost;\n')
    check('all current planned files accepted',j._v4215_all_planned_accepted(w,m))
    check('phantom provider has no provider-health problem',j._v424_provider_state_problem(w,m,'src-tauri/src/models.rs')=='',j._v424_provider_state_problem(w,m,'src-tauri/src/models.rs'))
    # Runtime cleanup removes the hallucinated aggregate without touching mod.rs.
    j._v4215_runtime_cleanup(w,m)
    check('runtime cleanup removes hallucinated models.rs',not (w/'src-tauri/src/models.rs').exists())
    check('runtime cleanup preserves models/mod.rs',(w/'src-tauri/src/models/mod.rs').exists())

    check('V42.15 report written',(w/j.V4215_MIGRATION_REPORT).exists())

# Optional replay assertions against the exact captured user evidence when available.
latest=Path('/mnt/data/latest_state_extract')
if latest.exists() and (latest/'JARVIS_PROJECT_STATE.json').exists():
    state=json.loads((latest/'JARVIS_PROJECT_STATE.json').read_text(encoding='utf-8',errors='replace'))
    dirty=str(state.get('user_request') or '')
    check('captured request demonstrates old Scala contamination','Adapter: scala_sbt' in dirty)
    check('V42.15 sanitizes captured request','scala_sbt' not in j._v4215_strip_injected_toolchain_lock(dirty,['react','rust']))
    graph=json.loads((latest/'JARVIS_V36_REPO_GRAPH.json').read_text(encoding='utf-8',errors='replace'))
    old_edges={x.get('to') for x in ((graph.get('files') or {}).get('src-tauri/src/checkout.rs') or {}).get('edges') or []}
    check('captured graph demonstrates old phantom edge','src-tauri/src/models.rs' in old_edges,old_edges)

print(f'RESULT {PASS}/{PASS+FAIL} PASS')
raise SystemExit(1 if FAIL else 0)
