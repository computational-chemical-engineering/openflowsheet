# C1 — build decisions (ADR 0008 Amendment 2, transient-readiness re-check)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: judge at the 0.2.0 cut commit K or at `main` → `main` `3c10e97` (docs-only after the tag `5c82b4c`). Alternative: check out K. Reversible by: re-running the check at K.
