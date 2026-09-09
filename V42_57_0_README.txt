Jarvis V42.57.0 — Evidence-Expanded Coordinated Convergence + Unbounded Active Qwen Streams

WHY THIS RELEASE EXISTS
The V42.56 GearTrack resume proved that safe candidate promotion worked: functional debt fell from 14 -> 13 -> 12 without breaking the Rust build. It then stalled because the remaining repairs crossed real integration boundaries. Qwen repeatedly recognized that checkout.rs needed related runtime/provider files such as main.rs/tools.rs, but a context-fitted transaction could omit one of those files and then reject Qwen's coordinated edit as out-of-scope. A separate absolute stream wall clock could also kill a useful repair while tokens were still arriving.

V42.57 CHANGES
1. Evidence-proven adaptive cross-file scope expansion
   - Functional repair evidence now prioritizes runtime/entrypoint owners as well as repositories/providers/services.
   - A model-requested extra file is NEVER trusted merely because the model names it.
   - If that exact file is already in Jarvis's bounded related-source evidence but was omitted by context fitting, the first candidate is rejected safely and the next attempt forces that file's COMPLETE CURRENT SOURCE into the prompt.
   - Model-invented/unproven paths remain out-of-scope and are rejected.
   - Coordinated edits still occur only in the disposable candidate clone and must pass syntax/semantic/component proof plus strict functional-debt improvement before commit.

2. Larger but still bounded evidence transaction
   - Related source files: 14 -> 18
   - Related source character budget: 90,000 -> 120,000
   - Model attempts per functional transaction: 3 -> 4
   These are evidence/attempt bounds, not project-stack assumptions.

3. Removed the active-stream 8-minute-style hard wall
   - Active local-Qwen absolute stream timeout: DISABLED (0 seconds).
   - A repair that keeps streaming useful tokens may run past 8 minutes and finish naturally.
   - Historical per-call hard_timeout values are stripped at the authoritative base Qwen seam in V42.57.
   - The provider default hard timeout is now 0.
   - The existing dead-stream/read idle timeout remains. If Qwen stops sending data entirely, Jarvis can still recover rather than hang forever.
   - The existing user Stop/cancellation path remains active.

4. Existing safety/quality gates remain authoritative
   - Exact current-source SEARCH/REPLACE protocol.
   - Stale hunk salvage, but no ambiguous/overlapping patches.
   - Validator-owned pruning for precise SQL/compiler findings.
   - Disposable candidate sandbox before any accepted-source write.
   - Test-integrity checks.
   - Real component build/test proof.
   - Strict functional debt reduction and new-debt rejection.
   - Atomic multi-file commit/rollback.
   - Final zero-debt publication/acceptance gate.

GEARTRACK REPLAY RESULT
Against the uploaded GearTrack Rust snapshot, checkout.rs now retains the important integration neighbors in the bounded related-source set, including tools.rs, app/runtime initialization, lib.rs and main.rs. If context fitting still has to omit a requested neighbor, V42.57 converts that rejection into an evidence-proven retry with the complete source forced into the next model prompt instead of repeating the same out-of-scope cycle.

TIMEOUT REGRESSION PROOF
The V42.57 provider test simulates a useful local-Qwen response completing after 500 seconds (8m20s). The response is accepted with the active hard timeout disabled instead of being killed by the old wall clock.

FOCUSED TEST RESULTS
- V42.57 evidence-expanded/unbounded-stream: 6/6 PASS
- V42.56 evidence-closed scoped repair: 5/5 PASS
- V42.55 model protocol/native contract identity: 35/35 PASS
- V42.52 durable functional progress: 19/19 PASS
- V42.51 functional transactions: 17/17 PASS
- V42.50 regression-safe functional promotion: 17/17 PASS
- Historical V42.7 router/timeout compatibility checks updated for the superseding unbounded wall: 16/16 PASS
- Python root/UI syntax compile: PASS
Total focused checks: 115 PASS, 0 FAIL.

RECOMMENDED NEXT RUN
Use this V42.57 Jarvis build and resume the best/latest GearTrack checkpoint/source instead of starting the project over. Ask Jarvis to "fix and finish this project". The accepted 14 -> 12 work from the previous run should be preserved in the latest checkpoint you feed it; V42.57 is specifically aimed at the cross-file convergence stall that appeared after that progress.

This release remains language/framework/toolchain agnostic. The new scope logic is based on dependency/runtime/provider evidence and applies equally to other stacks (for example controller/service/repository, provider/native bridge, header/implementation, module/entrypoint, or client/server boundaries).
