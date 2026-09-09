# Whole-Project Audit

- Final convergence must reason about the repository as a graph, not a sequence of isolated files.
- Collect static/contract/ownership/dependency problems and validate every component independently so the first failing component cannot hide later failures.
- Cluster failures by root cause. Prefer repairs that collapse many downstream errors: canonical providers, manifests/configs, schemas/interfaces, dependency declarations, then consumers.
- Re-run the whole audit after repairs. An issue is closed only when fresh deterministic/build/test evidence confirms it.
- Do not weaken build/test/acceptance requirements to make the audit green.
