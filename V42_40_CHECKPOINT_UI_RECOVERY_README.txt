JARVIS V42.40.2 - CHECKPOINT CONTROL, REPAIR MEMORY, AND DASHBOARD RECOVERY
============================================================================

INSTALL
-------
1. Fully close the Jarvis launcher, voice engine, dashboard server, and local
   Qwen server terminals. This is required so Python does not keep V42.37 code
   loaded in memory.
2. Make a backup of C:\Users\<USER>\Jarvis.
3. Extract this ZIP directly over C:\Users\<USER>\Jarvis and allow Windows to
   replace matching files. The ZIP contains the project root contents, not an
   extra wrapper directory.
4. Start Jarvis with the same launcher you normally use.
5. The dashboard server now verifies that the URL identifies itself as the
   Jarvis dashboard before it opens anything. It will never intentionally open
   the llama.cpp chat endpoint. Chrome/Edge uses a dedicated Jarvis dashboard
   profile so a cached llama-ui app cannot replace the dashboard page.
6. If port 8080 is already occupied, the dashboard chooses a safe fallback port,
   records the real URL in dashboard_endpoint.json, and opens that exact URL.
   Qwen's port 8081 is always excluded.
7. If you only
   need to recover the dashboard, run OPEN_JARVIS_DASHBOARD.bat.
8. If a browser cached the old UI, press Ctrl+F5 once.

CHAT PANEL RECOVERY
-------------------
- Drag the bright cyan corner at the bottom-right of LIVE CONVERSATION to
  resize it. It uses the same pointer-based resizing system as the other
  dashboard panels.
- Drag the LIVE CONVERSATION title bar to move it.
- The size and position persist across dashboard restarts.
- The new layout schema ignores the old saved geometry that could leave the
  input outside the visible panel.
- RESET CHAT restores only the chat panel. Reset Dashboard Layout restores all
  panels. Double-clicking a panel title also restores that panel.
- The text input has a protected minimum size and remains clickable while the
  panel is resized.

STOP + CHECKPOINT
-----------------
- STOP + CHECKPOINT appears while a Qwen project is queued or running.
- It closes the active local-Qwen HTTP stream, signals the project engine, and
  unwinds at a safe boundary.
- Jarvis packages the best accepted workspace as a resumable checkpoint. It
  never calls an unverified checkpoint a complete project.
- If stopped before real source exists, Jarvis records that fact instead of
  inventing an empty ZIP.
- Control state is written immediately to
  generated_projects\JARVIS_V4240_ACTIVE_PROJECT.json.
- Append-only stop history is written to
  generated_projects\JARVIS_V4240_STOP_EVENTS.jsonl, including early stops.

REPAIR AND FAILURE EVIDENCE
---------------------------
Each generated project can now retain:
- JARVIS_V4239_PROJECT_REPAIR_MEMORY.json: stable issue fingerprints, evidence,
  retry decisions, and occurrence counts across resume attempts.
- JARVIS_V4239_FULL_PASS_TRACE.jsonl: append-only repair decisions.
- JARVIS_V4239_FAILURE_REPORT.md: current component, error count, files, codes,
  decision, and next validation action.
- The existing command broker log: exact command, working directory, exit code,
  duration, stdout/stderr evidence, and timeout/block information.

The repair engine now accepts bounded repeated exact SEARCH/REPLACE operations
when the same broken text legitimately appears more than once. Compiler-proven
Rust/SQLx transaction corrections run before a model call. Candidate edits are
still disposable until the exact failing component passes or its diagnostic
count strictly decreases.

VALIDATION
----------
Run CHECK_V4240_CHECKPOINT_UI_RECOVERY.bat for the focused offline regression.
This release passed the V42.0, V42.35, V42.36, V42.37, and V42.40 regression
suites (159 checks total), full Python syntax compilation, JavaScript syntax,
HTML/CSS/JSON parsing, and a live local dashboard HTTP/layout smoke test.

The Windows standalone Chrome/Edge launch path is unit-verified in source but
cannot be physically opened by the Linux validation host. The normal URL
fallback remains present.

IMPORTANT LIMIT
---------------
No local model can guarantee a correct project for literally every language or
prompt when the required compiler, SDK, credentials, platform, or external
service is unavailable. V42.40.2 improves truthful completion: it gathers real
tool evidence, attempts bounded repair, preserves progress, and returns a
diagnostic checkpoint instead of looping or claiming success without proof.

