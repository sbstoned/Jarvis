"""Real HTTP upload -> dashboard worker -> IPC -> ZIP routing/import regressions.

The core's production handler/router are loaded without starting voice models.
Only the expensive Qwen job launch is a fixture. Upload bytes, retries, files,
HTTP requests, metadata, extraction and the sample persistence workflow are real.
"""
import ast
import io
import http.client
import json
import os
from datetime import datetime
from pathlib import Path
import re
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ui import dashboard as d
from ui.project_uploads import ProjectUploads, UploadError, CHUNK_BYTES
import local_qwen_project as project

ROOT = Path(__file__).resolve().parent


def load_core_routes(start):
    # Compile unchanged production definitions, avoiding jarvis.py's unrelated
    # import-time microphone/Whisper initialization on an offline test machine.
    names = {'AttachmentCommandResult', 'JarvisIPCHandler', 'clean_transcription',
             '_inline_qwen_profile_marker', '_attached_file_markers',
             '_normalize_attached_project_instruction', '_first_attached_zip',
             'process_command', '_start_qwen_project_job', '_qwen_project_worker',
             '_save_agent_jobs', '_load_agent_jobs', '_mark_interrupted_agent',
             '_reconcile_project_jobs', '_agent_jobs_snapshot'}
    tree = ast.parse((ROOT / 'jarvis.py').read_text(encoding='utf-8'))
    body = [node for node in tree.body if
            (isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names) or
            (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
             {'_JARVIS_ATTACHMENT_RE', '_JARVIS_PROFILE_RE'} for t in node.targets))]
    namespace = {'re': re, 'Path': Path, 'json': json, 'os': os, 'threading': threading,
                 'datetime': datetime, 'agent_jobs': {}, 'agent_jobs_lock': threading.RLock(),
                 'BaseHTTPRequestHandler': BaseHTTPRequestHandler,
                 'extract_profile_marker': lambda command: (command, ''),
                 'save_selected_profile': lambda profile: None,
                 'interrupt_current_speech': lambda: None,
                 '_active_agent_status_request': lambda command: False,
                 '_fast_command_response': lambda command, message, **kwargs: message,
                 'log': lambda message: None}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(ROOT / 'jarvis.py'), 'exec'), namespace)
    namespace['actual_start_job'] = namespace['_start_qwen_project_job']
    namespace['_start_qwen_project_job'] = start
    return namespace


