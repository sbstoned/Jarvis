JARVIS V42.44.0 - PHASE-AWARE COMPILER PROGRESS PROMOTION

Purpose
-------
V42.44 fixes the last-mile failure observed after V42.43 correctly generated the
SQLx joined-row repair but discarded the disposable candidate when the broader
component validator returned false with zero parseable compiler diagnostics.

Root cause
----------
A full component validator can advance through compilation and fail later in a
test or runtime-smoke stage. In that case the old gate saw:

  validator_ok = false
  parsed_compiler_diagnostics = 0

V42.43 correctly refused to treat parser-zero as success, but it had no second
proof to distinguish "compiler fixed, later gate now exposed" from "validator
failed before useful evidence." The good compiler repair could therefore be
thrown away and Jarvis fell back to slow model repair on the old source.

V42.44 behavior
---------------
1. The existing generic SQLx joined-struct repair remains unchanged in intent.
2. Candidate bytes are verified to differ from the accepted workspace before
   promotion is considered.
3. A failed full validator with zero parseable compiler diagnostics is NEVER
   treated as success by itself.
4. Jarvis runs a focused compile/build proof against the same disposable
   candidate. For Rust this uses the normal controlled command broker and
   `cargo build` in the exact component root.
5. If that focused compile proof succeeds, Jarvis atomically promotes the source
   repair as compile-phase progress, records the downstream validator failure,
   and immediately continues from the improved source revision.
6. Final publication is still impossible until the ordinary full component,
   whole-project, test, runtime, and acceptance gates pass.
7. If the focused compile proof fails or is unavailable, the candidate remains
   rejected. Parser-zero can never bypass validation.
8. Strategy generation is now `sqlx-joined-struct-row-v2-phase-aware`, so an
   exhausted V42.43 checkpoint can reopen exactly once for this genuinely new
   strategy. Repeated runs under the same V42.44 strategy remain circuit-broken.

GearTrack resume guidance
-------------------------
Resume the best GearTrack checkpoint; do not regenerate the project from scratch.
V42.44 should keep the deterministic SQLx repair if it truly clears Cargo build,
then allow the next test/runtime/database blocker to become the new repair target.

Safety / acceptance invariant
-----------------------------
No candidate is promoted merely because an error parser reports zero. Promotion
requires an actual source delta plus one of:
  - the full component validator passes;
  - the real compiler diagnostic count strictly decreases; or
  - a focused compile/build proof passes after the broader validator advances to
    a later failing stage.
Final completion still requires all normal acceptance gates to pass.
