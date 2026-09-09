JARVIS V42.43.0 - SQLX LAST-MILE + STRATEGY-GENERATION CONVERGENCE

Purpose
-------
V42.43 preserves V42.42.2 revision/component circuit breakers while fixing a real
last-mile convergence failure observed on the GearTrack checkpoint.

Changes
-------
1. Generic SQLx joined-struct repair
   - Detects rustc E0277 where SQLx is asked to decode a normal FromRow struct as
     one scalar tuple member, e.g. (Struct, Option<T>).
   - Repairs the query/use site by fetching a raw SQLx row and reconstructing the
     struct from named columns plus the joined/aliased extra column.
   - No GearTrack, Tool, checkout, or application-specific names are hardcoded.
   - Exact component build validation must improve before any source is promoted.

2. Compiler ownership correction
   - SQLx composite FromRow errors prioritize the primary query site over help/note
     definition locations. Ordinary provider-first trait errors keep prior behavior.

3. Strategy-generation-aware circuit breakers
   - JARVIS_REPAIR_STRATEGY_GENERATION scopes V42.41 deterministic/model attempts,
     V42.37 semantic-no-delta exclusions, and V42.43 revision exhaustion.
   - A genuinely new strategy generation can reopen an unchanged accepted revision
     once. Restarting the same release/strategy cannot.

4. Resume guidance
   - Resume the existing GearTrack checkpoint. Do not start the project over.
   - The V42.42.2 exhausted state is retained as history but no longer blocks the
     new SQLx strategy from one validator-gated attempt.

Acceptance rule
---------------
A deterministic or model patch is never accepted merely because it looks correct.
The exact failing component validator must pass or strictly reduce diagnostics, and
normal whole-project acceptance gates remain unchanged.
