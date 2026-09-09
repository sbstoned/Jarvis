Jarvis V42.28 - Best-Verified Resume Score + Endgame Closure

Base: the V42.26 compiler-proofed dependency-first repair pipeline that produced the strongest GearTrack error burn-down, plus the V42.27 parser-safety protections.

Primary regression fixed
------------------------
The legacy resume snapshot score treated all real-build failures coarsely. A trial with 37 TypeScript diagnostics and a trial with 3 diagnostics could both score as "deterministic clean, real validation failed", so the 3-error state was not guaranteed to replace working.

V42.28 changes resume scoring to use fresh compiler evidence:
  0 - build/test/runtime green
  1 - source compiles; remaining failure is runtime/integration
  2 - syntax-clean TypeScript semantic/type diagnostics (fewer is better)
  3 - TypeScript parser/syntax diagnostics (can hide semantic debt)
  4 - deterministic/static source defects

Consequences:
- 37 -> 3 semantic TypeScript diagnostics is objective checkpoint progress and is promoted.
- 3 syntax-clean semantic errors outrank a misleading single TS1128 parser error.
- Fixing one parser error and revealing several semantic errors is still forward progress.
- Checkpoints package the objectively promoted working state and include JARVIS_V4228_BEST_STATE_PROOF.json.

Endgame closure
---------------
When <= 6 TypeScript diagnostics remain, Jarvis gets one bounded compiler-proven deterministic cleanup transaction before more model reasoning. The edit commits only on strict fresh TypeScript improvement and still passes the V42.27 changed-file syntax gate. A second acceptance cycle is allowed only after that proven source delta.

Preserved behavior
------------------
- V42.26 dependency-first coordinated multi-file repair and global compiler-proof commit.
- V42.27 changed-file parser/syntax regression rejection and structural recovery.
- V42.25 same-revision loop fingerprint guard, event projection, prompt spill, semantic navigation.
- V42.24 atomic multi-file TypeScript staging.
- Consumer-first ownership, stable-provider protection, transactional rollback, infrastructure classification, build/runtime verification, cache isolation and topology protections.
