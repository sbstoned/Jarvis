# Production before tests

- Tests are consumers of production contracts, never substitutes for broken production.
- Before repairing an acceptance/integration test, make the production dependency closure syntax/build clean enough to execute the test meaningfully.
- If production has a compiler/parser/provider/config blocker, repair that root cause first and leave test assertions intact.
- Once production compiles, use tests as authoritative behavioral evidence; repair production when correct assertions expose a defect.
