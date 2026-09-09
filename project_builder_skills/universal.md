# Universal

V41.1 focused engineering rules:

- Honor the requested product, stack, platform, and observable behavior.
- Freeze public contracts before consumers; one canonical owner per domain type.
- Build vertical slices and run real build/test gates before advancing.
- Never claim completion from source inspection alone when a native verifier exists.

## V41.2 current-slice closure
- The full architecture is not the current filesystem. Consumers may reference only providers already green or planned in the active milestone.
- Never call a file green merely because a future provider exists in the architecture plan.

## V42.2 component build/config ownership
- Every buildable component owns a coherent build substrate: manifest/build descriptor, compiler configuration, source root, dependency command, build command, test command, and working directory must agree.
- A command must not point at a config/manifest inside another component merely to make a build command look complete. Shared configuration is allowed only when it is explicitly planned as shared.
- Validate configuration-path arguments before invoking the real compiler/build tool. If a conventional config path is wrong, repair the command/config relationship first; do not rewrite unrelated source files.
- Direct source self-import/self-include cycles are generation defects and should be rejected before commit when the reference resolves to the consumer file itself.
