JARVIS V42.20 - INFRASTRUCTURE-AWARE, DISK-BOUNDED BUILD-FIRST CONVERGENCE

This release is based on the stopped GearTrack V42.19 run from 2026-09-02. That run proved the Rust/Tauri component could compile, test, and smoke successfully, but React validation was blocked by a Jarvis Windows npm.CMD launcher defect. The run also produced excessive rebuildable data and carried stale planner-generated acceptance-test debt.

KEY FIXES
- Fixed Windows npm/npx/.cmd launch quoting: trusted batch shims use constrained `cmd /d /s /c call` with the executable path kept as its own argv token. Raw model-requested shell payloads remain blocked.
- Added infrastructure-vs-source failure classification. Broken tool invocation, missing executable/SDK, sandbox/CWD rejection, WinError 2 and spawn ENOENT do not trigger application source repair or 27B source analysis.
- Soft planner-only acceptance tests are retired before every authoritative audit unless the user explicitly asked Jarvis to create tests.
- Prior Jarvis-generated acceptance files marked as test requirement debt are also retired/quarantined when they were optional. Genuine user-authored existing tests remain enforced.
- Resume trials now share one rebuildable build/dependency cache rather than creating a separate Cargo/npm cache per trial.
- Validation Cargo builds default to CARGO_INCREMENTAL=0 and debug symbols disabled to reduce Tauri/Rust disk growth.
- Accepted trials are stripped of node_modules/target/build/runtime build caches before becoming the authoritative source checkpoint.
- Final/checkpoint packaging removes the shared build cache so generated_projects does not retain multi-GB build debris.
- Default convergence budgets tightened: 3 whole-project rounds, 2 resume sweeps, 180s fast-worker call, 300s 27B call, 300s file-generation wall, 240s file-repair wall. Explicit environment overrides remain available.
- The generic resume phrase “make its existing tests/build pass” no longer means “create missing tests.”

GEARTRACK STOPPED-RUN REGRESSION
- Exact npm.CMD spaced-path failure is classified as infrastructure.
- The old pre-quoted one-string /c command is not used.
- Stale tests/acceptance.test.tsx debt is removed.
- Existing Jarvis-generated src-tauri/tests/acceptance_2.rs test debt is removed when tests were not requested; this file was inconsistent with the SQLx backend.
- Rust/Tauri production source remains untouched by that QA cleanup.

VALIDATION
- V42.20 regression suite: 48/48 PASS.
- All Python modules compile.
- V42.15 topology suite: 22/22 PASS.
- V42.13 progress-watchdog suite: 26/26 PASS.
- V42.12 resume-isolation suite: 21/21 PASS.
- V42.11 ZIP-import suite: 25/25 PASS.
- V42.9 whole-project audit suite: 18/18 PASS.
- Historical V42.19/V42.18/V42.17/V42.16 identity assertions naturally report the newer V42.20 identity. V42.6's automatic second-leaf 27B promotion and V42.7's 12+ minute specialist watchdog expectations are intentionally superseded by V42.19/V42.20's build-evidence routing and bounded time budgets.
