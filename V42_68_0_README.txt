JARVIS V42.68.0 - TOOL-USING REPAIR SESSIONS + DURABLE PROJECT MEMORY

Purpose
-------
V42.67 fixed the largest prompt/owner-selection problems, but a model response was
still treated as the repair artifact. That meant an obvious local compiler error
could end an expensive outer attempt and the next trial had to rediscover it.

V42.68 changes the interaction model. Qwen now works on one issue inside the
existing disposable candidate workspace through bounded, host-controlled coding
tools. Jarvis remembers the issue, previous diagnostics and rejected drafts across
trial sweeps and checkpoint resumes.

Repair tools
------------
The model can request:
  search      - search authored project source only
  view        - read a bounded line range
  references  - find references to one identifier
  symbol      - find likely declarations
  edit        - exact SEARCH/REPLACE hunks against the current candidate source
  diagnose    - run immediate host-controlled diagnostics

There is NO arbitrary model shell. The model cannot execute free-form commands or
write outside the candidate issue owner through this interface.

Editing rules
-------------
Existing files use exact SEARCH/REPLACE hunks. For nontrivial files Jarvis rejects
a replacement whose SEARCH covers roughly the entire file. The model is instructed
to replace the smallest coherent function/method/region necessary for closure.

After an edit, Jarvis immediately:
  1. writes the draft only to the disposable candidate workspace;
  2. performs local symbol-closure checks;
  3. runs the existing content/syntax/compiler adapter;
  4. runs semantic-role diagnostics when available;
  5. if static diagnostics are clean, runs the existing functional-debt detector;
  6. returns any failure directly to Qwen in the SAME repair session.

Only after this internal preflight is clean does V42.68 hand the draft back to the
existing V42.51+ transaction gates for functional delta, component proof,
regression protection and atomic promotion.

This turns:
    generate -> outer build fails -> next attempt rediscovers error
into:
    inspect -> edit -> immediate diagnostics -> refine same draft -> prove -> commit

Durable project repair memory
-----------------------------
Jarvis stores bounded repair events in:
    .jarvis_memory/project_memory.sqlite3

For generated-project trial folders, the SQLite DB is stored at the job parent so
trial_01, trial_02, etc. share the same memory. A bounded portable snapshot is also
written to:
    <trial>/.jarvis_memory/repair_memory.json

That snapshot is intended to travel with a checkpoint ZIP. A resumed job can seed
its repair DB from the portable snapshot.

Stored repair memory includes:
  target owner
  issue identity
  source fingerprint
  tool actions
  exact diagnostics
  draft-preflight result
  accepted/rejected transaction result

It does not store provider secrets and is excluded from Jarvis authored-source
search because .jarvis* directories are internal.

Contract-first context
----------------------
Every repair session receives:
  validator findings
  validator-owned source locators
  build/test contract
  previous outer rejection evidence
  durable repair-memory summary
  symbol/reference map
  a bounded related-source neighborhood
  current candidate source

This lets Qwen inspect extra source only when necessary instead of receiving the
whole repository.

First-pass closure checks
-------------------------
For JS/TS-family files Jarvis performs cheap local closure checks before the native
compiler:
  - a removed local binding may not leave references behind;
  - a newly declared/destructured binding may not remain unused.

The language/compiler adapters remain authoritative. These lexical checks only catch
obvious mistakes earlier.

Preserved safety/acceptance behavior
------------------------------------
V42.68 preserves:
  V42.67 owner-local evidence and compact output budgets
  V42.65 workflow-test/cache endgame behavior
  candidate workspace isolation
  exact current-source replacement semantics
  compiler/build authority
  functional-debt proof
  component proof
  regression protection
  atomic commit/rollback
  strict final acceptance
  strict manual model selection
  stack/language/framework agnosticism

Expected live behavior
----------------------
Instead of:
  V42.67 functional transaction 1 -> bad patch -> outer reject -> attempt 2

a repair should normally look more like:
  V42.68 repair session step 1
  model edit
  immediate diagnostics
  V42.68 repair session step 2
  corrected edit against current candidate
  internal preflight clean
  functional/component proof
  accepted transaction

The raw model's first draft is not guaranteed perfect. The goal is that one repair
transaction can internally inspect, edit, diagnose and refine until the candidate is
actually ready for the expensive acceptance gates.
