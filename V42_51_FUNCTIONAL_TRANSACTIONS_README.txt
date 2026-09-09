JARVIS V42.51.0 - EVIDENCE-FED FUNCTIONAL TRANSACTIONS

INSTALL / RESUME
1. Fully close Jarvis and its running Python process before replacing code.
2. Back up your existing Jarvis folder. Extract this complete ZIP over it.
   Keep your existing local credentials, virtual environment, models and projects.
3. Restart Jarvis using your normal launcher. Active engine: V42.51.0.
4. Attach your GearTrack checkpoint ZIP and say:
   "Finish this existing project. Preserve its features and data. Fix the real
   backend, persistence, runtime wiring and workflow tests. Build and test it;
   only call it complete when the full acceptance checks pass."
   Resume the checkpoint; a fresh generation is not required.
5. Optional local regression check: CHECK_V4251_FUNCTIONAL_TRANSACTIONS.bat.

CHANGES
- Functional repair supplies actual related source, including provider APIs and
  models, instead of relying on filenames that the model cannot independently read.
- Related-file SEARCH/REPLACE edits are staged together in a disposable clone.
  Existing source and public APIs are preserved unless the validated repair needs
  a coordinated change. Out-of-scope paths and duplicate edits are rejected.
- Syntax/content, semantic ownership, affected-component, and functional-delta
  checks run before promotion. Failed candidates leave accepted source untouched.
- Compiler, test, exact-patch and functional rejection evidence is fed to the
  next attempt and persisted across bounded repair rounds.
- Retry identity includes relevant source dependencies. Provider changes can
  reopen an exhausted caller without backup/log churn reopening it.
- Independent production targets are attempted before a no-progress result;
  runtime wiring can progress after an exhausted lower-layer target. Tests remain
  last. Every promotion returns to the existing complete build/audit controller.
- Multi-file promotion checks for concurrent source edits and rolls back files
  already written if a later file write fails. This is exception rollback, not a
  crash-proof multi-file filesystem transaction.
- Existing generated Python acceptance tests retain their integrity checks.
  Comment-only edits cannot satisfy functional contracts. Newly introduced
  production/persistence findings reject a candidate. New bridge reachability
  is allowed as explicit remaining debt, never treated as project completion.
- A functioning bridge no longer makes a weak existing workflow test disappear
  from the functional audit.

UNIVERSAL SCOPE
The new planner and transaction policy are language/framework independent.
Common source extensions are discovered automatically; manifest-declared files
also participate with unlisted language extensions. Existing component/toolchain
adapters still perform each project's real validation. Existing fresh generation,
ZIP import/resume, compiler recovery and final packaging paths remain in place.
This is a builder update, not a GearTrack-specific source rewrite.

VALIDATION AND LIMITS
17 new offline regression tests passed, including actual Python/SQLite create,
invalid-input rejection and fresh-process persistence reads; real GCC compilation
and execution; Node execution; compiler rejection feedback; multi-file rollback;
checkpoint retry exhaustion/reopening; and scheduler fairness. Model replies in
these tests are deterministic fixtures. 17 V42.50 promotion regression checks
also passed after updating their release identity expectations.

The supplied GearTrack source was inspected and re-audited: 12 functional findings
remain in that attached snapshot. Its included reports contain older engine
versions and are historical evidence, not a trace proving a V42.50 repair run.
The checkpoint itself was not changed or certified complete in this delivery.

No live local-Qwen generation or Windows/Tauri build was run here. This release
cannot guarantee completion of every arbitrary software request. Correctness
still depends on model output, available toolchains/dependencies and meaningful
project-specific acceptance tests. Static contract heuristics are not formal
proof of behavior. Full build, runtime, functional and test gates remain final
acceptance authority; unresolved work must remain a checkpoint.

Bounded defaults: up to 10 related files / approximately 56,000 source characters,
2 model attempts per transaction, 2 transactions per dependency revision, and up
to 12 production groups considered per repair round. Oversized/unsupported
source still requires the existing generation/component paths or a smaller
repair scope; these budgets are not a promise of unlimited project context.
