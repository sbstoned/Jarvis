# Unity

V41.1 focused engineering rules:

- Preserve Assets, Packages, and ProjectSettings as canonical Unity roots.
- Validate with the installed Unity Editor in batchmode when available; do not treat dotnet build as equivalent engine proof.
- Keep C# scripts compatible with the project Unity version and package manifest.
