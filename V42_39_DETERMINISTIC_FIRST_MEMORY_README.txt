JARVIS V42.39 - DETERMINISTIC-FIRST REPAIR, DURABLE MEMORY, AND FAILURE EXPLANATIONS

WHY V42.38 STALLED
------------------
The captured GearTrack run had one failing Rust component. Its React build and
Vitest test were green, while Cargo reported 75 errors. V42.38 correctly rebuilt
the component's previous model timeouts and marked both Rust targets as transport
exhausted. The bug was ordering: it filtered exhausted model targets before
running its compiler-derived candidate parser. That prevented three already-known
source edits from entering isolated Cargo validation. The outer loop could then
launch a specialist audit even though no inference route was eligible.

V42.39 REPAIR ORDER
-------------------
1. Run a fresh whole-project/component audit.
2. Persist stable issue and component-revision memory.
3. Parse exact compiler suggestions and proven structural adapters.
4. Validate the combined deterministic candidate in a disposable component copy.
5. If needed, validate each deterministic target separately.
6. Promote only if that exact component passes or its diagnostic count strictly
   decreases.
7. Only then consult component-revision model transport eligibility.
8. If the unchanged blocked component is the only issue and neither deterministic
   nor model repair can proceed, save MODEL_TRANSPORT_BLOCKED and stop cleanly.

This applies to all registered project/component adapters. The GearTrack sqlx
FromRow and rustc replacement handlers are narrow evidence adapters; project names
and application-specific source are not hardcoded.

PERSISTENT REPAIR MEMORY
------------------------
Every full component audit refreshes JARVIS_V4239_PROJECT_REPAIR_MEMORY.json. It
contains component source tokens, active/resolved issue fingerprints, diagnostic
counts/codes/files, prior deterministic outcomes, model transport history, and
recent accepted repair events. Compiler line/column movement does not create a new
issue identity. Compact component-relevant memory is supplied to a later model
repair so rejected strategies are not repeated. Current source and current
validator evidence always override memory.

FAILURE LOGS INSIDE EVERY GENERATED/RESUMED PROJECT
--------------------------------------------------
JARVIS_V4239_FAILURE_REPORT.md is the human-readable current answer to:
- Which component failed?
- Which build/test command and component root were used?
- Which codes, files, and diagnostic count were observed?
- Why is this classified as a source, test, tool, storage, or transport failure?
- What action is required next?

JARVIS_V4239_FULL_PASS_TRACE.jsonl is the append-only machine-readable history of
each full pass, including source revision tokens and repair decisions.
JARVIS_PROJECT_JOURNAL.jsonl remains the accepted/no-delta/blocked event stream.
Recognized credentials are redacted; provider prompts/responses and environment
values are not copied into the new logs.

USING THE RELEASE
-----------------
1. Replace the old Jarvis folder with this complete package.
2. Fully close every old Jarvis/Python process.
3. Start Jarvis from this folder and confirm JARVIS_ACTIVE_ENGINE.txt says
   V42.39.0.
4. Attach the newest complete project checkpoint and ask Jarvis to finish or edit
   the project.
5. If it stops, open JARVIS_V4239_FAILURE_REPORT.md inside that checkpoint first.

Run CHECK_V4239_DETERMINISTIC_FIRST_MEMORY.bat for the focused regression suite.

IMPORTANT ACCEPTANCE BOUNDARY
-----------------------------
V42.39 materially fixes the observed repair ordering and loop behavior, but it
cannot guarantee arbitrary software is correct merely because a model produced
files. A project is complete only after its real toolchains pass the declared
build, tests, runtime/integration checks, and the original requirement gates.

