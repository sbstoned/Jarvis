JARVIS v2.74.1 - V34.1 UNIVERSAL BUILDER + RESILIENT BOOTSTRAP
================================================================

PURPOSE
-------
V34.1 is a general-purpose autonomous software-project builder. It is not tied to
inventory, Python, or any single framework. Jarvis plans the requested product,
selects/declares an appropriate native toolchain, defines repository-wide contracts,
materializes a visible skeleton, implements providers before consumers, provisions
dependencies, runs stack-appropriate validation, repairs concrete failures, and only
publishes a final ZIP after its acceptance gates pass.

BOOTSTRAP FAILURE FIX
---------------------
V33 could produce a valid architecture/README and still abort with:
  "Bootstrap did not produce real project source files. Errors: no source files recovered."

V34.1 does NOT treat that as an immediate terminal state. If strict model planning or
first-source transport fails, Jarvis:
  1. infers the requested native toolchain,
  2. creates a conventional deterministic recovery manifest,
  3. materializes valid-format source/build skeletons,
  4. marks recovery source with JARVIS_V34_RECOVERY_SEED,
  5. continues dependency-ordered implementation and acceptance repair.

Recovery/skeleton markers are HARD incomplete-project defects. They can never be
published as a verified final project.

TOOLCHAIN / VALIDATION COVERAGE
-------------------------------
Deterministic adapters include:
- Python / Python desktop
- static HTML/CSS/JavaScript
- Node.js, React, Next.js, Vue, Angular, Electron
- C/C++ with CMake
- Rust/Cargo
- Go modules
- C#/.NET
- Java Gradle / Maven
- Kotlin/JVM Gradle
- Android/Gradle
- Flutter/Dart
- Swift Package Manager
- native iOS/macOS Xcode projects (host-aware)
- React Native
- Unreal Engine / UnrealBuildTool-aware project structure
- Unity
- PHP/Composer
- Ruby/Bundler

Uncommon stacks may declare their own language/framework/build/package-manager and
safe build/test commands. V34.1 no longer silently converts unfamiliar projects to
Python.

HOST-AWARE VALIDATION
---------------------
Some platforms cannot be fully compiled on Windows. Native iOS/macOS is the key
example. Jarvis can generate the project on Windows but reports host-limited validation
instead of falsely claiming an Xcode compile occurred. Unreal/Unity similarly require
their installed engine toolchains for a full native build.

PROJECT SIZE
------------
Default planner limit: 160 files
Configurable hard maximum: 1000 files
Environment overrides:
  JARVIS_QWEN_PROJECT_MAX_FILES
  JARVIS_QWEN_PROJECT_HARD_MAX_FILES

PRESERVED SYSTEMS
-----------------
- V27 truncated-source continuation
- V30 provider/root-cause targeting and transactional rollback
- V32 throughput-aware bounded working contexts on the 262K Qwen3.5 server
- V33 contract-first, skeleton-first, dependency-ordered implementation
- hard final acceptance/build/package gates
