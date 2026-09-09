# Contract Graph Reconciliation

Use this skill when canonical model/type/schema ownership itself may be inconsistent.

- Treat accepted revisions plus the frozen contract registry as the durable truth; rejected drafts do not prove progress.
- If several provider files rotate with no accepted-state change, stop leaf repair and audit the ownership graph itself.
- Prefer an exact semantic provider (`tool_condition.*` for `ToolCondition`) over prose mentions or compatibility aliases in unrelated files.
- A semantic provider such as `category.*` must not silently become owner of unrelated contracts unless it is an intentional aggregate `types`, `domain`, `models`, `contracts`, `entities`, `enums`, or schema module.
- One canonical owner is allowed per component/language. Cross-language representations may each have their own owner.
- If the frozen plan omitted a dedicated provider and the current owner is contradictory, add the provider to the plan before repairing consumers.
- Simple frozen entities/enums may be regenerated deterministically from the contract registry. Do not invent fields or enum values.
- Rebuild/retest after provider/graph changes. Repair consumers only from fresh diagnostics.
- Never weaken tests, remove required behavior, or publish unresolved graph/build debt.

## V42.22 consumer-first compiler ownership

- Fresh compiler locations outrank heuristic owner/provider graphs.
- Do not rotate through every provider in the same component merely because it is canonical or shared.
- A parse-clean accepted semantic DTO/type provider is read-only by default.
- Repair the consumer/caller/component/hook first for prop, argument, generic, and ordinary member-use errors.
- Mutate a stable provider only when compiler evidence explicitly identifies its module/export/provider contract (for example TS2305/TS2307/TS2459/TS2724) or the provider file itself fails syntax/implementation validation.
- After one accepted consumer repair, rebuild before selecting another owner. Never make multiple source edits from stale compiler evidence.
