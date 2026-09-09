Jarvis V42.50.0 — Regression-Safe Functional Promotion

Why this release exists
-----------------------
V42.49 could accept a functional/persistence patch before proving that the
changed component still compiled. The GearTrack trial demonstrated the failure:
a persistence-oriented tools.rs change introduced three Rust E0308 errors even
though the Rust component had previously been green.

V42.50 acceptance order
-----------------------
1. Compiler/build/component health cannot regress.
2. The targeted functional issue family must strictly decrease in a disposable clone.
3. Only then can the source patch become authoritative.
4. Full project build/tests/runtime/functional acceptance reruns after promotion.

If an authoritative audit already contains a compiler/build failure, V42.50 routes
that failure to the native component repair controller before spending functional
repair budget.

Universal architecture
----------------------
This is not Rust/Tauri-specific. Rust uses the warm Cargo target cache because that
adapter exists; other stacks use their registered component validator/build adapter.
The invariant is universal: never trade a green component for a better functional
score.
