Jarvis V42.30 - Fresh Compiler Last-Mile Activation

Purpose
- Preserve V42.26's successful compiler-proof repair path.
- Preserve V42.27 parser safety, V42.28 best-state promotion, and V42.29 constraint solvers.
- Ensure a real small TypeScript tail (for example 8 diagnostics) is solved BEFORE broad Qwen repair.

Key changes
1. Resume preflight runs a fresh real validation snapshot and activates deterministic last-mile constraints for <=12 syntax-clean TypeScript diagnostics.
2. Old/noisy checkpoint or audit issue lists cannot suppress the last-mile solver.
3. Post-acceptance fallback repeats the same rule from fresh real compiler evidence, once and boundedly.
4. TS2322 object-shape errors can preserve declared boolean fields even when TypeScript puts the useful property detail on a continuation line.
5. An on-disk engine marker prevents future stale long-running Jarvis processes from silently starting project work after a newer engine is installed.
6. All last-mile changes remain provisional until a fresh whole-TypeScript compile and V42.28 best-state score prove improvement.
