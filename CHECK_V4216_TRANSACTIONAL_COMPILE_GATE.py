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
check('V42.16 behavior preserved in current release',ident.get('version') in {'V42.16.0','V42.17.0','V42.18.0'},ident)
check('universal strict syntax enabled',bool(ident.get('strict_all_language_source_syntax_gate')))
check('production-before-tests enabled',bool(ident.get('production_before_test_repair')))
check('atomic direct edit enabled',bool(ident.get('atomic_multifile_direct_edits')))

bad='find . -type f -not -path \'./node_modules/*\'\n'
err=j._content_validation_error('src-tauri/src/lib.rs',bad)
check('shell command rejected as Rust source',bool(err) and 'source transport gate' in err,err)
check('valid Rust not rejected by transport gate',not j._v4216_source_transport_contamination('src/lib.rs','pub fn run() {}\n'))

valid,errors=j._candidate_files_valid(Path(tempfile.gettempdir()),[('src/lib.rs',bad),('src/main.rs','fn main() {}\n')])
check('bootstrap candidate validator rejects malformed Rust',all(x[0].as_posix()!='src/lib.rs' for x in valid),valid)
check('bootstrap candidate keeps valid sibling',any(x[0].as_posix()=='src/main.rs' for x in valid),valid)
check('bootstrap reports syntax/transport evidence',any('lib.rs' in x for x in errors),errors)

with tempfile.TemporaryDirectory(prefix='v4216_') as td:
    w=Path(td)
    manifest={
      '_original_user_request':'Build a Rust application with acceptance tests',
      'components':[{'id':'rust','root':'.','toolchain_adapter':'rust','depends_on':[]}],
      'files':[
        {'path':'Cargo.toml','phase':'foundation'},
        {'path':'src/lib.rs','phase':'foundation'},
        {'path':'tests/acceptance_2.rs','phase':'testing'},
      ],
      'canonical_domain_contracts':{'entities':{},'enums':{}},
    }
    write(w/'Cargo.toml','[package]\nname="v4216test"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n')
    write(w/'src/lib.rs',bad)
    write(w/'tests/acceptance_2.rs','#[test]\nfn smoke(){ assert!(true); }\n')
    j._v413_mark_accepted(w,'Cargo.toml','test')
    j._v413_mark_accepted(w,'src/lib.rs','test')
    j._v413_mark_accepted(w,'tests/acceptance_2.rs','test')

    tx=j._candidate_transaction_error(w,manifest,'src/lib.rs',bad,user_request='Build it')
    check('transaction gate rejects command-in-Rust',bool(tx) and 'source transport gate' in tx,tx)

    blockers=j._v4216_production_blockers(w,manifest)
    check('production blocker finds corrupt lib.rs',any(x.get('file')=='src/lib.rs' for x in blockers),blockers)

    audit=j._v429_whole_project_audit(w,'Build it',manifest,run_components=False)
    check('whole-project audit catches language syntax',any(x.get('kind')=='language_syntax' and x.get('file')=='src/lib.rs' for x in audit.get('issues') or []),audit.get('issues'))
    check('audit is not falsely clean',not audit.get('clean'),audit)

    pprod=j._v429_issue_priority(manifest,{'file':'src/lib.rs','kind':'language_syntax','problem':'bad'})
    ptest=j._v429_issue_priority(manifest,{'file':'tests/acceptance_2.rs','kind':'static','problem':'bad'})
    check('production syntax outranks tests',pprod[0] < ptest[0],(pprod,ptest))

    # Verify the test repair wrapper redirects its budget to production blockers.
    called=[]
    old_prev=j._v4216_prev_repair_file_for_issues
    old_prod=j._v4216_validate_production_component
    try:
        def fake_prev(user_request,manifest,work,rel,problems,progress_callback=None,validation_failure=None):
            called.append(rel);return True
        j._v4216_prev_repair_file_for_issues=fake_prev
        j._v4216_validate_production_component=lambda *a,**k: None
        ok=j._repair_file_for_issues('Build it',manifest,w,'tests/acceptance_2.rs',['test failure'])
        check('test repair redirects to production',ok and called and called[0]=='src/lib.rs',called)
    finally:
        j._v4216_prev_repair_file_for_issues=old_prev
        j._v4216_validate_production_component=old_prod

    # Atomic direct-edit batch rollback: simulate a transport writing malformed Rust.
    original='pub fn run() {}\n';write(w/'src/lib.rs',original);j._v413_mark_accepted(w,'src/lib.rs','good')
    before=j._v413_load_accepted(w)
    old_direct=j._v4216_prev_direct_completion_edit
    try:
        def fake_direct(*args,**kwargs):
            write(w/'src/lib.rs',bad)
            return {'changed':['src/lib.rs'],'reason':'','summary':'fake'}
        j._v4216_prev_direct_completion_edit=fake_direct
        res=j._direct_completion_edit('Build it',manifest,[],w,['src/lib.rs'])
        check('atomic direct edit rejects batch',not res.get('changed'),res)
        check('atomic direct edit restores source',(w/'src/lib.rs').read_text(encoding='utf-8')==original,(w/'src/lib.rs').read_text())
        check('atomic direct edit restores accepted ledger',j._v413_load_accepted(w)==before,(before,j._v413_load_accepted(w)))
    finally:j._v4216_prev_direct_completion_edit=old_direct

# Data/config parser coverage.
check('invalid TOML rejected',bool(j._v4216_language_syntax_error(None,{},'Cargo.toml','[package\nname="x"')))
check('valid TOML accepted',not j._v4216_language_syntax_error(None,{},'Cargo.toml','[package]\nname="x"\n'))
check('transaction skill installed',(j.V36_SKILLS_DIR/'transactional-compile-gate.md').exists())
check('production-before-tests skill installed',(j.V36_SKILLS_DIR/'production-before-tests.md').exists())
check('AUTO specialist remains new 27B',j._v36_release_identity().get('auto_specialist_profile')=='27b38q2',j._v36_release_identity())
check('legacy 27B remains excluded',j._v36_release_identity().get('legacy_27b_auto_eligible') is False,j._v36_release_identity())

print(f'RESULT {PASS}/{PASS+FAIL} PASS')
raise SystemExit(1 if FAIL else 0)
