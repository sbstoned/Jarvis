JARVIS V42.19 - FAST BUILD-FIRST CONVERGENCE
============================================

Purpose
-------
V42.19 fixes the overnight/non-converging behavior observed after V42.18. It keeps the transactional repository protection and blocker-first repairs, but removes several contradictory or unnecessarily expensive paths that could keep a project running for hours.

Primary fixes
-------------
1. Routine source/test generation stays on the fast 9B worker. The word "acceptance" no longer promotes a normal test-file write to the slow 27B specialist.
2. The 27B specialist is reserved for fresh compiler/build-backed architecture or root-cause problems.
3. Per-file LLM semantic audit is OFF by default. Real compiler/build/test/runtime evidence is the authority.
4. Default convergence budgets are tighter: acceptance rounds <=5, no-progress rounds <=2, worker calls <=240s, 27B calls <=360s, file repair wall <=360s, file generation wall <=480s (unless explicitly overridden).
5. Planner-invented missing test source is soft by default. Existing tests still run; explicitly requested tests are still generated. This prevents expensive acceptance-test generation from delaying a normal project build.
6. Persistent topology tombstones reconcile Rust file-vs-directory modules. Once models/mod.rs is canonical, stale models.rs debt cannot be resurrected by another ledger/audit pass.
7. Project-level target "." is never routed into source-file generation.
8. Node import parsing accepts only plausible bare package specifiers, preventing parser artifacts such as "." or "|" from becoming fake npm dependencies.
9. Stale package-lock.json is detected deterministically and reconciled with the resolved project/system npm tool.
10. Conventional Tauri icon.ico/PNG assets are materialized deterministically before Cargo/Tauri validation.
11. Windows .cmd/.bat project/package-manager shims can be executed through a tightly constrained internal wrapper; model-requested shell execution remains blocked and batch arguments containing cmd metacharacters are rejected.
12. Project-local tools (tsc/vite/vitest/eslint/wrappers/venvs) continue to outrank unrelated global tools.

Expected behavior
-----------------
Jarvis should spend its time changing the repository and rerunning real component/project validation, not repeatedly generating QA files or asking a large model to reason about already-settled topology. When no accepted-state/error delta occurs for the bounded no-progress window, it must change strategy or stop with the exact blocker rather than run indefinitely.

Validation
----------
- V42.19 regression suite: 45/45 PASS
- V42.15 Rust topology suite: 22/22 PASS
- All 32 Jarvis Python source files compiled successfully.
- Older V42.18/V42.17/V42.16/V42.0 suites retain all functional checks; their only current failures are release-identity assertions because this package intentionally reports V42.19.
