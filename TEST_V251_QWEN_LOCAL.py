import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import multi_provider
import local_qwen_project


def test_provider_parser():
    assert multi_provider.extract_provider_request("use qwen to explain DNS") == ("qwen", "explain DNS")
    assert multi_provider.extract_provider_request("qwen: write a hello world") == ("qwen", "write a hello world")


def test_qwen_project_zip():
    obj = {
        "project_name": "calculator",
        "summary": "tiny calculator",
        "project_type": "python",
        "entrypoint": "calculator.py",
        "run_command": "python calculator.py",
        "acceptance_criteria": ["calculator source exists"],
    }
    candidates = [
        ("calculator.py", "def add(a, b):\n    return a + b\n"),
        ("README.md", "# Calculator\nRun calculator.py\n"),
    ]

    def accepted(request, work, source_zip, criteria, progress_callback=None, max_passes=None, base_manifest=None):
        files = local_qwen_project._existing_project_text_files(work)
        return {
            "verified": True,
            "manifest": base_manifest or {},
            "changed": files,
            "runs": [],
            "audits": [],
            "audit": {"complete": True, "missing": []},
            "checks": {"complete": True, "issues": []},
            "files": files,
        }

    with tempfile.TemporaryDirectory() as td:
        original_dir = local_qwen_project.GENERATED_DIR
        local_qwen_project.GENERATED_DIR = Path(td)
        try:
            with patch.object(local_qwen_project, "qwen_status", return_value=True), patch.object(
                local_qwen_project, "_direct_new_project_bootstrap", return_value=(True, obj, candidates, "")
            ), patch.object(local_qwen_project, "_agent_acceptance_loop", side_effect=accepted):
                ok, detail, zip_path = local_qwen_project.generate_project_zip(
                    "Make a calculator and give me a zip"
                )
            assert ok, detail
            assert zip_path and zip_path.exists()
            assert "verified project ZIP" in detail
            import zipfile
            with zipfile.ZipFile(zip_path) as archive:
                assert "calculator.py" in archive.namelist()
                assert "README.md" in archive.namelist()
        finally:
            local_qwen_project.GENERATED_DIR = original_dir


def test_dashboard_dropdown_order():
    html = (Path(__file__).parent / "ui" / "index.html").read_text(encoding="utf-8")
    auto_pos = html.index('value="auto"')
    qwen_pos = html.index('value="qwen"')
    nvidia_pos = html.index('value="nvidia"')
    assert auto_pos < qwen_pos < nvidia_pos


if __name__ == "__main__":
    test_provider_parser()
    test_qwen_project_zip()
    test_dashboard_dropdown_order()
    print("V2.51+ Qwen local integration tests passed.")
