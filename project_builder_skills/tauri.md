# Tauri

V42.1 focused engineering rules:

- Tauri is one mixed repository: the frontend `package.json` and web `src/` live at the repository root; the native Rust crate is `src-tauri/Cargo.toml` + `src-tauri/src/**/*.rs`.
- Never place `.ts`, `.tsx`, `.js`, or `.jsx` implementation files under `src-tauri/src/`. Shared concepts may have serialization-compatible representations per component, but each language owns its own source files.
- Keep the Tauri major version coherent across `tauri`, `tauri-build`, `@tauri-apps/cli`, and Tauri plugins. Do not mix Tauri-1 core API features with a Tauri-2 plugin architecture.
- Tauri 2 removed legacy core API feature flags such as `shell-open` / `shell-open-api` and `process-command-api`; use the appropriate v2 plugin and capability/permission model instead.
- Tauri 2 plugin permissions belong in `src-tauri/capabilities/` when frontend/plugin calls require them. Do not restore a Tauri-1 allowlist into a Tauri-2 config.
- Treat Cargo dependency-resolution diagnostics as authoritative. If Cargo says a dependency does not have a requested feature, repair the manifest before editing Rust consumers.
- Keep Foundation dependency-closed: `Cargo.toml`, `build.rs`, `tauri.conf.json`, minimal `main.rs`/`lib.rs`, and the frontend boot substrate. Domain models, DB repositories, commands, and UI features belong to later green milestones.
- Rust module filenames should be snake_case and portable across Windows/Linux. Use explicit `mod.rs`/module hubs only after the modules they declare are materialized.
- Run both frontend and native validation: npm dependency/build/test checks plus Cargo fetch/build/test (and `npm run tauri build` for final native packaging when the host has the required platform toolchain).
