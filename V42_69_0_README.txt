JARVIS V42.69.0 - COMPILER-IN-THE-LOOP DURABLE REPAIR

Purpose
-------
V42.68 proved that bounded search/view/reference/edit/diagnose tools and durable
repair memory work in a real GearTrack run, but that run exposed three blockers:

1. Exported TypeScript/JavaScript bindings could be falsely reported as unused
   local bindings by the cheap lexical closure preflight.
2. Valid tool JSON wrapped in <tool_call> or brief model prose could be discarded.
3. A candidate could pass the cheap preflight and then fail the real component
   compiler/test proof outside the internal repair session, forcing a new outer
   transaction instead of letting Qwen repair the exact compiler diagnostics.

V42.69 fixes those behaviors without weakening the existing acceptance gates.

Changes
-------
- Export-aware JS/TS closure checking. Exported functions/classes/consts and
  exported local names are treated as public API, not unused locals.
- Safe wrapped-tool extraction. Jarvis accepts exactly one complete schema-valid
  tool action even when surrounded by a common <tool_call> wrapper or short prose.
  Multiple different valid actions remain fail-closed as ambiguous.
- Real component compiler/test proof now runs after a syntactically/semantically
  clean in-session edit. Failures are fed back to the same Qwen repair session.
- Exact proof caching avoids rerunning the identical component proof again at the
  outer acceptance gate when the candidate bytes are unchanged.
- Internal edit budget is raised only slightly (4 edit rounds / 9 tool steps) so
  compiler feedback can be repaired without restoring the old unbounded behavior.
- Entry-point repairs receive a small generic module/topology hint to discourage
  duplicate wrappers and invented module paths when existing handlers/providers
  already exist.

Safety / acceptance authority
-----------------------------
- Qwen still has no arbitrary shell access.
- Existing files are still edited with exact SEARCH/REPLACE hunks.
- Whole-file rewrites remain bounded/discouraged.
- All edits remain inside disposable candidate workspaces until proven.
- V42.51+ functional delta, component proof, regression protection and final
  whole-project acceptance remain authoritative.
- Rejected candidate source is never promoted.

Recommended live validation
---------------------------
Resume the 114-file GearTrack checkpoint with V42.69 active and watch for:
- V42.69.0 in JARVIS_ACTIVE_ENGINE.txt and live state.
- no false unused warning for exported useCSVImportExport.
- wrapped tool actions being accepted instead of wasting a repair step.
- real TypeScript/Rust compiler errors appearing inside the SAME repair session.
- edit round N+1 repairing those exact errors.
- first accepted functional debt reduction from 8 to 7 or lower.

Focused regression command
--------------------------
python CHECK_V4269_COMPILER_LOOP.py
