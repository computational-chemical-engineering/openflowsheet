# C3 — build decisions (housekeeping)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: (b) which `sys.path` entries under the repo root does install-check strip → all except the running
  interpreter's own sysconfig paths (stdlib, purelib, platlib); `a44.outside_the_tree` unchanged. Alternative: require
  the venv outside the checkout (document only). Reversible by: reverting the filter commit. No ruling needed: R-347
  registers the record member, not the strip.
- DECISION: (c) how to remove the duplicate W27-A20…A22 → rename Amendment 3's three to W27-A80…A82 in prose and
  tests only; hashed JSON untouched. Alternative: suffixed ids (A20′). Reversible by: reverting the erratum commit.
- DECISION: (d) the schema `$id` move → not in C3; it changes a frozen interface and needs a design-lane ADR; backlog
  for the first v0.3 schema change. Alternative: an ADR now. Reversible by: writing that ADR.
- SKIPPED: (c) the W27-A20…A22 erratum → not done. Editing `docs/derivations/M06-W27-registration.md` changes its
  SHA-256, which is pinned in `benchmarks/m06/w27/preflight.py:57-65` (`REGISTERED_SHA256`, P2; value `bf48a521…`) and
  recorded in `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/preflight.json:45`; the live P2 would then fail, and
  the brief forbids changing preflight pins. Renaming only in tests would leave prose and tests disagreeing, and a
  uniqueness test over the prose cannot pass without the edit. Needs a ruling: (i) edit the prose and re-take the P2
  pin in one commit (a campaign-record decision for the workstation), or (ii) leave the prose and keep the
  disambiguation comment at `tests/test_m06_w27_coverage.py:434` (FA4-1, §23.11, already records the clash).
