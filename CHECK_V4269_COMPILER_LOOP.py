from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import jarvis_v4250_repair as gates
import jarvis_v4251_repair as transactions
import jarvis_v4268_repair as sessions
import jarvis_v4269_repair as v


class V4269Checks(unittest.TestCase):
    def test_exported_hook_not_false_unused(self):
        src = "export const useCSVImportExport = () => ({ exportCSV: () => 'x' });\n"
        self.assertEqual(v._closure_errors("src/hook.ts", src, src), [])

    def test_real_unused_local_still_caught(self):
        src = "const unusedThing = getThing();\nexport const useX = () => 1;\n"
        errors = v._closure_errors("src/hook.ts", src, src)
        self.assertTrue(any("unusedThing" in e for e in errors), errors)
        self.assertFalse(any("useX" in e for e in errors), errors)

    def test_removed_binding_with_reference_still_caught(self):
        before = "const mockTools = [];\nconsole.log(mockTools);\n"
        after = "console.log(mockTools);\n"
        errors = v._closure_errors("src/hook.ts", before, after)
        self.assertTrue(any("old local binding 'mockTools'" in e for e in errors), errors)

    def test_direct_action_parse(self):
        obj = v._parse_action('{"action":"search","query":"tools_create"}')
        self.assertEqual(obj["action"], "search")

    def test_tool_call_wrapper_parse(self):
        raw = 'I will inspect it first.\n<tool_call>{"action":"view","path":"src/lib.rs"}</tool_call>'
        obj = v._parse_action(raw)
        self.assertEqual(obj, {"action": "view", "path": "src/lib.rs"})

    def test_fenced_wrapper_parse(self):
        raw = '```json\n{"action":"references","symbol":"tools_create"}\n```'
        obj = v._parse_action(raw)
        self.assertEqual(obj["action"], "references")

    def test_ambiguous_actions_rejected(self):
        raw = (
            '<tool_call>{"action":"view","path":"a.rs"}</tool_call>\n'
            '<tool_call>{"action":"view","path":"b.rs"}</tool_call>'
        )
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            v._parse_action(raw)

    def test_topology_hint_is_bounded_and_generic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "src-tauri" / "src"
            p.mkdir(parents=True)
            (p / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
            (p / "lib.rs").write_text("pub fn run() {}\n", encoding="utf-8")
            (p.parent / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
            hint = v._topology_hint(root, "src-tauri/src/main.rs")
            self.assertIn("lib.rs", hint)
            self.assertIn("Cargo.toml", hint)
            self.assertIn("do not duplicate", hint)

    def test_install_identity_and_real_component_feedback_cache(self):
        old_proof = gates._component_candidate_proof
        old_quick = sessions._quick_diagnostics
        old_tx = transactions.repair_transaction
        old_parse = sessions._parse_action
        old_closure = sessions._local_closure_errors
        calls = {"n": 0}

        def fake_proof(g, root, clone, manifest, rel, progress_callback=None):
            calls["n"] += 1
            return {
                "available": True,
                "ok": False,
                "kind": "fixture_compiler",
                "output": "error[E0001]: exact compiler failure",
            }

        try:
            gates._component_candidate_proof = fake_proof
            sessions._quick_diagnostics = lambda *a, **k: []
            with tempfile.TemporaryDirectory() as td:
                root = Path(td) / "accepted"
                clone = Path(td) / "candidate"
                (root / "src").mkdir(parents=True)
                (clone / "src").mkdir(parents=True)
                (root / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
                (clone / "src" / "main.rs").write_text('fn main(){println!("x");}\n', encoding="utf-8")
                g = {
                    "_v36_release_identity": lambda: {},
                    "_progress": lambda *a, **k: None,
                    "JARVIS_DIR": td,
                }
                v.install(g)
                sessions._SESSION.root = str(root)
                try:
                    errors = sessions._quick_diagnostics(
                        g, clone, {}, "src/main.rs",
                        "fn main() {}\n",
                        'fn main(){println!("x");}\n',
                    )
                    self.assertTrue(any("REAL COMPONENT COMPILER/TEST PREFLIGHT FAILED" in e for e in errors), errors)
                    self.assertTrue(any("exact compiler failure" in e for e in errors), errors)
                    proof = gates._component_candidate_proof(g, root, clone, {}, "src/main.rs", None)
                    self.assertFalse(proof["ok"])
                    self.assertEqual(calls["n"], 1)
                finally:
                    for name in ("root", "v4269_component_proof_cache"):
                        try:
                            delattr(sessions._SESSION, name)
                        except Exception:
                            pass

                identity = g["_v36_release_identity"]()
                self.assertEqual(identity["version"], "V42.69.0")
                self.assertTrue(identity["export_aware_js_ts_closure"])
                self.assertTrue(identity["wrapped_tool_action_extraction"])
                self.assertTrue(identity["real_component_proof_inside_same_repair_session"])
                self.assertTrue(identity["same_transaction_compiler_refinement"])
                self.assertFalse(identity["arbitrary_model_shell_access"])
        finally:
            gates._component_candidate_proof = old_proof
            sessions._quick_diagnostics = old_quick
            transactions.repair_transaction = old_tx
            sessions._parse_action = old_parse
            sessions._local_closure_errors = old_closure


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(V4269Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"V42.69 compiler-loop checks passed: {result.testsRun}/{result.testsRun}")
