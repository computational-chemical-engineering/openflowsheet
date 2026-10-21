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
