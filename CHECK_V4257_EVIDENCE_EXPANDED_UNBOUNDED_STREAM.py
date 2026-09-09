from pathlib import Path
import json, shutil, tempfile, unittest
from unittest.mock import patch
import jarvis_v4251_repair as tx
import local_qwen_project as j
import multi_provider


class V4257EvidenceExpanded(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='v4257_'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_active_release_and_no_absolute_stream_wall(self):
        ident = j._v36_release_identity()
        self.assertEqual(ident['version'], 'V42.63.0')
        self.assertTrue(ident.get('evidence_proven_scope_expansion'))
        self.assertTrue(ident.get('forced_complete_source_on_scope_retry'))
        self.assertEqual(ident.get('active_stream_absolute_timeout_seconds'), 0)
        self.assertTrue(ident.get('dead_stream_idle_timeout_preserved'))
        self.assertEqual(j._qwen_profile_hard_timeout('repair'), 0)
        self.assertEqual(j._qwen_profile_hard_timeout('plan'), 0)
        self.assertEqual(multi_provider.QWEN_STREAM_HARD_TIMEOUT, 0)

    def test_provider_accepts_useful_stream_past_old_eight_minute_wall(self):
        class Response:
            status_code = 200
            text = ''
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def iter_lines(self, decode_unicode=True):
                yield 'data: {"choices":[{"delta":{"content":"OK"},"finish_reason":null}]}'
                yield 'data: [DONE]'
        with patch.object(multi_provider.requests, 'post', return_value=Response()), \
             patch.object(multi_provider, 'qwen_runtime_model_family', return_value='qwen35'), \
             patch.object(multi_provider.time, 'monotonic', side_effect=[0.0, 500.0, 500.0, 501.0, 501.0]):
            ok, raw = multi_provider.ask_qwen('return OK', hard_timeout=0, enable_thinking=False)
        self.assertTrue(ok, raw)
        self.assertEqual(str(raw), 'OK')
        self.assertGreaterEqual(raw.metadata.get('elapsed_seconds', 0), 500)

    def test_runtime_owner_is_retained_as_high_value_related_evidence(self):
        files = {
            'src/checkout.rs': 'pub async fn checkout(){ execute("UPDATE records SET x=1"); }\n',
            'src/main.rs': 'fn main(){ Builder::default().setup(init_db).manage(state).run(); }\n',
            'src/tools.rs': 'pub async fn tool(){ query_as("SELECT * FROM tools"); }\n',
            'src/noise.rs': 'pub fn checkout_label(){ let checkout = 1; }\n',
            'src/model.rs': 'pub struct Checkout { pub id: String }\n',
        }
        for rel, text in files.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding='utf-8')
        selected = list(tx.related_sources(self.tmp, 'src/checkout.rs', {}))
        self.assertIn('src/main.rs', selected)
        self.assertLess(selected.index('src/main.rs'), selected.index('src/noise.rs'))

    def test_rejected_related_file_becomes_forced_complete_source_on_retry(self):
        target = 'src/checkout.rs'
        runtime = 'src/main.rs'
        evidence = {
            target: 'pub fn checkout(){ let x = 1; }\n',
            runtime: 'fn main(){ let registered = false; }\n',
        }
        # Add enough secondary evidence that fitting must discard files, while
        # leaving room for the target + forced runtime owner.
        for i in range(7):
            evidence[f'src/noise_{i}.rs'] = ('pub fn noise_%d(){ let x = "%s"; }\n' % (i, 'x'*700))
        error = 'EVIDENCE_PROVEN_SCOPE_EXPANSION_REQUIRED: src/main.rs. retry with related file forced into source set: src/main.rs'
        forced = tx._requested_scope_expansions([error], evidence, target)
        self.assertEqual(forced, [runtime])
        ordered = tx._prioritized_evidence(evidence, target, forced)
        header = 'repair\n'
        # Large enough for target+runtime, too small for the whole evidence set.
        rendered, selected = tx.fit_source_prompt(header, ordered, target, 2400)
        self.assertIn(runtime, selected)
        self.assertIn(runtime, selected)
        self.assertIn('\"src/main.rs\": \"fn main', rendered)
        self.assertEqual(selected[target], evidence[target])

    def test_unproven_model_path_never_expands_scope(self):
        evidence = {'src/a.rs': 'fn a(){}\n', 'src/b.rs': 'fn b(){}\n'}
        errors = ['Duplicate or out-of-scope edit: src/invented.rs']
        self.assertEqual(tx._requested_scope_expansions(errors, evidence, 'src/a.rs'), [])

    def test_real_model_candidate_retry_forces_previous_related_scope_request(self):
        target = 'src/target.rs'
        runtime = 'src/runtime.rs'
        evidence = {target: 'pub fn target(){ let x = 1; }\n'}
        # Deliberately place the runtime owner last so the first constrained
        # prompt omits it; the adaptive retry must move it next to the target.
        for i in range(5):
            evidence[f'src/noise_{i}.rs'] = 'pub fn noise(){ let s = "%s"; }\n' % ('x' * 600)
        evidence[runtime] = 'pub fn runtime(){ let wired = false; }\n'
        for rel, text in evidence.items():
            p = self.tmp / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)

        prompts = []
        def model(_initial, *_args, **kwargs):
            rendered = kwargs['prompt_builder'](3600)
            prompts.append(rendered)
            return True, json.dumps({'edits':[{'file':runtime,'replacements':[
                {'search':'let wired = false','replace':'let wired = true'}]}]})

        g = {'_qwen_call': model, '_v4254_repair_evidence': lambda *a: {}}
        group = {'file':target, 'rows':[{'kind':'functional_bridge','problem':'wire runtime'}]}
        with self.assertRaises(ValueError) as first:
            tx._model_candidate(g, 'finish', {}, self.tmp, group, evidence, [], 1, None)
        self.assertIn('EVIDENCE_PROVEN_SCOPE_EXPANSION_REQUIRED', str(first.exception))
        self.assertNotIn('"src/runtime.rs": "pub fn runtime', prompts[0])

        changes = tx._model_candidate(g, 'finish', {}, self.tmp, group, evidence,
                                      [str(first.exception)], 2, None)
        self.assertIn(runtime, changes)
        self.assertIn('let wired = true', changes[runtime])
        self.assertIn('"src/runtime.rs": "pub fn runtime', prompts[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
