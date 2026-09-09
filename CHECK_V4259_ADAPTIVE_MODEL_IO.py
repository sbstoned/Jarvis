import unittest
from unittest.mock import patch

import jarvis_v4259_repair as v
import jarvis_v4251_repair as tx


class FakeResponse(str):
    def __new__(cls, text, metadata=None, partial_text=''):
        obj = super().__new__(cls, text)
        obj.metadata = dict(metadata or {})
        obj.partial_text = partial_text
        return obj


def prompt_for(owners=4, findings=4):
    files = [f'src/f{i}.ts' for i in range(owners)]
    rows = [{'file': files[i % owners], 'kind': 'functional_mock', 'problem': f'p{i}'} for i in range(findings)]
    return (
        'V42.59 CONNECTED FUNCTIONAL TRANSACTION.\n'
        'ISSUE OWNER FILES: ' + __import__('json').dumps(files) + '\n'
        'CURRENT CONTRACT FINDINGS:\n' + __import__('json').dumps(rows) + '\n'
        'AUTHORIZED VALIDATOR LOCATORS BY ISSUE OWNER:\n{}\n'
    )


class V4259AdaptiveModelIO(unittest.TestCase):

    def test_hauhau_27b_native_context_is_262144_but_runtime_default_is_hardware_fit(self):
        import qwen_model_manager as qmm
        from pathlib import Path
        self.assertEqual(qmm.MODEL_PROFILES['27b38q2'].get('native_context'), 262144)
        self.assertEqual(qmm._desired_context('27b38q2'), 40960)
        launcher = Path(__file__).with_name('START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
        self.assertIn("'--context-tokens', [string]$ContextTokens", launcher)
        self.assertIn("'--max-output-tokens', [string]$MaxOutputTokens", launcher)
        args = qmm._server_command('27b38q2', {'context': 40960, 'gpu_layers': 'all'})
        self.assertEqual(args[args.index('-c') + 1], '40960')
        self.assertEqual(args[args.index('-n') + 1], '20480')

    def test_hauhau_27b_6144_live_slot_is_not_accepted_as_matching_runtime(self):
        import qwen_model_manager as qmm
        with patch.object(qmm, '_health', return_value=True), \
             patch.object(qmm, 'active_profile', return_value='27b38q2'), \
             patch.object(qmm, '_runtime_context_tokens', return_value=6144), \
             patch.object(qmm, '_windows_server_commandline', return_value='llama-server.exe -np 1 --no-context-shift -c 6144'):
            self.assertFalse(qmm._runtime_matches('27b38q2'))


    def test_qwen_manager_prefers_target_slot_n_ctx_over_smaller_mtp_metadata(self):
        import qwen_model_manager as qmm
        response = type('R', (), {
            'status_code': 200,
            'json': lambda self: {
                'default_generation_settings': {'n_ctx': 262144, 'params': {'n_predict': 65536}},
                'speculative': {'draft': {'n_ctx': 6144}},
                'model_meta': {'context_length': 262144},
            },
        })()
        with patch.object(qmm.requests, 'get', return_value=response):
            self.assertEqual(qmm._runtime_context_tokens(), 262144)

    def test_provider_prefers_target_slot_n_ctx_over_smaller_mtp_metadata(self):
        import multi_provider as mp
        response = type('R', (), {
            'status_code': 200,
            'json': lambda self: {
                'default_generation_settings': {'n_ctx': 262144, 'params': {'n_predict': 65536}},
                'mtp': {'draft_context': {'n_ctx': 6144}},
            },
        })()
        mp._QWEN_RUNTIME_CONTEXT_CACHE.update({'time': 0.0, 'tokens': 0, 'profile_key': ''})
        with patch.object(mp.requests, 'get', return_value=response), \
             patch.object(mp, '_read_json_file', return_value={
                 'profile': '27b38q2', 'model_family': 'qwen3.8',
                 'context': 262144, 'generated_at': 'test',
             }):
            self.assertEqual(mp.qwen_runtime_context_tokens(cache_seconds=0), 262144)

    def test_qwen_manager_still_reports_real_small_target_slot_if_server_is_actually_small(self):
        import qwen_model_manager as qmm
        response = type('R', (), {
            'status_code': 200,
            'json': lambda self: {
                'default_generation_settings': {'n_ctx': 6144},
                'model_meta': {'context_length': 262144},
            },
        })()
        with patch.object(qmm.requests, 'get', return_value=response):
            self.assertEqual(qmm._runtime_context_tokens(), 6144)

    def test_27b_four_owner_budget_is_far_above_old_6144_ceiling(self):
        g = {'_v426_route_for_call': lambda *a: ('27b38q2', 'manual strict model lock')}
        budget, target, owners, findings = v._adaptive_functional_output(
            g, prompt_for(4, 4), 'V42.59 functional transaction 1: a + b + c + d', 'repair', 9000)
        self.assertEqual(target, '27b38q2')
        self.assertEqual((owners, findings), (4, 4))
        self.assertGreaterEqual(budget, min(24576, v.CAP_27B))
        self.assertLessEqual(budget, v.CAP_27B)

    def test_9b_budget_is_adaptive_but_bounded_separately(self):
        g = {'_v426_route_for_call': lambda *a: ('9b35', 'manual strict model lock')}
        budget, target, owners, _ = v._adaptive_functional_output(
            g, prompt_for(4, 4), 'V42.59 functional transaction 1: a + b + c + d', 'repair', 9000)
        self.assertEqual(target, '9b35')
        self.assertEqual(owners, 4)
        self.assertGreater(budget, 9000)
        self.assertLessEqual(budget, v.CAP_9B)

    def test_install_expands_related_source_ceiling_without_forcing_context(self):
        calls = []
        def base(prompt, callback=None, stage='Generating', profile='chat', **kwargs):
            calls.append((prompt, stage, profile, kwargs))
            return True, FakeResponse('{"edits":[]}', {'finish_reason':'stop'})
        g = {
            '_v36_release_identity': lambda: {'version':'V42.58.0'},
            '_qwen_call': base,
            '_v426_route_for_call': lambda *a: ('27b38q2','manual strict model lock'),
            '_v426_active_profile': lambda: '27b38q2',
            '_progress': lambda *a, **k: None,
            'QWEN38_WORKING_CONTEXT_REPAIR': 49152,
            'QWEN38_WORKING_CONTEXT_GENERATE': 32768,
            'QWEN38_WORKING_CONTEXT_PLAN': 49152,
            'QWEN38_WORKING_CONTEXT_AUDIT': 32768,
            'QWEN38_WORKING_CONTEXT_MAX': 65536,
            'QWEN35_WORKING_CONTEXT_REPAIR': 49152,
            'QWEN35_WORKING_CONTEXT_GENERATE': 32768,
            'QWEN35_WORKING_CONTEXT_PLAN': 32768,
            'QWEN35_WORKING_CONTEXT_AUDIT': 32768,
            'QWEN35_WORKING_CONTEXT_MAX': 98304,
        }
        old = tx.MAX_CHARS
        try:
            v.install(g)
            self.assertGreaterEqual(tx.MAX_CHARS, v.RELATED_SOURCE_CHARS)
            ident = g['_v36_release_identity']()
            self.assertEqual(ident['version'], 'V' + v.VERSION)
            self.assertTrue(ident['live_context_is_authoritative'])
            self.assertTrue(ident['does_not_force_unavailable_context'])
        finally:
            tx.MAX_CHARS = old

    def test_functional_transaction_overrides_legacy_9000_request_for_27b(self):
        calls = []
        def base(prompt, callback=None, stage='Generating', profile='chat', **kwargs):
            calls.append(kwargs)
            return True, FakeResponse('{"edits":[{"file":"src/f0.ts","replacements":[]}]}', {'finish_reason':'stop'})
        g = {
            '_v36_release_identity': lambda: {}, '_qwen_call': base,
            '_v426_route_for_call': lambda *a: ('27b38q2','manual strict model lock'),
            '_v426_active_profile': lambda: '27b38q2', '_progress': lambda *a, **k: None,
        }
        old = tx.MAX_CHARS
        try:
            v.install(g)
            g['_qwen_call'](prompt_for(4,4), None, 'V42.59 functional transaction 1: a + b + c + d',
                            profile='repair', max_tokens=9000, prompt_builder=lambda n: prompt_for(4,4))
            self.assertGreater(calls[0]['max_tokens'], 9000)
            self.assertIn('V42.59 ADAPTIVE EMISSION POLICY', calls[0]['prompt_builder'](100000))
        finally:
            tx.MAX_CHARS = old

    def test_length_response_retries_with_larger_budget_and_smaller_complete_instruction(self):
        calls = []
        partial = '{"edits":[{"file":"src/f0.ts","replacements":[{"search":"old","replace":"new"}]},{"file":"src/f1.ts"'
        def base(prompt, callback=None, stage='Generating', profile='chat', **kwargs):
            calls.append((prompt, kwargs))
            if len(calls) == 1:
                return False, FakeResponse('output limit', {'finish_reason':'length','max_tokens':kwargs.get('max_tokens')}, partial)
            return True, FakeResponse('{"edits":[{"file":"src/f0.ts","replacements":[{"search":"old","replace":"new"}]}]}', {'finish_reason':'stop'})
        g = {
            '_v36_release_identity': lambda: {}, '_qwen_call': base,
            '_v426_route_for_call': lambda *a: ('27b38q2','manual strict model lock'),
            '_v426_active_profile': lambda: '27b38q2', '_progress': lambda *a, **k: None,
        }
        old = tx.MAX_CHARS
        try:
            v.install(g)
            ok, raw = g['_qwen_call'](prompt_for(4,4), None, 'V42.59 functional transaction 1: a + b + c + d',
                                      profile='repair', max_tokens=9000, prompt_builder=lambda n: prompt_for(4,4))
            self.assertTrue(ok)
            self.assertEqual(len(calls), 2)
            self.assertGreaterEqual(calls[1][1]['max_tokens'], calls[0][1]['max_tokens'])
            self.assertLessEqual(calls[1][1]['max_tokens'], v.CAP_27B)
            rendered = calls[1][1]['prompt_builder'](120000)
            self.assertIn('V42.59 TRUNCATION RECOVERY', rendered)
            self.assertIn('1-2 issue-owner files', rendered)
            self.assertEqual(raw.metadata.get('v4259_length_retries'), 1)
        finally:
            tx.MAX_CHARS = old

    def test_nonfunctional_calls_preserve_existing_budget(self):
        calls = []
        def base(prompt, callback=None, stage='Generating', profile='chat', **kwargs):
            calls.append(kwargs)
            return True, FakeResponse('ok', {'finish_reason':'stop'})
        g = {
            '_v36_release_identity': lambda: {}, '_qwen_call': base,
            '_v426_route_for_call': lambda *a: ('27b38q2','manual strict model lock'),
            '_v426_active_profile': lambda: '27b38q2', '_progress': lambda *a, **k: None,
        }
        old = tx.MAX_CHARS
        try:
            v.install(g)
            g['_qwen_call']('plan', None, 'architecture plan', profile='plan', max_tokens=2048)
            self.assertEqual(calls[0]['max_tokens'], 2048)
        finally:
            tx.MAX_CHARS = old


if __name__ == '__main__':
    unittest.main(verbosity=2)
