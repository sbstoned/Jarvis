"""Native-process/HTTP fixtures for V42.63 (no model download or GPU required).

The controller, Popen, health polling, log files, timeouts and process cleanup are
real. Only the executable is substituted with a small llama.cpp protocol fixture.
Routing tests exercise the final installed engine with controlled startup results.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import qwen_model_manager as qmm


SERVER = r'''
import argparse, json, os, sys, time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
parser = argparse.ArgumentParser()
parser.add_argument('-m'); parser.add_argument('-c', type=int)
parser.add_argument('-ngl'); parser.add_argument('--port', type=int)
for flag in ('-mg', '-np', '-n', '-sm'):
    parser.add_argument(flag)
args, _ = parser.parse_known_args()
settings = json.loads(Path(args.m).read_text())
event = dict(pid=os.getpid(), model=args.m, context=args.c, gpu_layers=args.ngl)
with Path(args.m).parent.joinpath('events.jsonl').open('a') as handle:
    handle.write(json.dumps(event) + '\n')
mode = settings.get('mode', 'ready')
if mode == 'oom' or (mode == 'context_oom' and args.c > 16384) or (mode == 'gpu_oom' and args.ngl == 'all'):
    print('ggml_cuda: cudaMalloc failed: out of memory', file=sys.stderr, flush=True)
    sys.exit(20)
if mode == 'bad_model':
    print('error loading model: unknown model architecture test_arch', file=sys.stderr, flush=True)
    sys.exit(21)
if mode == 'noisy':
    print('loader progress ' * 40000, file=sys.stderr, flush=True)
print('native fixture started', flush=True)
start = time.monotonic()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        loading = time.monotonic() - start < settings.get('delay', 0.05)
        status = 503 if loading else 200
        if self.path == '/health':
            body = {'error': {'message': 'Loading model'}} if loading else {'status': 'ok'}
        elif self.path == '/props':
            body = {'model_path': settings.get('reported_model', args.m), 'total_slots': 1,
                    'default_generation_settings': {'n_ctx': settings.get('reported_context', args.c)},
                    'speculative': {'draft': {'n_ctx': 6144}}}
            if mode == 'no_props': status = 404; body = {}
        else:
            status = 404; body = {}
        data = json.dumps(body).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data))); self.end_headers()
        try: self.wfile.write(data)
        except OSError: pass
HTTPServer.allow_reuse_address = True
HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
'''


class NativeStartup(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.script = self.root / 'server fixture.py'
        self.script.write_text(SERVER, encoding='utf-8')
        self.exe = self.root / 'llama-server.exe'
        self.exe.touch()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        profiles = {key: dict(info, path=str(self.root / f'{key} model.gguf'))
                    for key, info in qmm.MODEL_PROFILES.items()}
        for info in profiles.values():
            Path(info['path']).write_text('{}')
        for name, value in {
            'JARVIS_DIR': self.root, 'QWEN_SERVER_EXE': str(self.exe),
            'QWEN_PORT': self.port, 'QWEN_BASE_URL': f'http://127.0.0.1:{self.port}',
            'RUNTIME_PROFILE': self.root / 'runtime.json',
            'SELECTION_FILE': self.root / 'selection.json',
            'STARTUP_REPORT': self.root / 'startup.json',
            'MODEL_PROFILES': profiles, '_OWNED_SERVER': None,
        }.items():
            self.stack.enter_context(patch.object(qmm, name, value))
        self.stack.enter_context(patch.dict(os.environ, {'JARVIS_QWEN_GPU_LAYERS': 'all',
                                                       'JARVIS_QWEN_STARTUP_FALLBACK': '1'}))
        # Preserve native Popen, redirection and platform flags. Python supplies
        # only the fixture executable; model selection/args are left untouched.
        launch = qmm._launch_server
        self.commands = []
        self.processes = []
        def fixture(command, out, err):
            self.commands.append(command)
            proc = launch([sys.executable, str(self.script)] + command[1:], out, err)
            self.processes.append(proc)
            return proc
        self.stack.enter_context(patch.object(qmm, '_launch_server', side_effect=fixture))
        # No external host processes are part of this isolated fixture.
        self.stack.enter_context(patch.object(qmm, '_windows_server_commandline', return_value=''))
        self.stack.enter_context(patch.object(qmm, '_stop_local_qwen', side_effect=self.stop_owned))
        self.addCleanup(self.stop_owned)
        qmm.save_selected_profile('auto')

    def stop_owned(self):
        for proc in self.processes:
            qmm._terminate_server(proc)
        qmm._OWNED_SERVER = None

    def model(self, key='9b35', **settings):
        Path(qmm.MODEL_PROFILES[key]['path']).write_text(json.dumps(settings))

    def run_model(self, key='9b35', **kwargs):
        return qmm.ensure_qwen_profile(key, timeout=kwargs.pop('timeout', 5),
                                       persist_selection=False, **kwargs)

    def events(self):
        path = self.root / 'events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_stopped(self):
        self.assertTrue(all(proc.poll() is not None for proc in self.processes))
        self.assertIsNone(qmm._OWNED_SERVER)
        self.assertFalse(qmm._port_open())

    def test_slow_503_loading_waits_for_native_readiness(self):
        self.model(delay=0.8)
        start = time.monotonic()
        messages = []
        ok, detail = self.run_model(progress=messages.append)
        self.assertTrue(ok, detail)
        self.assertGreaterEqual(time.monotonic() - start, 0.8)
        self.assertIsNone(self.processes[0].poll())
        self.assertTrue(qmm._health())
        self.assertEqual(qmm._runtime_context_tokens(), 40960)
        self.assertEqual(qmm._read_runtime_profile()['status'], 'ready')
        self.assertEqual(qmm.selected_profile(), 'auto')
        self.assertEqual(self.commands[0][0], str(self.exe))
        self.assertNotIn('powershell.exe', self.commands[0])
        self.assertIn('waiting for /health', '\n'.join(messages))

    def test_healthy_runtime_is_reused_without_new_process(self):
        self.assertTrue(self.run_model()[0])
        pid = qmm._OWNED_SERVER.pid
        self.assertTrue(self.run_model()[0])
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(qmm._OWNED_SERVER.pid, pid)

    def test_context_memory_fallback_is_same_model_and_reused(self):
        self.model(mode='context_oom')
        ok, detail = self.run_model()
        self.assertTrue(ok, detail)
        self.assertEqual([row['context'] for row in self.events()], [40960, 16384])
        self.assertEqual(len({row['model'] for row in self.events()}), 1)
        self.assertTrue(qmm._runtime_matches('9b35'))
        self.assertTrue(self.run_model()[0])
        self.assertEqual(len(self.commands), 2)
        self.assertLessEqual(qmm._read_runtime_profile()['max_output_tokens'], 8192)
        receipt = json.loads(qmm.STARTUP_REPORT.read_text())
        self.assertIn('out of memory', receipt['attempts'][0]['log_tail'])
        self.assertEqual(receipt['status'], 'ready')

    def test_gpu_memory_fallback_keeps_manual_27b_selection(self):
        self.model('27b38q2', mode='gpu_oom')
        qmm.save_selected_profile('27b38q2')
        ok, detail = self.run_model('27b38q2')
        self.assertTrue(ok, detail)
        self.assertEqual([r['gpu_layers'] for r in self.events()], ['all', 'all', '16'])
        self.assertEqual(len({row['model'] for row in self.events()}), 1)
        self.assertEqual(qmm.selected_profile(), '27b38q2')
        self.assertEqual(qmm.active_profile(), '27b38q2')

    def test_exhausted_oom_is_bounded_and_preserves_native_error(self):
        self.model(mode='oom')
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('out of memory', detail)
        self.assertEqual(len(self.commands), 3)
        self.assert_stopped()

    def test_bad_architecture_is_not_retried_as_memory_failure(self):
        self.model(mode='bad_model')
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('unknown model architecture test_arch', detail)
        self.assertEqual(len(self.commands), 1)
        self.assert_stopped()

    def test_large_stderr_does_not_block_startup(self):
        self.model(mode='noisy')
        ok, detail = self.run_model()
        self.assertTrue(ok, detail)
        self.assertGreater((self.root / 'qwen_server_stderr.log').stat().st_size, 500000)

    def test_timeout_terminates_and_reaps_native_server(self):
        self.model(delay=120)
        ok, detail = self.run_model(timeout=1)
        self.assertFalse(ok)
        self.assertIn('Timed out', detail)
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(json.loads(qmm.STARTUP_REPORT.read_text())['status'], 'timeout')
        self.assert_stopped()

    def test_stop_cancels_loading_and_prevents_fallback(self):
        self.model(delay=120)
        stop = threading.Event()
        timer = threading.Timer(0.7, stop.set)
        timer.start()
        self.addCleanup(timer.cancel)
        ok, detail = self.run_model(cancelled=stop.is_set)
        self.assertFalse(ok)
        self.assertIn('cancelled', detail)
        self.assertEqual(len(self.commands), 1)
        self.assert_stopped()

    def test_wrong_live_model_cannot_be_hidden_by_runtime_receipt(self):
        self.model(reported_model=qmm.MODEL_PROFILES['27b38q2']['path'])
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('different model', detail)
        self.assert_stopped()

    def test_wrong_live_context_is_rejected(self):
        self.model(reported_context=6144)
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('6,144', detail)
        self.assert_stopped()

    def test_unavailable_props_cannot_use_stale_context_as_ready(self):
        self.model(mode='no_props')
        ok, detail = self.run_model(timeout=1)
        self.assertFalse(ok)
        self.assertIn('Timed out', detail)
        self.assert_stopped()

    def test_busy_port_is_not_mistaken_for_model_success(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', self.port))
            sock.listen()
            with patch.object(qmm, '_health', return_value=False):
                ok, detail = self.run_model()
            self.assertFalse(ok)
            self.assertIn('occupied', detail)
            self.assertEqual(self.commands, [])

    def test_fallback_can_be_disabled(self):
        self.model(mode='oom')
        with patch.dict(os.environ, {'JARVIS_QWEN_STARTUP_FALLBACK': '0'}):
            ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertEqual(len(self.commands), 1)
        self.assert_stopped()

    def test_low_gpu_override_is_not_raised_by_fallback(self):
        self.model(mode='oom')
        with patch.dict(os.environ, {'JARVIS_QWEN_GPU_LAYERS': '0'}):
            self.assertFalse(self.run_model()[0])
        self.assertEqual([r['gpu_layers'] for r in self.events()], ['0', '0'])

    def test_auto_standby_can_use_peer_without_persisting_it(self):
        self.model(mode='bad_model')
        with patch.object(qmm, '_auto_profile', return_value='9b35'):
            ok, detail = self.run_model('auto')
        self.assertTrue(ok, detail)
        self.assertEqual(qmm.active_profile(), '27b38q2')
        self.assertEqual(qmm.selected_profile(), 'auto')
        worker_report = json.loads(qmm._profile_report_path('9b35').read_text())
        self.assertEqual(worker_report['status'], 'failed')
        self.assertIn('unknown model architecture', worker_report['attempts'][0]['log_tail'])

    def test_missing_executable_and_model_have_actionable_errors(self):
        self.exe.unlink()
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('JARVIS_QWEN_SERVER_EXE', detail)
        Path(qmm.MODEL_PROFILES['9b35']['path']).unlink()
        ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('DOWNLOAD_QWEN35', detail)
        self.assertEqual(self.commands, [])

    def test_mismatched_base_url_does_not_start_or_stop_local_processes(self):
        with patch.object(qmm, 'QWEN_BASE_URL', 'https://example.invalid'), \
             patch.object(qmm, '_stop_local_qwen') as stop:
            ok, detail = self.run_model()
        self.assertFalse(ok)
        self.assertIn('same local server port', detail)
        stop.assert_not_called()
        self.assertEqual(self.commands, [])


class RoutingPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import local_qwen_project
        import jarvis_v4240_repair
        cls.engine = local_qwen_project
        cls.control = jarvis_v4240_repair

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(self.control, '_STOP_EVENT', threading.Event()))
        self.stack.enter_context(patch.object(self.engine, '_v426_runtime_matches', return_value=False))
        self.stack.enter_context(patch.object(self.engine, '_v426_active_profile', return_value=''))
        self.stack.enter_context(patch.object(self.engine, 'qwen_status', return_value=False))
        self.stack.enter_context(patch.object(self.engine, 'V426_AUTO_ROUTING', True))
        self.stack.enter_context(patch.object(self.engine, 'V4219_FAST_ROUTING', True))
        self.stack.enter_context(patch.object(self.engine._V4224_ROUTE, 'force_worker', False, create=True))
        self.stack.enter_context(patch.object(self.engine._V4224_ROUTE, 'force_specialist', False, create=True))
        self.addCleanup(self.engine.clear_project_qwen_routing)

    def test_each_dropdown_manual_choice_is_locked_at_every_stage(self):
        j = self.engine
        for model in ('8b', '9b35', '27b38q2', '27b'):
            with self.subTest(model=model):
                j.configure_project_qwen_routing(model)
                for stage, call in [('Architecture', 'plan'), ('Generate source', 'generate'),
                                    ('root cause', 'repair'), ('Global convergence', 'audit')]:
                    self.assertEqual(j._v426_route_for_call(stage, call, 'source')[0], model)
                with patch.object(j, '_v426_ensure_qwen_profile', return_value=(False, 'OOM')) as start:
                    self.assertFalse(j._v426_switch_for_call('9b35', 'rescue')[0])
                    self.assertEqual([c.args[0] for c in start.call_args_list], [model])
                    self.assertFalse(start.call_args.kwargs['persist_selection'])

    def test_auto_routes_routine_tests_to_worker_and_hard_diagnostics_to_27b(self):
        j = self.engine
        j.configure_project_qwen_routing('auto')
        self.assertEqual(j._v426_route_for_call('Generating src-tauri/tests/application.rs', 'generate', 'source')[0], '9b35')
        self.assertEqual(j._v426_route_for_call('cross-component integration root cause', 'repair', 'source')[0], '27b38q2')
        self.assertEqual(j._v426_route_for_call('leaf repair', 'repair', 'source')[0], '9b35')

    def test_auto_initializes_worker_and_actual_calls_can_promote(self):
        j = self.engine
        with patch.object(j, '_v426_ensure_qwen_profile', return_value=(True, 'ready')) as start:
            self.assertTrue(j.prepare_project_qwen_routing('auto')[0])
            target, reason = j._v426_route_for_call('root cause', 'repair', 'source')
            self.assertTrue(j._v426_switch_for_call(target, reason)[0])
        self.assertEqual([c.args[0] for c in start.call_args_list], ['9b35', '27b38q2'])

    def test_auto_does_not_repeat_exhausted_load_every_hard_stage(self):
        j = self.engine
        j.configure_project_qwen_routing('auto')
        def result(model, **kwargs):
            return (False, 'native OOM') if model == '27b38q2' else (True, 'ready')
        with patch.object(j, '_v426_ensure_qwen_profile', side_effect=result) as start:
            self.assertTrue(j._v426_switch_for_call('27b38q2', 'root cause')[0])
            self.assertTrue(j._v426_switch_for_call('27b38q2', 'root cause again')[0])
            self.assertEqual([c.args[0] for c in start.call_args_list], ['27b38q2', '9b35', '9b35'])
            j.configure_project_qwen_routing('auto')
            self.assertTrue(j._v426_switch_for_call('27b38q2', 'new project')[0])
            self.assertEqual([c.args[0] for c in start.call_args_list].count('27b38q2'), 2)

    def test_auto_reuses_healthy_pool_member_on_project_start(self):
        j = self.engine
        with patch.object(j, '_v426_active_profile', return_value='27b38q2'), \
             patch.object(j, 'qwen_status', return_value=True), \
             patch.object(j, '_v426_runtime_matches', side_effect=lambda model: model == '27b38q2'), \
             patch.object(j, '_v426_ensure_qwen_profile') as start:
            self.assertTrue(j.prepare_project_qwen_routing('auto')[0])
            start.assert_not_called()

    def test_cancellation_prevents_peer_start(self):
        j = self.engine
        j.configure_project_qwen_routing('auto')
        def cancelled(model, **kwargs):
            self.control._STOP_EVENT.set()
            self.assertTrue(kwargs['cancelled']())
            return False, 'cancelled'
        with patch.object(j, '_v426_ensure_qwen_profile', side_effect=cancelled) as start:
            with self.assertRaises(self.control.ProjectStopRequested):
                j._v426_switch_for_call('9b35', 'initial')
            self.assertEqual(start.call_count, 1)

    def test_fast_routing_control_and_forced_specialist_still_work(self):
        j = self.engine
        j.configure_project_qwen_routing('auto')
        with patch.object(j, 'V4219_FAST_ROUTING', False), \
             patch.object(j, '_v4219_prev_auto_target', return_value=('27b38q2', 'configured policy')):
            self.assertEqual(j._v426_route_for_call('routine', 'generate', 'source')[0], '27b38q2')
        with patch.object(j._V4224_ROUTE, 'force_specialist', True):
            self.assertEqual(j._v426_route_for_call('cluster', 'repair', 'source')[0], '27b38q2')
            j.configure_project_qwen_routing('9b35')
            self.assertEqual(j._v426_route_for_call('cluster', 'repair', 'source')[0], '9b35')

    def test_recorded_16k_fallback_limits_provider_and_project_when_props_unavailable(self):
        import multi_provider as provider
        j = self.engine
        data = {'profile': '9b35', 'model_family': 'qwen35', 'context': 16384,
                'generated_at': 'fixture', 'pid': 123, 'status': 'ready'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'qwen_runtime_profile.json').write_text(json.dumps(data))
            with patch.object(j, 'JARVIS_DIR', root), \
                 patch.object(j, '_active_qwen_model_family', return_value='qwen35'), \
                 patch.object(provider, 'JARVIS_DIR', root), \
                 patch.object(provider, '_QWEN_RUNTIME_CONTEXT_CACHE', {}), \
                 patch.object(provider.requests, 'get', side_effect=OSError('temporarily unavailable')):
                self.assertEqual(provider.qwen_runtime_context_tokens(), 16384)
                self.assertEqual(j._qwen_effective_context_tokens(), 16384)


class LauncherCompatibility(unittest.TestCase):
    def test_no_argument_cli_uses_saved_dropdown_and_does_not_overwrite_it(self):
        with patch.object(qmm, 'selected_profile', return_value='27b38q2'), \
             patch.object(qmm, 'ensure_qwen_profile', return_value=(True, 'ready')) as start:
            self.assertEqual(qmm._main([]), 0)
            self.assertEqual(start.call_args.args[0], '27b38q2')
            self.assertFalse(start.call_args.kwargs['persist_selection'])

    def test_cli_preserves_spaces_explicit_settings_and_exit_failure(self):
        profiles = {key: dict(value) for key, value in qmm.MODEL_PROFILES.items()}
        with patch.object(qmm, 'MODEL_PROFILES', profiles), \
             patch.object(qmm, 'QWEN_PORT', qmm.QWEN_PORT), \
             patch.object(qmm, 'QWEN_BASE_URL', qmm.QWEN_BASE_URL), \
             patch.object(qmm, 'QWEN_SERVER_EXE', qmm.QWEN_SERVER_EXE), \
             patch.object(qmm, 'ensure_qwen_profile', return_value=(False, 'native error')) as start:
            self.assertEqual(qmm._main(['--profile', '9b35', '--model-path', 'D:/Model Dir/model.gguf',
                                        '--server-exe', 'C:/Server Dir/llama-server.exe', '--port', '18081',
                                        '--context-tokens', '65536', '--max-output-tokens', '4096']), 1)
            self.assertEqual(qmm.MODEL_PROFILES['9b35']['path'], 'D:/Model Dir/model.gguf')
            self.assertEqual(qmm.QWEN_SERVER_EXE, 'C:/Server Dir/llama-server.exe')
            self.assertEqual(qmm.QWEN_BASE_URL, 'http://127.0.0.1:18081')
            self.assertEqual(start.call_args.kwargs['context_tokens'], 65536)
            self.assertEqual(start.call_args.kwargs['max_output_tokens'], 4096)

    def test_context_and_cache_overrides_reach_native_argument_list(self):
        with patch.dict(os.environ, {'JARVIS_QWEN_35_CONTEXT': '65536',
                                     'JARVIS_QWEN_GPU_LAYERS': '8',
                                     'JARVIS_QWEN_CACHE_TYPE_K': 'q8_0',
                                     'JARVIS_QWEN_CACHE_TYPE_V': 'q8_0'}):
            context = qmm._desired_context('9b35')
            args = qmm._server_command('9b35', qmm._startup_attempts('9b35', context)[0])
        for flag, value in [('-c', '65536'), ('-np', '1'), ('-ngl', '8'),
                            ('--cache-type-k', 'q8_0'), ('--cache-type-v', 'q8_0')]:
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn('--no-context-shift', args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
