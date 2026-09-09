JARVIS V42.0 CAPABILITY-FIRST SANDBOX / COMMAND-BROKER FACTORY
================================================================

V42 keeps the V41.3 accepted-revision and repair-convergence system and adds a
runtime layer around the model.

1. CAPABILITY-FIRST STARTUP
   - Jarvis starts a developer capability scan in a background thread while the
     voice stack loads.
   - Before project architecture begins, Qwen receives factual host capability
     evidence (Node/npm, Rust/Cargo, compilers, .NET, Java, Android SDK, Docker,
     WSL, Unreal/Unity common install detection, etc.).
   - A missing tool never authorizes changing the requested tech stack.

2. TOOLCHAIN READINESS
   - After architecture is frozen, Jarvis resolves each component's declared
     required_tools against the real host and writes JARVIS_V42_TOOLCHAIN_READINESS.json.
   - Optional lightweight trusted tool bootstrap exists behind
     JARVIS_AUTO_INSTALL_TOOLS=1. Large engines/SDKs are never silently installed.

3. CONTROLLED COMMAND BROKER
   - Build/test/dependency commands use subprocess(shell=False).
   - stdin is disabled, timeouts are mandatory, destructive host-management
     commands and shell-control operators are blocked, and output/exit code/
     duration are logged as structured evidence.
   - Project-local caches/targets isolate pip/npm/Cargo/Gradle/NuGet/Go state.

4. SANDBOX MODEL
   - Default: controlled native workspace. This is intentionally compatible with
     Windows-native Tauri, MSVC, WPF, Unreal and Unity workflows.
   - Docker and WSL are discovered as optional stronger backends but are not
     forced onto Windows-native projects.
   - Native controlled mode is NOT claimed to be a VM security boundary.

5. PLAN COVERAGE
   - V42 checks the reviewed architecture for explicitly requested behavior
     clusters such as CSV import/export, tests, checkout flows, search/filter,
     dashboard, authentication, notifications and settings.
   - If the normal architecture reviews still omit a requested behavior, V42
     performs one bounded plan correction before implementation starts.
   - A domain entity/schema mentioning a feature does not count as implementing it.

6. OWNER RECONCILIATION
   - Split domain files such as entities.rs + enums.rs now prefer exact semantic
     providers. Compatibility aliases cannot steal canonical ownership.

The goal is fewer framework-specific patches: Qwen designs and repairs source;
Jarvis owns environment facts, command execution, evidence, revision state,
build/test gates, and packaging.
