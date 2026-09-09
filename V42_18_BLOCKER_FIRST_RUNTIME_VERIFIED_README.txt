JARVIS V42.18 - BLOCKER-FIRST RUNTIME-VERIFIED CONVERGENCE
===========================================================

Purpose
-------
V42.18 fixes the repair-loop behavior observed in the uploaded GearTrack runtime while preserving the V42.16 transactional compile gate and V42.17 repository-protection/convergence controls.

Observed root cause from the uploaded runtime
---------------------------------------------
1. InventoryView.tsx contained a mechanically provable duplicated JSX input fragment.
2. V42.17 already had a safe deterministic JSX repair, but it only ran after subsystem exhaustion.
3. Before exhaustion, the patch model was shown line-numbered source. Qwen copied viewer numbers into SEARCH blocks, attempted oversized rewrites, and sometimes returned incomplete blocks.
4. Jarvis could therefore spend bounded repair passes on the same Inventory blocker before reaching the deterministic repair that could have solved it immediately.
5. Missing tsconfig.node.json also prevented the real frontend build from becoming the authoritative next source of errors.

V42.18 changes
--------------
- Deterministic syntax repair gets first refusal before model/subsystem repair.
- Exact edit prompts use compact raw, unnumbered source windows.
- Legacy line-numbered SEARCH/REPLACE blocks are detected and normalized before parsing/applying.
- Explicit same-revision repair ladder:
  deterministic repair -> bounded transactional leaf/subsystem -> fresh root-cause strategy -> authoritative build/audit.
- The same failed model/subsystem family is not re-entered at an unchanged accepted repository revision.
- One authoritative current blocker is persisted from fresh audit/build evidence.
- Error-delta tracking records whether accepted edits reduce the real error set.
- Repeated unchanged audits are marked stalled rather than treated as progress.
- Successful production checks are cached by accepted repository revision; red checks are never cached as green.
- Missing conventional TypeScript/Vite substrate such as tsconfig.node.json and index.html is restored deterministically when the repository proves it is required.
- Referenced deterministic PNG/ICO assets retain V42.17 recovery.
- Real build/test validation remains authoritative, followed by bounded runtime/startup smoke where a safe launcher exists.
- The existing acceptance-test generation/requirement system is retained and tied to a final V42.18 acceptance contract based on the original user request.
- Project-local tools are discovered: Gradle/Maven wrappers, Python virtualenv executables, and node_modules/.bin TypeScript/Vite/Vitest/ESLint CLIs.

Sandbox / command broker improvements
-------------------------------------
- Commands must execute inside the resolved project root by default.
- Direct cmd/PowerShell/bash/sh shell payloads are blocked by default; explicit opt-in exists for trusted cases.
- Provider/API credentials are removed from generated-project environments by default.
- Timed-out commands terminate the full spawned process tree.
- Project-local dependency/build caches remain isolated under .jarvis_runtime.
- Docker/WSL remain optional stronger backends where appropriate.
- Native-controlled mode is intentionally NOT described as a VM/security boundary; it is a constrained project execution layer.

Uploaded GearTrack regression result
------------------------------------
On a copy of the supplied .jarvis_runtime snapshot, V42.18:
- repaired the malformed InventoryView.tsx before any model retry;
- reduced the duplicated search input value fragment from 2 copies to 1;
- produced parser-clean InventoryView.tsx;
- restored missing tsconfig.node.json;
- generated a reference-compatible tsconfig.node.json (the first draft caught during testing used noEmit and was corrected after the real compiler exposed TS6310);
- advanced npm run build past the old TS5058 missing-tsconfig blocker and the Inventory parser blocker.

The resulting real build then exposed 39 ordinary TypeScript semantic/integration errors across 10 files (App.tsx, components, and hooks). This is expected evidence for the next repair stage: V42.18 now has fresh compiler blockers to work down rather than looping on the malformed Inventory fragment.

Validation
----------
- CHECK_V4218_BLOCKER_FIRST_RUNTIME.py: 43/43 PASS
- CHECK_V4217_EXHAUSTED_BLOCKER_CONVERGENCE.py: 20/20 PASS
- CHECK_V4216_TRANSACTIONAL_COMPILE_GATE.py: 24/24 PASS
- CHECK_V4215_RUST_TOPOLOGY_RESUME_AUTHORITY.py: 22/22 PASS
- CHECK_V420_CAPABILITY_SANDBOX.py: 20/20 PASS
- Python compileall over the complete Jarvis source tree: PASS

Important expectation
---------------------
No general software agent can guarantee every arbitrary project will be error-free on the first model response. V42.18 is designed so model mistakes become bounded engineering work: preserve accepted code, identify a real blocker, change strategy when progress stops, rerun the actual build/test gate, smoke-test supported runtimes, and publish only when the final acceptance gate is clean.
