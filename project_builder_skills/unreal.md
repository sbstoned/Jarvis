# Unreal

V41.1 focused engineering rules:

- A .uproject plus Source/*/*.Build.cs and *.Target.cs defines the native topology.
- Use UnrealBuildTool/Build.bat from the installed engine; do not substitute CMake for an Unreal project.
- Derive a concrete target from *.Target.cs and use the requested platform when known.
