import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import local_qwen_project as qproj


def main():
    root = Path(tempfile.mkdtemp(prefix="jarvis_resume_test_"))
    old_generated = qproj.GENERATED_DIR
    old_accept = qproj._acceptance_repair_cycle
    old_snapshot = qproj._resume_validation_snapshot
    try:
        qproj.GENERATED_DIR = root / "generated"
        qproj.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        # 1) V27 checkpoint packaging preserves credential/config assets so later resume passes still have them.
        work = root / "project"
        work.mkdir()
        (work / "main.py").write_text("def value():\n    pass\n", encoding="utf-8")
        (work / "ai_providers.env").write_text("OPENAI_API_KEY=LOCAL_TEST_VALUE\n", encoding="utf-8")
        (work / ".env.production").write_text("APP_TOKEN=LOCAL_TEST_VALUE\n", encoding="utf-8")
        (work / "credentials.json").write_text('{"client":"local-test"}\n', encoding="utf-8")
        (work / "private.pem").write_text("-----BEGIN TEST KEY-----\nabc\n-----END TEST KEY-----\n", encoding="utf-8")
        (work / "client.p12").write_bytes(b"\x00PKCS12TEST\x01")
        manifest = {
            "project_name": "resume-demo",
            "project_type": "python",
            "entrypoint": "main.py",
            "acceptance_criteria": ["value works"],
            "files": [{"path": "main.py", "purpose": "entrypoint", "exports": ["value"]}],
        }
        snap = qproj._resume_validation_snapshot(work, manifest, "finish", include_real=False)
        assert snap["issue_count"] >= 1
        checkpoint, _ = qproj._package_resume_checkpoint_zip(
            work, manifest, "build the original app", "finish this project",
            ["main.py is incomplete"], resume_count=1, snapshot=snap, stamp="20990101_000000",
        )
        with zipfile.ZipFile(checkpoint) as zf:
            names = set(zf.namelist())
            assert "main.py" in names
            assert ".jarvis_resume.json" in names
            assert "ai_providers.env" in names
            assert ".env.production" in names
            assert "credentials.json" in names
            assert "private.pem" in names
            assert "client.p12" in names
            metadata = json.loads(zf.read(".jarvis_resume.json"))
            assert metadata["original_request"] == "build the original app"
            assert metadata["status"] == "checkpoint_incomplete"

        # 2) A generic finish request recovers the original request and increments resume_count.
        extracted = root / "extracted"
        extracted.mkdir()
        qproj._safe_extract_zip(checkpoint, extracted)
        seed = qproj._resume_seed_from_workspace(extracted, checkpoint, "finish this project")
        assert seed["effective_request"] == "build the original app"
        assert seed["resume_count"] == 2
        visible = qproj._existing_project_text_files(extracted)
        assert ".jarvis_resume.json" not in visible
        assert "ai_providers.env" in visible
        assert ".env.production" in visible
        assert "credentials.json" in visible
        assert "private.pem" in visible
        assert "client.p12" not in visible  # binary asset is preserved, but not dumped into text context
        binary_inventory = qproj._qwen_binary_sensitive_asset_inventory(extracted)
        assert "client.p12" in binary_inventory

        # 3) Monotonic promotion: first sweep improves code but is still incomplete;
        # second sweep starts from that improved file and reaches acceptance.
        work2 = root / "monotonic"
        work2.mkdir()
        (work2 / "main.py").write_text("def value():\n    pass\n", encoding="utf-8")
        manifest2 = {
            "project_name": "monotonic-demo",
            "project_type": "python",
            "entrypoint": "main.py",
            "acceptance_criteria": ["value works"],
            "files": [{"path": "main.py", "purpose": "entrypoint", "exports": ["value"]}],
        }
        job_root = root / "resume_job"
        job_root.mkdir()
        calls = {"n": 0}

        def fake_accept(_request, _manifest, trial, _progress=None):
            calls["n"] += 1
            path = Path(trial) / "main.py"
            if calls["n"] == 1:
                path.write_text("def value():\n    return 1\n", encoding="utf-8")
                return False, ["one later validation remains"]
            assert "return 1" in path.read_text(encoding="utf-8")
            return True, []

        qproj._acceptance_repair_cycle = fake_accept
        qproj._resume_validation_snapshot = (
            lambda w, m, r, include_real=True: old_snapshot(w, m, r, include_real=False)
        )
        ok, issues, _best = qproj._run_resume_sweeps(
            "finish", manifest2, work2, job_root, generic_resume=True, max_sweeps=2
        )
        assert ok is True, issues
        assert "return 1" in (work2 / "main.py").read_text(encoding="utf-8")

        # 4) Rollback: a bad trial that corrupts clean code must never replace the best checkpoint.
        work3 = root / "rollback"
        work3.mkdir()
        original = 'print("ok")\n'
        (work3 / "main.py").write_text(original, encoding="utf-8")
        manifest3 = {
            "project_name": "rollback-demo",
            "project_type": "python",
            "entrypoint": "main.py",
            "acceptance_criteria": ["runs"],
            "files": [{"path": "main.py", "purpose": "entrypoint", "exports": []}],
        }
        job3 = root / "rollback_job"
        job3.mkdir()

        def bad_accept(_request, _manifest, trial, _progress=None):
            (Path(trial) / "main.py").write_text("def broken(:\n", encoding="utf-8")
            return False, ["bad trial"]

        qproj._acceptance_repair_cycle = bad_accept
        ok, _issues, _best = qproj._run_resume_sweeps(
            "finish", manifest3, work3, job3, generic_resume=True, max_sweeps=1
        )
        assert ok is False
        assert (work3 / "main.py").read_text(encoding="utf-8") == original

        print("Resume/checkpoint regression checks passed.")
    finally:
        qproj.GENERATED_DIR = old_generated
        qproj._acceptance_repair_cycle = old_accept
        qproj._resume_validation_snapshot = old_snapshot
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
