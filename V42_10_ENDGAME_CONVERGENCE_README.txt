JARVIS V42.10 - ENDGAME CONVERGENCE + TRUE WHOLE-PROJECT AUDIT
================================================================

Purpose
-------
V42.10 fixes the late-stage acceptance/test deadlock observed in project_20260831_204118 and strengthens final convergence without weakening publication requirements.

Key fixes
---------
1. Requirement-owner self-acceptance
   A real file that owns requirement debt (for example tests) may be evaluated as the artifact that satisfies that debt. Final acceptance remains strict and still requires an accepted implementation.

2. Provider-safe test generation
   Acceptance/integration tests are instructed to import production contracts and behavior instead of copying/redefining production models. After repeated failed test-owner attempts, Jarvis can create a production-linked compile/smoke test seed rather than looping forever.

3. Test runner substrate closure
   Components with planned tests must have a native runnable test command. React/Vite test plans get Vitest configuration and package test dependencies/scripts; Rust test plans use cargo test; other adapters use their registered native test command when available.

4. Deterministic conventional endgame files
   Stable boilerplate such as tsconfig.node.json and compatible TypeScript contract barrels are generated deterministically rather than consuming repeated model repair attempts.

5. Rust module reachability
   Planned top-level Rust production modules are exposed from src/lib.rs so cargo check/test compiles the actual generated backend instead of accidentally validating an almost-empty crate root.

6. Safe cargo check
   The command broker no longer mistakes --message-format for the destructive Windows FORMAT command.

7. Local TypeScript diagnostics only
   Live diagnostics use the project's node_modules/.bin/tsc. Jarvis restores npm dependencies when needed and will not allow npx to download the unrelated deprecated package named tsc.

8. Real test quality gate
   An accepted test must contain a real test declaration, an assertion, and a reference/import to production code/contracts. Empty/TODO/fake-model tests do not satisfy final acceptance.

9. True whole-project audit
   Every final convergence round validates every discovered component independently, in addition to all planned files, canonical providers, requirements, static contracts, dependencies and ownership checks. One failing component cannot hide another.

Exact 204118 replay
-------------------
The supplied project snapshot had 45 accepted revisions and was looping on src-tauri/tests/acceptance_2.rs. The journal showed repeated cycles where the test was rejected because "tests owner is not a real implemented file" before it could itself satisfy that requirement, plus later attempts that redefined Tool, CheckoutRecord, Person and Category.

In a deterministic replay of that exact snapshot:
- static whole-project issues before V42.10 endgame closure: 10
- static whole-project issues after V42.10 deterministic endgame closure: 0

This does not claim the application is compiled successfully in this Linux validation environment. The next Windows run remains responsible for real npm/TypeScript/Vite and Cargo/Rust build/test/runtime evidence.

AUTO model routing
------------------
AUTO remains the default:
- Qwen3.5 9B HauhauCS Aggressive: routine generation/first-pass repairs
- Qwen3.8 27B HauhauCS Aggressive Q2_K_P: architecture, repeated/root-cause failures, difficult integration and global convergence
- legacy OBLITERATED 27B is not used automatically
- manual dropdown selections remain strictly locked

Publication rule
----------------
Jarvis may publish a project ZIP only after the final whole-project audit, real build/test/runtime validation, requirement acceptance and unresolved debt all reach green/zero.
