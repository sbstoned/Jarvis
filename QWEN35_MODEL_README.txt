JARVIS - QWEN3.5 9B HAUHAUCS AGGRESSIVE - V32 NATIVE 262K THROUGHPUT

Default: 262,144 native context, GPU/offloaded KV when llama.cpp can fit it, prompt caching ON, one slot.
Fallback: 131,072. Extended YaRN is opt-in with JARVIS_QWEN35_TRY_YARN=1.

V32 deliberately separates SERVER CONTEXT from WORKING PROMPT SIZE: the server keeps 262K available, while ordinary generate/repair calls use bounded 32K-65K working windows to avoid massive repeated prefill.

--- HISTORICAL NOTES ---
JARVIS - QWEN3.5 9B HAUHAUCS AGGRESSIVE - V31.1 1M YaRN
=========================================================

Dropdown profile:
  QWEN3.5 9B - HAUHAUCS AGGRESSIVE Q4_K_M (1M YARN)

Default model location:
  D:\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\GGUF\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf

Install model:
  Double-click DOWNLOAD_QWEN35_9B_AGGRESSIVE_Q4_K_M.bat

V31.1 runtime ladder:
  1. 1,010,000 tokens - YaRN factor 4 - q4_0 K/V - CPU KV when supported
  2.   524,288 tokens - YaRN factor 2 - q4_0 K/V - CPU KV when supported
  3.   262,144 tokens - native context - q4_0 K/V - CPU KV when supported
  4.   131,072 tokens - native context - q8_0 K/V
  5.    65,536 tokens - native context - q8_0 K/V
  6.    40,960 tokens - final memory-safe fallback - q8_0 K/V

The launcher reads llama-server --help before using YaRN. If the installed build
lacks the required YaRN flags, it skips >262K and starts at the native 262,144
context instead of launching an invalid configuration.

For >=262K attempts, V31.1 disables the server RAM prompt cache where supported so
that memory is available for the very large context state. It also disables KV
offload at those sizes when supported, moving KV to CPU memory so the Q4_K_M
weights can remain GPU resident on the 8 GB RTX 4070 Laptop.

The model is 262K native and the model card states it is extendable to 1M with
YaRN. Qwen's official long-context example uses factor 4 with a 1,010,000-token
maximum and recommends adjusting the static YaRN factor to the actual target.

V31.2: Qwen3.5-9B is now the default/AUTO local model. The 8B remains available in the dropdown.

V31.1 FIX: Qwen3.5 ignores legacy JARVIS_QWEN_CONTEXT=40960 and context caches are invalidated on model switch. Live /props context is verified before startup is declared successful.

Qwen3.5 automatic fallback floor is 131,072 tokens. 40,960 remains only for the separate Qwen3-8B profile.
