JARVIS V42.69.2 - SAFE RESUME TRIAL PROMOTION
=============================================

Why this release exists
-----------------------
A real GearTrack V42.69.1 run successfully accepted two functional repairs and reduced
functional debt from 8 to 6. During the next resume sweep, Windows left rebuildable
Cargo state behind when the legacy promoter attempted to delete the authoritative
working directory. The legacy sequence was effectively:

    rmtree(working, ignore_errors=True)
    move(trial_01, working)

If `working` survived because a compiler/cache file was still open, `shutil.move`
placed `trial_01` inside the surviving directory. The next sweep then cloned the bad
shape and produced `trial_02/trial_01/...`, with missing project-root files and false
component roots.

V42.69.2 changes
----------------
1. Safe in-place accepted-trial promotion
   - Never moves a whole trial directory onto a possibly surviving destination.
   - Clones accepted source to a sibling stage, then synchronizes authored state into
     the authoritative workspace.
   - Rebuildable directories (Cargo target, node_modules, build caches, Jarvis runtime
     caches, etc.) are preserved and cannot change project-root topology.

2. Resume root guard and legacy self-recovery
   - Detects a legacy `working/trial_NN` project nested under a non-project container.
   - Uses the actual project root when creating the next trial.
   - Refuses destination-inside-source recursion when no unambiguous root can be found.
   - Verifies every cloned/promoted workspace still looks like a project root.

3. Jarvis repair memory is internal, not application source
   - `.jarvis_memory/repair_memory.json` remains physically portable for checkpoints.
   - It is excluded from authored-source and whole-project acceptance accounting.
   - Manifest entries for `.jarvis_memory` are removed before resume validation.

4. V42.69.1 behavior preserved
   - export-aware JS/TS closure checks
   - safe wrapped tool-action extraction
   - same-session real compiler/test feedback
   - durable repair memory
   - Windows-safe SQLite handle lifecycle
   - strict compiler, functional and regression acceptance gates

Focused regression check
------------------------
Run:

    .\.venv\Scripts\python.exe CHECK_V4269_2_TRIAL_PROMOTION.py

The checks reproduce the malformed Windows rollover shape, verify legacy unwrapping,
verify cache-preserving in-place promotion, verify `.jarvis_memory` audit exclusion,
and confirm the installed release identity reports V42.69.2.

Expected next GearTrack behavior
--------------------------------
Resume from the clean checkpoint containing the accepted 6-issue state. A successful
sweep rollover must create:

    trial_02\
        src\
        src-tauri\
        tests\
        package.json

and must NOT create:

    trial_02\trial_01\...
