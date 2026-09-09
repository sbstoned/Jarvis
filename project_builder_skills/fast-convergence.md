# Fast convergence

- Collapse error families by root cause. Do not spend multiple model turns on equivalent leaf errors.
- Prefer deterministic repairs and provider-level changes before model-authored consumer rewrites.
- After a provider/config/manifest changes, immediately obtain fresh build/test evidence; stale diagnostics must not drive more edits.
- Two failed focused leaf strategies are enough to escalate to a bounded subsystem/root-cause repair.
- Keep repair context focused on the target, provider contracts, direct dependents, and exact diagnostics; omit unrelated repository history.
- Final delivery remains strict: speed optimizations may reduce redundant attempts, never acceptance coverage or real validation.

## V42.22 build-first repair cadence

1. Run the real component compiler/build.
2. Parse exact compiler file locations.
3. Apply deterministic mechanical fixes first.
4. Repair at most a small number of compiler-located consumers.
5. As soon as one repair is accepted, stop editing and rerun the real build.
6. Reuse unchanged green sibling-component validation by source fingerprint.
7. If repeated fresh builds show no accepted-state/error-signature improvement, stop boundedly instead of rotating through unrelated providers.
