JARVIS V31.1 - QWEN3.5 1M YARN CONTEXT FIX

Why V31 could still show 40,960:
1. Legacy JARVIS_QWEN_CONTEXT=40960 could override Qwen3.5.
2. multi_provider could cache the prior 8B server context for up to 60 seconds after a model switch.
3. local_qwen_project still used 40,960 as a generic diagnostic/fallback value.

V31.1 fixes all three.

Qwen3.5 launch policy:
  1,010,000  YaRN factor 4
    524,288  YaRN factor 2
    262,144  native
    131,072  native

The generic legacy variables JARVIS_QWEN_CONTEXT and JARVIS_QWEN_CONTEXT_TOKENS are ignored when the selected model is Qwen3.5. Use JARVIS_QWEN_35_CONTEXT only if you intentionally want to override Qwen3.5.

START_QWEN_LOCAL.ps1 now queries /props before announcing success. If llama.cpp reports a different live context than the requested -c value, Jarvis treats that as a failed attempt rather than pretending the requested context is active.

Qwen3.5 automatic fallback floor is 131,072 tokens. 40,960 remains only for the separate Qwen3-8B profile.
