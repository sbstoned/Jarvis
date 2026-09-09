# Functional acceptance and convergence

A successful build is necessary but is not proof that the requested software works.
Treat functional completion as a dependency graph:

1. **Providers and persistence first.** Repair schema/DML/serialization/service/provider contracts before callers or entry files.
2. **Production integration second.** Replace mock/demo/local-only services with the project's existing real backend, IPC, API, storage, or platform seam while preserving public APIs.
3. **Runtime bridge/state third.** Wire only commands/routes/handlers that are reachable from executable production code. Identify the actual runtime entry/delegation path before editing it. Reuse existing provider functions; do not move domain logic into main/app/lib entry files.
4. **Workflow proof last.** Add meaningful tests that execute real behavior through a public boundary and verify observable state/results. Never weaken tests to get green.

Repair strategy:
- Prefer the smallest exact patch over whole-file regeneration.
- Group related defects in one target coherently.
- If the same unchanged target and issue family fails bounded patch attempts, rotate to other independent work instead of continuing/rephrasing/retrying indefinitely.
- Rebuild and re-audit after every accepted source change.
- Framework-specific adapters may provide evidence (IPC commands, routes, schema, etc.), but the core policy is stack-agnostic.
