# Dependency-graph repair

- Repair providers before consumers when many failures share one model/type/interface/schema/header/module.
- A planned canonical provider that is missing, rejected, stale, or incomplete is a root cause; restore it before rewriting callers.
- Re-run dependency/build evidence after a provider changes. Do not continue repairing consumers against stale diagnostics.
- Prefer one authoritative provider per component. Do not create compatibility duplicates merely to silence compiler/type errors.
- When several errors share the same dependency edge or symbol family, treat them as one root-cause cluster rather than unrelated leaf defects.
