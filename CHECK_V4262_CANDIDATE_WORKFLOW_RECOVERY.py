"""Offline regression proof for V42.62.

Cache eviction/locking and model responses are injected. Active engine cloning,
HTTP streaming/parsing, transaction gates, subprocess tests, and SQLite are real.
This does not run a live Qwen model or the user's unattached project checkpoint.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

import local_qwen_project as j
import jarvis_v4240_repair as control
import jarvis_v4251_repair as tx
import jarvis_v4252_repair as durable
import jarvis_v4254_repair as convergence
import jarvis_v4259_repair as adaptive
from jarvis_model_protocol import parse_source_file
from jarvis_workspace_copy import copy_source_tree
from CHECK_V4255_MODEL_PROTOCOL import model_server
from CHECK_V4254_WORKFLOW_CONVERGENCE import SERVICE, TEST, RUNNER


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@contextmanager
def evict_cache_on_traversal():
    scan = os.scandir
    def guarded(path):
        if not isinstance(path, int) and '.jarvis_shared_build_cache' in os.fsdecode(path).casefold():
            raise FileNotFoundError(2, '[WinError 3] cache entry evicted during validation', str(path))
        return scan(path)
    with patch.object(os, 'scandir', side_effect=guarded):
        yield


def envelope(path, source):
    return '<<<JARVIS_FILE path=' + json.dumps(path) + '>>>\n' + source.rstrip('\n') + '\n<<<JARVIS_END_FILE>>>'


class WorkspaceIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'working'
        self.source = {
            'src/main.rs':'fn main() {}\n', 'web/main.tsx':'export const value = 1;\n',
            'service/app.py':'value = 1\n', 'native/main.cpp':'int main() { return 0; }\n',
            'engine/main.uncommon':'authored custom-language source\n',
            'Cargo.lock':'# authored dependency lock\n',
        }
        for rel, text in self.source.items(): write(self.root, rel, text)
        for rel in ('.jarvis_shared_build_cache/npm/_cacache/content-v2/blob',
                    'web/.JARVIS_SHARED_BUILD_CACHE/npm/_cacache/blob',
                    'service/.jarvis_shared_build_cache/cargo/evicted'):
            write(self.root, rel, 'volatile')

    def tearDown(self):
        self.temp.cleanup()

    def assert_clone(self, clone):
        for rel, text in self.source.items():
            self.assertEqual((clone / rel).read_text(), text)
        self.assertFalse(any(p.name.casefold() == '.jarvis_shared_build_cache' for p in clone.rglob('*')))

    def test_active_candidate_excludes_evicted_root_nested_and_case_variant_caches(self):
        with evict_cache_on_traversal():
            handle, clone = j._copy_project_for_candidate_validation(self.root)
        try:
            self.assert_clone(clone)
            self.assertTrue((self.root / '.jarvis_shared_build_cache/npm/_cacache/content-v2/blob').exists())
        finally:
            handle.cleanup()
        self.assertFalse(clone.exists())

    def test_active_compiler_cluster_uses_same_policy(self):
        with evict_cache_on_traversal():
            handle, clone = j._v4224_clone_workspace(self.root)
        try:
            self.assert_clone(clone)
        finally:
            shutil.rmtree(handle)

    def test_resume_and_checkpoint_copies_use_same_policy(self):
        with evict_cache_on_traversal():
            clone = j._copy_resume_workspace(self.root, self.base / 'trial')
            checkpoint = j._copy_resume_workspace(clone, self.base / 'checkpoint')
        self.assert_clone(clone)
        self.assert_clone(checkpoint)

    def test_zip_import_excludes_old_nested_cache(self):
        archive = self.base / 'checkpoint.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('project/src/main.py', 'print("kept")\n')
            z.writestr('project/child/.jarvis_shared_build_cache/npm/_cacache/blob', 'volatile')
        j._safe_extract_zip(archive, self.base / 'imported')
        self.assertEqual((self.base / 'imported/src/main.py').read_text(), 'print("kept")\n')
        self.assertFalse((self.base / 'imported/child/.jarvis_shared_build_cache').exists())

    def test_authored_copy_failure_is_strict_and_partial_destination_is_cleaned(self):
        scan = os.scandir
        def locked(path):
            if not isinstance(path, int) and Path(path) == self.root / 'src':
                raise PermissionError(13, 'locked authored source', str(path))
            return scan(path)
        destination = self.base / 'candidate'
        with patch.object(os, 'scandir', side_effect=locked):
            with self.assertRaises((OSError, shutil.Error)):
                copy_source_tree(self.root, destination)
        self.assertFalse(destination.exists())
        self.assertEqual((self.root / 'src/main.rs').read_text(), self.source['src/main.rs'])

    def test_candidate_failure_cleans_temporary_handle(self):
        created = []
        real_temp = tempfile.TemporaryDirectory
        def capture(*args, **kwargs):
            handle = real_temp(*args, **kwargs)
            created.append(Path(handle.name))
            return handle
        with patch.object(tempfile, 'TemporaryDirectory', side_effect=capture), \
             patch.object(j, 'copy_source_tree', side_effect=PermissionError('source locked')):
            with self.assertRaises(PermissionError): j._copy_project_for_candidate_validation(self.root)
        self.assertTrue(created)
        self.assertTrue(all(not p.exists() for p in created))

    def test_accepted_dependencies_remain_available_and_survive_candidate_cleanup(self):
        write(self.root, 'package.json', '{"name":"fixture","version":"1.0.0"}')
        write(self.root, 'node_modules/fixture/index.js', 'module.exports = 123;\n')
        with evict_cache_on_traversal():
            handle, clone = j._copy_project_for_candidate_validation(self.root)
        try:
            self.assertEqual((clone / 'node_modules/fixture/index.js').read_text(), 'module.exports = 123;\n')
        finally:
            handle.cleanup()
        self.assertTrue((self.root / 'node_modules/fixture/index.js').exists())


class StrictSourceProtocol(unittest.TestCase):
    def test_preserves_quotes_backslashes_unicode_and_source_indentation(self):
        for target in ('tests/application.rs', 'tests/application.test.ts', 'tests/test_application.py', 'tests/feature.uncommon'):
            source = '    literal = "quoted \\ path café"\n    another = \'value\'\n'
            self.assertEqual(parse_source_file(envelope(target, source), target), source)

    def test_rejects_wrong_path_partial_extra_and_multiple_files(self):
        target = 'tests/test_application.py'
        good = envelope(target, 'assert True\n')
        for bad in (good.replace(target, '../other.py'), good.rsplit('\n', 1)[0],
                    'explanation\n' + good, good + '\ntrailing', good + '\n' + good,
                    envelope(target, ''), '```python\nassert True\n```'):
            with self.subTest(response=bad):
                with self.assertRaises(ValueError): parse_source_file(bad, target)


class CappedTransportRecovery(unittest.TestCase):
    def test_output_cap_still_retries_smaller_complete_response(self):
        class Response(str):
            def __new__(cls, text, finish):
                instance = super().__new__(cls, text)
                instance.metadata = {'finish_reason':finish}
                instance.partial_text = text if finish == 'length' else ''
                return instance
        calls = []
        def model(prompt, callback=None, stage='', profile='', **kwargs):
            calls.append((prompt, kwargs))
            if len(calls) == 1:
                return False, Response('{"edits":[', 'length')
            return True, Response('{"edits":[]}', 'stop')
        g = {'_qwen_call':model, '_v36_release_identity':lambda:{},
             '_progress':lambda *a,**k:None,
             '_v426_route_for_call':lambda *a:('27b38q2','selected model')}
        adaptive.install(g)
        ok, raw = g['_qwen_call']('ISSUE OWNER FILES: ["tests/app.rs"]',
            stage='functional transaction 1', profile='repair', max_tokens=adaptive.CAP_27B)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertEqual([c[1]['max_tokens'] for c in calls], [adaptive.CAP_27B]*2)
        self.assertIn('1-2 issue-owner files', calls[1][0])
        self.assertEqual(raw.metadata['v4259_length_retries'], 1)

    def test_repeated_truncation_remains_bounded_and_unaccepted(self):
        class Response(str):
            metadata = {'finish_reason':'length'}
            partial_text = '{"edits":['
        model = Mock(return_value=(False, Response('output limit')))
        g = {'_qwen_call':model, '_v36_release_identity':lambda:{},
             '_progress':lambda *a,**k:None,
             '_v426_route_for_call':lambda *a:('27b38q2','selected model')}
        adaptive.install(g)
        ok, _ = g['_qwen_call']('ISSUE OWNER FILES: ["tests/app.rs"]',
            stage='functional transaction 1', profile='repair', max_tokens=adaptive.CAP_27B)
        self.assertFalse(ok)
        self.assertEqual(model.call_count, 1 + adaptive.LENGTH_RETRIES)


class TransactionRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'working'
        self.source = SERVICE.replace('id, label', 'id, title')
        write(self.root, 'storage.py', self.source)
        write(self.root, 'run_workflow.py', RUNNER)
        write(self.root, '.jarvis_shared_build_cache/npm/_cacache/content-v2/blob', 'volatile')
        self.target = 'tests/test_application.py'
        self.manifest = {
            'files':[{'path':'storage.py'},{'path':'run_workflow.py'}],
            'components':[{'id':'notes','root':'.','toolchain_adapter':'custom',
                'build_command':f'"{sys.executable}" -m py_compile storage.py',
                'test_command':f'"{sys.executable}" run_workflow.py'}],
            'requirements':['persist notes across restart and reject blank titles'],
        }
        self.rows = [r for r in durable.functional_issues(self.root, 'finish', self.manifest)
                     if r['kind'] == 'functional_test_coverage']
        self.group = {'file':self.target,'phase':5,'kinds':['functional_test_coverage'],'rows':self.rows}
        self.assertEqual(len(self.rows), 1)

    def tearDown(self):
        self.temp.cleanup()

    def test_invalid_json_then_raw_test_passes_real_validation_and_persistence(self):
        def respond(payload, number):
            prompt = payload['messages'][0]['content']
            if number == 1:
                return {'text':'{"edits":[{"file":"tests/test_application.py","content":"broken "quote"}]}'}
            self.assertNotIn('response_format', payload)
            self.assertIn('without JSON', prompt)
            self.assertIn('Invalid transaction JSON', prompt)
            self.assertIn('SELECT id, title', prompt)
            return {'text':envelope(self.target, TEST)}
        with model_server(respond) as calls, evict_cache_on_traversal():
            ok, errors = tx.repair_transaction(vars(j), 'finish', self.manifest, self.root, self.group)
        self.assertTrue(ok, errors)
        self.assertEqual(len(calls), 2)
        self.assertEqual((self.root / 'storage.py').read_text(), self.source)
        self.assertEqual((self.root / self.target).read_text(), TEST)
        self.assertEqual(durable.functional_issues(self.root, 'finish', self.manifest), [])
        proof = subprocess.run([sys.executable, 'run_workflow.py'], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(proof.returncode, 0, proof.stdout + proof.stderr)

    def test_contradictory_new_test_cannot_be_promoted(self):
        wrong = TEST.replace('(note_id,"saved across restart")', '(note_id,"contradictory expected value")')
        with model_server(lambda *_:{'text':envelope(self.target, wrong)}):
            ok, errors = tx.repair_transaction(vars(j), 'finish', self.manifest, self.root, self.group,
                                              prior_errors=['Invalid transaction JSON from earlier attempt'])
        self.assertFalse(ok)
        self.assertFalse((self.root / self.target).exists())
        self.assertEqual((self.root / 'storage.py').read_text(), self.source)
        self.assertTrue(any('AssertionError' in error for error in errors), errors)

    def test_infrastructure_failure_uses_zero_model_calls_and_preserves_repair_budget(self):
        model = Mock(side_effect=AssertionError('must not call model'))
        g = dict(vars(j))
        g['_qwen_call'] = model
        g['_copy_project_for_candidate_validation'] = Mock(side_effect=PermissionError('authored source locked'))
        g['_append_project_event'] = Mock()
        tx.install(g)
        changed = g['_v429_repair_audit_round']('finish', self.manifest, self.root, {'issues':self.rows})
        self.assertFalse(changed)
        model.assert_not_called()
        self.assertEqual(g['_copy_project_for_candidate_validation'].call_count, 2)
        ledger = json.loads((self.root / tx.LEDGER).read_text())
        states = list(ledger['groups'].values())
        self.assertTrue(states)
        self.assertTrue(all(s['attempts'] == 0 and s['infrastructure_blocked'] for s in states))
        self.assertFalse((self.root / self.target).exists())

    def test_transient_copy_retry_reuses_one_model_generation(self):
        actual = j._copy_project_for_candidate_validation
        copies = []
        def copy(root):
            copies.append(root)
            if len(copies) == 1: raise FileNotFoundError('transient source race')
            return actual(root)
        with model_server(lambda *_:{'text':json.dumps({'edits':[{'file':self.target,'content':TEST}]})}) as calls, \
             patch.object(j, '_copy_project_for_candidate_validation', side_effect=copy):
            ok, errors = tx.repair_transaction(vars(j), 'finish', self.manifest, self.root, self.group)
        self.assertTrue(ok, errors)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(copies), 2)

    def test_infrastructure_checkpoint_resumes_after_filesystem_recovers(self):
        g = dict(vars(j))
        def validator(root, *args):
            proof = subprocess.run([sys.executable, 'run_workflow.py'], cwd=root,
                                   capture_output=True, text=True, timeout=30)
            return proof.returncode == 0, proof.stdout + proof.stderr
        def audit(root, request, manifest, **kwargs):
            rows = durable.functional_issues(root, request, manifest)
            ok, output = validator(root)
            if not ok:
                rows.append({'file':'.','kind':'component_validation','problem':output})
            return {'clean':ok and not rows, 'issues':rows, 'components':[]}
        g['_v429_whole_project_audit'] = audit
        g['_v35_validate_component'] = validator
        g['_qwen_call'] = Mock(return_value=(True, json.dumps({'edits':[{'file':self.target,'content':TEST}]})))
        g['_copy_project_for_candidate_validation'] = Mock(side_effect=PermissionError('source locked'))
        tx.install(g)
        convergence.install(g)
        ok, issues = g['_v429_whole_project_convergence']('finish', self.manifest, self.root)
        self.assertFalse(ok)
        g['_qwen_call'].assert_not_called()
        self.assertTrue(any(row['kind'] == 'validation_infrastructure' for row in issues))
        report = json.loads((self.root / convergence.REPORT).read_text())
        self.assertEqual(report['status'], 'infrastructure_blocked')
        self.assertNotIn('exhausted_revision', report)
        # Same source and request; only the filesystem condition changes.
        g['_copy_project_for_candidate_validation'] = j._copy_project_for_candidate_validation
        ok, issues = g['_v429_whole_project_convergence']('finish', self.manifest, self.root)
        self.assertTrue(ok, issues)
        self.assertEqual(g['_qwen_call'].call_count, 1)
        self.assertTrue((self.root / self.target).exists())

    def test_stop_before_clone_does_not_call_model_or_change_source(self):
        event = control._STOP_EVENT
        event.set()
        try:
            with patch.object(j, '_qwen_call') as model, patch.object(j, '_copy_project_for_candidate_validation') as clone:
                with self.assertRaises(control.ProjectStopRequested):
                    tx.repair_transaction(vars(j), 'finish', self.manifest, self.root, self.group)
                model.assert_not_called()
                clone.assert_not_called()
        finally:
            event.clear()

    def test_existing_production_edits_keep_exact_json_protocol(self):
        group = {'file':'storage.py','kinds':['persistence_sql_prepare'],'rows':[]}
        seen = []
        def model(prompt, *args, **kwargs):
            seen.append(kwargs)
            return True, json.dumps({'edits':[{'file':'storage.py','replacements':[
                {'search':'title required','replace':'nonblank title required'}]}]})
        result = tx._model_candidate({'_qwen_call':model}, 'finish', self.manifest, self.root, group,
                                     {'storage.py':self.source}, ['Invalid transaction JSON earlier'], 2, None)
        self.assertIn('nonblank title required', result['storage.py'])
        self.assertEqual(seen[0]['response_schema'], tx.SCHEMA)


if __name__ == '__main__':
    unittest.main(verbosity=2)
