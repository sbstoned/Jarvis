JARVIS V41.1 UNIVERSAL MULTI-TOOLCHAIN FACTORY
================================================

This release extends the existing V40.x convergence/milestone engine instead of replacing it.

Key changes
-----------
- 59 registered native toolchain adapters plus dynamic custom-toolchain support.
- 58 compact project_builder_skills cards loaded dynamically during architecture, file generation, and repair.
- Framework/engine specificity outranks language (Unity/C#, Unreal/C++, Qt/C++, Tauri/Rust, Android/Kotlin, iOS/Swift, Electron/TypeScript, xmake/C++).
- Project kinds (game/mobile/desktop/web/backend/etc.) are separate from target platform (Android/iOS/Windows/macOS/Linux/web/cross-platform).
- Unknown explicit ecosystems are not silently converted into Python. Custom adapters require real source/layout evidence plus a non-noop build/test path.
- Unreal/Unity discovery checks PATH, environment overrides, and common Windows install locations.
- Unreal validation can derive a concrete *.Target.cs target and run Win64 Development through UnrealBuildTool when the engine exists.
- jarvis.py no longer hard-codes max_files=80; it uses JARVIS_QWEN_PROJECT_MAX_FILES (default 160), while the generator enforces its hard ceiling (default 1000).
- Casual imperative project requests can route directly to autonomous project generation; explanatory questions remain chat.

Validation
----------
Run CHECK_V411_UNIVERSAL_FACTORY.bat or: python CHECK_V411_UNIVERSAL_FACTORY.py
The deterministic release regression contains exactly 135 checks.

Important
---------
A host-specific engine project is only marked fully verified when its real native toolchain is actually available and the declared build/test gate passes. Otherwise Jarvis reports host-unverified/checkpoint state instead of pretending a different toolchain proved it.
