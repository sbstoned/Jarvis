JARVIS V42.2 - UNIVERSAL COMPONENT BOUNDARY CONVERGENCE FACTORY
===============================================================

Primary regression fixed:
  GearTrack diagnostic workspace project_20260830_183449 failed because the
  root React/TypeScript build script invoked:

      tsc -p src-tauri/tsconfig.json && vite build --outDir dist

  src-tauri is a separate Rust/Tauri build component, and that tsconfig did not
  exist. V42.2 treats this as a build-command/config-ownership defect rather
  than a source-code defect.

V42.2 additions:
- Universal component command/config boundary gate.
- Registry-driven config-path flag knowledge for tsc, Vite, Vitest, Jest,
  ESLint, pytest, Cargo, Maven, Gradle, dotnet and Composer.
- Build-substrate closure before implementation. TypeScript components must
  plan component-owned tsconfig.json; Vite SPA components must plan their host.
- Safe deterministic TypeScript config creation only for stable templates
  (React, plain Vite, plain Node). Framework-owned configs remain framework/model
  generated rather than receiving a risky generic config.
- Deterministic repair of invalid/cross-component tsc -p/--project references.
- Pre-execution component command validation before compiler/package-manager use.
- Semantic TS5058 failure signature and deterministic repair path.
- Direct JS/TS and Python self-import guard before source commit.
- Final requested-behavior coverage barrier immediately before implementation.
  Later plan merges can no longer silently drop requested real tests/features.
- Test coverage recognition includes test/, tests/, spec/, specs/, test/spec
  filenames, and explicit test-purpose files.
- Universal/mixed-repo/typeScript skill guidance updated with component build
  boundary rules.

The design remains stack agnostic. V42.2 does not make Tauri the default and
never substitutes an unrelated language/framework when the requested stack is
missing locally.

Exact 183449 replay findings:
- Root tsconfig.json is now added to Foundation before implementation.
- src-tauri/tsconfig.json is NOT invented.
- The bad package build script rewrites to:
      tsc -p tsconfig.json && vite build --outDir dist
- The original TS5058 condition is eliminated.
- The next hidden source defect in that snapshot (src/App.tsx importing itself
  via ./App) is now rejected at the central candidate gate before acceptance.
- With a non-self-importing App in the replay, the real TypeScript compiler
  completes successfully. Full Vite execution was not claimed in this Linux
  environment because the attached node_modules contains Windows-native Rollup
  optional dependencies.

Validation summary:
  V41.1 universal factory                 135 / 135 PASS
  V41.2 React/Vite convergence             14 / 14 PASS
  V41.3 repair convergence                 29 / 29 PASS
  V41.3 failed-workspace replay             7 / 7 PASS
  V42.0 capability/sandbox                 20 / 20 PASS
  V42.1 Tauri/Cargo convergence             26 / 26 PASS
  V42.2 component-boundary convergence      19 / 19 PASS
  --------------------------------------------------------
  TOTAL                                   250 / 250 PASS

Top-level Python files compile: 14 / 14, 0 errors.
Toolchain adapters preserved: 59.
Skill cards preserved: 58.
