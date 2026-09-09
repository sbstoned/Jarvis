# React

V41.1 focused engineering rules:

- Use conventional React repository layout and native tooling.
- Keep manifests/configuration as metadata unless the ecosystem explicitly treats them as source.
- Declare dependencies and public interfaces before consumers.
- Use real non-interactive build/test commands and repair exact failures.

## V41.2 current-slice React convergence
- An early `main.tsx`/`main.jsx` is a dependency-closed boot shell. It must not import `App`, screens, feature components, hooks, or styles scheduled for later milestones.
- Integrate the real `App` only after its providers are materialized and green; use the integration-touchpoint pass to evolve the boot shell.
- For TypeScript React, the active `tsconfig` must enable JSX (`react-jsx` preferred for React 17+).
