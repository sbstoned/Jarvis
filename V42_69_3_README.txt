JARVIS V42.69.3 - CONNECTED FUNCTIONAL REPAIR

Problem
-------
V42.69.2 could remove a simulated frontend operation, pass compilation, and then
discard the draft when final validation discovered a missing backend operation.
The internal functional check ignored new defects whenever the original owner's
issue count decreased. The model was restricted to the original file, so it could
not finish the newly required provider operation in the same candidate.

On Windows, a locked temporary npm cache could also make cleanup raise after the
repair result was determined. That exception bypassed the return path that saves
the causal rejection in the scheduler ledger and portable repair memory.

Changes
-------
* Internal functional preflight and final promotion use the same new-debt rule.
* A live validator finding can authorize an existing related source file inside
  the same temporary candidate. Full source is supplied before editing. A model
  cannot grant itself write scope by naming a file.
* Keep the caller draft while repairing its provider. A session edits at most
  three files using the existing tool/edit budgets and exact SEARCH/REPLACE edits.
* Run syntax/content checks while assembling the connected edit, then prove every
  changed component before returning it. Compiler/workflow failures are fed back
  into that same session. The outer validation and atomic promotion gates remain.
* Include related source and build/test configuration in compiler-proof cache
  identity. A sibling edit cannot reuse proof of an older revision.
* Preserve success, rejection, and Stop results when temporary cleanup fails.
  Record a cleanup warning without treating it as a code repair result.
* Recheck original source immediately before promotion to preserve concurrent
  user edits. No rejected candidate is promoted.

Existing behavior
-----------------
The builder remains independent of language/framework. Native adapters still own
diagnostics. Existing functional/runtime/test gates, manual model lock, AUTO
routing, checkpointing, and V42.69.2 trial promotion/root recovery are preserved.
New bridge/runtime wiring remains explicit follow-up debt and still prevents
final completion, as it did before this change.

Validation
----------
Run CHECK_V4269_3_FUNCTIONAL_CLOSURE.py with Jarvis's Python environment. It drives
the active scheduler/session/transaction code using deterministic model replies.
Its real Python/SQLite workflow checks success, invalid input, persisted state,
and reading that state from a separate process. It also tests same-session repair
of a failing workflow, cleanup failures, Stop, and concurrent edits.

The development replay of the supplied V42.69.2 checkout responses reproduced six
baseline functional findings and the new checkout-provider finding. The updated
preflight retained the caller draft and authorized the existing backend provider.
Uploaded source, logs, and model responses are not included in this repository.

These checks do not represent a live Qwen/Windows completion run. Final completion
still requires the actual generated project's build, runtime, and workflow gates.

Update
------
Stop/checkpoint the active project and fully close Jarvis before updating files.
From your Jarvis checkout on fix/compiler-loop-v4269:

    git pull --ff-only origin fix/compiler-loop-v4269

Launch START_COMMAND_CENTER.bat and confirm V42.69.3. Resume the latest checkpoint
with "finish this project". There is no need to regenerate the project.
