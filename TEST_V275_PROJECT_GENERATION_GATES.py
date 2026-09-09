from pathlib import Path
import json
import tempfile
import zipfile

import local_qwen_project as lq
from multi_provider import ProjectTools


def test_empty_workspace_is_authoritative():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        tools = ProjectTools(root)
        assert tools.root == root.resolve()
        assert tools.list_files('.') == {'files': []}


def test_truncated_bootstrap_salvages_only_complete_files():
    raw = (
        '{"project_name":"demo","entrypoint":"main.py","files":['
        '{"path":"requirements.txt","content":"requests\\n"},'
        '{"path":"main.py","content":"print(123)\\nexcept Exception as e: self'
    )
    obj, candidates = lq._parse_direct_project_bootstrap(raw)
    assert obj.get('project_name') == 'demo', obj
    assert obj.get('entrypoint') == 'main.py', obj
    assert [x[0] for x in candidates] == ['requirements.txt'], candidates
    declared = [x.get('path') for x in obj.get('files', []) if isinstance(x, dict)]
    assert 'requirements.txt' in declared and 'main.py' in declared, declared


def test_finish_without_changes_is_rejected_until_real_write():
    original = lq._qwen_call
    try:
        actions = iter([
            {'action': 'finish', 'summary': 'done', 'memory': 'done'},
            {'action': 'tool', 'tool': 'workspace_info', 'args': {}, 'memory': 'workspace checked'},
            {'action': 'tool', 'tool': 'write_file', 'args': {'path': 'main.py', 'content': 'print("ok")\n'}, 'memory': 'created main'},
            {'action': 'finish', 'summary': 'created and validated main.py', 'memory': 'done'},
        ])

        def fake_call(prompt, progress_callback=None, stage='Generating', profile=None, max_tokens=None):
            assert stage == 'Qwen coding agent'
            return True, json.dumps(next(actions))

        lq._qwen_call = fake_call
        with tempfile.TemporaryDirectory() as td:
            result = lq._run_qwen_project_tool_agent(
                'Create a hello world Python app', Path(td), criteria=['main.py exists'], max_turns=6
            )
            assert result.get('complete'), result
            assert result.get('changed') == ['main.py'], result
            assert (Path(td) / 'main.py').exists()
            assert result.get('finish_attempts') == 2, result
    finally:
        lq._qwen_call = original


def test_static_gate_requires_manifest_files_and_entrypoint():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / 'requirements.txt').write_text('requests\n', encoding='utf-8')
        manifest = {
            'entrypoint': 'main.py',
            'files': [{'path': 'main.py'}, {'path': 'requirements.txt'}],
        }
        checks = lq._static_project_checks(root, ['requirements.txt'], manifest)
        assert not checks['complete'], checks
        assert 'Required file does not exist: main.py' in checks['issues'], checks
        assert 'Declared entrypoint does not exist: main.py' in checks['issues'], checks



def test_bootstrap_required_files_survive_reindex():
    base = {
        'project_name': 'demo',
        'entrypoint': 'main.py',
        'files': [{'path': 'main.py'}, {'path': 'requirements.txt'}],
    }
    current = lq._bootstrap_manifest_from_files(
        'Create demo', base, [('main.py', '')]
    )
    merged = lq._merge_bootstrap_expectations(current, base)
    required = lq._manifest_required_paths(merged)
    assert required == ['main.py', 'requirements.txt'], required
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / 'main.py').write_text('print("ok")\n', encoding='utf-8')
        checks = lq._static_project_checks(root, ['main.py'], merged)
        assert not checks['complete'], checks
        assert 'Required file does not exist: requirements.txt' in checks['issues'], checks

def test_new_project_recovers_from_empty_bootstrap_with_tool_write():
    originals = {
        'qwen_status': lq.qwen_status,
        '_direct_new_project_bootstrap': lq._direct_new_project_bootstrap,
        '_qwen_call': lq._qwen_call,
        '_fast_audit_project': lq._fast_audit_project,
    }
    try:
        lq.qwen_status = lambda timeout=2.0: True
        lq._direct_new_project_bootstrap = lambda *a, **k: (
            False,
            {'project_name': 'recovery-demo', 'entrypoint': 'main.py', 'files': [{'path': 'main.py'}]},
            [],
            '{"project_name":"recovery-demo","entrypoint":"main.py","files":[{"path":"main.py","content":"print(1)',
        )
        actions = iter([
            {'action': 'tool', 'tool': 'workspace_info', 'args': {}, 'memory': 'empty workspace confirmed'},
            {'action': 'tool', 'tool': 'write_file', 'args': {'path': 'main.py', 'content': 'print("recovered")\n'}, 'memory': 'main created'},
            {'action': 'finish', 'summary': 'Created runnable main.py', 'memory': 'done'},
        ])

        def fake_call(prompt, progress_callback=None, stage='Generating', profile=None, max_tokens=None):
            if stage == 'Qwen coding agent':
                return True, json.dumps(next(actions))
            return True, '{}'

        def fake_audit(request, manifest, criteria, work, completed, progress_callback=None):
            good = (Path(work) / 'main.py').is_file()
            return {'complete': good, 'missing': [] if good else ['main.py missing'], 'repairs': [], 'notes': []}

        lq._qwen_call = fake_call
        lq._fast_audit_project = fake_audit
        ok, detail, output = lq.generate_project_zip(
            'Create a tiny hello world Python program', max_files=5, max_audit_passes=1
        )
        assert ok, detail
        assert output and Path(output).exists(), output
        with zipfile.ZipFile(output) as zf:
            assert 'main.py' in zf.namelist(), zf.namelist()
            assert b'recovered' in zf.read('main.py')
            report = json.loads(zf.read('JARVIS_GENERATION.json'))
            assert report['verified'] is True
            assert report['workspace_change_evidence']['agent_changed_count'] == 1
            assert report['workspace_change_evidence']['final_project_file_count'] >= 1
    finally:
        for name, value in originals.items():
            setattr(lq, name, value)


if __name__ == '__main__':
    test_empty_workspace_is_authoritative()
    test_truncated_bootstrap_salvages_only_complete_files()
    test_finish_without_changes_is_rejected_until_real_write()
    test_static_gate_requires_manifest_files_and_entrypoint()
    test_bootstrap_required_files_survive_reindex()
    test_new_project_recovers_from_empty_bootstrap_with_tool_write()
    print('PASS: v2.75 project generation materialization / anti-hallucination gates')
