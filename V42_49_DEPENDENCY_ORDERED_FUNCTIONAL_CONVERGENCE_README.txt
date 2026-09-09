Jarvis V42.49.0 - Dependency-Ordered Functional Convergence

Why V42.49 exists
------------------
V42.48 correctly removed backup/checkpoint ghosts and bounded whole functional rounds,
but a real GearTrack run exposed two deeper convergence problems:

1. the hardest integration root was scheduled before smaller provider/persistence work;
2. one functional "attempt" could expand through older repair layers into whole-file
   rewrites, truncated continuations, diagnosis, and subsystem escalation.

The same run also exposed a stack-adapter ownership bug: the Tauri auditor preferred
src-tauri/src/lib.rs even when src-tauri/src/main.rs directly owned the running Builder.

V42.49 changes
--------------
- dependency order: provider/persistence -> production integration -> runtime bridge -> workflow tests;
- actual runtime entry/delegation detection for Tauri instead of blindly preferring lib.rs;
- reachable-command tracing: dormant helper declarations do not force unused backend handlers;
- provider-contract evidence can be added when a reachable command has no domain provider operation;
- functional retries are keyed by target bytes + stable issue family, not changing diagnostic prose;
- unrelated accepted changes cannot reopen the same unchanged hard target;
- functional primary repair is patch-only; no automatic whole-file rewrite/continuation/subsystem sweep inside one attempt;
- exhausted hard targets rotate out so independent repairs can proceed;
- V42.48 live-source filtering, compiler convergence, warm Cargo proof, transactional safety, checkpointing, and strict final acceptance remain preserved;
- core behavior stays language/framework/toolchain agnostic; stack adapters only supply evidence.
