JARVIS V42.15 - RUST MODULE TOPOLOGY + RESUME TOOLCHAIN AUTHORITY + ENDGAME GUARD

This release fixes the final convergence regression observed in the resumed GearTrack project on 2026-09-01.

Observed failure chain:
1. Generic repair wording contained "escalate".
2. Legacy substring toolchain detection matched the substring "scala" inside "escalate" and injected a Scala/sbt toolchain lock.
3. An unplanned Scala scaffold (build.sbt / Scala source) polluted the resumed React + Rust/Tauri repository.
4. Rust imports such as crate::models::tool::Tool were not mapped through the actual directory module topology (src/models/mod.rs + src/models/tool.rs).
5. A generated competing src-tauri/src/models.rs then gained false graph relevance and became a quarantined 27B repair target.
6. Old accepted-revision entries for deleted/nested paths remained in the ledger.

V42.15 changes:
- Bare Scala/Rust/React language/framework detection is word-boundary guarded. "escalate" is not Scala; "trust" is not Rust.
- Jarvis-generated historical EXPLICIT USER TOOLCHAIN LOCK blocks that contradict reconstructed current components are removed from resume authority and model prompts.
- High-confidence unplanned Scala/sbt pollution recorded by the old Project KB is quarantined before component rediscovery.
- Rust module resolution understands crate/self/super/package-root imports and directory modules:
    crate::models                    -> src/models/mod.rs
    crate::models::tool::Tool        -> src/models/tool.rs
- If foo/mod.rs exists, a competing unplanned foo.rs is treated as stale topology even if an earlier repair already materialized it.
- Repo graph provider/edge authority excludes stale flat aggregates and rebuilds Rust import edges from compiler-style module topology.
- Resume migration prunes accepted-revision entries that no longer exist in current authored/planned topology.
- Runtime whole-project audit cleans late hallucinated flat providers before they can become repair authority.
- Once every current planned file is accepted, an unplanned ambiguous provider cannot trigger provider-first/deterministic/27B synthesis; Jarvis reruns real whole-project validation instead.
- @tauri-apps/api is normalized to runtime dependencies during deterministic Node/Tauri manifest reconciliation.

AUTO model behavior is unchanged:
- Qwen3.5 9B = routine worker
- NEW Qwen3.8 27B Aggressive Q2_K_P = hard specialist
- old 27B remains excluded from AUTO

Final publication remains strict: build/tests/runtime/requirements/debt must all be green before ZIP publication.
