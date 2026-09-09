Jarvis V42.66.0 - Fast Bounded Connected Repair

Why this release exists
-----------------------
A live GearTrack resume on V42.63 exposed a throughput/protocol failure that the
older successful V42.61 run did not make painful enough:

- the functional scheduler grouped 4 connected production owners in one model call;
- V42.59 adaptive I/O expanded the transaction's explicit <=9k request to a
  20,480-token connected-repair allowance;
- the selected 27B model spent 5,260.38 seconds (~87.7 minutes) producing 17,596
  response characters;
- the provider reported finish_reason=stop, but the final edit ended mid-source,
  so strict JSON parsing rejected the entire response;
- three earlier edit objects in that response were already syntactically complete,
  but the old protocol discarded all of them because the trailing edit was incomplete.

The working project was protected correctly, but too much model time was wasted.

What V42.66 changes
-------------------
V42.66 keeps the V42.61/V42.58 connected scheduler and all existing
candidate/build/functional/rollback gates. It changes model emission and recovery:

1. Connected validation stays intact, but each model response focuses on one issue
   owner by default. Related provider/runtime source is still available as evidence,
   so a genuinely cross-file fix can remain coordinated.

2. The explicit transaction output request is now a ceiling rather than a floor.
   Defaults:
     - 27B production repair: 6,144 tokens max
     - 9B production repair: 8,192 tokens max
     - workflow-test repair: 8,192 tokens max
   Environment overrides remain available through the JARVIS_V4266_* variables.

3. Related-source evidence is capped at 120,000 characters by default instead of
   allowing the V42.59 300k expansion to dominate a normal 40,960-token live slot.

4. Malformed-output recovery can salvage at most one fully decoded leading edit
   object when only a later/trailing edit is incomplete. Jarvis never balances
   braces, closes strings, invents source, or repairs truncated code. The salvaged
   edit still has to pass the exact replacement gate, syntax/build validation,
   functional improvement check, component proof, and regression protections.

5. Internal retries rotate the focused issue owner so one slow/difficult owner does
   not monopolize every bounded attempt.

6. Production transactions retain 4 attempts. Missing executable workflow tests get
   up to 6 bounded attempts. Resume sweeps default to at least 8 so smaller verified
   improvements can accumulate without stopping after only a few owners.

7. local_qwen_project.py does not need to be rewritten. The existing V42.63 startup
   layer now activates V42.66 after native model startup/routing is installed.

What is NOT weakened
--------------------
- Manual model selection remains a strict lock.
- AUTO/hybrid routing behavior is preserved.
- Rejected candidates never overwrite accepted source.
- Compiler/build/runtime evidence remains authoritative.
- Functional debt must strictly decrease before a candidate is promoted.
- Missing workflow tests still block final completion.
- Protected regressions still reject promotion.
- Useful active Qwen streams still have no arbitrary 8-minute wall-clock cutoff.
- Architecture remains language/framework/toolchain agnostic.

Validation performed for this patch
-----------------------------------
The focused V42.66 check passes 12/12 tests against the V42.61 repair modules,
including bounded 27B output, connected-owner focus, retry rotation, workflow-test
attempt policy, resume-sweep policy, evidence cap, and deterministic complete-prefix
salvage of the exact malformed-output shape seen in the live run.

After installing
----------------
Fully stop the current Jarvis run before replacing engine files. Relaunch Jarvis and
confirm JARVIS_ACTIVE_ENGINE.txt / the dashboard reports V42.66.0. Resume the same
GearTrack checkpoint; do not start the project over.
