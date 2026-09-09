JARVIS V42.24 - COMPILER-DIRECTED MULTI-FILE INTEGRATION TRANSACTIONS

Purpose
-------
V42.23 could correctly reject bad App.tsx repairs but could still revisit App.tsx as a
leaf after subsystem/exhausted-blocker recovery. This version treats connected
TypeScript consumer errors as one bounded integration transaction.

Key behavior
------------
* Fresh TypeScript compiler locations are the repair authority.
* Connected App/components/hooks are grouped through local imports.
* Stable DTO/type providers are not a blanket first repair target.
* A disposable workspace is used for coordinated candidate patches.
* Candidate files are promoted together only when the whole TypeScript diagnostic
  count decreases.
* First cluster attempt routes to the 9B worker; a second distinct attempt may use the
  27B specialist.
* An exhausted cluster is remembered at the current accepted revision so inherited
  leaf/subsystem recovery cannot silently restart the same App.tsx loop.
* V42.23 resume-policy migration, deterministic TypeScript burn-down, V42.22
  consumer-first ownership, V42.21 semantic-role gates, V42.20 infrastructure/cache
  controls, transactional rollback, and real build/runtime validation remain active.
