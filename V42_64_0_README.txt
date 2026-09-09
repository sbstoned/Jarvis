Jarvis V42.64.0 — Durable Functional Promotion + Test Substrate Reconciliation

V42.63 successfully produced a GearTrack trial with 7 functional issues from an
8-issue baseline, but the outer resume scorer discarded it because an older soft-test
policy had cleared the React test command. V42.10 then reported a false test_substrate
deterministic issue, so the objectively better production source looked worse.

V42.64 fixes the policy conflict without weakening final acceptance:
- restore evidence-proven native test commands from current project manifests,
  package scripts, persisted component graph, or native toolchain files;
- workflow test coverage remains explicit functional debt and must pass for final;
- false/test-only substrate debt cannot erase a compiler-safe production functional
  reduction such as 8 -> 7 during resume promotion;
- TypeScript/Rust/compiler diagnostics are never deferred;
- V42.63 one-owner-first repair batching remains;
- V42.62 candidate-cache isolation and crash-safe better-trial preservation remain;
- V42.60 27B hardware-fit runtime context remains 40,960 with 262,144 native max;
- resume sweep default is increased to 8 so incremental one-owner progress can be
  retained across enough bounded sweeps to finish a larger tail in one run.

This policy is language/framework/toolchain agnostic.
