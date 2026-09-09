Jarvis V42.4 Provider-First Fast Global Convergence
====================================================

Purpose
-------
V42.4 addresses the overnight-convergence failure pattern where Jarvis repeatedly
patched multiple consumers while a shared canonical provider was missing or had
never reached an accepted revision.

Key changes
-----------
1. Canonical-provider health prepass before global acceptance and runtime diagnosis.
2. Consumer repairs are rerouted to unhealthy canonical providers first.
3. Planned providers are injected into subsystem repair even when missing from the live repo graph.
4. TypeScript/JavaScript same-stem emitted import aliases (e.g. ./types.js -> planned ./types.ts)
   are recognized by the architecture dependency gate.
5. Default focused leaf patch attempts reduced from four to two before escalation.
6. Runtime repair target fan-out reduced by default to three root-cause candidates.
7. Repair wall time reduced by default to eight minutes per target (environment override supported).
8. Repair prompts receive focused prefill compaction; planning/generation/audit budgets are unchanged.
9. Added dependency-graph-repair, type-contracts, and fast-convergence skill cards.
10. V42.3 progressive build debt + strict global zero-debt publish gate remain intact.

Universal design
----------------
Provider-first behavior is not TypeScript-specific. The same root-cause rule applies
to C/C++ headers, Rust model modules, Java interfaces/classes, C# contracts, Go
packages, Python schemas, Swift protocols/models, database schemas, generated API
contracts, and custom toolchains.

Environment overrides
---------------------
JARVIS_V424_PROVIDER_FIRST=0             disable provider-first prepass
JARVIS_V424_FAST_REPAIR=0                restore inherited repair breadth/time defaults
JARVIS_V37_PATCH_CANDIDATES=N            explicit leaf patch candidate count
JARVIS_QWEN_RUNTIME_REPAIR_TARGETS=N     explicit runtime target fan-out
JARVIS_QWEN_FILE_REPAIR_WALL_SECONDS=N   explicit per-file repair timebox
JARVIS_V424_REPAIR_PROMPT_TOKENS=N       focused leaf repair prefill target
JARVIS_V424_SUBSYSTEM_PROMPT_TOKENS=N    subsystem repair prefill target
