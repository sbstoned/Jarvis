JARVIS V35 UNIVERSAL COMPLETION ENGINE
======================================

This build upgrades V34.1 toward the goal: one user prompt -> complete, reproducible, working project ZIP.

MAJOR V35 CHANGES
-----------------
1. Multi-component build graph
   Jarvis no longer stops after the first package/build marker. It discovers and validates every buildable component in mixed repositories (for example npm + Cargo for Tauri, npm + Gradle/Xcode for React Native, or frontend + backend stacks).

2. Explicit stack lock vs inferred stack
   Only technologies actually named by the user are hard-locked. Generic wording such as "desktop app", "mobile app", "web app", "calculator", and "game" can be architected into the most appropriate stack instead of silently forcing Python.

3. Expanded adapters
   Added/strengthened recognition for Tauri, SvelteKit, Nuxt, Vite, Expo, Godot, React Native, Unreal, Unity, Android/Gradle, SwiftPM/Xcode, Flutter, Rust, Go, .NET, CMake, Maven, Composer, Bundler and others.

4. Hierarchical planning
   The planner schema now includes a component graph plus files/contracts. Planning output allowance defaults to 16K tokens so larger repositories can be described more completely. Component information is fed back into file-generation architecture context.

5. Clean Python verification
   Python projects are copied to a disposable workspace, a fresh virtual environment is created, declared dependencies are installed, code is compiled, tests run, and the real entrypoint is smoke-started. This prevents packages already installed on the Jarvis host from hiding undeclared dependencies.

6. Reproducible native dependency/build gates
   npm installs dependencies before build/test. Cargo fetch/build/test, Go module download/test/build, dotnet restore/build/test, Gradle/Android builds, Maven, Flutter, Composer, Bundler, CMake, SwiftPM and other supported native tools are validated independently per component.

7. Strict host verification
   Missing Xcode, UnrealBuildTool, Unity, Godot, Swift, Flutter or another required host tool no longer counts as success. V35 returns an UNVERIFIED_HOST_TOOLCHAIN failure/checkpoint instead of falsely labeling the project COMPLETE.

8. Real validation only
   No-op commands/scripts such as "echo success", "echo no tests", "true" or "no test specified" cannot satisfy the build/test/acceptance gate.

9. Executable acceptance checks
   The architecture manifest can contain deterministic command and artifact-exists acceptance tests. These run only through Jarvis's safe-command gate and must pass before final completion.

10. Compiler diagnostics
    Common compiler error formats are condensed into file/line diagnostic hints before the failure enters the repair loop, giving the local 9B model more targeted evidence.

11. First-run delivery scripts
    Generated projects get:
      SETUP_AND_RUN.bat  - installs declared dependencies and launches the project
      BUILD_PROJECT.bat  - runs declared setup/build/test steps across components
      RUN_PROJECT.bat    - normal later launch
      JARVIS_RUN_INSTRUCTIONS.txt

12. Runtime/artifact proof
    Python receives clean-environment startup smoke testing. Runnable Node/Rust/Go/.NET components receive additional startup smoke where appropriate, and common web frameworks must actually produce their expected build output directory.

IMPORTANT LIMIT
---------------
No Windows-only local builder can genuinely compile every possible target in existence. Native Apple projects still require an Xcode/macOS build host; engine projects require the matching engine/toolchain. V35 handles this honestly by refusing to mark an unavailable host build as COMPLETE.

QUICK SELF-TEST
---------------
Run CHECK_V35_UNIVERSAL_BUILDER.bat from Windows. It tests V35 loading, stack recognition, no-op rejection, and mixed Node+Rust component discovery without needing to generate a project.
