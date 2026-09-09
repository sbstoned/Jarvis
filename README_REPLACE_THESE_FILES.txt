JARVIS v2.74.1 - QWEN3.5 9B V37 SMALL-MODEL SOFTWARE FACTORY

CURRENT RELEASE: see V37_SMALL_MODEL_FACTORY_README.txt, V37_VALIDATION_REPORT.txt, and V37_RESEARCH_NOTES.txt. Older notes below are retained as migration history.

JARVIS v2.74.1 - QWEN3.5 9B V31.1 1M YARN + V30 ROOT-CAUSE COMPLETION ENGINE
==================================================================

This bundle preserves the V27 project-completion engine and adds a third local
Qwen choice:

  QWEN3.5 9B - HAUHAUCS AGGRESSIVE Q4_K_M (1M YARN)

Existing choices remain:
  QWEN3 8B - ABLITERATED Q4_K_M (8 GB FAST)
  QWEN3.8 27B - OBLITERATED Q4_K_M (LARGE QUALITY)

WHAT CHANGED
------------
* Dashboard dropdown can select qwen35 / profile 9b35.
* qwen_model_manager.py can install-detect, persist, switch, and identify the new model.
* START_QWEN_LOCAL.ps1 uses a Qwen3.5-specific long-context profile:
    first try 131,072 tokens, then automatic 65,536 / 40,960 fallback on memory failure.
* Qwen3-8B keeps its existing 40,960-token one-slot max-context profile.
* V31.2: AUTO now prefers Qwen3.5-9B; the 8B remains an explicit fallback/dropdown choice.
* multi_provider.py and local_qwen_project.py use model-aware sampling.
* Qwen3.5 precise coding thinking uses temp 0.6 / top_p 0.95 / top_k 20 /
  min_p 0 / presence 0; non-thinking emission uses temp 0.7 / top_p 0.8 /
  top_k 20 / min_p 0 / presence 1.5.
* One llama.cpp server remains on port 8081; switching never keeps multiple models resident.
* New resumable downloader:
    DOWNLOAD_QWEN35_9B_AGGRESSIVE_Q4_K_M.bat


V30 RUNTIME/REPAIR CONVERGENCE CHANGES
--------------------------------------
* Python module graph now indexes BOTH nested import spellings when valid, e.g.
    app.inventory_service
    StockPilot.app.inventory_service
  so consumer-required exports cannot disappear just because different files use different import roots.
* Transactional full-file repairs now preserve imports required through either alias.
* `ImportError: cannot import name X from Y` routes to Y's provider instead of repeatedly rewriting the caller.
* Missing module-level function exports are synthesized surgically first and the exact failing validator is replayed.
* Non-improving surgical runtime changes are rolled back automatically.
* Stable runtime failures are counted across acceptance passes/resume state.
* Repeated failures escalate to provider/dependency targets and track which targets already failed.
* Once one replay-gated repair advances the validator, Jarvis stops editing from stale failure evidence and starts a fresh validation pass.

INSTALL
-------
Do NOT install this patch while a Qwen project generation is still running.
Let the current job finish first.

Then:
  1. Extract this ZIP.
  2. Run INSTALL_REPLACEMENTS.bat
  3. Run DOWNLOAD_QWEN35_9B_AGGRESSIVE_Q4_K_M.bat
  4. Restart Jarvis using START_COMMAND_CENTER.bat
  5. Select QWEN3.5 9B in the dashboard dropdown.

Default model path:
  D:\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\GGUF\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf

The installer creates a timestamped backup before replacing files.

V31.1 FIX: Qwen3.5 ignores legacy JARVIS_QWEN_CONTEXT=40960 and context caches are invalidated on model switch. Live /props context is verified before startup is declared successful.
