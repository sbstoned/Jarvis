Jarvis V42.8 Contract Graph Reconciliation + Specialist Takeover

Purpose
-------
V42.8 fixes a convergence-loop class where provider-first repair was correctly
following an incorrect canonical-owner map. The real GearTrack run demonstrated
category.ts being assigned unrelated ownership, which caused repeated repairs of
category/tool/checkout-event providers without any increase in accepted revisions.

Key changes
-----------
1. Accepted-state provider-loop detector
   Temporary/rejected drafts do not reset the loop clock. If canonical providers
   rotate without a new accepted revision, Jarvis escalates the graph itself.

2. New 27B specialist takeover in AUTO
   Contract-graph/root-cause reconciliation is sent to the new Qwen3.8 27B
   HauhauCS Aggressive Q2_K_P specialist. Manual model selections remain locked.

3. Canonical-owner graph reconciliation
   Exact semantic filenames outrank prose aliases. A non-aggregate file cannot
   silently own multiple unrelated domain contracts. Missing dedicated providers
   may be inserted into the frozen architecture.

4. Deterministic simple canonical providers
   Pure entities/enums can be materialized from the frozen contract registry for
   supported languages, eliminating repeated model guesses at field/enum names.

5. Fresh evidence after graph repair
   Repo graph, contract registry, Project KB, build/test diagnostics are refreshed
   before consumer repairs continue.

6. TS2688 module type-root repair
   When TypeScript reports a dependency package incorrectly listed as a global
   type root (including the observed Tauri plugin entries), Jarvis removes that
   invalid type-root entry deterministically and retries the real build.

The final publish policy is unchanged: whole-project build/tests/runtime and
zero unresolved requirement/build debt are still required before ZIP publication.

Exact GearTrack replay (project_20260831_140748)
------------------------------------------------
The attached failed-run architecture was replayed against V42.8. Before repair:
  ui.ToolCondition     -> src/contracts/category.ts
  ui.CheckoutEventType -> src/contracts/checkout_event.ts

V42.8 changes those to:
  ui.ToolCondition     -> src/contracts/tool_condition.ts
  ui.CheckoutEventType -> src/contracts/checkout_event_type.ts

The replay then deterministically materialized/revalidated the canonical provider
set with zero remaining provider-health issues. It also removed the observed bogus
Tauri-plugin entries from TypeScript compilerOptions.types while preserving
vite/client. The V42.3 generic React history debt owner is now planned as .tsx.
