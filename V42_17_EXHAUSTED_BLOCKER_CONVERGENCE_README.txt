JARVIS V42.17 - EXHAUSTED BLOCKER CONVERGENCE
================================================

Purpose
-------
V42.17 fixes the endgame failure exposed by the GearTrack run where one malformed
InventoryView.tsx exhausted file + subsystem repair, while Jarvis kept re-running
successful syntax checks on unchanged neighboring files.

What changed
------------
1. Unchanged parser-result cache
   - Language syntax results are cached by source-content hash and parser context.
   - Unchanged green files no longer execute/log the same parser command every audit.
   - Source changes invalidate the cache automatically.

2. Context-aware Rust parsing
   - Rust source is staged inside a preserved Rust module tree before rustfmt parsing.
   - A models/mod.rs file is no longer orphaned from category.rs/tool.rs/etc. during
     syntax validation.
   - The cache context includes sibling Rust-module hashes so related changes invalidate it.

3. Transactional deterministic JSX duplicate recovery
   - Mechanically provable exact duplicate JSX attributes are removed.
   - A dangling repeated attribute-tail after a self-closing JSX tag is removed only
     when it exactly matches a suffix of the preceding tag body.
   - Conflicting duplicate attribute values are NOT guessed away.
   - The repaired candidate is committed only when parser evidence becomes green.

4. Exhausted-blocker circuit
   - A subsystem-exhausted blocker gets one fresh alternate/root-cause transaction at
     the current source revision.
   - Jarvis then obtains fresh component build evidence when available.
   - It does not treat repeated validation of unrelated green files as progress.
   - If accepted repository state cannot move after the bounded alternate strategy,
     Jarvis stops with the exact consolidated blocker instead of looping overnight.

5. Deterministic required-asset recovery
   - Missing planned PNG/ICO assets are regenerated without a model call.
   - Missing PNG/ICO files referenced by Tauri/common desktop config are also detected
     and materialized before component build/audit.
   - This directly covers the GearTrack icons/icon.ico failure family.

Preserved from V42.16
---------------------
- universal transactional source/compile gate
- bad-model-output rollback and accepted-revision protection
- production-before-tests policy
- atomic multi-file direct edit rollback
- provider-first convergence and canonical ownership
- bounded specialist/global no-progress watchdogs
- strict zero-debt publish gate

Validation
----------
Run:
  python CHECK_V4217_EXHAUSTED_BLOCKER_CONVERGENCE.py

The previous V42.16 regression check remains applicable except its exact version
identity assertion intentionally reports V42.17 instead of V42.16.
