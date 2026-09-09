Jarvis V42.26 - Compiler-Proofed Dependency-First TypeScript Convergence

Primary V42.25 failure fixed:
V42.25 staged connected files together, but its final cluster commit still replayed an older per-file whole-project no-progress transaction gate. A globally improving multi-file candidate could therefore be rejected because one individual file did not make the whole project green by itself. V42.26 removes that contradictory final leaf replay. A cluster that strictly reduces the fresh real TypeScript diagnostic count, passes content validation, and preserves semantic file roles is committed atomically.

Additional convergence changes:
- Dependency-first cluster execution: hooks/services are repaired before components and App/main integration roots.
- Six compiler-owned model files per coordinated transaction by default.
- Signature-directed TS2554 missing-argument repair.
- Signature-directed TS2345 wrong-argument replacement when the compiler's expected type and an in-scope producer agree.
- TS2339 missing member alias reconciliation such as createThing -> createThingCommand without mutating the provider.
- Response<T>.data unwrapping for React state setters when the wrapper contract proves a data field exists.
- Compiler-proven unused parameter/function/local cleanup.
- Side-effecting unused initializers are preserved with void rather than silently dropped.
- String true/false object fields are corrected to booleans when fresh TS2322 evidence proves the target property is boolean.
- Structural fixes protect symbols that stale TS6133 diagnostics would otherwise remove in the same compiler snapshot.
- Fresh whole-project TypeScript measurement remains the acceptance authority.

The changes are stack-agnostic at the supervisor level. The added deterministic fixes activate only for matching TypeScript compiler diagnostics and do not hard-code GearTrack filenames or domain models.
