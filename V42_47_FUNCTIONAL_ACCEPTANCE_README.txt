JARVIS V42.47.0 — FUNCTIONAL ACCEPTANCE CONVERGENCE

V42.46 proved that Jarvis can converge real compiler failures and reach a green
build. V42.47 closes the next failure mode: a project may compile, test a trivial
smoke assertion, and stay alive while its actual user workflows are not wired.

Publication is now blocked by concrete functional contract debt, including:
- frontend/backend runtime calls with no registered handler contract;
- application state/persistence initialization that is never installed in the runtime;
- production hooks/services that explicitly retain mock/demo/simulated behavior;
- SQL DML that references columns absent from the declared schema;
- SQLx INSERT/UPDATE decoded with fetch_one without RETURNING (or a follow-up SELECT);
- string "null" persisted where SQL NULL is intended;
- explicit SQLx FromRow SELECT projections that omit required struct fields;
- cross-boundary projects whose integration tests only prove a symbol exists.

These findings are emitted into the ordinary whole-project audit and therefore use
Jarvis's existing bounded repair, compiler/build validation, checkpoint, and
circuit-breaker machinery. They are not GearTrack hardcodes. Tauri/SQLx are
conservative adapters inside a general runtime-seam/persistence-contract layer.

A project can be published only after ordinary build/test/runtime validation AND
this functional audit are clean. V42.46 compiler convergence remains preserved.

Repair routing: functional/persistence findings get a dedicated one-change-at-a-time dispatch before inherited fallback strategies; each accepted change is followed by fresh build/test/runtime/functional audit evidence.
