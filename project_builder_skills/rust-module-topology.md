# Rust module topology

- Resolve `crate::foo` to `src/foo.rs` OR `src/foo/mod.rs` from actual crate topology.
- Resolve `crate::foo::bar` to `src/foo/bar.rs` when that semantic module exists.
- Never synthesize `foo.rs` when `foo/mod.rs` is already the canonical module root.
- Reexports from `mod.rs` are consumers/barrels, not permission to redefine child domain structs/enums.
- Compiler/Cargo module resolution outranks heuristic symbol-reference edges.
