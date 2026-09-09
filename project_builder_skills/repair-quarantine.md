# Repair Quarantine

- Accepted repository revisions are the progress clock; temporary candidate drafts are not progress.
- If the same provider/repair family fails twice without an accepted-state change, stop repeating the leaf strategy.
- Quarantine that repair family, escalate to root-cause/contract-graph analysis, and repair the owner/provider/config/dependency before retrying consumers.
- Missing Foundation and shared canonical providers outrank feature consumers.
- Reopen a quarantined family only after accepted state changes or a graph/root-cause reconciliation changes the authoritative repair strategy.
