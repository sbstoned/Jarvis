# Testing

V41.1 focused engineering rules:

- Use conventional Testing repository layout and native tooling.
- Keep manifests/configuration as metadata unless the ecosystem explicitly treats them as source.
- Declare dependencies and public interfaces before consumers.
- Use real non-interactive build/test commands and repair exact failures.

## V41.2 build-gate diagnosis
- Compiler/build failures are root-cause evidence. `TS17004` repairs TypeScript JSX configuration; `TS2307` on a relative import repairs provider closure/ownership, not random unrelated files.
- A milestone may advance only after its real build/test command reruns green after repair.
