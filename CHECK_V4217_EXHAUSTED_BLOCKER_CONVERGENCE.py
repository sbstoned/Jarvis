import json, os, tempfile
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

ident=j._v36_release_identity()
check('V42.17 behavior preserved in current release',ident.get('version') in {'V42.17.0','V42.18.0'},ident)
check('parser cache enabled',bool(ident.get('parser_result_cache_by_source_and_context')))
check('rust context parser enabled',bool(ident.get('rust_module_tree_context_parser')))
check('mechanical JSX recovery enabled',bool(ident.get('mechanical_jsx_duplicate_recovery')))
check('deterministic required asset recovery enabled',bool(ident.get('deterministic_required_asset_recovery')))
check('bounded exhausted stop enabled',bool(ident.get('exhausted_blocker_bounded_stop')))
check('V42.16 transactional syntax gate preserved',bool(ident.get('strict_all_language_source_syntax_gate')))
check('V42.16 atomic direct edit preserved',bool(ident.get('atomic_multifile_direct_edits')))

# Reproduce the GearTrack corruption shape: duplicate attr plus a dangling duplicated tail.
malformed='''export function InventoryView(){return (<div>\n<input\n  type="text"\n  type="text"\n  value={searchQuery}\n  onChange={handleSearch}\n/>\n  value={searchQuery}\n  onChange={handleSearch}\n/>\n</div>)}\n'''
fixed,did=j._v4217_mechanical_jsx_candidate(malformed)
check('mechanical repair recognizes GearTrack duplicate shape',did,fixed)
check('mechanical repair removes duplicate type attribute',fixed.count('type="text"')==1,fixed)
check('mechanical repair removes dangling duplicated tail',fixed.count('value={searchQuery}')==1 and fixed.count('onChange={handleSearch}')==1,fixed)

# Conflicting duplicate attribute values are deliberately not guessed away.
ambiguous='''const x=<input\n type="text"\n type="number"\n/>;\n'''
amb_fixed,amb_did=j._v4217_mechanical_jsx_candidate(ambiguous)
check('conflicting JSX attributes are preserved for semantic repair',amb_fixed.count('type=')==2,amb_fixed)

# Parser cache must make the second unchanged green parse a true no-op.
with tempfile.TemporaryDirectory(prefix='v4217_cache_') as td:
    w=Path(td);calls=[];old=j._v4217_prev_language_syntax_error
    try:
        def fake(work,manifest,rel,content):
            calls.append((rel,content));return ''
        j._v4217_prev_language_syntax_error=fake
        a=j._v4216_language_syntax_error(w,{},'src/a.js','const a=1;\n')
        b=j._v4216_language_syntax_error(w,{},'src/a.js','const a=1;\n')
        check('unchanged green parser result cached',a=='' and b=='' and len(calls)==1,calls)
        c=j._v4216_language_syntax_error(w,{},'src/a.js','const a=2;\n')
        check('source change invalidates parser cache',c=='' and len(calls)==2,calls)
    finally:j._v4217_prev_language_syntax_error=old

# Required Tauri ICO omitted from manifest should be recovered from config reference.
with tempfile.TemporaryDirectory(prefix='v4217_asset_') as td:
    w=Path(td)
    manifest={'components':[{'id':'desktop','root':'src-tauri','toolchain_adapter':'tauri'}],'files':[{'path':'src-tauri/tauri.conf.json','phase':'foundation'}]}
    write(w/'src-tauri/tauri.conf.json',json.dumps({'bundle':{'icon':['icons/icon.ico','icons/icon.png']}}))
    changed=j._v4217_recover_required_assets(w,manifest)
    check('missing referenced icon.ico recovered','src-tauri/icons/icon.ico' in changed,changed)
    check('missing referenced icon.png recovered','src-tauri/icons/icon.png' in changed,changed)
    check('recovered ICO nonempty',(w/'src-tauri/icons/icon.ico').exists() and (w/'src-tauri/icons/icon.ico').stat().st_size>0)
    check('recovered PNG nonempty',(w/'src-tauri/icons/icon.png').exists() and (w/'src-tauri/icons/icon.png').stat().st_size>0)
    changed2=j._v4217_recover_required_assets(w,manifest)
    check('asset recovery is idempotent',changed2==[],changed2)

# Exhausted-state lookup must identify the exact quarantined repair signature.
with tempfile.TemporaryDirectory(prefix='v4217_exhausted_') as td:
    w=Path(td);rel='src/InventoryView.tsx';problem='parse failure'
    write(w/rel,'bad')
    state={'files':{rel:{j._v381_repair_signature(rel,[problem],problem):{'failures':1,'subsystem_exhausted':True}}}}
    j._v381_save_repair_state(w,state)
    sig,row=j._v4217_exact_exhausted_entry(w,rel,[problem],problem)
    check('exact exhausted blocker recognized',bool(sig) and bool(row and row.get('subsystem_exhausted')),(sig,row))

print(f'RESULT {PASS}/{PASS+FAIL} PASS')
report={'version':'V42.17.0','pass':PASS,'fail':FAIL,'total':PASS+FAIL,'identity':ident}
(ROOT/'V42_17_VALIDATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(1 if FAIL else 0)
