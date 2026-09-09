JARVIS V42.58.0 - CONNECTED FUNCTIONAL CLUSTER CONVERGENCE
==========================================================

Purpose
-------
V42.57 correctly expanded late-stage repair evidence and removed the absolute
8-minute active Qwen stream wall clock, but remaining functional defects could
still be scheduled and judged by one arbitrary "primary" file. A legitimate
multi-file repair could therefore improve a connected peer (for example a
provider or runtime owner) and still be rejected because the original primary
file's issue count did not decrease in that exact candidate.

V42.58 changes the repair/progress unit from one primary file to a small,
evidence-connected functional cluster.

Key changes
-----------
1. Evidence-connected repair clustering
   - Same language alone is NOT enough to cluster files.
   - Edges require concrete topology/integration evidence: direct module/entity
     references, a shared persistence entity/table, or same-layer production
     mocks that independently identify a shared real integration seam.
   - Clusters are bounded to 6 issue-owner files and complete source is required.

2. Cluster-level progress
   - Every validator-owned issue file in the cluster is tracked independently.
   - A candidate may be promoted when the total owned cluster debt strictly
     decreases and no issue owner regresses, even when the arbitrary first file
     in the cluster is unchanged.
   - New unrelated functional debt is still rejected.

3. Per-owner validator scope
   - Structured SQL/compiler ownership locators are applied independently to
     every issue-owning file in a coordinated transaction.
   - Unrelated hunks remain pruned; exact-current-source replacements are still
     required.

4. Independent-target starvation protection
   - Unconnected files remain independent repair targets.
   - A failed cluster does not prevent later independent clusters from being
     attempted in the same audit round.

5. Durable rejected-trial evidence
   - Before an unimproved disposable resume trial is deleted, bounded rejection
     metadata is retained in JARVIS_V4258_REJECTED_TRIAL_EVIDENCE.json.
   - Rejected trial source is NEVER copied into the accepted workspace.
   - The retained evidence includes transaction ledger state and bounded model
     response receipts/hashes, allowing the next resume to diagnose non-progress.

6. No absolute active-stream timeout remains
   - The V42.57 policy is preserved: useful Qwen streams may run longer than
     8 minutes with no Jarvis wall-clock cutoff.
   - Dead/idle stream handling and cooperative user Stop remain enabled.

GearTrack checkpoint replay
---------------------------
The uploaded GearTrack resumable checkpoint is scheduled as:

  Backend cluster:
    src-tauri/src/checkout.rs
    src-tauri/src/tools.rs
    src-tauri/src/main.rs

  Frontend integration cluster:
    src/hooks/useCSVImportExport.ts
    src/hooks/useCategories.ts
    src/hooks/useCheckouts.ts
    src/hooks/usePersons.ts

  Workflow proof targets (last):
    src-tauri/tests/application.rs
    tests/application.integration.test.ts

The backend evidence set includes app.rs, db.rs, lib.rs and other runtime/schema
owners. The frontend evidence set includes useTauriCommands.ts and the existing
provider/runtime seams.

Safety / acceptance behavior preserved
--------------------------------------
- Disposable candidate workspaces
- Exact current-source edit protocol
- Syntax and semantic validation
- Real affected-component build/test proof
- No regression in previously clean components
- New functional debt rejection
- Atomic commit/rollback
- Final whole-project publication gate
- Dead-stream idle handling
- Cooperative Stop/checkpoint control

This remains language/framework/toolchain agnostic; no GearTrack-, Tauri-, Rust-
or React-specific repair rule is required for the clustering policy itself.
