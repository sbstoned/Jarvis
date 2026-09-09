Jarvis V42.35 - Candidate Runtime Parity + Verified Universal Convergence

Root cause fixed
- Repair candidates were copied to an external artifact directory while node_modules was excluded.
- The original tsc executable then compiled that dependency-less candidate.
- A correct 8-error GearTrack repair appeared to create 57-64 new React/Vite/module errors, so Jarvis rejected it.
- V42.30's regression checked generated text but did not execute this real external-candidate compiler path.

V42.35 behavior
1. Disposable TypeScript candidates reference the accepted component's restored dependency tree by symlink or Windows directory junction; dependencies are never copied into source or ZIPs.
2. Source-diff scanning prunes links/junctions and cannot enumerate or package node_modules.
3. A missing-dependency diagnostic avalanche in a candidate is classified as validator infrastructure, not a source regression and not a reason to ask Qwen to rewrite application code.
4. A bundler alias that build evidence proves is shadowing a declared package namespace is removed deterministically, while unrelated application aliases are preserved.
5. A declared Node test command can no longer coexist with zero executable test owners. Native "no tests found" evidence adds an explicit manifest-owned test; React/Vitest gets a safe production-import smoke seed, while other stacks continue through normal model-driven test generation. If the original/current prompt explicitly requests tests, Qwen implements the requirement-specific test instead of accepting the generic smoke seed.
6. Existing tests are never hidden by this rule. If test files already exist, Jarvis treats "no tests found" as a runner/filter configuration defect instead of adding a second test.
7. Resume last-mile repair runs the already-transactional constraint solver from the authoritative workspace. Source still commits only after a fresh native compiler proves a strict improvement.
8. Resume uses up to four bounded sweeps by default, while existing no-progress and same-revision loop guards remain active.
9. When an accepted transaction changes the file named by a projected blocker, that stale blocker is invalidated and the projection requires a fresh whole-project validation. Only a real green audit clears validation-pending state.
10. A successful compile remains an intermediate milestone. Jarvis continues through tests, runtime smoke, integration/contract checks, and explicit requirements.
11. Both project modes remain available: create a new project from a prompt, or attach an existing/checkpoint ZIP and request fixes, completion, or feature edits.
12. The architecture remains stack-agnostic. The runtime-parity bridge fixes the concrete TypeScript candidate validator defect without making React, Tauri, or GearTrack the universal planner. Non-TypeScript adapters retain their native restore/build/test gates and custom components retain declared verification commands.

Important upgrade step
- Fully close the existing Jarvis window/process before starting V42.35.
- JARVIS_ACTIVE_ENGINE.txt must read V42.35.0. The boot guard refuses new project work if disk files and the running engine do not match.
