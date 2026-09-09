# Infrastructure-first validation

- Separate **project/source failures** from **validator/toolchain infrastructure failures** before choosing a repair target.
- Executable-not-found, sandbox denial, broken batch-wrapper invocation, unavailable SDK/compiler, external-CWD rejection, and process-spawn ENOENT are infrastructure debt. Do not ask a coding model to edit application source for them.
- Repair or refresh the runtime/toolchain deterministically, rerun the same real validator once, then stop boundedly with exact evidence if infrastructure is still unavailable.
- On Windows, package-manager `.cmd`/`.bat` shims may be invoked only through Jarvis's constrained internal batch wrapper; model-requested raw `cmd /c` remains prohibited.
- Share rebuildable dependency/compiler caches across disposable resume trials instead of copying or recreating them in each trial. Never package caches, `node_modules`, Cargo `target`, or runtime build state into the deliverable.
- Generated acceptance tests are consumers, not production API authorities. If Jarvis invented an optional acceptance test and the user did not ask for generated tests, that test must not block a production build. User-authored/existing tests remain authoritative.
