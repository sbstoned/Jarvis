JARVIS V32 QWEN3.5 CONTEXT / THROUGHPUT

Qwen3.5 default server context: 262,144 native.
Jarvis working prompt windows: ~32K-65K normally, <=98K for direct whole-project edits.
This preserves long-context capacity without making every call pay 262K-scale prefill cost.
If native 262K cannot fit with hot KV offload, V32 falls to 131,072 rather than defaulting to CPU-KV crawl.
Set JARVIS_QWEN35_TRY_YARN=1 only to experiment with >262K YaRN.

--- HISTORICAL NOTES ---
JARVIS QWEN MAX-CONTEXT STARTUP PATCH
======================================

This build starts the installed Qwen3-8B Abliterated Q4_K_M server automatically whenever Jarvis starts.
No separate PowerShell llama-server command is required.

Expected managed Qwen endpoint:
  http://127.0.0.1:8081

Expected 8B runtime:
  context                  40960 tokens
  server max generation    32768 tokens
  parallel slots           1
  GPU layers               all
  split mode               none (single RTX 4070)
  main GPU                 0
  KV cache                 q8_0 / q8_0
  flash attention          on when supported
  context shift            off
  Jinja                    on
  reasoning format         deepseek when supported
  temperature              0.6
  top-k                    20
  top-p                    0.95
  min-p                    0
  presence penalty         1.5
  repeat penalty           1.0

Jarvis startup files already call START_QWEN_LOCAL.bat automatically:
  START_COMMAND_CENTER.bat
  START_ALL.bat
  START_JARVIS.bat
  START_JARVIS_SERVICES.bat
  START_VOICE_ENGINE.bat

The launcher now checks the actual running context. A healthy old 8192-token Qwen server is NOT accepted;
it is stopped and replaced with the requested managed runtime. It also stops duplicate llama-server processes
using the same selected GGUF on another port so the 8 GB GPU is not split between two copies.

Verification:
  Double-click CHECK_QWEN_MAX_CONTEXT.bat

For Qwen3-8B the expected result is:
  Context     : 40960
  One slot    : True
  Ctx shift   : OFF
  GPU layers  : ALL
  Split mode  : NONE / single GPU
  PASS

Emergency override only if 40960 cannot allocate on the machine:
  set JARVIS_QWEN_CONTEXT=32768

The V27 local_qwen_project.py completion engine is retained. It budgets against the live llama.cpp /props
context size, resumes truncated files across multiple calls, validates/repairs the repository, and only publishes
completed output after its acceptance gates pass.

QWEN3.5 9B V31.1 1M YARN
-------------------------
The HauhauCS Qwen3.5-9B Aggressive Q4_K_M profile is profile 9b35.
V31.1 attempts 1,010,000 tokens using YaRN factor 4, then automatically falls back:
  524,288 (YaRN factor 2) -> 262,144 native -> 131,072 minimum.
CHECK_QWEN_MAX_CONTEXT.bat shows the live context, YaRN state, KV type and fallback.

V31.1 FIX: Qwen3.5 ignores legacy JARVIS_QWEN_CONTEXT=40960 and context caches are invalidated on model switch. Live /props context is verified before startup is declared successful.

Qwen3.5 automatic fallback floor is 131,072 tokens. 40,960 remains only for the separate Qwen3-8B profile.
