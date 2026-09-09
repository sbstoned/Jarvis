# Vite

V41.1 focused engineering rules:

- Use conventional Vite repository layout and native tooling.
- Keep manifests/configuration as metadata unless the ecosystem explicitly treats them as source.
- Declare dependencies and public interfaces before consumers.
- Use real non-interactive build/test commands and repair exact failures.

## V41.2 Vite substrate rules
- Unless `vite.config` explicitly sets a different `root`, the HTML host is repository-root `index.html`, not `src/index.html`.
- A Foundation build must contain a valid root HTML host and a dependency-closed entry module before `vite build` is allowed to gate the milestone.
- If `tsc -b` references `tsconfig.node.json`, that config must be planned/materialized in the same Foundation slice.
