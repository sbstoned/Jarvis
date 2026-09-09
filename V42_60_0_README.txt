JARVIS V42.60.0 - HARDWARE-FIT NATIVE-CONTEXT MODEL I/O

WHY THIS VERSION EXISTS
V42.59 correctly identified the HauhauCS Qwen3.8-27B native maximum as 262,144
tokens, but incorrectly used that capability ceiling as the default live llama.cpp
KV-cache allocation. On local hardware that can make the server fail to become
healthy before a project agent starts.

V42.60 keeps the model facts and the runtime allocation separate:
  * Qwen3.8-27B native/model maximum: 262,144 tokens
  * Default live Jarvis runtime context: 40,960 tokens
  * Minimum accepted healthy 27B runtime: 16,384 tokens
  * Default 27B server/repair output cap at 40,960 live context: 20,480 tokens
  * Override live context: JARVIS_QWEN_38_RUNTIME_CONTEXT (up to 262,144)

Jarvis reads llama.cpp /props and budgets every call against the context that is
actually healthy. It does not pretend the theoretical model maximum is currently
allocated. The MTP/draft-context parsing fix from V42.59 is preserved.

V42.58 connected functional clusters, V42.59 truncation recovery, unbounded active
stream wall-clock behavior, rollback/compile/functional gates, and universal
language/toolchain behavior are all preserved.
