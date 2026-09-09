JARVIS V42.59.0 - ADAPTIVE MODEL I/O + NATIVE 262K QWEN3.8 27B CONTEXT
======================================================================

Why this release exists
-----------------------
V42.58 proved that connected functional clusters can converge real multi-file
integration defects, but live runs exposed two model-I/O bottlenecks:

1. A connected transaction could still be constrained by a small output budget
   (for example 2,048 / 6,144 tokens), causing valid multi-file JSON repairs to
   be truncated before Jarvis could validate them.
2. The manually selected Qwen3.8-27B HauhauCS Aggressive Q2_K_P could be launched
   in an old ~6K hardware-fit slot even though the model's native maximum context
   is 262,144 tokens.

V42.59 fixes both without weakening V42.58's compile, functional, rollback,
cluster-scope, or final-acceptance gates.

Qwen3.8-27B HauhauCS Aggressive Q2_K_P
-------------------------------------
Profile: 27b38q2
Native context target: 262,144 tokens
Server max-output target: 65,536 tokens

Manual selection remains a strict lock: choosing this model in the dropdown keeps
all project calls on this model. A live 6,144-token slot no longer counts as a
matching runtime for this profile; Jarvis restarts it at the requested native
262,144-token context.

Environment override (only if the host cannot allocate the native window):
  JARVIS_QWEN_38_CONTEXT=<tokens>

The supported native ceiling remains 262,144. The HauhauCS model card also describes
framework-specific extension up to 1,000,000 tokens, but V42.59 deliberately uses
the native 262,144-token maximum by default for reliability.

V42.59 also fixes the misleading 6,144-token dashboard/voice status seen with some
MTP/speculative llama.cpp /props payloads. Jarvis now reads the documented target
slot value at default_generation_settings.n_ctx before considering draft/speculative
metadata, so a small MTP/draft window cannot be mistaken for the main model context.
If the *actual target slot* really is only 6,144, Jarvis still reports that truth and
restarts the manually selected 27B profile at the requested 262,144 context instead
of pretending the small slot is valid.

Launcher
--------
V42.59 includes START_QWEN_LOCAL.ps1 in the complete package so model switching no
longer depends on a stale launcher left over from an older Jarvis installation.
For 27b38q2 it launches llama-server with:
  -c 262144
  -n 65536
  -np 1
  --no-context-shift
  --jinja

Jarvis still reads /props and budgets against the live context actually exposed by
llama.cpp. Optional JARVIS_QWEN_CACHE_TYPE_K / JARVIS_QWEN_CACHE_TYPE_V overrides
are supported if a host needs lower-precision KV cache to fit the full window.

Adaptive repair output
----------------------
Connected functional transactions now size output using:
  * selected model profile
  * connected issue-owner count
  * functional finding count
  * prompt size

27B repair output may grow to 65,536 tokens. 9B and other profiles retain separate
bounded caps. If the provider still returns finish_reason=length, Jarvis retries the
same transaction with a larger allowance and asks for a smaller complete subset of
the connected cluster rather than accepting truncated JSON or restarting the entire
project from scratch.

Context policy
--------------
The live 262K server slot is the authority. Jarvis does not stuff 262K into every
small request; it expands working context when the task requires it and compacts
oversized prompts before llama.cpp would need context shifting. Connected 27B repair
may use the full native slot, with the requested output reserve subtracted from input.

Universality
------------
These changes are model-I/O and dependency-cluster orchestration. They do not encode
GearTrack, Rust, React, Tauri, or SQLite-specific repair behavior. Existing language,
framework, toolchain, sandbox, validation, rollback, and acceptance machinery remains
in force.
