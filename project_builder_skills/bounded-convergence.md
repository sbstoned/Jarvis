# Bounded convergence and specialist progress

Use accepted repository state and real validator/audit evidence as the only progress clock.

- Never treat a model response, draft, retry count, or elapsed time as progress.
- Do not repeat an already-rejected strategy at the same accepted revision.
- A canonical-provider failure gets at most one focused specialist diagnosis per unchanged accepted state by default.
- If the specialist does not create accepted progress, prefer deterministic contract/owner/config synthesis and dependency-root repair over another model call.
- Cluster whole-project failures by root cause. Provider/config/dependency/build-graph fixes precede consumer edits.
- Revalidate every independently discoverable component so one failing stack cannot hide another.
- If specialist + deterministic recovery cannot change accepted state across the bounded no-progress budget, stop with consolidated evidence rather than looping indefinitely.
- Never weaken build, test, runtime, requirement, or zero-debt acceptance criteria to escape a loop.
