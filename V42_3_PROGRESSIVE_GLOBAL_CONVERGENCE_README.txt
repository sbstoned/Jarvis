JARVIS V42.3 PROGRESSIVE GLOBAL CONVERGENCE FACTORY
===================================================

Design rule: flexible while building, ruthless before publishing.

What changed from V42.2
-----------------------
1. Final architecture coverage gaps no longer automatically abort generation.
   Jarvis first asks Qwen to correct the plan; if concrete requested behavior/test
   owners are still absent, V42.3 adds the smallest stack-native planned owners,
   records them as requirement debt, and continues.

2. Requirement Debt Ledger
   .jarvis_build/V423_REQUIREMENT_DEBT.json tracks plan gaps, synthetic owners,
   intermediate build debt, unresolved materialization and convergence status.
   Debt is internal and is not a substitute for implementation. A debt owner that
   never becomes a real implemented file is a hard final acceptance failure.

3. Progressive build debt
   Milestone/component build failures are still repaired immediately when practical.
   If a bounded repair does not converge but the repository has useful independent or
   future planned work, Jarvis can continue materializing the rest of the plan instead
   of discarding the whole run. The normal whole-project acceptance engine then owns
   the final convergence.

4. Strict final convergence remains mandatory
   Before publication Jarvis still requires deterministic/static checks, missing-file
   recovery, API/contract repair, real dependency/build/test validation, requested test
   ownership, semantic QA, final verification and the hard publish gate. Build debt is
   never allowed in a published final ZIP.

5. Expanded developer ecosystem registry
   72 registry adapters plus the universal/custom fallback. New registered ecosystems
   include Deno, Bun, PowerShell, Bash, Docker Compose, Kubernetes/Helm, Clojure, F#,
   Crystal, Racket, Fortran/CMake, CUDA/CMake and Rust/WebAssembly.

6. Expanded capability discovery
   Additional probes include Deno, PowerShell, Bash, kubectl, Helm, Podman, uv,
   Poetry, pytest, Ruff, mypy, Clojure/Lein/Babashka, Crystal, Racket, NVCC,
   gfortran and wasm-pack.

7. Expanded skill library
   76 skill cards. Added universal process/domain cards for build systems,
   diagnostics, integration testing, data import/export, APIs, Docker, Kubernetes,
   secure engineering, and additional language/runtime ecosystems.

8. Registry-driven imported-project detection
   New ecosystems can be detected from their registered marker files when resuming or
   importing a repository, reducing the need to add another central routing branch.

9. More context headroom where it matters
   Planning, repair and audit default working windows use at least 49,152 tokens on
   Qwen3.5 when the user has not overridden them. Routine file generation remains
   compact for throughput; the live model context remains available as the ceiling.

10. More bounded final repair budget
    Default whole-project acceptance has a little more room to converge while keeping
    no-progress limits and transactional repair guards. It is still bounded.

The target remains language/framework agnostic. Adapter cards describe native ecosystem
commands and conventions; universal Jarvis machinery owns planning, environment,
generation, revision acceptance, repair, convergence, validation and packaging.
