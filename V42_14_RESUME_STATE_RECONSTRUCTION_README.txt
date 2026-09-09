JARVIS V42.14 - CURRENT-VERSION RESUME STATE RECONSTRUCTION

Purpose
-------
V42.14 fixes attached-project resumes that successfully extract source but then rebuild the wrong internal Jarvis state. Older or partial checkpoints may not contain .jarvis_resume.json, may contain stale owner/contract graphs, or may contain plan paths that no longer match the actual repository.

New resume authority order
--------------------------
1. Actual authored project files and manifests
2. Frozen user requirements and canonical domain contracts from the checkpoint
3. Current-version component/toolchain discovery
4. Current-version canonical owner/repo/contract graph reconstruction
5. Current compiler/build/test evidence
6. Historical Jarvis state only as migration evidence

Key fixes
---------
- Reuses JARVIS_V33_ARCHITECTURE.json as migration input when checkpoint resume metadata is absent.
- Rehydrates JARVIS_V381_DOMAIN_CONTRACTS.json into the current manifest.
- Re-detects real components from on-disk manifests instead of trusting stale component IDs.
- Reconstructs domain ownership from real semantic providers such as src/types/*.ts and Rust models/*.rs.
- Suppresses stale flat providers such as src/types.ts when src/types/ exists, and models.rs when models/mod.rs exists.
- Removes objective duplicate nested component roots such as src-tauri/src-tauri/* when the canonical src-tauri/* counterpart exists.
- Establishes imported authored files as revision-bound baseline files; they are still audited/built/tested by current Jarvis.
- Rebuilds architecture, domain owners, repo graph, contract registry, component graph, and Project KB.
- Clears stale repair-loop state before current-version auditing.
- Reconciles Tauri package/Cargo/config major-version evidence before Qwen repair.
- Removes invalid Cargo default-run values when no matching binary target exists.
- If npm ci reports package/lock drift, performs one package-lock-only reconciliation and retries validation.
- Prevents specialist escalation from treating an old phantom aggregate provider as current authority.

The strict final gate remains unchanged: every component must build/test/runtime validate, requirements must be satisfied, and unresolved debt must be zero before ZIP publication.
