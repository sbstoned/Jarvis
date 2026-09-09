JARVIS V30 ROOT-CAUSE REPAIR ENGINE
==================================

This build extends the V27 continuation engine and Qwen3.5 multi-model support.

Primary convergence fixes:
1. Nested Python projects are indexed under every valid local import alias used by Jarvis validation.
2. Consumer-required module exports are enforced across all aliases during transactional repairs.
3. Runtime `cannot import name` failures target the provider module, not only the consumer traceback frame.
4. Missing top-level function exports use surgical synthesis + exact validator replay before full-file rewrites.
5. Repeated stable failures persist counts/failed targets in JARVIS_PROJECT_STATE.json and trigger root-cause escalation.
6. Replay-gated runtime repair stops immediately after one target advances the validator, avoiding extra edits based on stale failure text.

Useful optional environment controls:
  JARVIS_QWEN_RUNTIME_REPEAT_ESCALATION=2
  JARVIS_QWEN_RUNTIME_TARGET_FAILURE_LIMIT=2
  JARVIS_QWEN_RUNTIME_FAILURE_HISTORY_LIMIT=20

The normal final acceptance/build/runtime gates remain authoritative.
