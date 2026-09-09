JARVIS V42.1 TAURI/CARGO + MIXED-ROOT CONVERGENCE FACTORY
==========================================================

V42.1 is a full-project upgrade on top of V42.0. It preserves the capability
manager, command broker, project-local runtime state, optional WSL/Docker
backends, tool bootstrap, V41.3 accepted-revision repair loop, V41.2 React/Vite
substrate, and the universal 59-adapter / 58-skill factory.

WHY V42.1 EXISTS
----------------
The GearTrack diagnostic run project_20260830_171300 exposed two root causes:

1) Cargo/Tauri dependency-resolution failure
   Cargo.toml selected Tauri 2 but requested the legacy core feature `shell-open`.
   Cargo correctly reported that the Tauri 2 crate has no such feature, but the
   older repair path did not convert that exact diagnostic into a deterministic
   Cargo.toml edit.

2) Wrong-language Tauri backend plan
   The reviewed architecture placed TypeScript model files under
   src-tauri/src/models/*.ts. src-tauri/src is the Rust crate source root. This
   caused later owner self-healing to invent Rust providers and destabilized
   Tool / Category / CheckoutEvent / ToolCondition ownership.

V42.1 FIXES
-----------
- Tauri-2 Cargo hardening removes obsolete legacy core features before the first
  real dependency-resolution gate while preserving valid core features.
- Exact Cargo diagnostic repair recognizes:
    package X depends on Y with feature Z but Y does not have that feature
  and removes only the invalid feature from the named dependency before retry.
- The known nonexistent `sqlx-build` pseudo dependency from the live regression
  is removed deterministically; arbitrary unavailable/private packages are NOT
  silently deleted.
- Cargo loop signatures now identify semantic dependency failures such as:
    cargo-invalid-feature:tauri:shell-open
  rather than depending on whichever wrapper line happened to be last.
- Tauri plan sanitation converts JS/TS accidentally planned under src-tauri/src
  into canonical Rust .rs module paths before ownership or milestones freeze.
- Rust module filenames are normalized to snake_case for Windows/Linux portability.
- SQLx migrations accidentally planned under src-tauri/src/db/migrations are
  normalized to src-tauri/migrations.
- Every frozen backend domain contract gets a stable Rust owner unless the plan
  already contains a trustworthy explicit Rust provider.
- Exact Rust provider filenames outrank incidental prose mentions when resolving
  Tool / Category / CheckoutEvent / enum ownership.
- Backend domain model files are kept out of the minimal Foundation milestone.
- A late deterministic src-tauri/src/models/mod.rs hub is planned only after
  canonical model providers exist.
- Cross-cutting db/mod.rs and commands/mod.rs are treated as integration/module
  substrate rather than domain entity owners.
- A final root-language commit gate rejects future JS/TS source accidentally
  written under src-tauri/src even if an earlier planning wrapper regresses.
- The Tauri skill card now explicitly teaches Tauri-2 plugin/capability behavior,
  root-language separation, major-version coherence, and manifest-first repair.

REGRESSION RESULT
-----------------
V41.1 universal factory:            135 / 135 PASS
V41.2 React/Vite convergence:        14 / 14 PASS
V41.3 repair convergence:            29 / 29 PASS
V41.3 failed-workspace replay:        7 / 7 PASS
V42.0 capability/sandbox:            20 / 20 PASS
V42.1 Tauri/Cargo convergence:       26 / 26 PASS
                                    ------------
TOTAL:                              231 / 231 PASS

Top-level Python compile pass: 13 files, 0 errors.

IMPORTANT
---------
These deterministic guards remove failures that the build system can prove are
manifest/root-layout errors. They do not weaken real builds. Cargo/npm/compiler
validation still has to pass before Jarvis can publish a generated project ZIP.
