JARVIS V42.16 - UNIVERSAL TRANSACTIONAL COMPILE GATE + PRODUCTION-BEFORE-TESTS
================================================================================

PURPOSE
-------
V42.16 fixes a core mutation-safety failure discovered in the latest resumed GearTrack run:
a Qwen direct/patch response containing a terminal `find ...` command was written into
`src-tauri/src/lib.rs` and the orchestration moved on to repairing an acceptance test.

The fix is universal. It is not a Rust/GearTrack special case.

CORE RULE
---------
Every model-written file is a CANDIDATE until the central commit gate accepts it.

candidate -> language parser/syntax gate -> ownership/import/contract gates
          -> exact real-validator replay when applicable -> commit or rollback

A model response by itself is never progress.

V42.16 CHANGES
--------------
1. Strict all-language source gate
   - Removed legacy "accept syntax errors and fix them later" behavior.
   - Obvious terminal commands/prose/Markdown transport contamination are rejected as source.
   - Uses available isolated parsers where safe (e.g. rustfmt parser, gofmt, node --check,
     Ruby/PHP/Swift/Lua/Bash parsers, local TypeScript compiler parser, Python/JSON/JSONC/TOML/YAML).
   - Unknown/custom languages still rely on their declared real component build/test path.

2. Non-Python transactional validator replay
   - The old transaction implementation performed its disposable-clone runtime replay only for Python.
   - V42.16 replays a real build/test failure for non-Python candidate repairs when the failure
     explicitly names the target file.
   - If the exact failure signature remains unchanged, the candidate is rejected and live state is preserved.

3. Production before acceptance-test repair
   - Acceptance/integration tests are consumers, not a workaround for broken production code.
   - Before spending repair budget on a test, Jarvis checks concrete production syntax/provider blockers
     and a safe production-only component command when available.
   - Production/compiler blockers are repaired first; tests become authoritative behavioral evidence
     only after production is executable enough to test.

4. Whole-project language parser audit
   - Whole-project convergence now parses/structurally validates every authored/planned source/config
     before final acceptance, even if an old accepted-revision ledger says the file is green.
   - This catches corrupted baseline/resume files before downstream symptom repair.

5. Atomic direct-edit batches
   - Multi-file direct edits are now an atomic batch at the central green gate.
   - If any changed file fails the universal gate, every file in that batch and the accepted-revision
     ledger are restored to the pre-edit state.

6. Universal priority ordering
   - Language-syntax/production/provider failures outrank test consumers in whole-project repair ordering.
   - Existing canonical ownership, provider-first repair, current-topology resume reconstruction,
     AUTO 9B/new-27B routing, anti-loop watchdogs, and zero-debt final publishing remain enabled.

AUTO MODEL ROUTING
------------------
AUTO worker:     Qwen3.5 9B
AUTO specialist: NEW Qwen3.8 27B Aggressive Q2_K_P
Legacy 27B:      never AUTO-selected; manual only

VALIDATION
----------
- V42.16 regression: 24/24 PASS
- Full inherited + V42.16 regression stack: 656/656 PASS across 21 suites
- Python compileall: PASS (28 top-level Python files)
- Dashboard/AirTouch JavaScript node --check: PASS
- Exact uploaded corrupted lib.rs replay: REJECTED before commit as intended
- Toolchain adapters: 73
- Skill cards: 90
- Strict final zero-debt publish gate: preserved
