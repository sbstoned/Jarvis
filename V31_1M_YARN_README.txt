JARVIS V31.1 - QWEN3.5 9B ~1M YARN CONTEXT
=========================================

This build keeps the V27 continuation engine and V30 root-cause/provider repair
engine, and adds a Qwen3.5-specific long-context startup ladder.

Default Qwen3.5 target:
  1,010,000 tokens
  --rope-scaling yarn
  --rope-scale 4
  --yarn-orig-ctx 262144

Automatic fallback ladder:
  1,010,000 -> 524,288 -> 262,144 -> 131,072 -> 65,536 -> 40,960

Context-specific memory policy:
  >262K: static YaRN, q4_0 K/V, CPU KV when supported, server RAM prompt cache off
   262K: native RoPE, q4_0 K/V, CPU KV when supported
  <=131K: native RoPE, q8_0 K/V, normal KV offload

The launcher validates available llama.cpp flags from `llama-server --help`.
If YaRN CLI support is missing, extended contexts are skipped safely.

Important: a model supporting 1M context does not guarantee a 16 GB RAM / 8 GB
VRAM laptop can allocate it. The fallback ladder is intentional and the actual
running context is written to qwen_runtime_profile.json and exposed by /props.

Run CHECK_QWEN_MAX_CONTEXT.bat after startup to see what actually loaded.

V31.1 FIX: Qwen3.5 ignores legacy JARVIS_QWEN_CONTEXT=40960 and context caches are invalidated on model switch. Live /props context is verified before startup is declared successful.

Qwen3.5 automatic fallback floor is 131,072 tokens. 40,960 remains only for the separate Qwen3-8B profile.
