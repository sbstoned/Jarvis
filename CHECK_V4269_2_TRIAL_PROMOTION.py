from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import jarvis_v4268_repair as sessions
import jarvis_v4269_2_repair as v


class V42692Checks(unittest.TestCase):
    def make_project(self, root: Path, label: str = "new") -> Path:
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "src" / "main.ts").write_text(
            f"export const state = '{label}';\n", encoding="utf-8"
        )
        (root / "src-tauri").mkdir(parents=True, exist_ok=True)
        (root / "src-tauri" / "Cargo.toml").write_text(
            "[package]\nname='fixture'\nversion='0.1.0'\nedition='2021'\n",
            encoding="utf-8",
        )
        (root / "package.json").write_text(
            '{"name":"fixture","scripts":{"build":"tsc"}}\n', encoding="utf-8"
        )
        return root

    def test_legacy_nested_trial_is_unwrapped(self):
        with tempfile.TemporaryDirectory() as td:
            malformed = Path(td) / "working"
            # This is the exact shape left by legacy rmtree+move on Windows: only
            # rebuildable residue survives at the root and the accepted trial is moved inside it.
            (malformed / "src-tauri" / "target").mkdir(parents=True)
            (malformed / "src-tauri" / "target" / "locked.bin").write_text("cache", encoding="utf-8")
            nested = self.make_project(malformed / "trial_01", "accepted")
            self.assertFalse(v._looks_like_project_root(malformed))
            self.assertEqual(v._resolve_project_root(malformed), nested.resolve())

    def test_safe_promotion_preserves_rebuildable_cache_without_nesting(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage = self.make_project(root / "stage", "accepted")
            work = self.make_project(root / "working", "old")
            (work / "src" / "stale.ts").write_text("export const stale=true;\n", encoding="utf-8")
            (work / "src-tauri" / "target").mkdir(parents=True)
            cache = work / "src-tauri" / "target" / "locked.bin"
            cache.write_text("keep", encoding="utf-8")

            v._sync_promoted_tree(stage, work)

            self.assertIn("accepted", (work / "src" / "main.ts").read_text(encoding="utf-8"))
            self.assertFalse((work / "src" / "stale.ts").exists())
            self.assertTrue(cache.exists())
            self.assertFalse(any(p.name.startswith("trial_") for p in work.iterdir()))
            self.assertTrue((work / "package.json").is_file())
            self.assertTrue((work / "src-tauri" / "Cargo.toml").is_file())

    def test_portable_memory_is_not_application_manifest_source(self):
        manifest = {
            "files": [
                {"path": ".jarvis_memory/repair_memory.json", "purpose": "internal"},
                {"path": "src/main.ts", "purpose": "entrypoint"},
            ]
        }
        removed = v._sanitize_manifest_in_place(manifest)
        self.assertEqual(removed, 1)
        self.assertEqual([x["path"] for x in manifest["files"]], ["src/main.ts"])
        self.assertTrue(v._internal_rel(".jarvis_memory/repair_memory.json"))
        self.assertFalse(v._internal_rel("src/main.ts"))

    def test_installed_copy_flattens_legacy_root_and_audit_filters_memory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            malformed = base / "legacy_work"
            (malformed / "src-tauri" / "target").mkdir(parents=True)
            self.make_project(malformed / "trial_01", "accepted")
            destination = base / "trial_02"

            def old_copy(src, dst):
                src, dst = Path(src), Path(dst)
                if dst.exists():
                    shutil.rmtree(dst)
                return Path(shutil.copytree(src, dst))

            def old_resume(_request, manifest, _work, _job, _callback=None,
                           generic_resume=True, prior_issues=None, max_sweeps=None):
                self.assertFalse(any(
                    str((x or {}).get("path") or "").startswith(".jarvis_memory/")
                    for x in manifest.get("files", []) if isinstance(x, dict)
                ))
                return False, ["remaining"], {"score": (1, 1, 1)}

            def old_audit(_root, _request, _manifest, run_components=True, progress_callback=None):
                return {
                    "clean": False,
                    "issues": [
                        {"file": ".jarvis_memory/repair_memory.json", "kind": "missing"},
                        {"file": "src/main.ts", "kind": "real"},
                    ],
                }

            events = []
            g = {
                "_v36_release_identity": lambda: {},
                "_progress": lambda *a, **k: None,
                "_copy_resume_workspace": old_copy,
                "_commit_resume_trial": lambda *a, **k: None,
                "_run_resume_sweeps": old_resume,
                "_v429_whole_project_audit": old_audit,
                "_append_project_event": lambda *a, **k: events.append((a, k)),
                "JARVIS_DIR": str(base),
            }

            original_memory_writer = sessions._write_portable_memory
            sessions._write_portable_memory = lambda _root: None
            try:
                v.install(g)
                g["_copy_resume_workspace"](malformed, destination)
                self.assertTrue((destination / "src" / "main.ts").is_file())
                self.assertTrue((destination / "src-tauri" / "Cargo.toml").is_file())
                self.assertFalse((destination / "trial_01").exists())

                manifest = {
                    "files": [
                        {"path": ".jarvis_memory/repair_memory.json"},
                        {"path": "src/main.ts"},
                    ]
                }
                g["_run_resume_sweeps"]("finish", manifest, destination, base / "job")
                self.assertEqual([x["path"] for x in manifest["files"]], ["src/main.ts"])

                audit = g["_v429_whole_project_audit"](destination, "finish", manifest)
                self.assertEqual([x["file"] for x in audit["issues"]], ["src/main.ts"])

                identity = g["_v36_release_identity"]()
                self.assertEqual(identity["version"], "V42.69.2")
                self.assertTrue(identity["safe_in_place_trial_promotion"])
                self.assertTrue(identity["legacy_nested_trial_auto_unwrap"])
                self.assertTrue(identity["portable_repair_memory_excluded_from_authored_audit"])
                self.assertTrue(identity["same_transaction_compiler_refinement"])
            finally:
                sessions._write_portable_memory = original_memory_writer

    def test_installed_commit_does_not_move_trial_inside_surviving_work(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            trial = self.make_project(base / "trial_01", "accepted")
            work = self.make_project(base / "working", "old")
            # Simulate exactly the kind of rebuildable residue that made legacy
            # shutil.rmtree(work, ignore_errors=True) unsafe on Windows.
            cache = work / "src-tauri" / "target" / "debug" / "cache.bin"
            cache.parent.mkdir(parents=True)
            cache.write_text("keep", encoding="utf-8")

            def old_copy(src, dst):
                src, dst = Path(src), Path(dst)
                if dst.exists():
                    shutil.rmtree(dst)
                return Path(shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                    "node_modules", "target", "build", ".jarvis_runtime", ".jarvis_build",
                    ".jarvis_shared_build_cache", ".jarvis_backups", ".jarvis_failures"
                )))

            g = {
                "_v36_release_identity": lambda: {},
                "_progress": lambda *a, **k: None,
                "_copy_resume_workspace": old_copy,
                "_commit_resume_trial": lambda *a, **k: None,
                "_run_resume_sweeps": lambda *a, **k: (False, [], {}),
                "_v429_whole_project_audit": lambda *a, **k: {"clean": True, "issues": []},
                "_append_project_event": lambda *a, **k: None,
                "JARVIS_DIR": str(base),
            }
            original_memory_writer = sessions._write_portable_memory
            sessions._write_portable_memory = lambda _root: None
            try:
                v.install(g)
                g["_commit_resume_trial"](trial, work, None)
                self.assertIn("accepted", (work / "src" / "main.ts").read_text(encoding="utf-8"))
                self.assertTrue(cache.exists())
                self.assertFalse((work / "trial_01").exists())
                self.assertTrue((work / "src-tauri" / "Cargo.toml").is_file())
            finally:
                sessions._write_portable_memory = original_memory_writer


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V42692Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"V42.69.2 trial-promotion checks passed: {result.testsRun}/{result.testsRun}")
