"""V42.69.1: Windows-safe durable repair-memory connection lifecycle.

V42.69's compiler-loop regression check exposed a real V42.68 resource-lifecycle
bug on Windows: sqlite3.Connection.__exit__ commits/rolls back but does not close
the connection, so TemporaryDirectory/candidate cleanup could fail with WinError 32.

This hotfix preserves V42.69 behavior and wraps the existing memory connector so
every `with _memory_connect(...)` block closes its SQLite handle on exit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import jarvis_v4268_repair as sessions

VERSION = "42.69.1"
ENGINE = "COMPILER_LOOP_MEMORY_WINDOWS_SAFE_FACTORY"


class _ClosingMemoryConnection:
    """Delegate to sqlite3.Connection and guarantee close after context exit."""

    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        self._connection.__enter__()
        return self._connection

    def __exit__(self, exc_type, exc, tb):
        try:
            return self._connection.__exit__(exc_type, exc, tb)
        finally:
            self._connection.close()

    def close(self):
        return self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def install(g: dict[str, Any]):
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]

    if not getattr(sessions, "_v4269_1_memory_close_installed", False):
        previous_memory_connect = sessions._memory_connect

        def memory_connect(root):
            return _ClosingMemoryConnection(previous_memory_connect(root))

        sessions._memory_connect = memory_connect
        sessions._v4269_1_memory_close_installed = True

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r"jarvis_v42(?:4[0-9]|5[0-9]|6[0-9])_repair", name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r"V42\.\d+(?:\.\d+)?(?!\d)", "V" + VERSION, str(text))
        fields = dict(fields)
        fields["engine_version"] = "V" + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version="V" + VERSION,
            engine=ENGINE,
            sqlite_memory_connection_close_on_context_exit=True,
            windows_candidate_cleanup_safe=True,
            durable_project_repair_memory=True,
            same_transaction_compiler_refinement=True,
            compiler_and_functional_gates_preserved=True,
            rejected_candidate_source_never_promoted=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _progress=progress,
        _v36_release_identity=identity,
        V4269_1_VERSION=VERSION,
        V4269_1_ENGINE=ENGINE,
    )
    try:
        Path(
            g.get("JARVIS_DIR") or Path(__file__).resolve().parent,
            "JARVIS_ACTIVE_ENGINE.txt",
        ).write_text("V" + VERSION + "\n", encoding="utf-8")
    except OSError:
        pass
