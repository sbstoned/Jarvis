JARVIS V42.52.0 - Durable functional progress

Install the COMPLETE ZIP into a fresh folder after fully closing Jarvis. Use
the included normal launcher. The active engine marker must show V42.52.0.
Keep your local provider/model settings, credentials and existing project ZIPs.
Attach the saved checkpoint or trial source ZIP and request:
  Finish this existing project. Preserve its features and public APIs.

Changes:
- Functional findings now participate in the real outer resume score. Two
  compiler-green trials with fewer functional defects are no longer tied.
- Promoted improvements survive the next sweep and checkpoint export/import.
- Discarded trial diagnostics cannot replace the retained source's findings.
- Previously passing compilation/runtime validation cannot regress for a
  smaller functional count. Unverified validation never means completion.
- Constant SQLite statements are prepared against isolated declared schemas
  before expensive component rebuilds. The adapter catches invalid SELECT,
  INSERT, UPDATE and RETURNING columns, including the wrong-person-column
  query seen in the failed trial. It never accesses the application database.
- Functional rejection feedback names the relevant target findings and gives
  exact search-match counts. Coordinated provider/caller edits remain supported.
- Dashboard audit state includes functional findings appended by final gates.

Universal scope:
The controller and transaction policies do not depend on a project name,
programming language or framework. Existing native toolchain adapters continue
to own build, test and runtime checks. SQLite preparation is an optional
database adapter, not an assumption that every project uses SQLite. Unknown
dialects, dynamic SQL, external schema and unavailable functions require the
project's native validation. SQL preparation is not business-workflow proof.

Validation:
Run CHECK_V4252_DURABLE_FUNCTIONAL_PROGRESS.bat on Windows, or run its three
Python scripts individually. Tests use controlled model replies and actual
resume/checkpoint code; the completed Python service is exercised through
SQLite writes, invalid-input failure, reads and a fresh-process persistence
check. The V42.51 suite also exercises C compilation and JavaScript execution
when those host tools are installed. See V42_52_VALIDATION_REPORT.json for the
actual commands, outputs, skips and limitations on the packaging host.

This is the complete Jarvis application package, not certification that a
particular generated project has reached final acceptance. No finite test
suite can guarantee every possible project or language. Final projects still
require their actual build, tests, runtime and functional gates to pass. A
bounded run that cannot satisfy those gates must remain an honest resumable
checkpoint; it must never be relabeled as a working final project.
