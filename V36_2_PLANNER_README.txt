JARVIS V36.2.0 - CHUNKED HIERARCHICAL PLANNER / DEPENDENCY CLOSURE
====================================================================

V36.2 is the recommended replacement for V36.1.

WHY THIS RELEASE EXISTS
-----------------------
A real V36.1 TaskForge run exposed the remaining bottleneck: a large full-stack architecture request could exceed the model watchdog, after which the inherited V34 recovery path created an undersized 11-file manifest. Jarvis then spent a long time implementing and repairing a repository that was structurally incomplete.

V36.2 moves the completion gate before implementation.

NEW PROJECT PIPELINE
--------------------
1. Freeze a deterministic source-requirement ledger from the original prompt.
2. Compile the ledger into machine-owned requirements while preserving every source requirement.
3. Plan product/components in a small bounded architecture call.
4. Plan each buildable component independently in bounded calls.
5. Merge cross-component contracts.
6. Run a dependency/provider closure review before source generation.
7. Reject suspiciously-small/incomplete complex architectures instead of building them.
8. Materialize contract skeletons only after the architecture gates pass.
9. Generate in dependency order with the existing V36 transactional/patch/validation engine.

TASKFORGE-SPECIFIC FAILURES NOW COVERED
---------------------------------------
- React/Vite + FastAPI remains two independent components.
- A complex planner failure no longer falls back to an 11-file demo architecture.
- Plain one-per-line acceptance requirements are frozen even if copy/paste removed bullets/numbers.
- Requirement coverage can no longer report a vacuous 100% from 0 source requirements.
- tsconfig.json is validated as JSONC (comments and trailing commas allowed); package.json remains strict JSON.
- Planned depends_on paths must exist before implementation.
- Generated Python/TypeScript internal imports must resolve to files in the frozen architecture.
- Generated Node/TypeScript bare package imports must be declared in package.json once the manifest exists.
- A failed component planner retries in a smaller bounded call; if it still fails, Jarvis stops before implementation instead of knowingly building a partial project.

PERFORMANCE INTENT
------------------
V36.2 deliberately trades one giant high-risk architecture call for several smaller calls. For a two-component full-stack project the expected architecture flow is roughly:
- requirements compiler
- component overview
- frontend plan
- backend plan
- dependency closure

Each output is bounded and much smaller than the previous complete-manifest response. This is intended to work better with the local Qwen3.5 9B model and the existing six-minute watchdog.

LEGACY RECOVERY
---------------
The inherited tiny V34 recovery path is disabled by default in V36.2. It can be explicitly re-enabled only for diagnostics with:
  JARVIS_V362_ALLOW_LEGACY_TINY_RECOVERY=1
This is not recommended for normal project generation.

VERIFY
------
Run:
  CHECK_V362_ALL.bat

The suite includes the inherited V36 tests, V36.1 real-run tests, and V36.2 planner/dependency-closure regressions.