def project_zip(wrapper=True, large=False):
    body = io.BytesIO()
    prefix = 'trial_03/' if wrapper else ''
    with zipfile.ZipFile(body, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(prefix + 'storage.py', '''import sqlite3
def save(name):
    if not name.strip(): raise ValueError("name required")
    with sqlite3.connect("app.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, name TEXT)")
        return db.execute("INSERT INTO notes(name) VALUES (?)",(name,)).lastrowid
def names():
    with sqlite3.connect("app.db") as db:
        return [row[0] for row in db.execute("SELECT name FROM notes ORDER BY id")]
''')
        archive.writestr(prefix + 'notes.md', 'An existing application checkpoint, with authored source.')
        archive.writestr(prefix + 'src/Main.kt', 'fun main() = println("preserved Kotlin source")\n')
        archive.writestr(prefix + 'src/experiment.uncommon', 'preserve this language too\n')
        archive.writestr(prefix + 'src-tauri/target/cache.bin', b'rebuildable')
        if large:
            import random
            archive.writestr(prefix + 'assets/fixture.bin', random.Random(42).randbytes(2 * CHUNK_BYTES + 8192))
    return body.getvalue()


class UploadWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='jarvis_upload_tests_')
        cls.root = Path(cls.temp.name)
        cls.original_store = d.PROJECT_UPLOADS
        cls.original_ipc = d.IPC_URL
        cls.launches = []
        cls.busy = False

        def start(command, source_zip=None, qwen_profile='auto'):
            if cls.busy:
                return False, 'A project is saving its checkpoint. Your ZIP is retained.'
            if source_zip is None:
                raise AssertionError('ZIP repair was routed to NEW project generation')
            cls.launches.append({'command': command, 'source_zip': str(source_zip), 'profile': qwen_profile})
            return True, 'Existing project accepted for repair.'

        cls.core = load_core_routes(start)
        cls.ipc = ThreadingHTTPServer(('127.0.0.1', 0), cls.core['JarvisIPCHandler'])
        cls.dashboard = ThreadingHTTPServer(('127.0.0.1', 0), d.DashboardHandler)
        for server in (cls.ipc, cls.dashboard):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        d.IPC_URL = f'http://127.0.0.1:{cls.ipc.server_port}'
        cls.base = f'http://127.0.0.1:{cls.dashboard.server_port}'

    @classmethod
    def tearDownClass(cls):
        for server in (cls.dashboard, cls.ipc):
            server.shutdown()
            server.server_close()
        d.PROJECT_UPLOADS, d.IPC_URL = cls.original_store, cls.original_ipc
        cls.temp.cleanup()

    def setUp(self):
        type(self).busy = False
        self.launches.clear()
        self.work = Path(tempfile.mkdtemp(dir=self.root))
        d.PROJECT_UPLOADS = ProjectUploads(self.work / 'uploads')

    def request(self, path, value=None, *, body=None, headers=None, method='POST'):
        if body is None and method == 'POST':
            body = json.dumps(value if value is not None else {}).encode()
        request = urllib.request.Request(self.base + path, data=body,
                                         headers=headers or {'Content-Type': 'application/json'}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def upload(self, body, name='Trial 3 (saved).zip'):
        status, row = self.request('/api/uploads', {'name': name, 'size': len(body)})
        self.assertEqual(status, 200, row)
        for offset in range(0, len(body), CHUNK_BYTES):
            status, result = self.request(f'/api/uploads/{row["id"]}/chunk', body=body[offset:offset+CHUNK_BYTES],
                                         headers={'Content-Type': 'application/octet-stream', 'X-Upload-Offset': str(offset)})
            self.assertEqual(status, 200, result)
        return self.request(f'/api/uploads/{row["id"]}/complete')

    def await_job(self, job_id):
        import time
        for _ in range(200):
            status, job = self.request('/api/command/' + job_id, method='GET')
            if job['status'] in {'completed', 'failed'}:
                return job
            time.sleep(.01)
        self.fail('Command worker did not complete')

    def test_complete_http_ipc_route_import_and_real_persistence(self):
        source = project_zip()
        status, ready = self.upload(source)
        self.assertEqual(status, 200, ready)
        self.assertEqual(Path(ready['path']).read_bytes(), source)
        status, queued = self.request('/api/command', {'command': 'fix and finish this project', 'qwen_profile': 'auto',
                                                       'attachments': [ready], 'require_project_zip': True})
        self.assertEqual(status, 202, queued)
        job = self.await_job(queued['job_id'])
        self.assertIs(job['attachment_accepted'], True)
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.launches[0]['source_zip'], ready['path'])
        imported = self.work / 'imported'
        report = project._safe_extract_zip(self.launches[0]['source_zip'], imported)
        self.assertEqual(report['wrapper_stripped'], 'trial_03')
        self.assertTrue((imported / 'src/experiment.uncommon').is_file())
        self.assertTrue((imported / 'src/Main.kt').is_file())
        self.assertFalse((imported / 'src-tauri/target').exists())
        workflow = '''from storage import save,names
import subprocess,sys
assert save('persisted')==1
assert names()==['persisted']
try: save(' ')
except ValueError: pass
else: raise AssertionError('invalid input accepted')
assert names()==['persisted']
subprocess.run([sys.executable,'-c',"from storage import names; assert names()==['persisted']"],check=True)
'''
        result = subprocess.run([sys.executable, '-c', workflow], cwd=imported, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_attachment_never_queues_a_new_project(self):
        status, error = self.request('/api/command', {'command': 'fix and finish this project',
                                                      'attachments': [{'path': str(self.work / 'missing.zip')}]})
        self.assertEqual(status, 422)
        self.assertEqual(error['code'], 'attachment_missing')
        self.assertFalse(self.launches)

    def test_plain_existing_project_request_requires_zip(self):
        status, error = self.request('/api/command', {'command': 'fix and finish this project', 'attachments': []})
        self.assertEqual((status, error['code']), (422, 'project_zip_required'))

    def test_incomplete_upload_is_not_an_attachment(self):
        _, row = self.request('/api/uploads', {'name': 'project.zip', 'size': 10})
        self.assertNotIn('path', row)
        status, error = self.request('/api/command', {'command': 'finish', 'attachments': [row]})
        self.assertEqual((status, error['code']), (422, 'attachment_incomplete'))

    def test_oversize_rejected_before_reading_file_bytes(self):
        d.PROJECT_UPLOADS.max_bytes = 100
        status, error = self.request('/api/uploads', {'name': 'project.zip', 'size': 101})
        self.assertEqual((status, error['code']), (413, 'upload_too_large'))
        self.assertFalse(list(d.PROJECT_UPLOADS.sessions.glob('*.part')))

    def test_interrupted_chunk_does_not_publish_partial_file(self):
        _, row = self.request('/api/uploads', {'name': 'source.txt', 'size': 6})
        connection = http.client.HTTPConnection('127.0.0.1', self.dashboard.server_port, timeout=5)
        connection.putrequest('POST', f'/api/uploads/{row["id"]}/chunk')
        connection.putheader('Content-Length', '6')
        connection.putheader('X-Upload-Offset', '0')
        connection.endheaders()
        connection.send(b'abc')
        connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        self.assertEqual(response.status, 408)
        self.assertEqual(json.loads(response.read())['code'], 'upload_interrupted')
        connection.close()
        self.assertEqual(d.PROJECT_UPLOADS.status(row['id'])['received'], 0)
        status, error = self.request(f'/api/uploads/{row["id"]}/complete')
        self.assertEqual((status, error['code']), (409, 'upload_incomplete'))
        self.assertFalse(list(d.PROJECT_UPLOADS.root.glob('*.zip')))
        d.PROJECT_UPLOADS.chunk(row['id'], 0, b'abcdef')
        self.assertEqual(Path(d.PROJECT_UPLOADS.complete(row['id'])['path']).read_bytes(), b'abcdef')

    def test_retry_of_saved_chunk_is_idempotent(self):
        _, row = self.request('/api/uploads', {'name': 'source.txt', 'size': 6})
        url = f'/api/uploads/{row["id"]}/chunk'
        for _ in range(2):
            status, value = self.request(url, body=b'abc', headers={'X-Upload-Offset': '0'})
            self.assertEqual((status, value['received']), (200, 3))
        self.request(url, body=b'def', headers={'X-Upload-Offset': '3'})
        _, ready = self.request(f'/api/uploads/{row["id"]}/complete')
        self.assertEqual(Path(ready['path']).read_bytes(), b'abcdef')

    def test_conflicting_retry_preserves_already_saved_bytes(self):
        store = d.PROJECT_UPLOADS
        row = store.create({'name': 'source.txt', 'size': 6})
        store.chunk(row['id'], 0, b'abc')
        with self.assertRaises(UploadError) as context:
            store.chunk(row['id'], 0, b'xyz')
        self.assertEqual(context.exception.code, 'chunk_mismatch')
        store.chunk(row['id'], 3, b'def')
        self.assertEqual(Path(store.complete(row['id'])['path']).read_bytes(), b'abcdef')

    def test_resume_after_dashboard_restart(self):
        row = d.PROJECT_UPLOADS.create({'name': 'source.txt', 'size': 6})
        d.PROJECT_UPLOADS.chunk(row['id'], 0, b'abc')
        d.PROJECT_UPLOADS = ProjectUploads(d.PROJECT_UPLOADS.root)
        status, resumed = self.request('/api/uploads', {'id': row['id'], 'name': 'source.txt', 'size': 6})
        self.assertEqual((status, resumed['received']), (200, 3))
        d.PROJECT_UPLOADS.chunk(row['id'], 3, b'def')
        self.assertEqual(Path(d.PROJECT_UPLOADS.complete(row['id'])['path']).read_bytes(), b'abcdef')

    def test_finalization_recovers_rename_before_metadata_save(self):
        store = d.PROJECT_UPLOADS
        row = store.create({'name': 'source.txt', 'size': 3})
        store.chunk(row['id'], 0, b'abc')
        with patch.object(store, '_save', side_effect=OSError('interrupted metadata write')):
            with self.assertRaises(OSError): store.complete(row['id'])
        restarted = ProjectUploads(store.root)
        result = restarted.status(row['id'])
        self.assertEqual(result['upload_status'], 'complete')
        self.assertEqual(Path(result['path']).read_bytes(), b'abc')

    def test_invalid_zip_has_actionable_error_and_no_final_path(self):
        status, error = self.upload(b'not a zip at all')
        self.assertEqual((status, error['code']), (422, 'invalid_zip'))
        self.assertFalse(list(d.PROJECT_UPLOADS.root.glob('*.zip')))

    def test_unsafe_zip_is_rejected_before_project_launch(self):
        body = io.BytesIO()
        with zipfile.ZipFile(body, 'w') as z: z.writestr('../outside.py', 'unsafe')
        status, error = self.upload(body.getvalue())
        self.assertEqual((status, error['code']), (422, 'unsafe_zip'))
        self.assertFalse(self.launches)

    def test_busy_worker_declines_but_retains_uploaded_zip(self):
        _, ready = self.upload(project_zip())
        type(self).busy = True
        _, queued = self.request('/api/command', {'command': 'finish this project', 'attachments': [ready]})
        job = self.await_job(queued['job_id'])
        self.assertIs(job['attachment_accepted'], False)
        self.assertTrue(Path(ready['path']).is_file())
        self.assertFalse(self.launches)

    def test_offline_core_keeps_zip_and_dashboard_health_then_recovers(self):
        body = project_zip()
        _, ready = self.upload(body)
        # A bound, non-listening local socket deterministically refuses IPC;
        # the upload server and its real health endpoint remain running.
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            with patch.object(d, 'IPC_URL', f'http://127.0.0.1:{unavailable.getsockname()[1]}'):
                self.assertFalse(d.ipc_is_online())
                status, health = self.request('/api/health', method='GET')
                self.assertEqual(status, 200)
                self.assertIs(health['ok'], True)
                self.assertEqual(health['build_id'], d.DASHBOARD_BUILD_ID)
                _, queued = self.request('/api/command', {'command': 'finish this project', 'attachments': [ready]})
                job = self.await_job(queued['job_id'])
                self.assertEqual(job['status'], 'failed')
                self.assertIs(job['attachment_accepted'], False)
                self.assertIn('IPC is offline', job['error'])
        self.assertEqual(Path(ready['path']).read_bytes(), body)
        self.assertFalse(self.launches)
        # The same completed upload can be submitted after IPC comes back.
        _, queued = self.request('/api/command', {'command': 'finish this project', 'attachments': [ready]})
        recovered = self.await_job(queued['job_id'])
        self.assertEqual(recovered['status'], 'completed')
        self.assertIs(recovered['attachment_accepted'], True)
        self.assertEqual(len(self.launches), 1)

    def test_actual_core_does_not_start_during_checkpoint_save(self):
        release = threading.Event()
        worker = threading.Thread(target=lambda: release.wait(5))
        worker.start()
        try:
            self.core['agent_jobs'] = {69: {'id': 69, 'job_type': 'qwen_project', 'status': 'stopping', 'thread': worker}}
            started, message = self.core['actual_start_job']('finish', source_zip='ready.zip')
            self.assertFalse(started)
            self.assertIn('checkpoint', message)
        finally:
            release.set()
            worker.join(5)
            self.core['agent_jobs'] = {}

    def test_cancel_cleans_partial_but_preserves_completed_source(self):
        store = d.PROJECT_UPLOADS
        row = store.create({'name': 'source.txt', 'size': 3})
        store.cancel(row['id'])
        with self.assertRaises(UploadError): store.status(row['id'])
        row = store.create({'name': 'source.txt', 'size': 3})
        store.chunk(row['id'], 0, b'abc')
        ready = store.complete(row['id'])
        store.cancel(row['id'])
        self.assertEqual(Path(ready['path']).read_bytes(), b'abc')

    def test_changed_or_outside_attachment_is_not_silently_dropped(self):
        _, ready = self.upload(project_zip())
        Path(ready['path']).write_bytes(b'changed')
        status, error = self.request('/api/command', {'command': 'finish', 'attachments': [ready]})
        self.assertEqual((status, error['code']), (422, 'attachment_changed'))
        self.assertFalse(self.launches)

    def test_legacy_raw_upload_is_still_usable(self):
        old = d.UPLOADS_DIR
        d.UPLOADS_DIR = str(d.PROJECT_UPLOADS.root)
        try:
            status, row = self.request('/api/upload', body=project_zip(False),
                                       headers={'Content-Type': 'application/octet-stream', 'X-Filename': 'old-client.zip'})
            self.assertEqual(status, 200, row)
            self.assertEqual(d.PROJECT_UPLOADS.resolve_attachments([row])[0]['kind'], 'zip')
        finally:
            d.UPLOADS_DIR = old

    @unittest.skipUnless(shutil.which('node'), 'Node required for the production JavaScript transport/UI test')
    def test_javascript_client_and_ui_against_real_http_server(self):
        source = self.work / 'Trial 3 (saved).zip'
        source.write_bytes(project_zip(large=True))
        result = subprocess.run(['node', str(ROOT / 'CHECK_V4253_UPLOAD_CLIENT.js'), self.base, str(source)],
                                cwd=ROOT, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main(verbosity=2)
