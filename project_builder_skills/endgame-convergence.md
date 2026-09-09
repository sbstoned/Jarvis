# Endgame convergence

Use this skill during late integration, acceptance-test creation, and whole-project repair.

- A requirement owner is allowed to become the artifact that satisfies its own requirement. Never require `tests` to be already satisfied before accepting the real test that satisfies it.
- Tests consume production contracts and behavior. Never copy/redeclare production models, DTOs, enums, records, schemas, interfaces, or structs inside tests merely to make a test compile.
- When a test cannot import production code, repair module/public API reachability rather than cloning the production definition.
- Every real test must use the native project test runner, reference production code, execute a test case, and contain meaningful assertions.
- Conventional build/test configuration should be deterministic where its semantics are stable; do not waste model retries producing malformed JSON boilerplate.
- A compiler/analyzer must use the project's installed compiler/toolchain, never an unrelated package fetched because a command name happened to collide.
- Whole-project convergence validates every independent component in the same audit round. One failing component must not hide another.
- For Rust, ensure planned production modules are reachable from the crate root so `cargo check` and `cargo test` compile the actual authored code.
- Prefer root-cause fixes that collapse many downstream errors. Do not lower final acceptance standards.
