"""Production job loading, scheduling, persistence and HTTP/core workflows.

Voice initialization is excluded by loading unchanged core definitions via AST.
The expensive model operation is a fixture; the scheduler, worker, IPC, ZIP
import, SQLite workflow, thread ownership and persisted job records are real.
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

from CHECK_V4253_PROJECT_UPLOADS import load_core_routes, project_zip
from ui import dashboard as d
from ui.project_uploads import ProjectUploads
import local_qwen_project as project


class JobLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jobs_file = self.root / 'agent_jobs.json'
        self.n = load_core_routes(None)
        self.n.update(AGENT_JOB_FILE=str(self.jobs_file), agent_next_number=1,
                      normalize_profile=lambda value: value or 'auto',
                      agent_completion_queue=deque(), qwen_project_busy=threading.Event())
        self.n['_start_qwen_project_job'] = self.n['actual_start_job']
        self.release = threading.Event()
        self.entered = threading.Event()
        self.servers = []

    def tearDown(self):
        self.release.set()
        for job in self.n['agent_jobs'].values():
            thread = job.get('thread')
            if thread and thread.ident is not None:
                thread.join(5)
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.temp.cleanup()

    def seed(self):
        checkpoint = self.root / 'saved.zip'
        checkpoint.write_bytes(project_zip())
        workspace = self.root / 'working'
        workspace.mkdir()
        (workspace / 'source.uncommon').write_text('preserve my project')
        rows = {
            '63': {'id': 63, 'job_type': 'qwen_project', 'status': 'stopping', 'stage': 'checkpoint',
                   'source_zip': str(checkpoint), 'zip_path': str(checkpoint), 'project_path': str(workspace)},
            '69': {'id': 69, 'job_type': 'qwen_project', 'status': 'running'},
            '70': {'id': 70, 'job_type': 'qwen_project', 'status': 'queued'},
            '60': {'id': 60, 'job_type': 'qwen_project', 'status': 'completed', 'result': 'original completed result'},
        }
        self.jobs_file.write_text(json.dumps(rows))
        return rows, checkpoint, workspace

    def parked_worker(self, job_id):
        self.entered.set()
        self.release.wait(5)

    def test_restart_retires_all_active_statuses_and_persists_history(self):
        rows, checkpoint, workspace = self.seed()
        original = checkpoint.read_bytes()
        self.n['_load_agent_jobs']()
        disk = json.loads(self.jobs_file.read_text())
        for job_id in (63, 69, 70):
            self.assertEqual(self.n['agent_jobs'][job_id]['status'], 'interrupted')
            self.assertEqual(disk[str(job_id)]['status'], 'interrupted')
            self.assertEqual(disk[str(job_id)]['stage'], 'interrupted')
        self.assertEqual(disk['60'], rows['60'])
        self.assertEqual(disk['63']['zip_path'], str(checkpoint))
        self.assertEqual(checkpoint.read_bytes(), original)
        self.assertEqual((workspace / 'source.uncommon').read_text(), 'preserve my project')
        self.assertEqual(self.n['agent_next_number'], 71)

    def test_dead_stopping_record_does_not_block_new_worker(self):
        self.n['agent_jobs'] = {63: {'id': 63, 'job_type': 'qwen_project', 'status': 'stopping'}}
        self.n['agent_next_number'] = 64
        self.n['_qwen_project_worker'] = self.parked_worker
        accepted, message = self.n['actual_start_job']('finish this project', source_zip='saved.zip')
        self.assertTrue(accepted, message)
        self.assertTrue(self.entered.wait(2))
        self.assertEqual(json.loads(self.jobs_file.read_text())['63']['status'], 'interrupted')
        self.assertEqual(self.n['agent_jobs'][64]['source_zip'], 'saved.zip')

    def test_live_worker_still_blocks_after_result_until_cleanup_finishes(self):
        self.n['_qwen_project_worker'] = self.parked_worker
        self.assertTrue(self.n['actual_start_job']('first')[0])
        self.assertTrue(self.entered.wait(2))
        self.n['agent_jobs'][1]['status'] = 'completed'
        accepted, message = self.n['actual_start_job']('second', source_zip='saved.zip')
        self.assertFalse(accepted)
        self.assertIn('retained', message)
        self.release.set()
        self.n['agent_jobs'][1]['thread'].join(2)
        self.assertTrue(self.n['actual_start_job']('second', source_zip='saved.zip')[0])

    def test_thread_start_failure_is_reported_and_retry_can_start(self):
        self.n['_qwen_project_worker'] = self.parked_worker
        with patch.object(threading.Thread, 'start', side_effect=RuntimeError('worker allocation failed')):
            accepted, message = self.n['actual_start_job']('first', source_zip='saved.zip')
        self.assertFalse(accepted)
        self.assertIn('allocation failed', message)
        self.assertEqual(json.loads(self.jobs_file.read_text())['1']['status'], 'failed')
        self.assertTrue(self.n['actual_start_job']('retry', source_zip='saved.zip')[0])
        self.assertTrue(self.entered.wait(2))

    def test_simultaneous_commands_start_exactly_one_worker(self):
        self.n['_qwen_project_worker'] = self.parked_worker
        barrier = threading.Barrier(2)
        def send():
            barrier.wait(2)
            return self.n['actual_start_job']('finish', source_zip='saved.zip')[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(len(self.n['agent_jobs']), 1)
        self.assertEqual(len(json.loads(self.jobs_file.read_text())), 1)

    def test_concurrent_saves_cannot_restore_older_running_status(self):
        self.n['agent_jobs'] = {1: {'id': 1, 'status': 'running'}}
        replace_entered, release_replace = threading.Event(), threading.Event()
        newer_started, newer_finished = threading.Event(), threading.Event()
        original_replace = self.n['os'].replace
        failures = []
        def replace(source, target):
            if threading.current_thread().name == 'older-save':
                replace_entered.set()
                release_replace.wait(3)
            original_replace(source, target)
        def old_save():
            if not self.n['_save_agent_jobs'](): failures.append('old save failed')
        def newer_save():
            newer_started.set()
            with self.n['agent_jobs_lock']:
                self.n['agent_jobs'][1]['status'] = 'completed'
            if not self.n['_save_agent_jobs'](): failures.append('new save failed')
            newer_finished.set()
        with patch.object(self.n['os'], 'replace', side_effect=replace):
            old = threading.Thread(target=old_save, name='older-save')
            old.start()
            self.assertTrue(replace_entered.wait(2))
            newer = threading.Thread(target=newer_save)
            newer.start()
            self.assertTrue(newer_started.wait(2))
            newer_finished.wait(.05)
            release_replace.set()
            old.join(3)
            newer.join(3)
        self.assertFalse(failures, failures)
        self.assertEqual(json.loads(self.jobs_file.read_text())['1']['status'], 'completed')

    def start_servers(self):
        ipc = ThreadingHTTPServer(('127.0.0.1', 0), self.n['JarvisIPCHandler'])
        dashboard = ThreadingHTTPServer(('127.0.0.1', 0), d.DashboardHandler)
        for server in (ipc, dashboard):
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.servers.append(server)
        return f'http://127.0.0.1:{ipc.server_port}', f'http://127.0.0.1:{dashboard.server_port}'

    def request(self, base, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_real_http_handoff_starts_production_worker_after_restart_and_persists(self):
        self.seed()
        self.n['_load_agent_jobs']()
        imported = self.root / 'imported'
        calls = []
        def edit(request, source_zip, **kwargs):
            calls.append(str(source_zip))
            project._safe_extract_zip(source_zip, imported)
            workflow = """from storage import save,names
