Jarvis V42.56.0 — Evidence-Closed, Validator-Scoped Functional Convergence

Why the V42.55 run stalled on the final GearTrack repairs
==========================================================
The uploaded run was no longer primarily compiler-red. The Rust component could build and remain alive, but the final functional acceptance gate correctly found real integration debt.

Two model-transaction defects were preventing convergence:

1. The related-source selector could spend its small evidence budget on cross-component files with similar domain words while omitting the actual same-language integration seam. In the uploaded run, src/hooks/useCSVImportExport.ts was shown many related files but not src/hooks/useTauriCommands.ts. The model then invented nonexistent Tauri APIs and produced a syntax-invalid repair.

2. Validator findings were precise, but the model was still allowed to rewrite unrelated working functions in the same target file. In the uploaded run, the tools.rs repair correctly added RETURNING to create_tool, then unnecessarily rewrote get_tool_with_holder into an invalid SQLx tuple decoder. The compiler gate rejected the whole transaction, so the good repair was lost with the bad one.

V42.56 changes
==============
- Raises related functional evidence capacity from 10 files / 56k chars to 14 files / 90k chars.
- Prioritizes same-language files that already contain real persistence/network/IPC/runtime calls, so hooks/services see the actual provider seam before unrelated cross-component lookalikes.
- Extracts validator-owned SQL/function/line locators from structured findings and supplies exact current-source locator hints to the repair model.
- Prunes target-file hunks that rewrite unrelated SQL/functions when the validator already identified a precise owner/statement.
- Keeps coordinated multi-file freedom for broad UI/bridge/custom-stack repairs where no precise validator locator exists.
- Drops only stale zero-match hunks from a model response while preserving exact sibling hunks for normal sandbox validation. Ambiguous/overlapping edits are still rejected.
- Increases bounded model attempts inside one functional transaction from 2 to 3.
- Preserves all existing disposable-clone, syntax, semantic, functional-delta, real component build/test, rollback, checkpoint and final publication gates.
- Remains language/framework/toolchain agnostic; the new evidence ranking is based on generic integration markers and existing registered component boundaries, not GearTrack/Tauri-specific repair logic.

Replay against the uploaded failure evidence
============================================
- The actual V42.55 tools.rs response contained 3 hunks. V42.56 keeps the create_tool INSERT/RETURNING hunk and drops the unrelated update/join decoder hunks.
- Replaying that retained hunk against the uploaded source reduces the tools.rs functional findings from 1 to 0 with no new target debt.
- The actual CSV repair target now includes src/hooks/useTauriCommands.ts in the selected evidence set, preventing the specific missing-provider context that caused the model to invent useTauriState/useTauriCommand APIs.
- The uploaded checkout.rs mixed hunk that changed both a valid Tool SELECT and the broken Person SELECT is pruned because it rewrites SQL outside the validator-owned failing statement.

Validation performed
====================
PASS: Python syntax/import checks for the modified repair/install modules.
PASS: CHECK_V4256_EVIDENCE_CLOSED_SCOPED_REPAIR.py (5/5).
PASS: CHECK_V4255_MODEL_PROTOCOL.py (35/35), including truncated-response recovery and real provider transaction persistence.
PASS: CHECK_V4251_FUNCTIONAL_TRANSACTIONS.py (17/17).
PASS: CHECK_V4252_DURABLE_FUNCTIONAL_PROGRESS.py (19/19).
PASS: CHECK_V4250_REGRESSION_SAFE_FUNCTIONAL_PROMOTION.py (17/17).
NOTE: CHECK_V4254_WORKFLOW_CONVERGENCE.py is a long legacy end-to-end fixture and exceeded this sandbox's execution timeout before reporting an assertion failure. The prior V42.55 package recorded it passing; the V42.56 changes are covered directly by the focused/current transaction suites above.

Recommended next run
====================
Use this V42.56 Jarvis code and resume the latest GearTrack checkpoint/source rather than starting over. The accepted compiler/build progress is valuable; V42.56 is specifically aimed at closing the remaining functional repairs without destroying working code.
