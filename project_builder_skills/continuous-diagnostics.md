# Continuous diagnostics

- Treat every accepted edit like an IDE save: immediately re-check syntax, self-imports, internal dependencies, canonical ownership, and file-local contract rules.
- Keep diagnostics attached to the current accepted revision; drafts and rejected candidates are not progress.
- Once a component has enough accepted source to produce meaningful compiler/analyzer evidence, run its fast incremental analyzer through Jarvis's command broker.
- If a previously green or nearly complete component regresses, repair the exact analyzer evidence immediately and re-run it once.
- Do not interpret errors caused only by intentionally unmaterialized future files as proof that a partial component is irreparable.
- Periodic component validation and the final whole-project audit remain stricter than per-edit diagnostics.
