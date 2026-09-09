JARVIS V42.42.2 - DURABLE CHECKPOINT RECOVERY AND FULL COMPILER EVIDENCE
================================================================

WHAT THIS RELEASE FIXES
-----------------------

V42.42.1 fixed the public launch chain in V42.42.0. V42.42.2 additionally
registers nested accepted workspaces directly with the checkpoint controller,
retains that path through worker shutdown, and preserves representative errors
from the entire compiler stream instead of keeping only its repetitive tail.
The outer current guard
correctly recognized V42.42, but the retained V42.41 compatibility wrapper then
compared the disk marker with its own historical constant and rejected the run
before the generator was called. Every retained wrapper now resolves the final
installed in-process identity at call time. A genuinely old process still fails
the marker check and must be restarted; a current process can pass through every
compatibility layer into the real generator/editor.

V42.41 could reduce a real project's compiler failures, but a changed diagnostic
message or issue identifier could reopen the same accepted repository revision.
That let older audit wrappers spend more model calls after the current repair
strategy had already been exhausted.

V42.42 makes the accepted repository revision plus failing component the retry
authority. Diagnostic order, line numbers, workspace paths, and error-text churn
no longer create a new repair budget. When every bounded strategy for that exact
revision/component is exhausted, an active dashboard project run stops at a safe
boundary and creates an incomplete resumable checkpoint instead of looping.

NEW REPAIR BEHAVIOR
-------------------

* One revision/component ledger merges legacy V42.41 issue IDs.
* Exact component validators remain the only authority for accepting an edit.
* Rust compiler evidence can drive one atomic multi-file transaction, including
  common SQLx, Tauri 2 path, Cargo dependency, duplicate import, unresolved import,
  invalid error-constructor, borrow, and direct async recursion failures.
* A candidate is promoted only when the real component diagnostic count decreases
  or the component becomes green.
* A validated result from the existing V42.41 transaction cannot be rejected just
  because its accepted-revision projection is written a moment later.
* The first no-change model cycle keeps the exact revision open for one distinct
  full-evidence retry; the second no-change cycle closes it without looping.
* A new release with a newly implemented repair strategy can reopen an older
  terminal revision once, while same-release wording churn still cannot.
* Repeated SEARCH/REPLACE handling once again allows the safe viewer-line-number
  normalizer to process copied line-number prefixes.
* Current project state is reduced from the latest whole-project audit or terminal
  record, so stale historical blockers do not keep directing workers after a fresh
  audit has established different facts.

MEMORY AND WORKER HANDOFFS
--------------------------

Jarvis now has a SQLite WAL shared-memory store with personal, project, run, and
worker scopes. Background workers receive a bounded structured contract containing
the goal, current repository truth, constraints, validation authority, known facts,
and available MCP capabilities. Worker start/result/failure records are shared so
another worker can continue from evidence instead of reconstructing the day from
raw chat.

Raw personal conversation is not copied into project worker context or generated
project snapshots. Secret-shaped values are redacted before structured memory is
written. This is engineering continuity, not permission to expose credentials.

MCP CAPABILITY REGISTRY
-----------------------

JARVIS_MCP_TOOL_CATALOG.json prioritizes useful development capabilities such as
GitHub, Playwright, Docker, language servers, package registries, database
introspection, runtime telemetry, Cloudflare, and Figma. The registry discovers
already configured servers and reports command availability without copying their
arguments or credentials. It does not silently install tools, connect accounts, or
grant permissions.

PROJECT-SIDE EVIDENCE
---------------------

During a run, V42.42 can write these records into the active project workspace so
they survive a manual stop or automatic exhausted checkpoint:

* JARVIS_V4242_REVISION_LEDGER.json
* JARVIS_V4242_CONVERGENCE_TRACE.jsonl
* JARVIS_V4242_REPAIR_STATUS.md
* JARVIS_V4242_RUN_STATE.json
* JARVIS_V4242_TERMINAL_STATE.json (only at terminal exhaustion)
* JARVIS_V4242_SHARED_CONTEXT.json
* JARVIS_V4242_VALIDATOR_EVIDENCE.json
* JARVIS_V4242_LAST_VALIDATOR_OUTPUT.txt
* Existing V42.40 manual checkpoint and stop-event records remain supported.

The dashboard heartbeat records stage, activity, percentage, diagnostic count,
repository token, model role/profile, stream state, and token estimates when the
caller provides them. Logs are flushed/atomically replaced at safe update points.

HOW TO USE ON WINDOWS
---------------------

1. Fully close the old Jarvis voice engine, dashboard server, and local Qwen server.
2. Extract this ZIP into a new folder. Do not merge it over a running installation.
3. Start Jarvis with the same launcher you normally use.
4. If a browser did not open, run OPEN_JARVIS_DASHBOARD.bat.
5. The active marker must read V42.42.2.
6. Run CHECK_V4242_REVISION_MEMORY_CONVERGENCE.bat for the focused offline test.

For an unfinished generated project, attach the newest checkpoint ZIP and ask
Jarvis to finish or repair it. A checkpoint is intentionally not labeled complete.

BOUNDARIES
----------

No finite repair engine can guarantee that every possible prompt, language,
framework, external service, SDK, or hardware target will build on every host.
V42.42 improves convergence, evidence, and safe failure behavior; it does not fake
success. Missing toolchains, unavailable credentials/services, ambiguous product
requirements, or an unimplemented error family can still require user input or a
new repair strategy. Publication remains blocked until the declared build, tests,
runtime/integration checks, and original requested behavior all pass.
