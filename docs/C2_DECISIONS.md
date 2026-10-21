# C2 — build decisions (OpenIDAES-450 split registration)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: register-number ranges for the cloud queue (branches run unmerged in parallel) → C2 R-486…R-494, C1
  R-495…R-499, C3 R-500…R-504, S01 R-505…R-519, L01 R-520…R-529, S02 R-530…R-539. Alternative: renumber at merge.
  Reversible by: renumbering an unmerged branch's entries before its merge.
