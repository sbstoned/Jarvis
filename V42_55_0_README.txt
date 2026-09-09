JARVIS V42.55.0 - Complete distribution with repaired model execution

Based on your uploaded Jarvis_V42_54_0_COMPLETE.zip. All original archive
members and resources are retained. This ZIP updates Jarvis itself; it does
not claim that the unfinished attached GearTrack project is accepted.

START THIS VERSION
1. If an old job is running, use STOP + CHECKPOINT and let its save finish.
2. Fully close Jarvis and its dashboard.
3. Extract this complete ZIP into a fresh folder. Keep the previous folder
   and your saved project ZIP until the new installation is working.
4. Start jarvis.py using your usual Jarvis Python environment and model setup.
5. Confirm engine V42.55.0 and dashboard build v42.55.0-exact-model-protocol.
6. Attach your project/checkpoint ZIP, wait until it is ready, then send
   "finish this project" using Enter or the send button.

ROOT CAUSES FIXED
- The current transaction requested up to 9,000 output tokens, but inherited
  model wrappers reduced that to 2,800 and appended conflicting source/JSON,
  provider/consumer and framework-specific instructions. One model-call
  policy now uses the caller's format, existing router and actual context.
- Structured source evidence is never cut through the middle of a file or
  JSON value. Functional transactions select complete related files that fit
  the active model. Edits to omitted files are rejected. If even the complete
  target cannot fit, the error explains the context limitation.
- Streams now distinguish normal completion, token-limit truncation, broken
  connections and malformed frames. Partial JSON transactions cannot commit.
  Bounded response excerpts, source hashes and completion metadata are kept in
  the project's diagnostic model-output records, with rejection feedback for
  the next attempt. Hidden retries no longer discard invalid strict output.
- Large-file generation retains its explicit continuation mechanism. Partial
  source remains a draft until a completed response finishes the file and the
  normal syntax, component and acceptance gates validate the candidate. A
  syntactically valid prefix is not treated as a complete implementation.
- SEARCH/REPLACE blocks resolve against the same original snapshot. Exact
  duplicate blocks apply once; disjoint edits cannot accidentally target newly
  inserted text. Ambiguous or conflicting overlaps fail before any write.
- SQLx result checks now associate a mutation with its own row-fetch chain,
  including direct literals and local aliases. An execute() call no longer
  inherits a later function's fetch_one(). Separate result defects have
  separate identities, so a real partial repair can reduce the debt.
- SQLite preparation failures use stable owner/operation/table/error identity
  and occurrence counts. Adding a RETURNING projection or imports does not
  turn the same outstanding column error into new debt. Different bad
  columns, tables, owners and additional failing queries still block promotion.
- Workflow test paths follow the declared runner, adapter and component
  ownership. A JavaScript configuration file cannot select a JavaScript test
  for Cargo. Supported mixed JS/TS tests remain valid; custom language paths
  and the existing toolchain catalog remain supported.

CONTROLS PRESERVED
The existing AUTO model router, manual model locks, one-peer watchdog rescue,
STOP + CHECKPOINT, real command broker, disposable validation, concurrent edit
protection, rollback, best-state retention and strict final acceptance remain.
Previous chunked ZIP uploads, Enter/send acknowledgement, busy-draft retention,
stale-job cleanup and matching dashboard/server identity fixes are retained.

VERIFICATION
145 checks passed: 128 unittest cases plus 17 legacy regression checks.
All 85 Python source files parsed; dashboard/upload JavaScript syntax passed.

New tests run through production _qwen_call and ask_qwen against a local HTTP
SSE fixture, then through the actual transaction and registered custom adapter
build/test commands. A repaired SQLite service proves successful writes, a
rejected invalid input without extra persisted rows, and reads after a new
process starts. A large-file generation test continues a truncated response
and executes both completed functions. Existing upload, UI send, job lifecycle,
SQLite, C, JavaScript, rollback and checkpoint workflow checks also pass.

The latest uploaded run snapshots were replayed in an isolated workspace.
Fixing the missing INSERT RETURNING projection reduces static debt from 14
to 13 with no new debt. The three real wrong-column queries remain blocking,
and the backend test target is now src-tauri/tests/application.rs. This replay
is a diagnostic check, not a Rust build or final GearTrack acceptance.

Model replies in the tests are controlled fixtures. Live Qwen inference,
Windows GUI/voice startup and a full generated desktop application were not
executed on this Linux host; Rust/Cargo were unavailable here. Each project
still needs its installed native build, test and runtime tools, plus passing
original-requirement acceptance. A checkpoint remains unfinished when those
checks fail. This update improves the universal agent's execution machinery;
it does not establish that every model-generated program will be correct.

RUN THE CHECKS
Windows: CHECK_V4255_MODEL_PROTOCOL.bat
Other hosts: use the Python commands in that file in your Jarvis environment.
V42_55_0_VALIDATION_REPORT.json and V42_55_0_TEST_OUTPUT.txt record the results.
