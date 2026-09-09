JARVIS V42.46.0 — COMPILER-HINT LAST-MILE CONVERGENCE

Why this release exists
-----------------------
V42.45 successfully crossed the previous SQLx plateau. On the resumed GearTrack
checkpoint it generated the joined-row repair, proved it with the warm Cargo cache,
and committed a new accepted revision. Rust diagnostics dropped from 7 to 2.

The newly exposed compiler blocker was a normal rustc E0277 at src-tauri/src/app.rs:
a PathBuf was interpolated with Display syntax inside format!(...), and rustc explicitly
recommended calling `.display()`. V42.45 had no deterministic rule for that compiler
hint, so it fell back to local-model patching. The model transport then returned no
usable patch bytes across several bounded calls.

V42.46 behavior
---------------
1. Retains the V42.45 generic SQLx joined-struct row repair and warm Cargo target cache.
2. Adds a generic rustc-directed Path/PathBuf Display repair. It only fires when:
   - rustc reports E0277 for Path/PathBuf Display,
   - rustc explicitly recommends `.display()`,
   - the exact failing format! source line is present in compiler evidence, and
   - local source proves the captured value is path-shaped.
3. The edit is still made only in a disposable candidate and must pass the real Cargo
   compile gate before promotion.
4. This allows the known GearTrack compiler sequence to converge deterministically:
   7 SQLx diagnostics -> 2 PathBuf diagnostics -> 0 compile diagnostics, subject to
   the real Windows Cargo compiler.
5. A compile-green repair is still only intermediate progress. Jarvis immediately
   reruns full component/build/test/runtime acceptance and repairs any newly exposed
   blockers before publishing a final project.
6. Bounded model fallback is retained for unknown cases, but empty/no-patch transport
   is now less expensive under this strategy generation: default worker/specialist
   patch watchdogs are 120/240 seconds and the same transport failure is cooled down
   after one state-local failure unless environment variables explicitly override it.
7. New strategy generation:
   rust-compiler-hints-v4-sqlx-path-display-warm-cache
   This reopens an exhausted older-strategy revision once while preserving the
   same-strategy circuit breaker.

Safety/acceptance invariants retained
-------------------------------------
- No diagnostic suppression or compiler-option weakening.
- No project-specific GearTrack hardcoding in the repair rule.
- Source changes remain transactional and validator-gated.
- Rejected candidates cannot mutate accepted source.
- Intermediate compiler success is not final project acceptance.
- Full project build/tests/runtime gates remain authoritative.
- Revision/component anti-loop budgets remain bounded.
