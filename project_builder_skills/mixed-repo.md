# Mixed Repo

V41.1 focused engineering rules:

- Treat each independently buildable root as a component.
- Declare component dependency direction and validate every component, not only the first marker found.
- Do not duplicate shared contracts across package-manager or language boundaries.

## V42.2 component boundary rule
For mixed repositories, treat each build root as an execution boundary. Root-level frontend commands must not consume nested backend compiler configs (and nested components must not reach into sibling configs) unless the architecture explicitly defines that config as shared. Keep command cwd, manifest, compiler config, and source root aligned per component.
