"""Offline regressions; controlled edits exercise the real resume/checkpoint code.

No live Qwen or Windows GUI is needed. Compiler fixtures use real Python
compilation, and the completed service workflow uses actual SQLite persistence.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import local_qwen_project as j
import jarvis_v4251_repair as tx
import jarvis_v4252_repair as v
from jarvis_sql_contracts import sqlite_contract_issues


SERVICE = '''import sqlite3
SCHEMA = "CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
def add(title):
    if not title.strip():
        raise ValueError("title required")
    with sqlite3.connect("notes.db") as db:
        db.execute(SCHEMA)
        return db.execute("INSERT INTO notes(title) VALUES (?)", (title,)).lastrowid
def get(note_id):
    with sqlite3.connect("notes.db") as db:
        return db.execute("SELECT id, label FROM notes WHERE id = ?", (note_id,)).fetchone()
def list_notes():
    with sqlite3.connect("notes.db") as db:
        return db.execute("SELECT id, description FROM notes ORDER BY id").fetchall()
'''

WORKFLOW = '''import sqlite3, subprocess, sys
from storage import add, get, list_notes
note_id = add("first saved note")
assert get(note_id) == (note_id, "first saved note")
assert list_notes() == [(note_id, "first saved note")]
try:
    add("   ")
except ValueError:
    pass
else:
    raise AssertionError("invalid title accepted")
assert sqlite3.connect("notes.db").execute("SELECT count(*) FROM notes").fetchone()[0] == 1
subprocess.run([sys.executable, "-c", "from storage import list_notes; assert list_notes() == [(1, 'first saved note')]"], check=True)
'''


def issue(problem, kind='persistence_sql_prepare', file='storage.py'):
    return {'file': file, 'kind': kind, 'problem': problem}


def snapshot(rows, score=(0, 0, 0), real_ok=True):
    return v.enrich_snapshot({'score': score, 'real_ok': real_ok, 'deterministic_issues': [],
                              'weighted_issues': 0, 'hashes': {}}, rows)


class DurableProgress(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def compile_project(self, root, *args):
        result = subprocess.run([sys.executable, '-m', 'py_compile', 'storage.py'],
                                cwd=root, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr

    def prepare_service(self):
        work = self.root / 'working'
        work.mkdir()
        (work / 'storage.py').write_text(SERVICE, encoding='utf-8')
        return work, {'project_name': 'notes', 'files': [{'path': 'storage.py'}]}

    def run_sweeps(self, work, manifest, count=2, reject=False):
        inputs = []

        def acceptance(request, plan, trial, callback=None):
            path = Path(trial) / 'storage.py'
            source = path.read_text()
            inputs.append(source)
            if reject:
                path.write_text(source.replace('SELECT id, label', 'SELECT id, unrelated'))
                return False, ['discarded-trial-only problem']
            if 'SELECT id, label' in source:
                source = source.replace('SELECT id, label', 'SELECT id, title')
            else:
                source = source.replace('SELECT id, description', 'SELECT id, title')
            path.write_text(source)
            rows = v.functional_issues(trial, request, plan)
            return not rows, rows

        with ExitStack() as stack:
            stack.enter_context(patch.object(j, '_run_real_project_validation', side_effect=self.compile_project))
            stack.enter_context(patch.object(j, '_deterministic_acceptance_issues', return_value=[]))
            stack.enter_context(patch.object(j, '_acceptance_repair_cycle', side_effect=acceptance))
            stack.enter_context(patch.object(j, '_progress', return_value=None))
            result = j._run_resume_sweeps('finish the existing notes service', manifest, work,
                                           self.root / 'job', max_sweeps=count)
        return result, inputs

    def test_active_engine_and_guards(self):
        self.assertEqual(j._v36_release_identity()['version'], 'V42.63.0')
        for name in ('_v4249_engine_disk_guard', '_v4250_engine_disk_guard'):
            self.assertTrue(getattr(j, name)()[0])

    def test_functional_improvement_changes_equal_compiler_score(self):
        before = snapshot([issue(str(n)) for n in range(12)])
        after = snapshot([issue(str(n)) for n in range(10)])
        self.assertLess(after['score'], before['score'])
        self.assertEqual(after['issue_count'], 10)
        self.assertFalse(after['fully_verified'])

    def test_compiler_regression_cannot_buy_functional_progress(self):
        before = snapshot([issue('old')])
        after = snapshot([], score=(2, 1, 0), real_ok=False)
        self.assertGreater(after['score'], before['score'])
        self.assertTrue(j._resume_protected_regressions(before, after))

    def test_compiler_improvement_may_reveal_functional_debt(self):
        before = snapshot([], score=(4, 2, 1), real_ok=False)
        after = snapshot([issue('newly reachable failure')])
        self.assertLess(after['score'], before['score'])
        self.assertFalse(j._resume_protected_regressions(before, after))
        self.assertFalse(after['fully_verified'])

    def test_new_sql_failure_rejects_lower_total(self):
        before = snapshot([issue('old1'), issue('old2')])
        after = snapshot([issue('new wrong column')])
        self.assertTrue(j._resume_protected_regressions(before, after))

    def test_unknown_validation_never_claims_complete(self):
        self.assertFalse(snapshot([], real_ok=None)['fully_verified'])

    def test_person_query_from_failed_trial_is_rejected(self):
        text = '''use sqlx::SqlitePool;
const SCHEMA: &str = r#"CREATE TABLE persons(id TEXT PRIMARY KEY, name TEXT NOT NULL)"#;
let query = "SELECT id, name, current_holder_id FROM persons WHERE id = ?";
sqlx::query_as::<_, Person>(query).fetch_one(pool).await?;
'''
        rows = sqlite_contract_issues([('src/db.rs', text)])
        self.assertEqual(len(rows), 1)
        self.assertIn('no such column: current_holder_id', rows[0]['problem'])

    def test_select_update_insert_and_returning_prepare(self):
        text = '''import sqlite3
schema = "CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)"
a = "SELECT wrong FROM items"
b = "UPDATE items SET wrong = ? WHERE id = ?"
c = "INSERT INTO items(wrong) VALUES (?)"
d = "INSERT INTO items(name) VALUES (?) RETURNING wrong"
db.execute(a)
db.execute(b)
db.execute(c)
db.execute(d)
'''
        self.assertEqual(len(sqlite_contract_issues([('db.py', text)])), 4)

    def test_valid_joins_ctes_aliases_quotes_and_parameters(self):
        sql = '''-- sqlite
CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE events(id INTEGER, item_id INTEGER REFERENCES items(id));
SELECT i.name FROM items AS i JOIN events AS e ON i.id=e.item_id WHERE i.id=:id;
WITH picked AS (SELECT name FROM items WHERE id=$id) SELECT name FROM picked;
UPDATE items SET name=@name WHERE id=?2 RETURNING name;
INSERT INTO items(name) VALUES ('literal ? :ignored') RETURNING "name";
'''
        self.assertEqual(sqlite_contract_issues([('db.sql', sql)]), [])

    def test_validation_never_executes_application_mutations(self):
        database = self.root / 'app.db'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE items(id INTEGER)')
            db.execute('INSERT INTO items VALUES (7)')
        original = database.read_bytes()
        text = f'''import sqlite3
db = sqlite3.connect({str(database)!r})
schema = "CREATE TABLE items(id INTEGER)"
query = "DELETE FROM items"
db.execute(query)
'''
        self.assertEqual(sqlite_contract_issues([('db.py', text)]), [])
        self.assertEqual(database.read_bytes(), original)
        with sqlite3.connect(database) as db:
            self.assertEqual(db.execute('SELECT id FROM items').fetchall(), [(7,)])

    def test_other_dialects_are_not_forced_into_sqlite(self):
        text = 'import psycopg\nschema="CREATE TABLE items(id INTEGER)"\nquery="SELECT wrong FROM items"'
        self.assertEqual(sqlite_contract_issues([('db.py', text)]), [])

    def test_dynamic_sql_comments_and_documentation_are_ignored(self):
        text = '''"""SELECT wrong FROM items"""
import sqlite3
schema = "CREATE TABLE items(id INTEGER)"
# q = "SELECT missing FROM items"
q = f"SELECT {column} FROM items"
'''
        self.assertEqual(sqlite_contract_issues([('db.py', text)]), [])
        ts = 'import "sqlite3"; const schema = "CREATE TABLE items(id INTEGER)"; // "SELECT bad FROM items"\nconst q = `SELECT ${column} FROM items`;'
        self.assertEqual(sqlite_contract_issues([('db.ts', ts)]), [])

    def test_additive_migration_columns_are_recognized(self):
        sql = '-- sqlite\nCREATE TABLE items(id INTEGER); ALTER TABLE items ADD COLUMN name TEXT; SELECT name FROM items;'
        self.assertEqual(sqlite_contract_issues([('db.sql', sql)]), [])

    def test_typescript_sqlite_queries_are_checked(self):
        text = 'import Database from "better-sqlite3"; const schema = `CREATE TABLE items(id INTEGER)`; db.prepare("SELECT missing FROM items");'
        self.assertEqual(len(sqlite_contract_issues([('db.ts', text)])), 1)

    def test_sql_rejection_happens_before_component_rebuild(self):
        path = self.root / 'db.py'
        source = 'import sqlite3\nschema="CREATE TABLE items(id INTEGER)"\nq="SELECT missing FROM items"\ndb.execute(q)\n'
        path.write_text(source)
        response = (True, json.dumps({'edits': [{'file': 'db.py', 'replacements': [
            {'search': 'SELECT missing FROM items', 'replace': 'SELECT other_missing FROM items'}]}]}))
        fake = {'_qwen_call': lambda *a, **k: response, '_extract_json': j._extract_json,
                '_copy_project_for_candidate_validation': j._copy_project_for_candidate_validation}
        group = {'file': 'db.py', 'kinds': ['persistence_sql_prepare'], 'rows': v.functional_issues(self.root)}
        with patch.object(tx.gates, '_component_candidate_proof') as proof:
            ok, errors = tx.repair_transaction(fake, 'finish', {}, self.root, group)
            proof.assert_not_called()
        self.assertFalse(ok)
        self.assertIn('other_missing', '\n'.join(errors))
        self.assertEqual(path.read_text(), source)

    def test_audit_state_preserves_functional_debt(self):
        j._v429_write_audit(self.root, {'clean': False, 'issues': [issue('still broken')]})
        record = j._v4218_state(self.root)['last_audit']
        self.assertFalse(record['clean'])
        self.assertEqual(record['functional_issue_count'], 1)
        self.assertEqual(record['issue_count'], 1)

    def test_real_resume_controller_preserves_first_sweep_and_completes_workflow(self):
        work, manifest = self.prepare_service()
        (ok, issues, final), inputs = self.run_sweeps(work, manifest)
        self.assertTrue(ok, issues)
        self.assertEqual(len(inputs), 2)
        self.assertNotIn('SELECT id, label', inputs[1])
        self.assertTrue(final['fully_verified'])
        result = subprocess.run([sys.executable, '-c', WORKFLOW], cwd=work, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_partial_improvement_survives_checkpoint_export_and_import(self):
        work, manifest = self.prepare_service()
        (ok, issues, best), _ = self.run_sweeps(work, manifest, count=1)
        self.assertFalse(ok)
        self.assertEqual(best['functional_issue_count'], 1)
        destination = self.root / 'checkpoint.zip'

        def package(root, *args):
            with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.write(Path(root) / 'storage.py', 'storage.py')
            return destination, 1

        with patch.object(j, '_package_workspace_zip', side_effect=package):
            out, count = j._package_resume_checkpoint_zip(work, manifest, 'notes service', 'finish', issues, snapshot=best)
        imported = self.root / 'imported'
        j._safe_extract_zip(out, imported)
        metadata = json.loads((imported / j.RESUME_METADATA_FILE).read_text())
        self.assertEqual(metadata['validation_snapshot']['functional_issue_count'], 1)
        self.assertEqual(metadata['status'], 'checkpoint_incomplete')
        # Historical metadata cannot grant a false pass after an import.
        metadata['validation_snapshot']['score'] = [0, 0, 0]
        (imported / j.RESUME_METADATA_FILE).write_text(json.dumps(metadata))
        with patch.object(j, '_run_real_project_validation', side_effect=self.compile_project), patch.object(j, '_deterministic_acceptance_issues', return_value=[]):
            fresh = j._resume_validation_snapshot(imported, manifest, 'finish')
        self.assertEqual(fresh['functional_issue_count'], 1)
        self.assertFalse(fresh['fully_verified'])
        self.assertNotIn('SELECT id, label', (imported / 'storage.py').read_text())

    def test_discarded_trial_diagnostics_do_not_replace_retained_findings(self):
        work, manifest = self.prepare_service()
        (ok, issues, best), _ = self.run_sweeps(work, manifest, count=1, reject=True)
        self.assertFalse(ok)
        self.assertNotIn('discarded-trial-only', str(issues))
        self.assertIn('label', str(issues))
        self.assertEqual((work / 'storage.py').read_text(), SERVICE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
