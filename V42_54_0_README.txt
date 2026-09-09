JARVIS V42.54.0 - Evidence-based project repair

This is the COMPLETE Jarvis distribution, based on your uploaded
Jarvis_V42_53_2_COMPLETE.zip. It contains the original distribution plus the
updated engine, matching dashboard/server build identity, tests and this report.
It is not a generated GearTrack project or a claim that GearTrack is finished.

USING THIS RELEASE
1. If the old job is still repeating the same failures, use STOP + CHECKPOINT
   and keep its saved project ZIP. Wait for the save to finish.
2. Fully close Jarvis and its dashboard before replacing the running code.
3. Extract this complete ZIP to a fresh folder. Keep your current installation
   and saved projects until you have verified the new one.
4. Start Jarvis from the new folder using your usual Python environment and
   configured model settings (the Python entry point is jarvis.py).
5. Confirm engine V42.54.0 and dashboard build
   v42.54.0-workflow-convergence. A different build means an old process or
   dashboard is still open; close it and launch from the new folder.
6. Attach your saved project/checkpoint ZIP, wait for it to be ready, then send
   "finish this project". The uploaded project's source remains the input.

WHAT CHANGED
- SQL validation follows constant queries into database execution calls and
  aliases. Ordinary messages such as "Update failed" and "Delete failed" no
  longer become SQL failures. Malformed SQL at real calls still fails. This
  optional SQLite adapter uses an isolated schema and EXPLAIN; it never runs
  application data mutations or opens the application's database.
- Missing tests and weak existence-only tests are one stable workflow debt.
  Repair transactions can create an explicitly supplied missing test path,
  validate it in a disposable workspace, then commit it and record ownership.
  Failed tests and concurrent user changes leave accepted files untouched.
- A feature repair can be retained while test discovery was already failing,
  only when the baseline AND candidate production builds pass, the functional
  contract improves, and tests/test configuration remain unchanged. Real
  assertion failures and compiler regressions cannot use this exception.
  Missing tests continue to block final acceptance.
- Repair prompts receive current source, requirements, commands and failure
  output. A specialist strategy is fed into the next repair attempt. Empty
  ownership graphs no longer trigger an evidence-free ownership audit.
- One convergence controller measures source and failure changes. Metadata,
  token counts and dashboard timestamps do not reset its progress budget.
  Identical missing-test failures can be reused within the same validation
  session; changed source, commands, dependencies or environment invalidate
  that evidence. Failed infrastructure checks are never cached as success.
- Repeated unchanged failures get one evidence-backed strategy change, then
  return honest checkpoint debt. The same exhausted source/failure/strategy
  cannot repeatedly restart expensive model loops on subsequent entry.
- Custom adapters recognize Python and manifest-declared languages outside the
  built-in source-extension catalog, while retaining real command validation.
- Previous chunked ZIP upload, Enter/send acknowledgement, draft preservation,
  stale-job recovery and dashboard identity fixes are retained.

VERIFICATION
110 regression checks passed locally: 93 unittest cases plus 17 legacy
regression checks. These include the actual HTTP upload/IPC path, production
JavaScript Enter/send handlers, job lifecycle persistence, candidate rollback,
compiler-regression rejection, and the repair controller's no-progress budget.

A workflow test imported a wrapped checkpoint ZIP, repaired a real SQLite
query, preserved the intermediate improvement with missing-test debt, created
an executable test, and ran it. The test checks a successful save, rejected
invalid input, unchanged row count after rejection, and data read from a new
process. A separate check ran the real registered custom component adapter's
build and test commands. Existing C and JavaScript workflow checks also passed.

All 82 Python source files were parsed, and the dashboard JavaScript passed
Node syntax checking. The supplied stopped-run snapshot was checked: its two
error-message SQL false positives disappeared; the three real wrong-column
queries remained failures.

Model replies in automated tests are controlled fixtures. No live Qwen model,
Windows voice/GUI startup, or full GearTrack desktop acceptance was executed
here. No finite release test can establish that every generated program in
every language works. Jarvis must run each project's actual installed build,
test and runtime tools; unsupported or failing verification remains unfinished.

RUN THE REGRESSIONS
Windows: CHECK_V4254_WORKFLOW_CONVERGENCE.bat
Other hosts: use the Python commands in that file with your Jarvis environment.
V42_54_0_VALIDATION_REPORT.json records the scope and results.

The default convergence budget permits up to 60 repair rounds and 7200 seconds,
with an earlier stop after two unchanged-source rounds or three rounds without
measurable failure reduction. JARVIS_V4254_MAX_ROUNDS and
JARVIS_V4254_WALL_SECONDS can adjust these ceilings. Increasing a ceiling does
not relax compilation, test or final acceptance requirements.
