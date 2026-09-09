Jarvis V42.6 - AUTO Hybrid Qwen Model Router
=============================================

Purpose
-------
AUTO is now the default Jarvis model-selection mode for project generation.
AUTO is intentionally limited to exactly these two local models:

1. FAST WORKER
   profile: 9b35
   Qwen3.5-9B HauhauCS Aggressive Q4_K_M

2. HARD-WORK SPECIALIST
   profile: 27b38q2
   Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf

The older Qwen3.8-27B OBLITERATED Q4_K_M model is NOT part of AUTO.
The Qwen3 8B model is NOT part of AUTO.
Both remain available as manual dropdown choices.

AUTO routing
------------
The new 27B Q2_K_P specialist is preferred for:
- requirements compilation and architecture planning
- architecture collision repair
- dependency-closure reasoning
- ambiguous runtime/build diagnosis
- canonical-provider/root-cause reasoning
- subsystem reconciliation
- cross-component/integration failures
- repeated repair families after the fast worker does not converge
- large coordinated repair/audit contexts
- global convergence / final acceptance reasoning

The 9B worker is preferred for:
- routine source-file generation
- straightforward first-pass leaf repairs
- small/local edits
- repetitive implementation work

Manual model selection is strict
--------------------------------
If the user explicitly selects 9B, new 27B Q2_K_P, old 27B, or 8B from the
dashboard dropdown, Jarvis locks the whole project to that exact model and will
not automatically promote or demote it.

Switching does not change the strategy
--------------------------------------
Both AUTO models use the SAME Jarvis project state, requirements ledger, skills,
toolchain adapters, capability/sandbox runtime, command broker, canonical owner
map, provider-first repair engine, build-debt ledger, real build/test evidence,
and zero-debt publish gate. Model switching changes only the local reasoning
engine used for a call.

Anti-thrashing behavior
-----------------------
AUTO does not use the 27B for every call. The 27B is reserved for high-leverage
reasoning. Routine generation returns to 9B. Repeated leaf-repair families are
promoted on the second matching repair call by default, before four or more
nearly-identical attempts can burn hours.

Environment controls
--------------------
JARVIS_V426_AUTO_ROUTING=1
JARVIS_V426_REPEAT_PROMOTE_AT=2
JARVIS_V426_HARD_PROMPT_TOKENS=18000

The temporary AUTO switches use persist_selection=False, so the dashboard remains
on AUTO rather than changing itself to 9B or 27B as routing decisions occur.
