JARVIS V42.25 — SEMANTIC / EVENT-GUARDED / PROVISIONAL MULTI-FILE FACTORY

Purpose
-------
V42.24 correctly recognized connected TypeScript integration failures, but its
per-file candidate helper still replayed the entire known build failure before the
other files in the transaction had been staged. Mutually-dependent repairs could
therefore be rejected one-by-one even though the complete set would improve the
project. The GearTrack runtime snapshot showed exactly this: two coordinated cluster
attempts produced no safe candidate while App.tsx and connected hooks remained the
same blocker family.

V42.25 changes
--------------
1. Provisional multi-file transaction gate
   - Each staged file still passes ownership, syntax, and semantic-role checks.
   - Single-file whole-build no-progress replay is deferred while the cluster is
     provisional.
   - The complete staged project is then typechecked once.
   - Nothing is promoted unless the global TypeScript diagnostic count decreases.

2. Semantic code intelligence
   - Deterministic import/export/reverse-consumer/symbol index is always available.
   - Optional installed language servers can provide read-only hover, definition,
     references, and implementation evidence.
   - No arbitrary JSON-RPC mutation surface is exposed.

3. Global loop hygiene
   - Repair calls are fingerprinted by accepted-repository revision + normalized
     blocker + target + strategy.
   - The default third identical same-revision repair is blocked.

4. Durable event projection
   - JARVIS_PROJECT_JOURNAL.jsonl remains the append-only durable event stream.
   - New V42.25 events carry sequence/id metadata.
   - JARVIS_V4225_EVENT_PROJECTION.json derives compact current convergence state.

5. Context spill
   - When the existing prompt budgeter compacts oversized context, the complete
     pre-compaction prompt is retained in the artifact plane and an inline diagnostic
     index is preserved.

6. Source/artifact plane separation
   - Disposable cluster workspaces and model spill files live beside the project in
     .jarvis_artifacts instead of inside authored source/checkpoint state.

7. Better cluster target selection
   - App/main integration roots remain first when compiler-proven.
   - High-error hooks/services are promoted ahead of low-leverage view cleanup.
   - Stable DTO/type providers remain protected unless compiler evidence names them.

DeepSeek Harness inspiration
----------------------------
The architectural ideas were independently adapted from the open-source DeepSeek
Harness patterns: narrow read-only LSP capability, append-only session/event state,
loop-hygiene guards, tool-output spill retention, and recorded-session regression
thinking. Jarvis remains a Python stack-agnostic software factory and does not vendor
DeepSeek Harness source code.
