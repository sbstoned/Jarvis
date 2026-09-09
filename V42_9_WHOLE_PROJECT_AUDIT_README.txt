Jarvis V42.9 - Continuous IDE Diagnostics + Quarantined Root-Cause + Whole-Project Audit
==========================================================

Key changes:
- Same canonical provider failing twice with no accepted revision delta is quarantined.
- AUTO promotes the quarantined root cause to the NEW Qwen3.8 27B Aggressive Q2_K_P specialist.
- Missing Foundation/canonical providers are repaired before downstream consumers.
- Pure enums/types/entities/schemas are synthesized deterministically from frozen contracts where safe.
- Whole-project audit scans all planned files, canonical providers, requirement ownership, cross-file deterministic checks, and validates every discovered component independently.
- Component failures are collected together instead of stopping discovery after the first failed component.
- Final convergence repeatedly audits -> clusters/repairs -> rebuilds/retests until green or the bounded convergence budget is exhausted.
- Existing strict zero-debt final publish gate remains authoritative.
- AUTO continues to use only the 9B worker + NEW 27B Q2_K_P specialist; legacy 27B is manual-only.

Continuous IDE-style diagnostics:
- Every accepted generation/repair receives immediate deterministic/static diagnostics.
- TypeScript/Rust/Python/Go/.NET/Dart/Flutter components receive bounded real analyzer checks once enough accepted material exists, and after every edit once the component has been green.
- Nearly complete or previously-green component regressions get one immediate evidence-driven repair/recheck.
- JARVIS_V429_LIVE_DIAGNOSTICS.json keeps the live per-file/component diagnostic state.
- The exhaustive whole-project audit and strict zero-debt final publish gate remain authoritative.
