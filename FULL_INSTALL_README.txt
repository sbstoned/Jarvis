JARVIS v2.74.1 V33 SYSTEMATIC BUILD COMPLETE SOURCE BUNDLE
=========================================

This archive contains the complete Jarvis source/project tree supplied for this build, including:
- Jarvis backend and voice/dashboard integration
- dashboard/UI files
- startup and desktop scripts
- Qwen3 / Qwen3.5 / Qwen3.8 local-model manager
- V27 truncated-file continuation
- V30 provider/root-cause repair and acceptance gates
- V32 native-262K throughput controls
- V33 contracts-first, skeleton-first, dependency-ordered project generation
- V33 failure-specific repair prompts and deterministic runtime diagnosis bypass
- hardware helper source/binaries and support tools already present in the supplied project

V33 IMPORTANT CHANGE
--------------------
New projects are now designed as a complete dependency/API contract before implementation. Jarvis materializes the planned repository shape immediately, then implements foundation/data/service/UI/entrypoint/tests in dependency order. See V33_SYSTEMATIC_BUILD_README.txt.

V32 RUNTIME CHANGE
------------------
Qwen3.5 still starts with a 262,144-token native server window, but routine coding calls use bounded
working windows and prompt reuse. Native 262K keeps KV offload enabled and lets llama.cpp --fit trade
model layers as needed, instead of forcing the hot KV state into system RAM. See
V32_THROUGHPUT_README.txt for details.

SECURITY NOTE
-------------
ai_providers.env is intentionally NOT included because the supplied installation contained live API keys.
INSTALL_REPLACEMENTS.bat does not overwrite your existing ai_providers.env.

UPGRADE AN EXISTING C:\Users\<USER>\Jarvis
-------------------------------------------
1. Let any active generation finish or stop it cleanly.
2. Extract this ZIP somewhere temporary.
3. Run INSTALL_REPLACEMENTS.bat from the extracted folder.
4. Restart Jarvis with START_COMMAND_CENTER.bat.
5. Run CHECK_QWEN_MAX_CONTEXT.bat, then CHECK_QWEN_PERFORMANCE.bat while Jarvis is idle.

FRESH/COPY INSTALL
------------------
If you replace the whole Jarvis directory, preserve your existing local ai_providers.env and any other
local credentials/configuration first, then restore them after copying the source bundle.

Do not commit ai_providers.env or other live credentials to Git.

V34.1 UNIVERSAL BUILDER UPDATE
------------------------------
This bundle includes V34.1 universal toolchain planning/validation and resilient
bootstrap recovery. See V34_1_UNIVERSAL_BUILDER_README.txt.

