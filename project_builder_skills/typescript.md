# Typescript

V41.1 focused engineering rules:

- Use conventional Typescript repository layout and native tooling.
- Keep manifests/configuration as metadata unless the ecosystem explicitly treats them as source.
- Declare dependencies and public interfaces before consumers.
- Use real non-interactive build/test commands and repair exact failures.

## V41.2 TypeScript build rules
- Any project compiling `.tsx` must set `compilerOptions.jsx`; for modern React use `react-jsx` unless the framework requires another supported mode.
- Project references used by `tsc -b` must point only to real/planned config files in the current build substrate.
- Treat `TS2307` for a relative import as provider ownership evidence: repair the missing/current provider or remove a premature future-milestone import from a bootstrap consumer.

## V42.2 TypeScript project-reference rule
Before using `tsc -p/--project`, verify that the referenced tsconfig exists/planned in the same build component. In mixed repositories, never point a frontend TypeScript build at a native/backend component directory to satisfy the compiler command.
