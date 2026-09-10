"""Regression guard: the runtime bootstrap must activate V42.64 then V42.65.

This intentionally tests the small V42.63 bridge instead of importing the full
project engine.  It catches the failure mode where successor repair modules are
committed to the repository but never installed by local_qwen_project.py.
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

import jarvis_v4263_repair as bridge

ROOT = Path(__file__).resolve().parent
EXPECTED = ["jarvis_v4264_repair", "jarvis_v4265_repair"]


def main() -> int:
    for name in EXPECTED:
        path = ROOT / f"{name}.py"
        assert path.is_file(), f"missing successor repair module: {path.name}"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    calls: list[str] = []
    originals = {name: sys.modules.get(name) for name in EXPECTED}
    try:
        for name in EXPECTED:
            fake = types.ModuleType(name)
            fake.install = lambda _g, module_name=name: calls.append(module_name)
            sys.modules[name] = fake

        with tempfile.TemporaryDirectory(prefix="jarvis_v4265_activation_") as tmp:
            g = {
                "_v36_release_identity": lambda: {},
                "_progress": lambda *args, **kwargs: None,
                "JARVIS_DIR": tmp,
                "_emit": lambda *_args, **_kwargs: None,
            }
            bridge.install(g)

        assert calls == EXPECTED, f"successor activation order was {calls!r}, expected {EXPECTED!r}"
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    active = (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text(encoding="utf-8").strip()
    assert active == "V42.65.0", f"checked-in active engine is {active!r}, expected 'V42.65.0'"

    print("PASS: V42.64 and V42.65 are present, syntactically valid, and activated in order from the runtime bootstrap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
