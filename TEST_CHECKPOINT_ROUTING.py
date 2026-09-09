import ast
import json
import re
import tempfile
import zipfile
from pathlib import Path

import local_qwen_project as qproj


def load_jarvis_attachment_helpers():
    source_path = Path(__file__).with_name('jarvis.py')
    source = source_path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    wanted_funcs = {
        '_inline_qwen_profile_marker',
        '_attached_file_markers',
        '_normalize_attached_project_instruction',
        '_first_attached_zip',
    }
    wanted_assigns = {'_JARVIS_ATTACHMENT_RE', '_JARVIS_PROFILE_RE'}
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if names & wanted_assigns:
                body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_funcs:
            body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {'re': re, 'Path': Path}
    exec(compile(module, str(source_path), 'exec'), ns)
    return source, ns


def main():
    source, ns = load_jarvis_attachment_helpers()
    root = Path(tempfile.mkdtemp(prefix='jarvis_checkpoint_route_'))
    zpath = root / 'stockpilot checkpoint.zip'
    with zipfile.ZipFile(zpath, 'w') as zf:
        zf.writestr('main.py', 'print("ok")\n')

    # Exact failure shape from the dashboard: profile + user text + attachment all on one line.
    command = (
        '[JARVIS_QWEN_PROFILE] 8b use qwen to finish this project '
        f'[JARVIS_ATTACHED_FILE] "{zpath}"'
    )
    clean_profile, profile = ns['_inline_qwen_profile_marker'](command)
    assert profile == '8b'
    clean, attached, seen = ns['_first_attached_zip'](clean_profile)
    assert seen is True
    assert attached == zpath.resolve()
    assert clean.lower() == 'finish this project'
    assert 'JARVIS_ATTACHED_FILE' not in clean
    assert 'JARVIS_QWEN_PROFILE' not in clean

    # Fail closed: a missing ZIP marker must not become a fresh generation request.
    missing = (
        'finish this project [JARVIS_ATTACHED_FILE] '
        + str(root / 'missing_checkpoint.zip')
    )
    clean_missing, attached_missing, seen_missing = ns['_first_attached_zip'](missing)
    assert seen_missing is True
    assert attached_missing is None
    assert clean_missing.lower() == 'finish this project'

    # Routing order: attached project handling must precede wants_project_zip/new generation.
    attach_route = source.index('if attached_zip is not None:')
    new_generation = source.index('if wants_project_zip(command):', attach_route)
    assert attach_route < new_generation
    assert 'zip_marker_seen and preattached_zip is None' in source

    # Resume-side sanitization independently protects checkpoint metadata from dashboard text.
    poisoned = (
        '[JARVIS_QWEN_PROFILE] 8b use qwen to finish this project '
        r'[JARVIS_ATTACHED_FILE] C:\Users\<USER>\Jarvis\chat_uploads\stockpilot_checkpoint.zip'
    )
    assert qproj._sanitize_resume_instruction(poisoned).lower() == 'finish this project'
    assert qproj._resume_request_is_generic(poisoned) is True

    # Architecture drift/source replacement is rejected for normal finish/repair resumes.
    before = root / 'before'
    after = root / 'after'
    before.mkdir(); after.mkdir()
    (before / 'main.py').write_text('print("ok")\n', encoding='utf-8')
    (before / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    (before / 'view.py').write_text('class View: pass\n', encoding='utf-8')
    (after / 'pom.xml').write_text('<project/>\n', encoding='utf-8')
    java_dir = after / 'src/main/java/com/stockpilot'
    java_dir.mkdir(parents=True)
    (java_dir / 'StockPredictor.java').write_text('class StockPredictor {}\n', encoding='utf-8')
    before_manifest = {'project_type': 'python', 'entrypoint': 'main.py'}
    after_manifest = {'project_type': 'java', 'entrypoint': 'src/main/java/com/stockpilot/StockPredictor.java'}
    regressions = qproj._resume_structure_regressions(
        before, before_manifest, after, after_manifest, 'finish this project', generic_resume=True,
    )
    assert any('architecture drifted from python to java' in x.lower() for x in regressions), regressions
    assert any('preserved only' in x.lower() for x in regressions), regressions

    # Explicit project-wide migrations are allowed to change architecture.
    allowed = qproj._resume_structure_regressions(
        before, before_manifest, after, after_manifest,
        'migrate this project from Python to Java', generic_resume=False,
    )
    assert allowed == [], allowed

    # If an old checkpoint contains poisoned generic metadata, a real historical generation request wins.
    seed_dir = root / 'seed'
    seed_dir.mkdir()
    (seed_dir / 'main.py').write_text('print("inventory")\n', encoding='utf-8')
    (seed_dir / qproj.RESUME_METADATA_FILE).write_text(json.dumps({
        'original_request': poisoned,
        'resume_count': 1,
        'manifest': {
            'project_name': 'StockPilot', 'project_type': 'python', 'entrypoint': 'main.py',
            'files': [{'path': 'main.py', 'purpose': 'entrypoint'}],
        },
    }), encoding='utf-8')
    (seed_dir / 'JARVIS_GENERATION.json').write_text(json.dumps({
        'request': 'Create the StockPilot Python inventory management desktop application.',
        'project_name': 'StockPilot', 'project_type': 'python', 'entrypoint': 'main.py',
    }), encoding='utf-8')
    seed = qproj._resume_seed_from_workspace(seed_dir, zpath, poisoned)
    assert seed['original_request'] == 'Create the StockPilot Python inventory management desktop application.'
    assert seed['effective_request'] == seed['original_request']
    assert seed['generic_resume'] is True

    # Integrated resume sweep: even a trial that claims acceptance and a better score cannot
    # replace a Python checkpoint with a Java repository during a generic finish request.
    guarded = root / 'guarded'
    guarded.mkdir()
    (guarded / 'main.py').write_text('print("stockpilot")\n', encoding='utf-8')
    (guarded / 'service.py').write_text('VALUE = 1\n', encoding='utf-8')
    guarded_manifest = {
        'project_name': 'StockPilot', 'project_type': 'python', 'entrypoint': 'main.py',
        'acceptance_criteria': ['existing app works'],
        'files': [{'path': 'main.py'}, {'path': 'service.py'}],
    }
    guard_job = root / 'guard_job'; guard_job.mkdir()
    old_accept = qproj._acceptance_repair_cycle
    old_snapshot = qproj._resume_validation_snapshot
    try:
        def fake_snapshot(work, manifest, request, include_real=True):
            files = qproj._existing_real_source_files(work)
            hashes = {}
            for rel in files:
                hashes[rel] = 'digest-' + rel
            is_java = any(rel.endswith('.java') for rel in files)
            return {
                'score': (0, 0, 0) if is_java else (2, 100, 1),
                'real_ok': True if is_java else None,
                'real_output': '', 'deterministic_issues': [], 'stable_issue_keys': [],
                'issue_files': [], 'hashes': hashes, 'weighted_issues': 0 if is_java else 100,
                'issue_count': 0 if is_java else 1,
            }

        def fake_accept(request, manifest, trial, progress=None):
            trial = Path(trial)
            for rel in list(qproj._existing_real_source_files(trial)):
                try:
                    (trial / rel).unlink()
                except Exception:
                    pass
            java = trial / 'src/main/java/com/stockpilot/StockPredictor.java'
            java.parent.mkdir(parents=True, exist_ok=True)
            java.write_text('class StockPredictor {}\n', encoding='utf-8')
            (trial / 'pom.xml').write_text('<project/>\n', encoding='utf-8')
            manifest.clear(); manifest.update({
                'project_name': 'StockPilot', 'project_type': 'java',
                'entrypoint': 'src/main/java/com/stockpilot/StockPredictor.java',
                'files': [{'path': 'src/main/java/com/stockpilot/StockPredictor.java'}],
            })
            return True, []

        qproj._resume_validation_snapshot = fake_snapshot
        qproj._acceptance_repair_cycle = fake_accept
        ok, _issues, _snap = qproj._run_resume_sweeps(
            'finish this project', guarded_manifest, guarded, guard_job,
            generic_resume=True, max_sweeps=1,
        )
        assert ok is False
        assert (guarded / 'main.py').exists(), 'Python checkpoint was replaced despite architecture guard'
        assert not (guarded / 'pom.xml').exists(), 'Java trial was incorrectly promoted'
        assert guarded_manifest['project_type'] == 'python'
    finally:
        qproj._acceptance_repair_cycle = old_accept
        qproj._resume_validation_snapshot = old_snapshot

    print('Checkpoint routing / architecture-lock regression checks passed.')


if __name__ == '__main__':
    main()

