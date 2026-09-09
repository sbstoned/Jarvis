JARVIS V42.45.0 — WARM-CACHE COMPILER PROMOTION

Why this release exists
-----------------------
V42.44 correctly generated the generic SQLx joined-row repair for the remaining
GearTrack Rust E0277 failure, but candidate validation ran inside a source-only
disposable clone. That clone did not contain Cargo build artifacts, so the full
Rust validator spent its bounded window rebuilding the Tauri/SQLx dependency
stack. The focused follow-up cargo build also timed out after 180 seconds even
though it had reached the GearTrack crate. The valid candidate was therefore
not promoted and the same seven compiler diagnostics remained.

V42.45 behavior
---------------
1. Compiler-directed Rust candidates are still created only in a disposable
   source clone.
2. Candidate compile proof now runs `cargo build --target-dir <accepted target>`
   from the clone. Only Cargo artifacts are shared; candidate source remains
   isolated.
3. The accepted workspace has already produced the compiler diagnostics, so its
   Cargo target directory normally contains the expensive dependency artifacts.
4. The compile gate has a bounded 300-second default timeout and at most two
   attempts. A timeout gets one warmed continuation instead of immediately
   spending model-repair cycles.
5. A real successful build can promote intermediate compiler progress. A strict
   diagnostic decrease can also be promoted transactionally.
6. Promotion is NOT final acceptance. Jarvis immediately reruns the normal full
   component/build/test/runtime validation from the improved accepted revision.
7. If direct Cargo proof is unavailable, the mature full component validator is
   retained as a fail-safe compatibility path.
8. The repair strategy generation is now:
   sqlx-joined-struct-row-v3-warm-cache-compile-gate
   This intentionally reopens an exhausted V42.44 revision once. Repeated V42.45
   attempts at the same accepted revision remain circuit-broken.

Additional cleanup
------------------
The project-run control state now replaces stale testing/preflight UI text when
an automatic checkpoint is saved, so the dashboard reports the terminal
checkpoint state rather than an earlier activity heartbeat.

Safety/acceptance invariants retained
-------------------------------------
- Source edits remain transactional and validator-gated.
- Rejected candidates cannot mutate accepted source.
- Anti-loop revision/component circuit breakers remain bounded.
- Compiler-progress promotion is not equivalent to project completion.
- Full final acceptance still requires the project-wide build/test/runtime gates.
- The strategy is generic Rust/SQLx behavior and is not GearTrack/Tool hardcoded.
