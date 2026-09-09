from pathlib import Path
import json
import tempfile
import zipfile

import local_qwen_project as lq
from multi_provider import ProjectTools


def test_projecttools_move_delete():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / 'one.txt').write_text('one', encoding='utf-8')
        (root / 'keep.txt').write_text('keep', encoding='utf-8')
        tools = ProjectTools(root)
        moved = tools.move_file('one.txt', 'sub/two.txt')
        assert moved.get('ok'), moved
        assert not (root / 'one.txt').exists()
        assert (root / 'sub/two.txt').read_text(encoding='utf-8') == 'one'
        deleted = tools.delete_file('sub/two.txt')
        assert deleted.get('ok'), deleted
        assert not (root / 'sub/two.txt').exists()
        assert (root / 'keep.txt').exists()


def test_tool_agent_existing_zip():
    original = {
        name: getattr(lq, name)
        for name in ('qwen_status', '_derive_existing_project_criteria', '_fast_audit_project', '_qwen_call')
    }
    try:
        lq.qwen_status = lambda timeout=2.0: True
        lq._derive_existing_project_criteria = lambda request, progress_callback=None: ['app prints goodbye']

        def fake_audit(request, manifest, criteria, work, completed, progress_callback=None):
            text = (Path(work) / 'app.py').read_text(encoding='utf-8')
            good = 'goodbye' in text
            return {
                'complete': good,
                'missing': [] if good else ['app.py still prints hello'],
                'repairs': [],
                'notes': [],
            }

        lq._fast_audit_project = fake_audit
        actions = iter([
            {'action': 'tool', 'tool': 'read_file', 'args': {'path': 'app.py'}, 'memory': 'Inspect app.py.'},
            {'action': 'tool', 'tool': 'replace_text', 'args': {'path': 'app.py', 'old': 'hello', 'new': 'goodbye', 'count': 1}, 'memory': 'Greeting replaced; validate.'},
            {'action': 'tool', 'tool': 'run_validation', 'args': {'command': 'python -m py_compile app.py'}, 'memory': 'Syntax validation requested.'},
            {'action': 'finish', 'summary': 'Updated greeting and validated Python syntax.', 'memory': 'Done.'},
        ])

        def fake_call(prompt, progress_callback=None, stage='Generating', profile=None, max_tokens=None):
            if stage == 'Qwen coding agent':
                return True, json.dumps(next(actions))
            return True, '{}'

        lq._qwen_call = fake_call

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td / 'sample.zip'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('app.py', 'print("hello")\n')
                archive.writestr('README.md', '# Demo\n')

            ok, detail, output = lq.analyze_and_edit_project_zip(
                'Change the app greeting from hello to goodbye', source, max_audit_passes=1
            )
            assert ok, detail
            assert output and Path(output).exists()
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                assert 'app.py' in names
                assert 'README.md' in names
                assert b'goodbye' in archive.read('app.py')
                assert not any('.jarvis_backups' in name for name in names)
    finally:
        for name, value in original.items():
            setattr(lq, name, value)


def test_warning_zip_keeps_download_marker():
    source = Path('jarvis.py').read_text(encoding='utf-8')
    assert 'Qwen returned a project ZIP with verification warnings.' in source
    assert 'DOWNLOAD_URL: /downloads/{zip_path.name}' in source
    assert 'complete_with_warnings' in source


if __name__ == '__main__':
    test_projecttools_move_delete()
    test_tool_agent_existing_zip()
    test_warning_zip_keeps_download_marker()
    print('PASS: v2.71 local Qwen tool-agent ZIP workflow regression checks passed.')
