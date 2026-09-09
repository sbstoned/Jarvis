Jarvis V41.2 - React/Vite Current-Slice Convergence Hardening
==============================================================

This release is the complete V41.1 Universal Multi-Toolchain Factory plus the
GearTrack regression fix from the 2026-08-30 failed generation.

Observed real failure
---------------------
The Foundation milestone accepted src/main.tsx even though it imported future
providers ./App and ./index.css. The real npm build then failed with TS2307.
tsconfig.json also omitted compilerOptions.jsx, causing TS17004. The architecture
planned Vite's HTML host as src/index.html instead of root index.html.

Root cause
----------
V39 had an active-milestone JS/TS import gate, but the later V38 transaction
wrapper called a captured older V36.2 import checker. As a result, the guard was
present in source but was bypassed by the final transaction call-chain.

V41.2 changes
-------------
1. Final late-bound current-slice JS/TS import closure gate. A bootstrap file
   cannot be called green merely because a provider exists in a future milestone.
2. React early entrypoints are kept dependency-closed. If a real build exposes a
   premature future App/style import, Jarvis deterministically restores a minimal
   boot shell instead of generating feature code early.
3. React TypeScript tsconfig.json is hardened with jsx=react-jsx.
4. Vite root topology is normalized: default HTML host is root index.html, not
   src/index.html, unless a custom Vite root is explicitly configured.
5. tsconfig.node.json is planned in the Foundation substrate when a TypeScript
   Vite config is present, preventing tsc -b references to nonexistent configs.
6. Compiler evidence is routed deterministically before model fallback:
   TS17004 -> TypeScript JSX configuration; TS2307 relative import -> provider/
   milestone closure; missing Vite index -> root host substrate.
7. React, Vite, TypeScript, Testing, and Universal skill cards include these rules.

Validation
----------
- Existing V41.1 universal regression: 135 / 135 PASS.
- V41.2 GearTrack React/Vite regression: 14 / 14 PASS.
- Exact failed GearTrack workspace after deterministic repair: real TypeScript
  `tsc -b` PASS; prior TS2307 and TS17004 errors are eliminated.
- Python compilation pass: see V41_2_VALIDATION_REPORT.json.

The final Vite/Rollup executable stage could not be replayed inside the Linux
packaging environment using the attached Windows node_modules tree because its
native Rollup optional dependency is Windows-specific. On the user's Windows
host Jarvis still runs the real `npm run build` gate normally; this release does
not weaken or skip that gate.
