JARVIS V42.23 - RESUME POLICY MIGRATION + TYPESCRIPT ERROR BURN-DOWN
====================================================================

Why this version exists
-----------------------
V42.22 correctly moved repair ownership toward the consumer reported by the real
compiler, but a resumed checkpoint could still contain historical architecture rules
such as "Provider-First Repair". Those old rules could be reconstructed into current
Jarvis architecture metadata and influence later repair subsystems.

The GearTrack checkpoint also showed that one TypeScript build can emit dozens of
symptoms that come from only a few causes. Treating each diagnostic as a separate Qwen
reasoning task wastes time and can hit no-progress limits before the build has a chance
to burn down simple compiler debt.

V42.23 changes
--------------
1. Current-engine resume policy migration
   - Old checkpoint orchestration text is migration input, never current authority.
   - Retires provider-first/provider-before-consumer repair rules on resume.
   - Rewrites derived architecture/domain-owner/repo-graph/contract artifacts after
     migration so stale policy cannot survive on disk.
   - New checkpoints are packaged with the current consumer-first repair policy.

2. Deterministic TypeScript burn-down before model work
   - Uses fresh tsc diagnostics as evidence.
   - Removes compiler-proven unused imports and unused object-destructure bindings.
   - Adds missing React hook imports when TS2304 explicitly identifies a hook.
   - Fixes redundant TypeScript re-exports such as export type { FilterState } when the
     same symbol is already exported by its declaration.
   - Fixes exact null -> undefined mismatches when the compiler proves that contract.
   - Restores Vite stylesheet typing via src/vite-env.d.ts when local CSS exists but
     TypeScript lacks vite/client ambient declarations.
   - Migrates window.__TAURI__.invoke to the Tauri 2 @tauri-apps/api/core invoke API
     when the package manifest proves Tauri API v2.

3. Clustered consumer wiring repair
   - Groups all compiler diagnostics for the same consumer file.
   - Repairs one compiler-owned consumer at a time, then immediately rebuilds.
   - Supplies nearby hooks/services/stores as read-only producer context so App.tsx and
     components can wire existing state instead of inventing DTO fields.
   - Stable type/provider files remain protected unless explicit compiler import/export
     evidence identifies them.

4. Progress-based continuation
   - Real build error count/signature is the progress clock.
   - 39 -> 24 -> 11 -> 4 -> 0 keeps running automatically.
   - Same normalized blocker set for two fresh builds stops boundedly.
   - TypeScript convergence has a 1500 second default wall, preventing multi-hour runs.
   - Up to 10 build/repair cycles are allowed only while real evidence is improving.

Preserved protections
---------------------
V42.22 consumer-first ownership, V42.21 semantic file-role/error-delta gates,
transactional accepted-state protection, topology tombstones, infrastructure-vs-code
classification, build-cache controls, sandbox restrictions, runtime smoke checks, and
real build/test final authority remain in place.

Recommended resume workflow
---------------------------
Fully stop the older Jarvis process, start V42.23, attach the newest project checkpoint
or the latest accepted working ZIP, and say "finish this project". Do not resume an
already-running older Python process because it retains the old orchestration code in
memory.
