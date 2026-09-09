Jarvis V42.48.0 - Bounded Functional Convergence

Why this release exists
-----------------------
A real V42.47 GearTrack resume ran for most of a day without reaching a terminal
result. Two defects were confirmed from the accepted workspace and journal:

1. The functional acceptance scanner treated files under .jarvis_backups/
   v36_checkpoints as live source. The real project had 13 live functional issues,
   but the audit inflated to 41 issues after historical backup copies were scanned.

2. The V42.47 functional repair round could attempt every functional issue before
   returning control to the normal no-progress circuit breaker. Rejected repairs
   created more backup snapshots, which created more ghost findings and more model
   work. Build-tool timeouts could also fall into ambiguous runtime Qwen diagnosis.

V42.48 changes
--------------
- Functional auditing is live-source-only and excludes all Jarvis/internal/cache/
  generated trees (.jarvis_backups, .jarvis_candidates, .jarvis_runtime, target,
  node_modules, build, dist, venvs, etc.).
- Related functional issues are grouped by live source file. Example: schema,
  RETURNING, and row-shape debt in one persistence file become one coherent repair
  transaction rather than three separate model calls.
- Production implementation debt is repaired before test-coverage debt.
- Model-backed functional repair is bounded per unchanged authored-source revision:
  2 groups/round, 2 attempts/group, 6 attempts/revision by default.
- The budget is keyed to a live-source content fingerprint, so creating backup files
  cannot reset the budget. A real accepted source change creates a fresh revision
  and therefore a fresh bounded budget.
- When a functional round makes no accepted source change, V42.48 returns control
  to the outer convergence/circuit-breaker system instead of entering the inherited
  unbounded per-issue fallback.
- Rust Cargo build/test validation gets an adaptive 600-second floor (fetch/check
  300 seconds) so a cold Tauri build is not mislabeled as a source defect after 180s.
- A build/test timeout without concrete compiler/test diagnostics is classified as
  validation infrastructure and is not sent to Qwen as an ambiguous source repair.
- Existing compile convergence, checkpointing, functional acceptance, stack adapters,
  and universal language/framework/toolchain behavior are preserved.

Defaults can be tuned with:
JARVIS_V4248_FUNCTIONAL_GROUPS_PER_ROUND
JARVIS_V4248_FUNCTIONAL_ATTEMPTS_PER_GROUP
JARVIS_V4248_FUNCTIONAL_ATTEMPTS_PER_REVISION
JARVIS_V4248_CARGO_BUILD_TIMEOUT
JARVIS_V4248_CARGO_FETCH_TIMEOUT
