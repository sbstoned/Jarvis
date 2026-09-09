import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import local_qwen_project


def test_generated_python_project_has_runner_and_exe_builder():
    responses = iter([
        (True, json.dumps({
            "project_name": "calculator",
            "summary": "working calculator",
            "project_type": "python",
            "entrypoint": "src/calculator.py",
            "run_command": "python src/calculator.py",
            "acceptance_criteria": ["calculator adds numbers"],
            "files": [
                {"path": "src/calculator.py", "purpose": "calculator"},
                {"path": "README.md", "purpose": "readme"},
            ],
        })),
        (True, "def add(a,b):\n    return a+b\n\nif __name__ == '__main__':\n    print(add(2,3))\n"),
        (True, "# Calculator\n"),
    ])
    complete_audit = {"complete": True, "missing": [], "repairs": [], "notes": []}
    with tempfile.TemporaryDirectory() as td:
        old = local_qwen_project.GENERATED_DIR
        local_qwen_project.GENERATED_DIR = Path(td)
        try:
            with patch.object(local_qwen_project, "qwen_status", return_value=True), patch.object(
                local_qwen_project, "ask_qwen", side_effect=lambda *a, **k: next(responses)
            ), patch.object(local_qwen_project, "_audit_project", return_value=complete_audit):
                ok, detail, zpath = local_qwen_project.generate_project_zip(
                    "make a calculator and give me a zip"
                )
            assert ok, detail
            assert zpath and zpath.exists()
            with zipfile.ZipFile(zpath) as zf:
                names = set(zf.namelist())
                assert "RUN_PROJECT.bat" in names
                assert "BUILD_EXE.bat" in names
                assert "JARVIS_RUN_INSTRUCTIONS.txt" in names
                assert "JARVIS_TEST_RESULTS.txt" in names
                assert "JARVIS_FEATURE_AUDIT.json" in names
                info = json.loads(zf.read("JARVIS_GENERATION.json"))
                assert info["entrypoint"] == "src/calculator.py"
                assert info["validation_failures"] == []
        finally:
            local_qwen_project.GENERATED_DIR = old


def test_project_route_is_background_and_tts_cleanup_exists():
    source = (Path(__file__).parent / "jarvis.py").read_text(encoding="utf-8")
    assert "def _qwen_project_worker(job_id):" in source
    assert "def _start_qwen_project_job(command):" in source
    assert "Qwen Project Agent" in source
    assert "qwen_project_busy.is_set()" in source
    assert "JarvisQwenProjectDone" in source
    assert 'update_live_state("LISTENING" if FOLLOW_UP_MODE else "STANDBY"' in source


if __name__ == "__main__":
    test_generated_python_project_has_runner_and_exe_builder()
    test_project_route_is_background_and_tts_cleanup_exists()
    print("PASS: v2.53+ Qwen project runner + background/speech regression checks passed.")
