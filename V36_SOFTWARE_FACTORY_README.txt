JARVIS V36.0.0 UNIVERSAL SOFTWARE FACTORY
==========================================

Purpose
-------
V36 keeps the one-user-prompt workflow, but moves project memory and verification away from the model and into deterministic Jarvis machinery. Qwen is asked to solve smaller engineering tasks with precise repository/contract evidence instead of remembering an entire project from raw context.

Major V36 changes
-----------------
1. PRE-IMPLEMENTATION REQUIREMENTS COMPILER
   - A fresh Requirements Engineer call converts the user prompt into functional requirements, constraints, acceptance criteria, and test scenarios before architecture/code.
   - The specification is machine-owned in JARVIS_V36_REQUIREMENTS.json during generation.

2. RANKED REPOSITORY GRAPH / REPO MAP
   - Python is parsed with AST; other common languages use conservative dependency-free symbol/import extraction.
   - File dependency edges are weighted from imports, unique symbol references, and the planned dependency DAG.
   - A PageRank-style centrality pass ranks the repository.
   - Qwen receives ranked symbols/signatures plus only a small number of complete relevant files instead of broad repository dumps.
   - Graph state is cached and invalidated by file mtime/size/manifest changes.

3. MACHINE-OWNED CONTRACT REGISTRY
   - Planned exports/contracts and actual Python AST method/function signatures are persisted in JARVIS_V36_CONTRACT_REGISTRY.json.
   - V36 follows annotated constructor dependencies into self attributes and checks bound cross-file calls deterministically.
   - This specifically catches StockPilot-style caller/provider drift such as self.db.insert_item(item) when the provider expects multiple positional fields.

4. PATCH-FIRST REPAIRS
   - New files are still generated as complete files.
   - Repairs first request exact SEARCH/REPLACE blocks, not a complete-file rewrite.
   - Jarvis applies each patch to a candidate only, validates it, and commits only if the transaction is safe.
   - If the first patch fails, V36 can generate additional candidates and choose the smallest validated repair.
   - Mature V35.1 full-file transactional repair remains the fallback.

5. PRE-COMMIT SYNTAX/CONFIG GATES
   - Python AST parse, JSON parse, TOML/XML parse, Node --check for ordinary JS, PHP -l and Ruby -c when those tools are available.
   - Invalid candidate edits never replace the live file.

6. FAILURE LOCALIZATION
   - Tracebacks/compiler-style file:line evidence, exception signatures, test identity, and common missing symbols are extracted into JARVIS_V36_LAST_FAILURE.json.
   - Debug prompts receive the localized failure, relevant repo graph slice, contracts, and target excerpt.

7. CHECKPOINT / ROLLBACK SUPPORT
   - Every patch/full-rewrite repair checkpoints the previous file under .jarvis_backups.
   - Every real green validation can create a compact source/config workspace checkpoint.
   - _v36_restore_last_green_checkpoint() can restore the latest green checkpoint for diagnostics/manual recovery.
   - Candidate repairs remain transactional, so most failed edits never need rollback at all.

8. FRESH SPECIALIZED MODEL ROLES
   - Requirements Engineer
   - Software Architect
   - Implementer
   - Debugger/Patch Engineer
   - QA Reviewer
   Each call is deliberately scoped to its role; Jarvis state remains the authority.

9. STACK-SPECIFIC SKILLS
   project_builder_skills/ contains concise rules for Python, Tkinter, React, Node, Tauri, Rust, Flutter, Android, Unreal, Godot, .NET, C++, and iOS.
   Only skills relevant to the chosen stack are injected.

10. CLEAN ENVIRONMENT / TOOLCHAIN VALIDATION
    - Existing V35 clean Python venv and per-component native validation remain.
    - Optional Docker clean-room validation is available for supported Python/Node components:
        set JARVIS_V36_CONTAINER_VALIDATION=1
      It is OFF by default because image pulls can add significant time and native Windows/engine projects require host validation.

11. LLAMA.CPP PROMPT CACHE + OPTIONAL SPECULATIVE DECODING
    - Existing multi_provider.py already sends cache_prompt=true.
    - V36 uses stable role prefixes and smaller changing context to make prompt-prefix reuse more useful.
    - START_QWEN_LOCAL.ps1 supports an OPT-IN ngram-simple speculative mode on llama.cpp builds that expose the current flags:
        set JARVIS_QWEN_SPECULATIVE_NGRAM=1
      Stop/restart the managed llama-server after changing it.
    - This is OFF by default until benchmarked on the user's hardware/model because speedup varies by workload/build.

12. JARVIS-BENCH
    - JARVIS_BENCH_V36.py contains a repeatable cross-stack prompt suite.
    - List cases:
        python JARVIS_BENCH_V36.py --list
    - Run one real Qwen generation:
        python JARVIS_BENCH_V36.py --limit 1
    - Run named cases:
        python JARVIS_BENCH_V36.py --ids stockpilot,tauri
    Real benchmark cases can each take 30-60+ minutes because they intentionally run the full Qwen pipeline.

High-impact behavior preserved from V35.1
----------------------------------------
- Universal/multi-component toolchain discovery.
- Tauri/Android/Gradle/Maven/Swift/Xcode/Unreal/Flutter/Rust/Go/.NET/etc. awareness.
- Clean Python venv validation.
- Strict PASS vs UNVERIFIED host-toolchain status.
- Node dependency installation and noninteractive framework-aware tests.
- Runtime smoke tests and executable acceptance gates.
- Fake/no-op build/test command rejection.
- Transport-marker salvage.
- Duplicate-provider architecture collision detection.
- InventoryView.COLUMNS class-constant false-positive fix.
- Evidence-first real failure repair priority.

Context guidance
----------------
Keep the llama.cpp server at the large native context you configured. V36 does NOT treat 262K as a target prompt size. The repo map, contract registry, target excerpts, and stack skills intentionally keep normal implementation/repair prompts much smaller and more relevant while retaining the native context as emergency capacity.

Useful environment controls
---------------------------
JARVIS_V36_DYNAMIC_CONTEXT=1
JARVIS_V36_PATCH_REPAIRS=1
JARVIS_V36_REQUIREMENTS_COMPILER=1
JARVIS_V36_REPAIR_CANDIDATES=3
JARVIS_V36_REPO_MAP_CHARS=14000
JARVIS_V36_RELATED_FULL_CONTEXT_CHARS=24000
JARVIS_V36_CONTAINER_VALIDATION=0
JARVIS_QWEN_SPECULATIVE_NGRAM=0

Recommended first test
----------------------
Use the exact same StockPilot prompt for V36 that was used to benchmark the old V34.1/V35 line. Record total time, generated files, Qwen repair calls, test failures, acceptance rounds, and final ZIP result. The included Jarvis-Bench stockpilot case can also be used for repeatable later comparisons.
