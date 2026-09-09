JARVIS V42.36 - FRESH COMPONENT / NATIVE COMPILER AUTHORITY
===========================================================

What was wrong
--------------
The observed GearTrack run was looping. The React component had already passed its
real Vite build and Vitest test, while Cargo still reported 75 Rust errors. However,
the compact event projection retained an older React blocker stored at component root
".". V42.35 invalidated a blocker only when that exact string matched a changed file,
so a repair to vite.config.ts could not invalidate the component-root blocker.

An inherited V42.21 global deterministic TypeScript scan also ran before/inside whole-
project audit repair. It could therefore edit InventoryView.tsx even though the newest
failing validator was Rust/Cargo. The accepted project source did not advance and the
same Cargo failure repeated.

V42.36 corrections
------------------
1. Every freshly executed component validator now updates current-blocker authority.
   A fresh green React result retires stale React evidence; a fresh failing Rust result
   replaces it immediately.
2. Compiler paths are resolved relative to the component command working directory.
   Cargo output such as src\tools.rs maps to src-tauri/src/tools.rs.
3. Definition locations (Rust ::: lines and analogous provider evidence) outrank
   cascading consumer locations for trait/schema/symbol-definition failures.
4. A native component failure is routed before global TypeScript recovery. Components
   that just passed are frozen.
5. Pre-audit global source mutation is disabled. Deterministic repairs still run from
   a focused, current failure route.
6. Native repair targets are distinct and bounded per accepted repository revision.
   With no source delta, Jarvis stops with exact evidence instead of cycling through
   unrelated files.
7. A non-TypeScript candidate is accepted only when replay of the same component
   strictly lowers its native compiler error count or passes. Line-number movement is
   not progress.
8. The generic candidate clone now receives the same read-only Node dependency parity
   as TypeScript cluster candidates, preventing an earlier green frontend from failing
   merely because a Rust candidate clone lost node_modules.
9. Projection, convergence-controller state, and dashboard status share the same fresh
   current blocker.

Captured GearTrack regression
-----------------------------
The saved checkpoint contains a green React/Vite/Vitest component and a failing Rust
component. V42.36 converts the stale React blocker to:

  component: rust
  file: src-tauri/src/models/tool.rs
  diagnostic files:
    - src-tauri/src/models/tool.rs
    - src-tauri/src/tools.rs
  native diagnostic count: 75

This does not hard-code GearTrack repairs. The route operates on component metadata,
real compiler locations, file existence, diagnostic ownership, native error deltas,
and accepted-source revisions. The same policy applies to other native toolchains and
custom components with declared real build/test commands.

Verification
------------
- Python syntax/import: PASS
- V42.36 focused regression: 31/31 PASS
- V42.35 compatibility regression: 33/33 PASS
- Exact saved GearTrack blocker-state replay: PASS
- Generic candidate dependency parity: PASS
- Current host Cargo build: NOT RUN (cargo/rustc unavailable in this environment)

Run on Windows
--------------
1. Fully close any running Jarvis process.
2. Replace the old installation with this complete ZIP.
3. Start Jarvis again. JARVIS_ACTIVE_ENGINE.txt must show V42.36.0.
4. Attach the newest GearTrack checkpoint ZIP and ask Jarvis to finish the project.
5. The first live failing target should be under src-tauri, not InventoryView.tsx.

Honest acceptance boundary
--------------------------
No finite local test can guarantee successful generation for every possible language,
SDK, external service, operating system, prompt, or project. Jarvis must have the real
toolchain/dependencies required by the requested project and must refuse to publish
when those validators cannot run or do not pass. V42.36 fixes the demonstrated routing
and looping defect while preserving this strict verification rule.
