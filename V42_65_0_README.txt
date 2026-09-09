Jarvis V42.65.0

Purpose
-------
Restore/preserve the fast V42.61 connected functional-repair scheduler that reduced the
recorded GearTrack functional debt from 12 issues to 2, while fixing the infrastructure
and workflow-test endgame failures that prevented those last two blockers from being
validated and promoted.

What the recorded V42.61 endgame actually showed
-------------------------------------------------
The remaining blockers were executable workflow tests (React and Rust). For the Rust
workflow-test repair, attempt 1 returned malformed transaction JSON and Jarvis correctly
retried it. Attempt 2 returned a complete candidate transaction, but the candidate never
reached compile/test validation: the legacy nested candidate-clone path copied
`.jarvis_shared_build_cache/cache/npm/_cacache` while npm was mutating that cache. On
Windows, disappearing cache blobs raised WinError 3 and aborted candidate validation.

V42.65 fixes the endgame without replacing V42.61's fast scheduler
------------------------------------------------------------------
- Keeps V42.61/V42.58 connected-cluster scheduling and coordinated cross-file repair.
- Does NOT enable V42.63's one-owner-only/minimal-batch scheduler.
- Candidate validation clones now reuse the active V42.61 source-only resume clone policy,
  so `.jarvis_shared_build_cache` and other rebuildable volatile caches are excluded.
- Ordinary functional repair transactions keep the V42.61 4-attempt budget.
- Missing workflow-test transactions get 6 bounded attempts because creating a new
  executable workflow test is more likely to need a retry for malformed JSON, compile
  errors, or incorrect fixture/setup assumptions.
- Workflow-test prompts are compact and evidence-bound: use only current public APIs,
  types, test runners, and setup proven by the supplied project evidence.
- 27B workflow-test output is capped to a compact endgame budget (default 8,192 tokens)
  instead of automatically requesting a very large connected-repair response.
- If a real native test command is already proven by the project/component graph,
  Jarvis can restore it when an older layer cleared it. This does not count as a pass.
- If an unexpected infrastructure exception occurs after a trial objectively improves,
  Jarvis may preserve that trial only after a fresh validation snapshot proves a strictly
  better score and no protected regression.

Safety / acceptance behavior preserved
--------------------------------------
- Final acceptance is NOT weakened.
- Missing workflow tests remain functional debt.
- A project cannot be labeled complete until required tests exist, execute, and pass.
- Candidate changes remain disposable until syntax/build/functional proof accepts them.
- Protected regressions still reject promotion.
- V42.60 hardware-fit behavior remains: Qwen3.8 27B native capability 262,144 tokens,
  default live runtime context 40,960 tokens.
- Useful active Qwen streams have no 8-minute absolute wall-clock timeout; idle/dead
  stream guards and user Stop remain.
- Architecture remains language/framework/toolchain agnostic.

Validation
----------
163 focused regression checks passed, including V42.65 endgame recovery, V42.61 cache
isolation, V42.60 27B runtime behavior, V42.59 adaptive I/O, V42.58 connected clusters,
functional transactions, durable progress, model protocol, and job lifecycle checks.
Startup compatibility also passed.