assert save('retained')==1
try: save(' ')
except ValueError: pass
else: raise AssertionError('invalid input accepted')
assert names()==['retained']
"""
            subprocess.run([sys.executable, '-c', workflow], cwd=imported, check=True)
            subprocess.run([sys.executable, '-c', "from storage import names; assert names()==['retained']"], cwd=imported, check=True)
            result = self.root / 'tested_project.zip'
            with zipfile.ZipFile(result, 'w') as archive:
                archive.write(imported / 'storage.py', 'storage.py')
            return True, 'Test workflow passed.', result
        self.n.update(begin_project_run=lambda *a: None, finish_project_run=lambda *a: None,
                      prepare_project_qwen_routing=lambda *a, **k: (True, 'Test model operation'),
                      clear_project_qwen_routing=lambda: None, record_project_heartbeat=lambda *a: None,
                      _shared_memory_event=lambda *a, **k: None, analyze_and_edit_project_zip=edit,
                      AutomaticRepairExhausted=project.AutomaticRepairExhausted,
                      ProjectStopRequested=project.ProjectStopRequested)
        ipc, base = self.start_servers()
        store = ProjectUploads(self.root / 'uploads')
        content = project_zip()
        pending = store.create({'name': 'GearTrack (2).zip', 'size': len(content)})
        store.chunk(pending['id'], 0, content)
        ready = store.complete(pending['id'])
        # Deliberately provide stale file history. UI must prefer the core.
        stale = self.root / 'stale_dashboard_jobs.json'
        stale.write_text(json.dumps({'63': {'id': 63, 'job_type': 'qwen_project', 'status': 'stopping'}}))
        with patch.object(d, 'IPC_URL', ipc), patch.object(d, 'PROJECT_UPLOADS', store), patch.object(d, 'AGENT_JOB_FILE', str(stale)):
            queued = self.request(base, '/api/command', {'command': 'fix and finish this project', 'attachments': [ready]})
            for _ in range(150):
                job = self.request(base, '/api/command/' + queued['job_id'])
                if job['status'] in {'completed', 'failed'}: break
                time.sleep(.01)
            self.assertIs(job.get('attachment_accepted'), True, job)
            worker = self.n['agent_jobs'][71]['thread']
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(self.n['agent_jobs'][71]['status'], 'completed', self.n['agent_jobs'][71])
            agents = self.request(base, '/api/agents')
            rows = {row['id']: row for row in agents}
            self.assertEqual(rows[63]['status'], 'interrupted')
            self.assertEqual(rows[71]['status'], 'completed')
            self.assertTrue(rows[71]['runtime_confirmed'])
        self.assertEqual(calls, [ready['path']])
        self.assertEqual(Path(ready['path']).read_bytes(), content)
        self.assertEqual(json.loads(self.jobs_file.read_text())['71']['status'], 'completed')
        self.assertTrue((imported / 'src/experiment.uncommon').is_file())

    def test_offline_dashboard_marks_saved_active_records_unconfirmed(self):
        self.seed()
        original = self.jobs_file.read_bytes()
        with socket.socket() as unavailable:
            unavailable.bind(('127.0.0.1', 0))
            with patch.object(d, 'IPC_URL', f'http://127.0.0.1:{unavailable.getsockname()[1]}'), patch.object(d, 'AGENT_JOB_FILE', str(self.jobs_file)):
                rows = {row['id']: row for row in d.normalize_agents()}
        self.assertEqual(rows[63]['status'], 'unconfirmed')
        self.assertEqual(rows[63]['last_known_status'], 'stopping')
        self.assertFalse(rows[63]['runtime_confirmed'])
        self.assertEqual(rows[60]['status'], 'completed')
        self.assertEqual(self.jobs_file.read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
