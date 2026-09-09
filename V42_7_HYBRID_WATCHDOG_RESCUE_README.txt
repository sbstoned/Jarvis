JARVIS V42.7 - HYBRID WATCHDOG RESCUE / ROLE-SPECIALIZED PLANNING
=================================================================

Why this release exists
-----------------------
The V42.6 AUTO hybrid run project_20260831_132131 proved that the new Qwen3.8-27B
Aggressive Q2_K_P could produce the high-level GearTrack architecture, but then
Jarvis asked the same 27B (running with a 6,144-token hardware-fit live context)
to emit large strict-JSON per-component plans. Two component-plan calls each hit
the configured six-minute watchdog, so V37 aborted before implementation.

V42.7 preserves all successful V42.3/V42.4/V42.6 behavior and changes the role split:

AUTO HYBRID
  27B38 Q2_K_P specialist:
    * frozen requirements / high-level architecture reasoning
    * architecture collision/root-cause diagnosis
    * subsystem/provider reconciliation
    * ambiguous failures
    * repeated repair escalation
    * global convergence / acceptance reasoning

  Qwen3.5-9B worker:
    * strict JSON per-component plan serialization
    * routine source generation
    * ordinary implementation
    * first-pass/local repairs

Watchdog/context rescue
-----------------------
In AUTO only, if the selected model hits a hard watchdog or a recognized context-limit
failure, Jarvis switches to the other AUTO model and retries the exact call once. It
never restarts the project or discards frozen requirements. This retry bypasses normal
routing so it cannot immediately switch back to the model that just failed.

Manual dropdown selections remain strict. Selecting 9B, the new 27B Q2_K_P, the old
27B OBLITERATED, or 8B means that exact model is used for the whole project and no
cross-model watchdog rescue occurs.

Bounded 27B watchdogs
---------------------
The new 27B receives realistic but bounded call windows:
  plan:    720 seconds
  repair:  900 seconds
  audit:   900 seconds
  generate:720 seconds

The detailed component-plan stage stays on the faster 9B, so these larger limits are
reserved for genuinely high-leverage reasoning rather than huge serialization jobs.

Preserved convergence machinery
--------------------------------
V42.7 keeps the "almost worked" V42.3 progressive/global-convergence behavior and all
later improvements:
  * requirement/build-debt ledger
  * automatic plan augmentation
  * progressive independent work
  * provider-first repair
  * reduced leaf patch candidates / faster escalation
  * component build-boundary gates
  * sandbox/capability manager and command broker
  * 73 registered toolchain adapters + universal/custom fallback
  * 79 skill cards
  * real build/test/runtime verification
  * strict zero-debt final ZIP gate

Validation
----------
Legacy + current regression checks: 428 / 428 PASS
Top-level Python files compiled: 19, errors: 0
Dashboard JavaScript syntax: PASS
Final ZIP integrity: see V42_7_VALIDATION_REPORT.json
