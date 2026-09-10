"""Exercise complete repair transactions with fixture model replies and real workflows.

No live model or user data is required. Compiler/workflow checks execute locally;
the model transport alone is deterministic so failure paths are reproducible.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import local_qwen_project as jarvis
import jarvis_v4249_repair as planner
import jarvis_v4250_repair as gates
import jarvis_v4251_repair as transactions
import jarvis_v4268_repair as sessions
import jarvis_v4269_repair as compiler_loop
import jarvis_v4266_repair as bounds
from jarvis_v4240_repair import _STOP_EVENT, ProjectStopRequested
from jarvis_workspace_copy import copy_source_tree


def write(root, rel, content):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def finding(rel, kind, problem):
    return {"file": rel, "kind": kind, "problem": problem}


class FunctionalClosureChecks(unittest.TestCase):
    CLIENT = 'import provider\n\ndef create(name):\n    return {"name": name}\n'
    PROVIDER = '''import sqlite3

def connection():
    db = sqlite3.connect("state.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    return db
'''
    SAVE = '''
def save(name):
    db = connection()
    try:
        with db:
            cursor = db.execute("INSERT INTO items(name) VALUES (?)", (name,))
            return cursor.lastrowid
    finally:
        db.close()
'''
    WORKFLOW = '''from pathlib import Path
import sqlite3
import subprocess
import sys
from client import create

Path("state.sqlite").unlink(missing_ok=True)
assert create("hammer") == 1
try:
    create("")
except ValueError:
    pass
else:
    raise AssertionError("empty name must be rejected")
with sqlite3.connect("state.sqlite") as db:
    assert db.execute("SELECT name FROM items").fetchall() == [("hammer",)]
subprocess.run([sys.executable, "-c", "import sqlite3; db=sqlite3.connect('state.sqlite'); assert db.execute('SELECT name FROM items').fetchall()==[('hammer',)]; db.close()"], check=True)
'''

    def make_project(self, root):
        write(root, "client.py", self.CLIENT)
        write(root, "provider.py", self.PROVIDER)
        write(root, "workflow.py", self.WORKFLOW)
        write(root, "pyproject.toml", '[project]\nname="repair-fixture"\nversion="0.0.1"\n')
        return {"files": [{"path": name} for name in ("client.py", "provider.py", "workflow.py")],
                "components": [{"id": "python", "root": ".", "toolchain_adapter": "python",
                                "test_command": [sys.executable, "workflow.py"]}]}

    def detect(self, root, *args):
        """A deterministic functional adapter; the separate workflow proves behavior."""
        root = Path(root)
        client = (root / "client.py").read_text()
        provider = (root / "provider.py").read_text()
        if 'return provider.save(name)' not in client:
            return [finding("client.py", "functional_mock", "create must persist through the provider")]
        if 'def save(name):' not in provider:
            return [finding("provider.py", "functional_provider", "reachable provider.save operation is missing")]
        return []

    def action(self, rel, search, replace):
        return True, json.dumps({"action": "edit", "path": rel,
                                 "replacements": [{"search": search, "replace": replace}]})

    def run_transaction(self, root, manifest, replies, *, locked_cleanup=False,
                        stop_after_call=False, mutate_during_proof=False, schedule=False):
        events, calls, proofs = [], [], []
        handles = []

        def copier(source):
            temp = tempfile.TemporaryDirectory()
            handles.append(temp)
            clone = Path(temp.name) / "project"
            copy_source_tree(source, clone)
            if not locked_cleanup:
                return temp, clone

            class LockedHandle:
                name = temp.name

                def cleanup(self):
                    temp.cleanup()
                    raise OSError(145, "fixture directory is not empty")

            return LockedHandle(), clone

        def model(prompt, *args, **kwargs):
            calls.append(prompt)
            self.assertLessEqual(len(calls), len(replies), "repair repeated instead of keeping its draft")
            if stop_after_call:
                _STOP_EVENT.set()
            return replies[len(calls) - 1]

        def syntax(_root, _manifest, rel, source):
            if rel.endswith('.py'):
                try:
                    compile(source, rel, 'exec')
                except SyntaxError as exc:
                    return str(exc)
            return ''

        def validator(clone, *_args):
            result = subprocess.run([sys.executable, "workflow.py"], cwd=clone,
                                    text=True, capture_output=True, timeout=15)
            proofs.append(result.returncode)
            if mutate_during_proof:
                write(root, 'provider.py', '# a concurrent user edit\n')
            return result.returncode == 0, result.stdout + result.stderr

        replacements = {
            '_qwen_call': model, '_copy_project_for_candidate_validation': copier,
            '_v4216_language_syntax_error': syntax, '_v35_validate_component': validator,
            '_content_validation_error': lambda *a: '', '_v4221_semantic_role_error': lambda *a: '',
            '_append_project_event': lambda _root, event, message, **fields: events.append((event, fields)),
            '_v36_build_repo_graph': lambda *a, **k: {}, '_v36_build_contract_registry': lambda *a, **k: {},
            '_v33_write_architecture': lambda *a, **k: None,
        }
        _STOP_EVENT.clear()
        try:
            with patch.dict(jarvis.__dict__, replacements), patch.object(
                planner, 'functional_acceptance_issues', side_effect=self.detect
            ), patch.object(transactions, '_cluster_evidence', side_effect=lambda r, g, m:
                            {g['file']: (Path(r) / g['file']).read_text()}
            ), patch.object(sessions.adaptive_io, '_route_target', return_value='9b35'), patch.object(
                bounds, 'PRODUCTION_ATTEMPTS', 1
            ):
                rows = self.detect(root)
                if schedule:
                    changed = jarvis._v429_repair_audit_round('finish', manifest, root,
                                                            {'issues': rows}, None, 1)
                    errors = []
                else:
                    group = planner._group_rows(rows)[0]
                    changed, errors = transactions.repair_transaction(
                        jarvis.__dict__, 'finish', manifest, root, group
                    )
                return changed, errors, calls, proofs, events
        finally:
            _STOP_EVENT.clear()
            for temp in handles:
                temp.cleanup()

    def repair_replies(self, broken_first=False):
        save = self.SAVE
        if not broken_first:
            save = save.replace('    db = connection()', '    if not name:\n        raise ValueError("name required")\n    db = connection()')
        replies = [self.action('client.py', 'return {"name": name}', 'return provider.save(name)'),
                   self.action('provider.py', '    return db\n', '    return db\n' + save)]
        if broken_first:
            replies.append(self.action('provider.py', 'def save(name):\n',
                                       'def save(name):\n    if not name:\n        raise ValueError("name required")\n'))
        return replies

    def test_scheduler_closes_dependency_repairs_real_workflow_and_commits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            changed, errors, calls, proofs, events = self.run_transaction(
                root, manifest, self.repair_replies(broken_first=True), schedule=True
            )
            self.assertTrue(changed, errors)
            self.assertEqual(len(calls), 3)
            self.assertIn('OWNER: provider.py', calls[1])
            self.assertIn('return provider.save(name)', calls[1])
            self.assertIn('empty name must be rejected', calls[2])
            self.assertIn(1, proofs)
            self.assertEqual(proofs[-1], 0)
            self.assertEqual(self.detect(root), [])
            commits = [fields for event, fields in events if event == 'v4251_transaction_committed']
            self.assertEqual(len(commits), 1)
            self.assertEqual(set(commits[0]['files']), {'client.py', 'provider.py'})
            result = subprocess.run([sys.executable, 'workflow.py'], cwd=root, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cleanup_cannot_turn_success_into_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            changed, errors, calls, proofs, events = self.run_transaction(
                root, manifest, self.repair_replies(), locked_cleanup=True
            )
            self.assertTrue(changed, errors)
            self.assertEqual(len(calls), 2)
            self.assertTrue(any(event == 'candidate_cleanup_deferred' for event, _ in events))
            memory = json.loads((root / '.jarvis_memory/repair_memory.json').read_text())
            self.assertTrue(any(e['event_type'] == 'transaction_result' and e['accepted'] for e in memory['events']))

    def test_cleanup_preserves_rejection_evidence_and_original_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            changed, errors, calls, proofs, events = self.run_transaction(
                root, manifest, [(False, 'fixture transport failure')], locked_cleanup=True
            )
            self.assertFalse(changed)
            self.assertIn('fixture transport failure', '\n'.join(errors))
            self.assertEqual((root / 'client.py').read_text(), self.CLIENT)
            memory = (root / '.jarvis_memory/repair_memory.json').read_text()
            self.assertIn('transaction_result', memory)
            self.assertIn('fixture transport failure', memory)

    def test_stop_with_unfinished_dependency_preserves_accepted_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            with self.assertRaises(ProjectStopRequested):
                self.run_transaction(root, manifest, self.repair_replies(),
                                     locked_cleanup=True, stop_after_call=True)
            self.assertEqual((root / 'client.py').read_text(), self.CLIENT)
            self.assertEqual((root / 'provider.py').read_text(), self.PROVIDER)

    def test_concurrent_source_change_prevents_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            changed, errors, *_ = self.run_transaction(
                root, manifest, self.repair_replies(), mutate_during_proof=True
            )
            self.assertFalse(changed)
            self.assertIn('source changed', '\n'.join(errors).lower())
            self.assertEqual((root / 'client.py').read_text(), self.CLIENT)
            self.assertEqual((root / 'provider.py').read_text(), '# a concurrent user edit\n')

    def test_partial_commit_failure_rolls_back_every_authored_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self.make_project(root)
            original_replace = os.replace

            def fail_second_file(src, dst):
                if Path(dst) == root / 'provider.py':
                    raise OSError('fixture promotion failure')
                return original_replace(src, dst)

            with patch.object(os, 'replace', side_effect=fail_second_file):
                changed, errors, *_ = self.run_transaction(root, manifest, self.repair_replies())
            self.assertFalse(changed)
            self.assertIn('fixture promotion failure', '\n'.join(errors))
            self.assertEqual((root / 'client.py').read_text(), self.CLIENT)
            self.assertEqual((root / 'provider.py').read_text(), self.PROVIDER)

    def test_dependency_enrollment_excludes_private_and_outside_files(self):
        with tempfile.TemporaryDirectory() as td:
            root, clone = Path(td) / 'accepted', Path(td) / 'candidate'
            manifest = self.make_project(root)
            write(root, '.env', 'EXAMPLE=not-a-secret\n')
            write(root, '.jarvis_memory/private.py', 'VALUE = 1\n')
            copy_source_tree(root, clone)
            paths = ['../outside.py', '.env', '.jarvis_memory/private.py', 'provider.py']
            rows = [finding(p, 'functional_provider', 'missing operation') for p in paths]
            evidence = {'client.py': self.CLIENT}
            originals, drafts, groups = dict(evidence), dict(evidence), {}
            enrolled = sessions._enroll_dependencies(root, clone, rows, manifest,
                                                     evidence, originals, drafts, groups)
            self.assertEqual(enrolled, ['provider.py'])
            self.assertEqual(set(drafts), {'client.py', 'provider.py'})

    def test_real_tauri_provider_finding_enters_session_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, 'src-tauri/src/item.rs', 'pub async fn get_all_items() {}\n')
            rows = planner._tauri_provider_issues(root, {'commands': {'items_update'}})
            self.assertEqual(len(rows), 1)
            before = finding('src/hooks/useItems.ts', 'functional_mock', 'persist data')
            group = {'file': before['file'], 'kinds': ['functional_mock'], 'rows': [before]}
            with patch.object(transactions, '_cluster_functional_delta',
                              return_value={'improved': True, 'before': [before], 'after': rows}):
                errors = sessions._functional_preflight(root, root, 'finish', {}, group)
            self.assertIn('items_update', '\n'.join(errors))
            self.assertIn('src-tauri/src/item.rs', '\n'.join(errors))

    def test_improved_owner_cannot_hide_new_provider_debt(self):
        before = finding("client.py", "functional_mock", "persist the record")
        after = finding("provider.py", "functional_provider", "save operation is missing")
        group = {"file": "client.py", "kinds": ["functional_mock"], "rows": [before]}
        with tempfile.TemporaryDirectory() as td, patch.object(
            transactions, "_cluster_functional_delta",
            return_value={"improved": True, "before": [before], "after": [after]},
        ):
            errors = sessions._functional_preflight(td, td, "finish", {}, group)
        self.assertTrue(errors, "An improved caller must keep repairing its missing provider")
        self.assertIn("provider.py", "\n".join(errors))

    def test_related_source_change_invalidates_compiler_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, "client.py", "import provider\n")
            write(root, "provider.py", "VALUE = 1\n")
            before = compiler_loop._proof_key(root, "client.py")
            write(root, "provider.py", "VALUE = 2\n")
            self.assertNotEqual(before, compiler_loop._proof_key(root, "client.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
