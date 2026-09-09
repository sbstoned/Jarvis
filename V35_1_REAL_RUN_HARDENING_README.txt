JARVIS V35.1.0 - REAL-RUN HARDENING
=====================================

This release is built from V35.0.4 and incorporates failure evidence observed in the older V34.1 StockPilot baseline run.

WHAT CHANGED
------------
1. Legacy transport-marker salvage
   - Exact outer lines such as:
       ===== END FILE StockPilot/app/database.py =====
     are stripped before source validation.
   - Valid candidates are salvaged deterministically instead of forcing an expensive Qwen rewrite.

2. Architecture collision gate
   - Detects likely duplicate authoritative providers before implementation.
   - Example caught:
       inventory_service.py -> InventoryService
       StockPilot/app/service.py -> InventoryService
   - The architecture is sent back for correction before code generation proceeds.

3. Correct live status identity and counts
   - Build status now reports V35.1.0 / UNIVERSAL_COMPLETION_ENGINE.
   - implemented_source_files is derived from the actual workspace rather than a stale caller counter.
   - Status includes planner mode, validation mode, component count, and detected context capacity.

4. Class-level member awareness
   - Static Python contract analysis now recognizes class constants/attributes such as InventoryView.COLUMNS.
   - Prevents repeated false repairs of valid class-level members.

5. Evidence-first repair preflight
   - When only lower-confidence class-member findings remain, Jarvis executes the real tests/build/startup first.
   - Concrete tracebacks/test failures are repaired before speculative static member reconciliation.

6. StockPilot-shaped call-signature detection
   - Concrete local calls such as db.insert_item(item) are checked against the actual provider signature.
   - Caller/provider arity drift is routed as a deterministic call-signature contract failure.

7. Framework-aware JavaScript tests
   - Vitest: forced to `vitest run`
   - Jest: forced to `--runInBand --ci`
   - React Scripts: forced to `--watchAll=false`
   - Playwright: noninteractive test invocation
   - Angular: `--watch=false`
   - Mocha/Node test runner: CI environment enabled
   - Prevents validation from hanging in watch mode.

8. Bounded hierarchical component refinement
   - Small single-component projects keep the fast path.
   - Large (default >=60 files) or multi-component repositories receive per-component architecture refinement.
   - Nested component ownership is resolved by the deepest component root.
   - Component refinement is bounded to avoid runaway planning cost on the local 9B model.

9. Existing V35 completion protections retained
   - Multi-component build validation
   - Clean Python venv validation
   - Strict PASS vs UNVERIFIED host-toolchain behavior
   - Real dependency/build/test validation
   - Runtime smoke checks
   - Deterministic acceptance tests
   - No-op/fake test rejection
   - Windows setup/build/run launchers

SELF TEST
---------
Run:
    python CHECK_V351_UNIVERSAL_BUILDER.py

or double-click:
    CHECK_V351_UNIVERSAL_BUILDER.bat

The release validation used 34 deterministic regression checks plus actual clean Python and Node build/test validation.

RECOMMENDED BENCHMARK
---------------------
Let the current V34.1 StockPilot baseline finish and save its final ZIP/journal.
Then run the SAME original StockPilot prompt on V35.1.0 and compare:
- plan/file count
- duplicate providers
- failed candidates
- repair calls
- total time
- test/build results
- runtime startup
- final acceptance result
