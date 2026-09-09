"""Offline regression/workflow proof for V42.54.

Model responses are controlled fixtures. Production transactions, SQL analysis,
ZIP import, subprocess builds, test execution and SQLite persistence are real.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import local_qwen_project as j
import jarvis_sql_contracts as sql
import jarvis_workflow_contracts as workflow
import jarvis_v4251_repair as tx
import jarvis_v4252_repair as durable
import jarvis_v4254_repair as v

SCHEMA = 'CREATE TABLE notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL)'
SERVICE = '''import os, sqlite3
SCHEMA = "CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
def add(title):
    if not title.strip(): raise ValueError("title required")
    with sqlite3.connect(os.environ["NOTES_DB"]) as db:
        db.execute(SCHEMA)
        return db.execute("INSERT INTO notes(title) VALUES (?)", (title,)).lastrowid
def get(note_id):
    with sqlite3.connect(os.environ["NOTES_DB"]) as db:
        return db.execute("SELECT id, label FROM notes WHERE id=?", (note_id,)).fetchone()
'''
RUNNER = '''from pathlib import Path
import subprocess, sys
if not list(Path("tests").glob("test_*.py")):
    print("No test files found")
    sys.exit(5)
sys.exit(subprocess.run([sys.executable,"-m","unittest","discover","-s","tests"]).returncode)
'''
TEST = '''import os, sqlite3, subprocess, sys, tempfile, unittest
from storage import add, get
class FeatureWorkflow(unittest.TestCase):
    def test_create_reject_and_reopen(self):
        with tempfile.TemporaryDirectory() as work:
            os.environ["NOTES_DB"] = os.path.join(work,"notes.db")
            note_id = add("saved across restart")
            self.assertEqual(get(note_id), (note_id,"saved across restart"))
            with self.assertRaises(ValueError): add(" ")
            self.assertEqual(sqlite3.connect(os.environ["NOTES_DB"]).execute("SELECT count(*) FROM notes").fetchone()[0],1)
            subprocess.run([sys.executable,"-c","from storage import get; assert get(1)==(1, 'saved across restart')"],check=True)
'''


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def call(args, root):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=30)
    return result.returncode == 0, '$ ' + ' '.join(args) + '\n' + result.stdout + result.stderr


def manifest():
    return {'files':[{'path':'storage.py'},{'path':'run_workflow.py'}],
            'components':[{'id':'notes','root':'.','toolchain_adapter':'custom',
                           'build_command':'python -m py_compile storage.py',
                           'test_command':'python run_workflow.py'}],
            'requirements':['persist notes and reject blank titles']}


class EvidenceConvergence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()

    def fake(self, model=None, auditor=None, validator=None):
        g = {'_v36_release_identity':lambda:{}, '_v429_repair_audit_round':lambda *a:False,
             '_v428_specialist_contract_audit':lambda *a:'legacy ownership',
             '_v429_whole_project_audit':auditor or (lambda *a,**k:{'clean':False,'issues':[]}),
             '_v35_validate_component':validator or (lambda *a:(False,'No test files found')),
             '_qwen_call':model or (lambda *a,**k:(True,'Repair the supplied feature and add its workflow test.')),
             '_extract_json':j._extract_json, '_copy_project_for_candidate_validation':j._copy_project_for_candidate_validation,
             '_progress':lambda *a,**k:None, '_append_project_event':lambda *a,**k:None,
             '_v4216_language_syntax_error':lambda root,m,rel,text:self.syntax(rel,text),
             '_v4216_validate_production_component':lambda root,m,rel:call([sys.executable,'-m','py_compile','storage.py'],root),
             '_v35_is_noop_command':j._v35_is_noop_command, '_v34_run_declared_command':j._v34_run_declared_command}
        tx.install(g)
        v.install(g)
        return g

    @staticmethod
    def syntax(rel, text):
        if Path(rel).suffix == '.py':
            try: compile(text,rel,'exec')
            except SyntaxError as error: return str(error)
        return ''

    def test_sql_messages_and_unused_constants_are_not_database_calls(self):
        source = 'import sqlite3\nschema=' + repr(SCHEMA) + '\nerror="Update failed"\nmessage="Delete failed"\nunused="SELECT wrong FROM notes"\n'
        self.assertEqual(sql.sqlite_contract_issues([('service.py',source)]), [])
        source = 'import "sqlite3"; const schema = `' + SCHEMA + '`; return {error: "Update failed", message: "Delete failed"};'
        self.assertEqual(sql.sqlite_contract_issues([('service.ts',source)]), [])

    def test_malformed_sql_at_real_call_remains_a_failure(self):
        source = 'import sqlite3\nschema=' + repr(SCHEMA) + '\ndb.execute("Update failed")\ndb.execute("Delete failed")'
        rows = sql.sqlite_contract_issues([('service.py',source)])
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row['kind']=='persistence_sql_prepare' for row in rows))

    def test_python_aliases_and_keyword_queries_reach_the_database(self):
        source = 'import sqlite3\nschema=' + repr(SCHEMA) + '\nquery="SELECT wrong FROM notes"\nalias=query\ndb.execute(sql=alias)'
        self.assertEqual(len(sql.sqlite_contract_issues([('service.py',source)])),1)

    def test_rust_alias_generic_and_macro_query_calls(self):
        for call_source in ['sqlx::query_as::<_, Note>(alias).fetch_one(pool).await?;', 'sqlx::query_as!(Note, query).fetch_one(pool).await?;']:
            source = 'use sqlx::SqlitePool; const SCHEMA: &str = r#"' + SCHEMA + '"#; let query = "SELECT wrong FROM notes"; let alias = query; ' + call_source
            with self.subTest(call=call_source):
                self.assertEqual(len(sql.sqlite_contract_issues([('service.rs',source)])),1)

    def test_java_go_and_js_adapters_follow_query_arguments(self):
        for name, source in [
            ('storage.java','// sqlite\nString schema="'+SCHEMA+'"; String sql="SELECT wrong FROM notes"; connection.prepareStatement(sql);'),
            ('storage.go','// sqlite\nschema := `'+SCHEMA+'`\nquery := "SELECT wrong FROM notes"\ndb.Query(query);'),
            ('storage.ts','import "sqlite3"; const schema=`'+SCHEMA+'`; const query="SELECT wrong FROM notes"; db.prepare(query);')]:
            with self.subTest(name=name): self.assertEqual(len(sql.sqlite_contract_issues([(name,source)])),1)

    def test_sql_dynamic_fragments_do_not_become_complete_queries(self):
        source = 'import "sqlite3"; const schema=`'+SCHEMA+'`; db.prepare("SELECT " + column);'
        self.assertEqual(sql.sqlite_contract_issues([('storage.ts',source)]),[])

    def test_missing_and_existence_only_tests_are_one_stable_debt(self):
        files = {'service.ts':'export const save = () => invoke("save");'}
        before = workflow.workflow_issues(files)
        files['tests/smoke.test.ts'] = 'import {save} from "../service"; expect(typeof save).toBe("function");'
        after = workflow.workflow_issues(files)
        self.assertEqual(len(before),1)
        self.assertEqual(len(after),1)
        self.assertEqual(workflow.debt_key(before[0]),workflow.debt_key(after[0]))
        self.assertFalse(durable.new_functional_regressions({'functional_issues':before},{'functional_issues':after}))

    def test_comments_and_existence_checks_do_not_prove_behavior(self):
        source = '// fetch database create update\nexpect(typeof App).toBe("function");'
        self.assertFalse(workflow.plausible_workflow(source))
        self.assertTrue(workflow.plausible_workflow(TEST))

    def test_custom_language_uses_declared_test_path(self):
        m = {'components':[{'id':'custom','root':'.','test_command':'custom check'}],
             'files':[{'path':'src/main.uncommon'},{'path':'tests/feature.uncommon'}]}
        rows = workflow.workflow_issues({'src/main.uncommon':'program main'},m)
        self.assertEqual(rows[0]['file'],'tests/feature.uncommon')

    def test_child_tests_do_not_hide_parent_test_debt(self):
        m = {'components':[{'id':'web','root':'.','test_command':'npm test'},
                           {'id':'server','root':'server','test_command':'python -m unittest'}]}
        rows = workflow.workflow_issues({'web.ts':'fetch("/notes")','server/tests/test_notes.py':TEST},m)
        self.assertEqual([row['component'] for row in rows],['web'])

    def test_missing_test_failure_is_not_a_compiler_blocker(self):
        self.assertFalse(v.is_component_blocker({'kind':'component_validation','problem':'No test files found'}))
        self.assertTrue(v.is_component_blocker({'kind':'component_validation','problem':'error TS2322: wrong type\nNo test files found'}))
        self.assertTrue(v.is_component_blocker({'kind':'component_validation','problem':'AssertionError: expected saved note'}))

    def test_feature_transaction_runs_despite_missing_test_component_failure(self):
        write(self.root,'storage.py',SERVICE)
        rows = [{'file':'storage.py','kind':'persistence_sql_prepare','problem':'wrong column'},
                {'file':'.','kind':'component_validation','problem':'No test files found'}]
        g = self.fake()
        with patch.object(tx,'repair_transaction',return_value=(True,[])) as transaction:
            self.assertTrue(g['_v429_repair_audit_round']('finish',{},self.root,{'issues':rows}))
            self.assertEqual(transaction.call_args.args[4]['file'],'storage.py')

    def test_staged_proof_requires_real_baseline_and_candidate_builds(self):
        write(self.root,'storage.py',SERVICE)
        clone = self.root/'candidate'
        clone.mkdir()
        write(clone,'storage.py',SERVICE.replace('id, label','id, title'))
        g = self.fake()
        result = v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')
        self.assertTrue(result['ok'],result)
        self.assertFalse(result['final_acceptance'])
        self.assertTrue(result['deferred_test_debt'])
        write(clone,'storage.py','def broken(')
        result = v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')
        self.assertFalse(result['ok'])
        self.assertIn('SyntaxError',result['output'])

    def test_previously_passing_tests_cannot_be_deferred(self):
        write(self.root,'storage.py',SERVICE)
        clone = self.root/'candidate'; clone.mkdir();write(clone,'storage.py',SERVICE)
        g = self.fake(validator=lambda root,*a:(True,'one test passed') if Path(root)==self.root else (False,'No test files found'))
        self.assertFalse(v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')['ok'])

    def test_real_assertion_failure_cannot_be_deferred(self):
        write(self.root,'storage.py',SERVICE)
        clone = self.root/'candidate';clone.mkdir();write(clone,'storage.py',SERVICE)
        g = self.fake(validator=lambda *a:(False,'AssertionError: invalid input persisted'))
        self.assertFalse(v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')['ok'])

    def test_new_tests_and_runner_config_must_pass_full_proof(self):
        write(self.root,'storage.py',SERVICE)
        clone = self.root/'candidate';clone.mkdir();write(clone,'storage.py',SERVICE)
        write(clone,'tests/test_application.py',TEST)
        g = self.fake()
        self.assertFalse(v.component_candidate_proof(g,self.root,clone,manifest(),'tests/test_application.py')['ok'])
        self.assertFalse(v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')['ok'])

    def test_build_proof_does_not_reuse_accepted_marker_cache(self):
        write(self.root,'storage.py',SERVICE)
        clone = self.root/'candidate';clone.mkdir();write(clone,'storage.py',SERVICE)
        g = self.fake()
        g['_v4218_prev_validate_production_component'] = lambda *a:(False,'fresh build rejected')
        g['_v4216_validate_production_component'] = lambda *a:(True,'stale green accepted token')
        self.assertFalse(v.component_candidate_proof(g,self.root,clone,manifest(),'storage.py')['ok'])

    def test_test_weakening_and_escape_paths_are_rejected(self):
        self.assertTrue(tx._test_integrity_error('tests/test_notes.py','assert x == 1\nassert y == 2','assert x == 1'))
        self.assertTrue(tx._test_integrity_error('package.json','{"test":"vitest run"}','{"test":"vitest run --passWithNoTests"}'))
        self.assertFalse(tx._safe_path(self.root,'../tests/escape.py'))
        self.assertFalse(tx._safe_path(self.root,'C:/tests/escape.py'))
        self.assertTrue(tx._test_integrity_error('src/lib.rs','#[test] fn saved() { assert_eq!(read(),1); }','pub fn saved() {}'))

    def test_plan_status_timestamps_are_not_source_progress(self):
        write(self.root,'storage.py',SERVICE)
        m=manifest();before=v.revision(self.root,m)
        m['files'][0]['updated_at']='new timestamp'
        m['components'][0]['status']='validating again'
        self.assertEqual(v.revision(self.root,m),before)
        m['components'][0]['test_command']='python -m unittest'
        self.assertNotEqual(v.revision(self.root,m),before)

    def test_runner_timestamps_do_not_reopen_identical_failure_budget(self):
        def audit(stamp):return {'issues':[{'file':'.','kind':'component_validation','component':'web','problem':'No test files found\nStart at '+stamp}]}
        self.assertEqual(v._failure_signature(audit('12:00')),v._failure_signature(audit('12:35')))
        self.assertNotEqual(v._failure_signature(audit('12:00')),v._failure_signature({'issues':[]}))

    def test_an_empty_existing_test_can_receive_complete_workflow_content(self):
        rel='tests/test_application.py';write(self.root,rel,'')
        g=self.fake(model=lambda *a,**k:(True,json.dumps({'edits':[{'file':rel,'content':TEST}]})))
        changes=tx._model_candidate(g,'finish',{},self.root,{'file':rel},{rel:''},[],1,None)
        self.assertEqual(changes[rel],TEST)

    def test_real_registered_custom_adapter_runs_build_and_tests(self):
        write(self.root,'storage.py',SERVICE.replace('id, label','id, title'))
        write(self.root,'run_workflow.py',RUNNER)
        m=manifest()
        ok,out=j._v35_validate_component(self.root,m,m['components'][0],'verify public service')
        self.assertFalse(ok)
        self.assertIn('No test files found',out)
        write(self.root,'tests/test_application.py',TEST)
        ok,out=j._v35_validate_component(self.root,m,m['components'][0],'verify public service')
        self.assertTrue(ok,out)
        self.assertIn('Ran 1 test',out)

    def test_custom_adapter_recognizes_declared_unlisted_source_language(self):
        write(self.root,'program.uncommon','actual program source')
        m={'files':[{'path':'program.uncommon','phase':'features'}]}
        self.assertTrue(j._v411_custom_component_is_verifiable(self.root,{'build_command':'make build'},m))
        self.assertFalse(j._v411_custom_component_is_verifiable(self.root,{'build_command':'echo success'},m))

    def test_failed_new_workflow_test_never_reaches_accepted_source(self):
        write(self.root,'storage.py',SERVICE.replace('id, label','id, title'))
        write(self.root,'run_workflow.py',RUNNER)
        m=manifest();bad=TEST.replace('fetchone()[0],1)', 'fetchone()[0],999)')
        self.assertNotEqual(bad,TEST)
        model=lambda *a,**k:(True,json.dumps({'edits':[{'file':'tests/test_application.py','content':bad}]}))
        g=self.fake(model=model,validator=lambda root,*a:call([sys.executable,'run_workflow.py'],root))
        rows=durable.functional_issues(self.root,'finish',m)
        group=tx.planner._group_rows(rows)[0]
        ok,errors=tx.repair_transaction(g,'finish',m,self.root,group)
        self.assertFalse(ok)
        self.assertIn('AssertionError','\n'.join(errors))
        self.assertFalse((self.root/'tests/test_application.py').exists())
        self.assertFalse(any(item['path']=='tests/test_application.py' for item in m['files']))

    def test_new_file_commit_rolls_back_and_preserves_concurrent_creation(self):
        clone = self.root/'candidate';clone.mkdir()
        write(clone,'tests/a.py','assert 1\n');write(clone,'tests/b.py','assert 2\n')
        replace = os.replace;calls=[]
        def fail_second(a,b):
            calls.append(b)
            if len(calls)==2: raise OSError('disk full')
            return replace(a,b)
        with patch.object(tx.os,'replace',side_effect=fail_second):
            with self.assertRaises(OSError): tx._commit({},self.root,clone,{'tests/a.py':None,'tests/b.py':None},{'tests/a.py':'','tests/b.py':''},{})
        self.assertFalse((self.root/'tests/a.py').exists())
        write(self.root,'tests/a.py','user creation')
        with self.assertRaises(ValueError): tx._commit({},self.root,clone,{'tests/a.py':None},{'tests/a.py':''},{})
        self.assertEqual((self.root/'tests/a.py').read_text(),'user creation')

    def test_unchanged_failures_stop_once_and_metadata_does_not_reset_budget(self):
        write(self.root,'storage.py',SERVICE)
        row = {'file':'storage.py','kind':'persistence_sql_prepare','problem':'same wrong column'}
        auditor = lambda *a,**k:{'clean':False,'issues':[row]}
        g = self.fake(auditor=auditor)
        counts = {'repair':0,'specialist':0,'audit':0}
        def repair(*args):
            counts['repair']+=1
            write(self.root,'JARVIS_TOKEN_PROGRESS.json',json.dumps(counts))
            return True  # Metadata-only "success" must not reset a source budget.
        def audit(*args,**kwargs): counts['audit']+=1;return auditor()
        def specialist(*args,**kwargs): counts['specialist']+=1;return 'same'
        g.update(_v429_repair_audit_round=repair,_v429_whole_project_audit=audit,_v429_specialist_whole_audit=specialist)
        self.assertFalse(g['_v429_whole_project_convergence']('finish',{},self.root)[0])
        self.assertEqual(counts,{'repair':2,'specialist':1,'audit':1})
        self.assertFalse(g['_v429_whole_project_convergence']('finish',{},self.root)[0])
        self.assertEqual(counts['repair'],2)
        write(self.root,'storage.py',SERVICE+'\n# new authored input\n')
        self.assertFalse(g['_v429_whole_project_convergence']('finish',{},self.root)[0])
        self.assertEqual(counts['repair'],4)

    def test_failure_cache_is_scoped_and_invalidates_source_and_commands(self):
        write(self.root,'storage.py',SERVICE)
        calls=[]
        def validator(*a): calls.append(a);return False,'No test files found'
        g = self.fake(validator=validator);m=manifest();component=m['components'][0]
        token = v._SESSION.set({})
        try:
            g['_v35_validate_component'](self.root,m,component)
            g['_v35_validate_component'](self.root,m,component)
            self.assertEqual(len(calls),1)
            write(self.root,'tests/test_application.py',TEST)
            g['_v35_validate_component'](self.root,m,component)
            self.assertEqual(len(calls),2)
            component['test_command']='python -m unittest'
            g['_v35_validate_component'](self.root,m,component)
            self.assertEqual(len(calls),3)
        finally: v._SESSION.reset(token)
        g['_v35_validate_component'](self.root,m,component)
        self.assertEqual(len(calls),4)

    def test_infrastructure_failures_are_not_cached(self):
        write(self.root,'storage.py',SERVICE);calls=[]
        g=self.fake(validator=lambda *a:(calls.append(a) or False,'network unavailable'))
        token=v._SESSION.set({})
        try:
            for _ in range(2):g['_v35_validate_component'](self.root,manifest(),manifest()['components'][0])
        finally:v._SESSION.reset(token)
        self.assertEqual(len(calls),2)

    def test_specialist_receives_current_source_commands_and_failure(self):
        write(self.root,'storage.py',SERVICE);m=manifest();prompts=[]
        row={'file':'storage.py','kind':'persistence_sql_prepare','problem':'no such column: label'}
        raw={'clean':False,'issues':[row],'components':[{'id':'notes','ok':False,'output':'$ python run_workflow.py\nNo test files found'}]}
        g=self.fake(model=lambda prompt,*a,**k:(prompts.append(prompt) or True,'Fix label and add a test.'),auditor=lambda *a,**k:raw)
        g['_v429_whole_project_audit'](self.root,'finish',m)
        g['_v429_specialist_whole_audit']('finish',m,self.root,raw)
        self.assertIn('SELECT id, label',prompts[0])
        self.assertIn('python run_workflow.py',prompts[0])
        self.assertIn('No test files found',prompts[0])
        self.assertIn('persist notes',prompts[0])
        self.assertIn('Fix label',v.repair_evidence(self.root,m)['specialist_brief'])
        before=len(prompts)
        self.assertEqual(g['_v428_specialist_contract_audit']('finish',{},self.root,[],'missing tests'),'')
        self.assertEqual(len(prompts),before)

    def test_checkpoint_import_repairs_real_sql_and_creates_executed_persistence_test(self):
        archive=self.root/'checkpoint.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('trial_03/storage.py',SERVICE)
            z.writestr('trial_03/run_workflow.py',RUNNER)
            z.writestr('trial_03/target/cache.bin',b'rebuildable')
        root=self.root/'working';j._safe_extract_zip(archive,root)
        m=manifest();prompts=[];snapshots=[]
        def validator(work,*args):
            ok,build=call([sys.executable,'-m','py_compile','storage.py'],work)
            if not ok:return ok,build
            ok,out=call([sys.executable,'run_workflow.py'],work)
            return ok,build+'\n'+out
        def model(prompt,*a,**k):
            prompts.append(prompt)
            if 'ISSUE OWNER FILES: ["storage.py"]' in prompt:
                edits=[{'file':'storage.py','replacements':[{'search':'SELECT id, label','replace':'SELECT id, title'}]}]
            elif 'ISSUE OWNER FILES: ["tests/test_application.py"]' in prompt:
                edits=[{'file':'tests/test_application.py','content':TEST}]
            else: raise AssertionError('Unexpected model call: '+prompt[:200])
            return True,json.dumps({'edits':edits})
        def audit(work,request,plan,**kwargs):
            rows=durable.functional_issues(work,request,plan)
            ok,out=g['_v35_validate_component'](work,plan,plan['components'][0])
            if not ok:rows.append({'file':'.','kind':'component_validation','component':'notes','problem':out})
            value={'clean':not rows and ok,'issues':rows,'components':[{'id':'notes','ok':ok,'output':out}]}
            snapshots.append(copy.deepcopy(value));return value
        g=self.fake(model=model,auditor=audit,validator=validator)
        ok,issues=g['_v429_whole_project_convergence']('finish and test the saved service',m,root)
        self.assertTrue(ok,issues)
        self.assertEqual(len(prompts),2)
        self.assertTrue(any(row['kind']=='functional_test_coverage' for row in snapshots[1]['issues']))
        self.assertFalse(snapshots[1]['clean'])
        self.assertNotIn('SELECT id, label',(root/'storage.py').read_text())
        self.assertTrue((root/'tests/test_application.py').exists())
        self.assertTrue(any(item['path']=='tests/test_application.py' for item in m['files']))
        ok,out=validator(root)
        self.assertTrue(ok,out)
        self.assertIn('Ran 1 test',out)
        self.assertFalse(durable.functional_issues(root,'finish',m))
        self.assertIn('No test files found',prompts[0])
        self.assertIn('NEW TEST PATHS',prompts[1])
        report=json.loads((root/v.REPORT).read_text())
        self.assertEqual(report['status'],'whole_audit_passed')
        self.assertEqual(report['issues'],[])


if __name__=='__main__':unittest.main(verbosity=2)
