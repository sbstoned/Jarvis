JARVIS V32 - QWEN3.5 NATIVE-262K THROUGHPUT / MONOTONIC PROGRESS
================================================================

WHY V31.2 COULD RUN ALL NIGHT WITH VERY LITTLE PROJECT DATA
------------------------------------------------------------
1. Native 262K forced -nkvo (CPU KV). That made the long-context attention state live in system RAM
   on a 16 GB laptop even though the 9B model was GPU resident.
2. The server disabled --cache-prompt, so repeated Jarvis prefixes were re-prefilled from scratch.
3. Jarvis treated the full 262K server context as a normal per-request working window, allowing routine
   file/repair calls to become much larger than necessary.
4. Source calls had unlimited hard wall time and up to 12 continuation calls; one stubborn file could
   monopolize the only Qwen slot for hours.
5. A syntactically complete file whose transport end marker was clipped still entered continuation,
   instead of immediately going to the stronger API/transaction validator.

V32 FIXES
---------
- Qwen3.5 default startup is native 262,144 (no wasted 1M/524K retries).
- Native 262K/131K keeps KV offload enabled. llama.cpp --fit chooses model offload so KV can stay hot.
- q4_0 KV at 262K; q8_0 at 131K.
- Per-slot --cache-prompt stays ON; large separate host cache remains disabled.
- 262K is still AVAILABLE, but routine Jarvis requests use bounded 32K-65K working windows.
- Direct whole-project operations are bounded to <=98K working context by default.
- File source output chunks default to 8K tokens, with 4 continuation calls instead of 12.
- A syntactically valid truncated envelope goes directly to transaction/API validation instead of blind continuation.
- Every local Qwen call has a hard watchdog (6 min plan/audit; 10 min generation/repair).
- Initial generation and file repair are timeboxed to 15 minutes, and bootstrap defaults to one outer file attempt before staging/materializing the best repairable candidate so Jarvis keeps moving.
- Default planned-file ceiling reduced from 80 to 48 and related full-file context from 6 to 4.
- Full V30 provider/root-cause, rollback, deterministic contracts, tests/build/runtime acceptance remain enabled.

EXPECTED RESULT
---------------
The server can still expose 262K native context, but small/medium coding calls no longer pay 262K-scale
prefill/CPU-KV costs. The project should materialize files steadily instead of spending the night on one file.

EXPERIMENTAL YARN
-----------------
Set JARVIS_QWEN35_TRY_YARN=1 before startup if you deliberately want the old extended YaRN ladder.
It is no longer the default on this 8 GB VRAM / 16 GB RAM machine.
