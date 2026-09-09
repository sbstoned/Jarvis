# Resume State Reconstruction

When Jarvis is asked to continue an attached existing project, the repository itself is the current authority.

- Treat historical Jarvis metadata as migration evidence, not as current-engine truth.
- Re-detect components/toolchains from real manifests and source roots.
- Rehydrate frozen requirements and domain contracts when available.
- Rebuild canonical ownership from actual semantic provider files.
- Prefer directory module topology when it exists (`types/`, Rust `foo/mod.rs`) over stale flat aggregate provider names.
- Remove objective duplicate nested component roots when a canonical counterpart exists.
- Bind imported authored files as the baseline revision; audit them, do not regenerate them merely because an old accepted ledger is missing.
- Rebuild repo graph, contract registry, component graph, Project KB, and current repair state before model-driven repairs.
- Reconcile deterministic manifest/lock/target inconsistencies before asking the model to redesign source code.
- A historical owner map, failure signature, or repair loop must never override current source topology and current compiler/build evidence.
