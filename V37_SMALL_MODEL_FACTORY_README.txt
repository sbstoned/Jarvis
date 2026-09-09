JARVIS V37.0.0 - SMALL-MODEL SOFTWARE FACTORY
==============================================

Purpose
-------
V37 is tuned around Qwen3.5-9B Q4_K_M. The user experience remains one prompt -> project ZIP, but internally Jarvis decomposes the work into bounded engineering steps and owns more deterministic state itself.

Major V37 changes
-----------------
1. Semantic dependency resolver
   - Separates source-file dependencies from npm/pip/runtime/tool metadata.
   - Resolves Python dotted module and :symbol notation to actual project files.
   - Prevents the exact V36.2 TaskForge architecture false rejection.

2. Non-lossy source requirement ledger
   - Tolerates prompts flattened by UI/provider transport.
   - Freezes explicit stack, functional, acceptance, testing, repair, and delivery requirements before Qwen summarizes them.
   - Preserves traceability into the compiled specification.

3. Small-model working profile
   - Native llama.cpp context remains available (for example 262,144).
   - Default plan/generate/repair/audit working context: 32,768 tokens.
   - File output budget: 6,144 tokens with bounded continuation.
   - Normal generation receives only the requirements relevant to the target file plus global stack/platform constraints.

4. Repository intelligence owned by Jarvis
   - Ranked repository map.
   - AST-derived machine contract registry.
   - Provider/caller relationships and signatures.
   - Qwen does not have to remember the whole repository.

5. Read-before-edit + patch-first repair
   - Existing files are read immediately before repair.
   - Repair output is SEARCH/REPLACE, not a full file.
   - Exact candidate is validated transactionally before it can replace live source.
   - Large established files are protected against destructive whole-file fallback.

6. Failure-only deliberation
   - First repair attempt goes straight from concrete evidence to a small patch.
   - If it fails, V37 may request one very small root-cause diagnosis brief, then gives that brief to the patch editor.
   - This avoids spending reasoning tokens on the common happy path.

7. Loop/no-progress protection
   - Recent patch candidate fingerprints and rejection reasons are persisted.
   - Repeated candidates are rejected.
   - Existing project-level no-progress limits remain active.

8. Focused file viewer
   - Failure repair receives roughly 100 numbered lines around the strongest failure location instead of blindly dumping an entire large file.
   - Repo map and machine contracts supply the surrounding architectural context.

9. Actionable planning failure
   - Architecture/preflight failure is reported as architecture/preflight failure.
   - It no longer falls through to the misleading "Bootstrap recovery exhausted without any materializable source" message.

10. Bounded component planning
    - Complex projects are planned component-by-component.
    - Each component receives enough file budget for a real architecture, but each model call stays bounded.
    - Complex projects never fall back to a knowingly tiny demo manifest.

Verification
------------
Run:
    CHECK_V37_ALL.bat

For end-to-end Qwen testing:
    JARVIS_BENCH_V37.bat
or:
    python JARVIS_BENCH_V37.py --ids taskforge

Important
---------
Passing the included deterministic regression tests validates Jarvis machinery. It does not guarantee that a 9B model will solve every arbitrary long-horizon software project. V37 is designed to maximize the probability of success by narrowing each model decision and making Jarvis responsible for requirements, architecture semantics, contracts, validation, checkpoints, and recovery.
