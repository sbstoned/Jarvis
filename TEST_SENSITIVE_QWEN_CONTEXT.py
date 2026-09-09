import tempfile
import shutil
import zipfile
from pathlib import Path

import local_qwen_project as qproj
import multi_provider as mp


def main():
    root = Path(tempfile.mkdtemp(prefix="jarvis_sensitive_context_"))
    old_generated = qproj.GENERATED_DIR
    try:
        qproj.GENERATED_DIR = root / "generated"
        qproj.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        work = root / "project"
        work.mkdir()

        (work / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (work / ".env").write_text("TOKEN=alpha\n", encoding="utf-8")
        (work / ".env.production").write_text("TOKEN2=beta\n", encoding="utf-8")
        (work / "ai_providers.env").write_text("OPENAI_API_KEY=gamma\n", encoding="utf-8")
        (work / "credentials.json").write_text('{"client":"delta"}\n', encoding="utf-8")
        (work / "secrets.json").write_text('{"secret":"epsilon"}\n', encoding="utf-8")
        (work / "client.pem").write_text("-----BEGIN TEST KEY-----\nzeta\n-----END TEST KEY-----\n", encoding="utf-8")
        (work / "client.p12").write_bytes(b"\x00\x01PKCS12TEST\x02")
        (work / "client.pfx").write_bytes(b"\x00\x01PFXTEST\x02")

        visible = set(qproj._existing_project_text_files(work))
        for name in [".env", ".env.production", "ai_providers.env", "credentials.json", "secrets.json", "client.pem"]:
            assert name in visible, (name, visible)
        assert "client.p12" not in visible
        assert "client.pfx" not in visible

        binary = qproj._qwen_binary_sensitive_asset_inventory(work)
        assert "client.p12" in binary
        assert "client.pfx" in binary

        out, _count = qproj._package_workspace_zip(work, "sensitive-demo", "20990101_000000")
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            for name in [".env", ".env.production", "ai_providers.env", "credentials.json", "secrets.json", "client.pem", "client.p12", "client.pfx"]:
                assert name in names, (name, names)

        tools = mp.ProjectTools(work)
        listed = set(tools.list_files(".").get("files", []))
        assert ".env" in listed and "client.p12" in listed
        assert "TOKEN=alpha" in tools.read_file(".env").get("content", "")
        assert tools.read_file("client.p12").get("binary") is True
        assert "error" in tools.write_file(".env", "CHANGED=1")
        assert "error" in tools.write_file(".env.production", "CHANGED=1")
        assert "error" in tools.write_file("client.pem", "CHANGED")

        print("Sensitive Qwen context/checkpoint preservation regression passed.")
    finally:
        qproj.GENERATED_DIR = old_generated
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
