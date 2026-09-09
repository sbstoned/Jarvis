Jarvis V42.22 - Consumer-First Compiler Ownership

Problem fixed
-------------
V42.21 correctly rejected damaging model edits, but an inherited provider-first heuristic still gave every canonical provider in the same component a positive repair score. A compiler error in App.tsx/components/hooks could therefore trigger repair rotation through clean DTO/type files such as category.ts, tool.ts, and checkout_record.ts.

V42.22 changes the repair authority order:

  fresh compiler location
    -> deterministic mechanical fix
    -> exact consumer/caller/component/hook repair
    -> fresh real build
    -> only then explicit provider repair when compiler evidence names that provider/module/export

Key changes
-----------
* Removes the same-component implicit provider bias.
* Protects accepted parse-clean TypeScript contract/DTO providers from speculative rewrites.
* TS2305/TS2307/TS2459/TS2724-style explicit module/export evidence can still target a provider.
* Parses TypeScript compiler locations and ranks App/entrypoint -> components/views -> hooks/services -> other source -> type providers.
* Gives a targeted repair read-only contracts from the target's actual local imports.
* Stops the repair round immediately after one accepted consumer edit so the next decision uses fresh build evidence.
* Merges duplicate React imports mechanically.
* Removes narrowly self-described cross-layer type hacks added only to satisfy unrelated Props contracts.
* Reuses unchanged green React/Rust component validation by source fingerprint to avoid rebuilding a green backend every frontend repair cycle.
* TypeScript build convergence allows several improving build/repair cycles but stops after repeated fresh-build no-progress, rather than running for hours.
* Preserves V42.21 semantic-role, runtime-entrypoint and compiler-error-delta transaction gates and all earlier sandbox/toolchain/topology protections.

This is stack-agnostic in intent: provider mutation requires direct evidence, while compiler-located consumers get first refusal. The TypeScript implementation is the first concrete adapter because that is the reproduced failure class.
