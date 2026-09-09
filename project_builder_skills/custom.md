# Custom

V41.1 focused engineering rules:

- Use a custom adapter only when source layout and real dependency/build/test/run commands are explicit.
- At least one non-noop build or test command is required before COMPLETE status.
- Do not silently substitute Python for an unfamiliar ecosystem.
