Jarvis V42.21 - Semantic Role / Error Delta / Real Entrypoint Gate

Primary regression fixed:
- A syntactically valid but semantically unrelated Vite config could replace a React component such as InventoryView.tsx.
- Placeholder main.tsx could keep a process alive while the real App was not mounted.
- Trivial TypeScript defects (redundant exports, missing React hook imports) could consume repeated model repair rounds.
- A candidate repair did not always have to demonstrate measurable TypeScript compiler improvement before commit.

V42.21 behavior:
- React component paths preserve planned component identity and renderable UI semantics.
- Vite/build configuration is rejected when proposed for a React UI component/type provider.
- Planned hook/service dependencies cannot all disappear in a broad unrelated replacement.
- Placeholder React entrypoints are rejected; deterministic recovery mounts the real App when unambiguous.
- Redundant TypeScript re-exports and missing React hook imports are repaired deterministically before model work.
- TypeScript repairs use a bounded pre-commit error-delta overlay when reliable dependency substrate is available.
- Same blocker/model-family work is capped per accepted repository revision.
- Whole-project convergence defaults to two global rounds; routine worker and specialist call ceilings are tightened.
- V42.20 infrastructure routing, Windows npm.cmd handling, cache pruning, topology tombstones, transactional compile gates, runtime sandboxing, and build-first validation are preserved.
