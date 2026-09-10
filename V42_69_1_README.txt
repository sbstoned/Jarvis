Jarvis V42.69.1
================

Purpose
-------
Windows-safe lifecycle hotfix for the durable SQLite repair-memory layer introduced in V42.68 and used by V42.69.

Observed failure
----------------
CHECK_V4269_COMPILER_LOOP.py passed all logic assertions but Windows could not remove the temporary accepted workspace because `.jarvis_memory/project_memory.sqlite3` was still open. Python's sqlite3.Connection context manager commits or rolls back on exit but does not close the connection.

Fix
---
V42.69.1 wraps Jarvis's existing repair-memory connector so every `with _memory_connect(...)` block closes the underlying SQLite handle in a `finally` path after commit/rollback.

This preserves:
- durable repair memory across trials/checkpoints;
- V42.69 compiler-in-the-loop same-session refinement;
- export-aware TypeScript/JavaScript closure checks;
- safe wrapped tool-action extraction;
- exact component-proof caching;
- disposable candidate isolation and all existing final acceptance gates.

Expected activation
-------------------
JARVIS_ACTIVE_ENGINE.txt should report:

V42.69.1

Focused check
-------------
Run:

.\.venv\Scripts\python.exe -m py_compile jarvis_v4269_repair.py jarvis_v4269_1_repair.py CHECK_V4269_COMPILER_LOOP.py jarvis_v4263_repair.py
.\.venv\Scripts\python.exe CHECK_V4269_COMPILER_LOOP.py

The Windows TemporaryDirectory cleanup in the compiler-loop regression test is part of the proof: if the SQLite handle is leaked, the test fails with WinError 32 during cleanup.
