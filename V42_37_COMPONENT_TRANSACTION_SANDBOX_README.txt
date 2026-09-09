JARVIS V42.37 - COMPONENT-ISOLATED TRANSACTION SANDBOX
=======================================================

Captured run result
-------------------
The V42.36 run was not making accepted Rust progress. It correctly selected
src-tauri/src/models/tool.rs, but the 9B patch call exceeded its two-minute
watchdog and the 27B rescue exceeded four minutes. The global same-revision
loop guard then blocked both fallback rewrite paths. No Rust source delta was
accepted; the last accepted event remained the earlier TypeScript 8 -> 0 fix.

The same run exposed two additional control-plane defects:

1. A Rust candidate replay used the repository-wide non-Python validator, which
   started with React. The unrelated Vite failure could therefore reject a Rust
   candidate without measuring Cargo.
2. Vite successfully launched and reported a bad project alias, but the ENOENT
   text was classified as missing-tool infrastructure. The invalid alias mapped
   @tauri-apps/api to /src-tauri/src-tauri/tauri.conf.json.

V42.37 changes
--------------
1. Candidate replay resolves the exact component id/root from fresh validator
   evidence and executes only that component.
2. Native/compiler repairs are staged in a disposable dependency-parity clone.
   Build-generated files in that clone are never promoted.
3. A bounded group of compiler-owned files can accumulate provisionally. Only
   selected authored source is atomically promoted, and only when that exact
   component passes or its diagnostic count strictly decreases.
4. Every repair writes JARVIS_V4237_REPAIR_BUNDLE.json with the component,
   adapter, command, working directory, diagnostic files/count, and targets.
5. Repair editing uses a compact, exact-source prompt and starts with the fast
   9B worker in AUTO. One bounded 27B peer rescue remains available. Default
   component-patch watchdogs are 90 seconds for 9B and 150 seconds for 27B.
6. Watchdog/connection/context failures are transport failures. They do not mark
   a repair strategy semantically exhausted. Per-state retry caps and a ten-minute
   cooldown stop tight timeout loops while allowing a later run to try again.
7. Bundler "could not load ... imported by ..." failures are source/config
   evidence after the tool has launched, not missing-executable infrastructure.
8. A narrow deterministic transaction removes an alias only when it shadows a
   declared package, points to a suspicious local file/path, and fresh component
   replay clears that exact loader failure.
9. The command broker scrubs unknown secret-shaped environment variables by
   default and isolates Yarn, Corepack, and Bun caches in addition to existing
   npm, pip, Cargo, Gradle, NuGet, and Go caches.
10. Project-local tool discovery now includes pnpm, Yarn, Bun, Cargo/Rust,
    project-local .NET, Composer, and Bundler paths.

Universal boundary
------------------
The orchestration is based on component metadata, validator evidence, command
working directories, compiler paths, source deltas, and manifests. It is not a
GearTrack source patch and does not assume React/Rust for arbitrary projects.
Adapter-specific deterministic helpers remain narrow and evidence-gated.

Verification
------------
Run CHECK_V4237_COMPONENT_TRANSACTION_SANDBOX.bat on Windows. Also run the
V42.36 and V42.35 regression checks to confirm compatibility.

Restart requirement
-------------------
Fully close the old Jarvis process before using this release. The disk marker
must read V42.37.0. Resume from the newest GearTrack checkpoint/current run ZIP;
do not restart from the older 8-error checkpoint.
