from __future__ import annotations

import json
import tempfile
from pathlib import Path

import jarvis_v4264_repair as v


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def fake_g(tmp: Path):
    return {
        '_v35_is_noop_command': lambda cmd: not str(cmd or '').strip() or 'no test specified' in str(cmd).lower(),
        '_v36_release_identity': lambda: {'version':'V42.63.0'},
        '_progress': lambda callback, text=None, **fields: None,
        '_deterministic_acceptance_issues': lambda work, manifest: [
            {'file':'.','kind':'test_substrate','problem':'missing runner'}
        ] if not manifest['components'][0].get('test_command') else [],
        '_resume_validation_snapshot': lambda work, manifest, request, include_real=True: {
            'score': (4,25,1,7), 'compiler_score': (4,25,1), 'real_ok': None,
            'deterministic_issues':[{'file':'.','kind':'test_substrate','problem':'missing runner'}],
            'functional_issues':[
                {'file':'src/service.ts','kind':'functional_mock','problem':'mock'},
                {'file':'tests/application.integration.test.ts','kind':'functional_test_coverage','problem':'workflow'},
            ],
            'functional_issue_count': 2, 'fully_verified': False,
            'typescript_diagnostics': 0, 'typescript_syntax_diagnostics': 0,
        },
        '_resume_snapshot_summary': lambda snap: {'score': list(snap.get('score') or ())},
        '_v429_whole_project_audit': lambda root, request, manifest, run_components=True, progress_callback=None: {
            'clean': False,
            'issues': [
                {'file':'tests/application.integration.test.ts','kind':'functional_test_coverage','component':'react','problem':'workflow'},
                {'file':'.','kind':'test_substrate','problem':'missing runner'},
            ],
        },
        '_v429_write_audit': lambda root, payload: None,
        'JARVIS_DIR': str(tmp),
        'RESUME_SWEEPS': 3,
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root/'package.json').write_text(json.dumps({
            'scripts': {'test':'vitest run'},
            'devDependencies': {'vitest':'^2.0.0'},
        }), encoding='utf-8')
        manifest = {
            'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':''}],
            'files':[{'path':'tests/application.integration.test.ts','phase':'test'}],
        }
        g = fake_g(root)
        restored = v._sync_test_commands(g, root, manifest, {'react'})
        check(restored and manifest['components'][0]['test_command'] == 'npm test', 'package test script was not restored')

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root/'JARVIS_V35_COMPONENT_GRAPH.json').write_text(json.dumps({
            'components':[{'id':'react','root':'.','test_command':'npm exec -- vitest run'}]
        }), encoding='utf-8')
        manifest = {
            'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':''}],
            'files':[{'path':'tests/application.integration.test.ts','phase':'test'}],
        }
        g = fake_g(root)
        restored = v._sync_test_commands(g, root, manifest, {'react'})
        check(manifest['components'][0]['test_command'] == 'npm exec -- vitest run', 'persisted component command was not restored')

    normalized = v._normalize_intermediate_score({
        'score':(4,25,1,7), 'compiler_score':(4,25,1), 'real_ok':None,
        'deterministic_issues':[{'file':'.','kind':'test_substrate','problem':'runner'}],
        'functional_issues':[
            {'file':'src/service.ts','kind':'functional_mock','problem':'mock'},
            {'file':'tests/application.integration.test.ts','kind':'functional_test_coverage','problem':'workflow'},
        ],
        'functional_issue_count':2,
        'typescript_diagnostics':0, 'typescript_syntax_diagnostics':0,
    })
    check(normalized['compiler_score'] == (1,1,0), 'test-only debt did not normalize to post-compile phase')
    check(normalized['score'] == (1,1,0,2), 'functional count did not remain promotion tie-breaker')
    check(not normalized['fully_verified'], 'intermediate normalization weakened final acceptance')

    hard = v._normalize_intermediate_score({
        'score':(4,25,1,1), 'compiler_score':(4,25,1), 'real_ok':None,
        'deterministic_issues':[{'file':'src/app.ts','kind':'syntax_error','problem':'bad syntax'}],
        'functional_issues':[{'file':'src/service.ts','kind':'functional_mock','problem':'mock'}],
        'functional_issue_count':1,
    })
    check(hard['score'] == (4,25,1,1), 'hard compiler/source debt was incorrectly deferred')

    tests_only = v._normalize_intermediate_score({
        'score':(4,25,1,1), 'compiler_score':(4,25,1), 'real_ok':None,
        'deterministic_issues':[{'file':'.','kind':'test_substrate','problem':'runner'}],
        'functional_issues':[{'file':'tests/a.test.ts','kind':'functional_test_coverage','problem':'workflow'}],
        'functional_issue_count':1,
    })
    check(tests_only['score'] == (4,25,1,1), 'final test-only tail was incorrectly treated as complete/intermediate production progress')

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root/'package.json').write_text(json.dumps({'scripts':{'test':'vitest run'}}), encoding='utf-8')
        g = fake_g(root)
        v.install(g)
        manifest = {
            'components':[{'id':'react','root':'.','toolchain_adapter':'react','test_command':''}],
            'files':[{'path':'tests/application.integration.test.ts','phase':'test'}],
        }
        rows = g['_deterministic_acceptance_issues'](root, manifest)
        check(not any(r.get('kind') == 'test_substrate' for r in rows), 'false substrate row survived after command restoration')
        check(g['RESUME_SWEEPS'] >= 8, 'incremental one-owner resume budget was not expanded')
        check(g['_v36_release_identity']()['version'] == 'V42.64.0', 'release identity not updated')

    print('V42.64 durable functional promotion checks: PASS')


if __name__ == '__main__':
    main()
