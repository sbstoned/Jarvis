JARVIS V42.67.0 - OWNER-LOCAL COMPACT REPAIR

Purpose
-------
Fix the remaining live V42.66 throughput problem without weakening Jarvis's
validation gates or overfitting to GearTrack.

Observed V42.66 problem
-----------------------
V42.66 correctly reported one owner / one finding, but the original V42.58
repair function had already built the connected-cluster evidence before V42.66
narrowed the model call. The label was small while the prefill could still be
large. A separate prompt-text classifier could also promote a normal production
repair to the 8,192-token workflow-test budget when unrelated test-debt text was
present elsewhere in the prompt.

What V42.67 changes
-------------------
1. Owner focus happens BEFORE evidence collection.
2. Normal owner evidence is capped to 42,000 characters by default.
3. At most two related files accompany the complete target source.
4. Existing source repairs use compact target-only SEARCH/REPLACE JSON instead
   of a multi-file edits array with repeated paths/source.
5. 27B production output starts at 3,072 tokens, then escalates only on bounded
   retries to 4,096 / 5,120 / 6,144.
6. Workflow-test budget is classified from the actual owner finding, never by
   searching unrelated prompt text.
7. If two compact attempts prove an atomic cross-file fix is necessary, Jarvis
   can fall back to the previous V42.61/V42.66 formatter, but only inside the
   already owner-local <=42K evidence neighborhood.
8. Malformed compact JSON may salvage only fully decoded leading replacement
   objects. It never balances braces, closes strings, or invents source.
9. V42.65's source-only candidate clone and evidence-proven test-command recovery
   are carried forward for the last-two workflow-test endgame.
10. Manual model selection, AUTO routing, compiler/build/runtime authority,
    functional-delta proof, component proof, rollback, regression protection and
    strict final acceptance remain unchanged.

Why MTP/Flash-Attention is not forced by this patch
---------------------------------------------------
The research confirmed current Qwen3.8 MTP builds can benefit from embedded MTP
and Flash Attention, but forcing optional runtime flags before testing the exact
installed llama.cpp binary risks startup failure or CPU fallback. V42.67 first
fixes the confirmed orchestration/prompt bottleneck. Runtime acceleration should
be enabled only after a local capability/performance smoke test proves the
installed server supports it correctly.

Expected live status
--------------------
A normal manual-27B production owner should show:
  V42.67.0 / OWNER_LOCAL_COMPACT_REPAIR_FACTORY
  1 connected owner / 1 finding
  first output request approximately 3,072 tokens
and the model prompt should contain the target plus only a tiny related-source
neighborhood instead of the original four-owner evidence set.
