JARVIS V42.38 - COMPONENT-SCOPED TRANSPORT CONVERGENCE
======================================================

What the captured V42.37 run was doing
---------------------------------------
The run made genuine frontend progress: the React/Vite build passed and Vitest
ran one test successfully. The Rust/Tauri component did not improve; Cargo
continued to report 75 errors and no Rust source transaction was accepted.

The repeated 80-92% UI states were orchestration activity, not proof that the
Rust error count was falling. Both local model routes repeatedly returned no
usable patch bytes for src-tauri/src/models/tool.rs and src-tauri/src/tools.rs.

Root cause
----------
V42.37 stored transport failures under a whole-repository source token. Adding
the unrelated frontend smoke test changed that token and erased the Rust
timeout counters even though no Rust source changed. A ten-minute cooldown also
made an unchanged exhausted target eligible again. Together these rules could
cycle forever at long intervals.

V42.38 corrections
-------------------
1. Repair history is keyed to the exact component's authored source/config
   revision. A root component excludes deeper component roots.
2. The append-only project journal reconstructs per-target transport failures
   when resuming old checkpoints, including evidence V42.37 lost after an
   unrelated edit.
3. There is no elapsed-time retry reset. After two no-response transactions per
   target/revision, model calls stop until that component really changes.
4. Exhaustion records MODEL_TRANSPORT_BLOCKED guidance and preserves the
   checkpoint. It does not continue pretending to repair unchanged code.
5. A transport-only transaction is reported as transport deferred/exhausted;
   it is never added to semantic no-progress history.
6. Exact compiler replacement hints are tried transactionally before model
   inference. A narrow rustc-proven missing sqlx::FromRow derive is also handled
   deterministically. Every edit still requires the same component to pass or
   strictly reduce its diagnostic count before promotion.
7. Component patch context is capped at 10,000 characters and output at 900
   tokens to reduce local-model prefill/generation stalls.
8. If the original prompt explicitly asks for tests, a production-symbol
   linkage smoke is runner bootstrap only. Final acceptance remains blocked
   until tests exercise behavior, state, a public command, or a rendered
   interaction.

What to expect on the GearTrack checkpoint
------------------------------------------
V42.38 will import the durable V42.37 timeout evidence. It should not restart
the same model loop because a frontend file changed. It can first apply
compiler-proven deterministic repairs such as a missing FromRow derive and
accept them only when Cargo's error count falls. If both model endpoints still
produce no patch bytes after their bounded allowance, the run will stop with a
clear transport-blocked checkpoint instead of sitting at a misleading progress
percentage indefinitely.

This is a universal engine fix
------------------------------
Component identity, roots, source/config revisions, commands, diagnostics,
compiler suggestions, and strict validator deltas drive the orchestration. The
engine does not contain a GearTrack application patch. Adapter-specific helpers
are narrow, evidence-gated, disposable, and subject to the same validator.

Use
---
Fully close the old Jarvis process before replacing its files, then start
V42.38 and resume from the newest project checkpoint. The active-engine marker
must read V42.38.0. Run CHECK_V4238_COMPONENT_SCOPED_CONVERGENCE.bat for the
focused regression suite.
