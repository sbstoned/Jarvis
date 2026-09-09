JARVIS V42.41.0 - AUTHORITATIVE REPAIR CONTROLLER
==================================================

This release fixes the production repair-routing failure observed in GearTrack
job 56.  V42.40.2 was loaded, but V42.37's audit and real-repair closures called
their captured local repair function.  The V42.40 deterministic transaction,
persistent memory, and current event identity were bypassed.

WHAT CHANGED
------------
1. Both production repair entrypoints now resolve the registered component
   repair controller at call time.  Future controllers cannot be silently
   bypassed by an older closure.

2. Native failures pass through one V42.41 controller.  It first opens a
   disposable exact-component workspace and applies conservative
   compiler-directed strategies.  Only the component's real validator may
   promote the candidate, and only when it passes or its diagnostic count
   strictly decreases.

3. Rust compiler evidence can safely drive exact old/new suggestions, required
   SQLx FromRow derives/features, invalid enum matches against String fields,
   borrow-safe nullable SQL binds, and the retained SQLx transaction correction.
   These are adapter strategies rather than project-specific GearTrack patches.

4. Every exact compiler failure plus accepted repository revision receives a
   durable strategy ledger.  By default, an unchanged revision receives one
   bounded model component transaction.  A second identical entry is stopped
   by the circuit breaker rather than spending another long worker/specialist
   cycle on unchanged code.

5. Local-Qwen streaming is progress-aware.  Useful streamed tokens extend the
   initial deadline up to a bounded absolute maximum.  Default compact repair
   windows are 240 seconds for the 9B worker and 480 seconds for the 27B
   specialist.  STOP + CHECKPOINT continues to cancel the active stream.

6. Project journals and the event projection are now written through a durable
   base emitter and stamped V42.41.0.  Old wrapper layers can no longer replace
   the current engine version with V42.36/V42.37.

PROJECT-LOCAL EVIDENCE
----------------------
Generated or resumed projects now receive:

  JARVIS_V4241_REPAIR_LEDGER.json
  JARVIS_V4241_REPAIR_TRACE.jsonl
  JARVIS_V4241_REPAIR_STATUS.md

V42.40 checkpoint/control filenames are preserved for compatibility, but their
records identify V42.41.0 while this release is active.

VALIDATION
----------
Run CHECK_V4241_AUTHORITATIVE_REPAIR.bat on Windows.  The check covers the
actual audit and real-repair dispatch entrypoints, deterministic candidate
promotion/rejection, event version identity, persistent circuit breaking, and
progress-aware streaming.

No offline test can guarantee that every arbitrary requested program is valid
or that an unavailable SDK exists.  Jarvis still requires the requested
toolchain and executable acceptance tests.  V42.41 makes the repair controller
truthful and convergent: it retains real improvements, stops repeated unchanged
strategies, checkpoints unresolved work, and never labels an unverified project
complete.

