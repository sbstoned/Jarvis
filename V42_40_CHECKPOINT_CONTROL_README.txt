JARVIS V42.40 - STOP + CHECKPOINT AND COMPILER-GATED REPEATED REPAIR

WHAT CHANGED

1. The chat command bar now shows a red STOP + CHECKPOINT button only while a
   Qwen project job is queued, running, or stopping.
2. Clicking it sets a cooperative stop token, closes the active local-Qwen HTTP
   stream, and asks the worker to unwind to a safe checkpoint boundary. It then
   records a durable project event and packages the best accepted working tree
   as a resumable checkpoint.
3. Disposable repair trials are never promoted merely because the user stops.
   The checkpoint comes from the authoritative accepted workspace.
4. Exact SEARCH/REPLACE blocks that occur multiple times may now be staged in
   the disposable component sandbox. They still cannot reach the real project
   unless the native component validator reports a strict diagnostic decrease.
5. Rust compiler evidence now supports general SQLx transaction dereferencing
   and removal of invalid enum matches when rustc proves the match expression is
   already a String. These rules are driven by diagnostic wording and source
   structure, not project or filename allowlists.

STOP WORKFLOW

Click STOP + CHECKPOINT. Jarvis confirms the stop immediately, cancels an active
model stream, and responds with a download link when the safe checkpoint is
written. The agent briefly displays SAVING CHECKPOINT while the worker unwinds
and then changes to STOPPED. Attach that checkpoint ZIP later and say "finish
this project" to continue from the preserved accepted state.

IMPORTANT

A stopped checkpoint is intentionally not labeled a verified final project.
Final publication still requires real build, test, runtime, integration, and
original-requirement acceptance evidence.
