Jarvis V42.27 - Parser-Safe Compiler Delta + Structural Recovery
================================================================

Observed regression fixed
-------------------------
A coordinated TypeScript repair could reduce the TOTAL diagnostic count (for example
10 -> 3) while one of the changed files introduced a new parser failure such as
TS1128.  The global error delta therefore looked good even though the accepted source
contained malformed syntax.  The later bounded repair system then repeatedly tried to
patch the malformed file with Qwen.

V42.27 changes
--------------
1. Changed TypeScript/TSX files in a coordinated transaction must be syntax-clean in
   the real TypeScript compiler output before the transaction may commit.  A lower
   global diagnostic count can no longer hide a parser regression in a changed file.
2. TypeScript grammar codes/messages (including TS1128 "Declaration or statement
   expected") are recognized by the deterministic-syntax-first repair ladder.
3. A conservative structural recovery can remove an orphaned module-level return/body
   fragment left behind by a partial helper cleanup.  It commits only when the real
   TypeScript compiler proves the target parser diagnostics disappear and semantic file
   identity is preserved.
4. Compiler-proven unused typed arrow functions are removed by balanced declaration
   boundaries starting AFTER the => token.  Destructured parameter braces are never
   mistaken for the function body.
5. Deterministic structural recovery runs before exhausted model/subsystem re-entry.
6. New journal/projection events carry the current V42.27 engine identity.

Preserved
---------
V42.26 compiler-proofed multi-file transactions, V42.25 semantic navigation/event
projection/global loop guard/spill, V42.24 compiler-connected clusters, V42.23 resume
migration and TS burn-down, consumer-first ownership, transactional rollback, runtime
validation, Rust topology protections, sandboxing, and build/toolchain infrastructure
handling remain in place.
