# L01 — build decisions (component-library gaps, development half)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- DECISION: L01 base → `wp/C-merge` (C2 split needed, unmerged at start). Alternative: wait for the merge. Reversible by: rebasing onto main after the merge (same tree).
- DECISION: which components enter the library → only those an existing method serves in some development case (R-A: all non-reaction packages `cubic_pr`, phases within {vapor}). Alternative: admit by case count alone. Reversible by: widening R-A in a spec amendment and regenerating `l01_projection.json`.
- DECISION: Water's phases → vapour only (PR 1976, ADR 0026); liquid water is `needs new method: iapws95` (or a PR liquid-mixture regime). Alternative: extend the pure-NH3 liquid regime to pure water. Reversible by: a later ADR adding a liquid regime; records unchanged.
- DECISION: where new components live → new file `benchmarks/l01/components.yaml` and new provider `pr-lib-v1`; C1 byte-identical. Alternative: append to C1's file/module (moves `pr-c1-v1` hashes and every C1 n-vector). Reversible by: retiring `pr-lib-v1` (nothing committed depends on it).
- DECISION: the library's reference convention → reuse `PR-C1-ref-v1` (same datum). Alternative: a new name registered in `conventions.py` and `interfaces-frozen.md`. Reversible by: renaming in the record file before WO-3 exposes the route.
- DECISION: the C1 records in the library → copy H2, N2, Ar, CH4 verbatim (L01.A02); omit NH3. Alternative: copy all five (brings the pure-liquid regime). Reversible by: adding NH3 with its regime in a later amendment.
- DECISION: vapour root rule → largest root, refuse `vapour_root_metastable` (ADR 0026 D2) and `vapour_root_liquid_like` (v < (Z_c/B_c)·b_mix). Alternative: C1's light-gas rule alone (labels compressed liquid water vapour). Reversible by: a spec amendment of §4.2; only refusals change.
- DECISION: CO → stopped by W27-R24 (c) (`Co` casefolds to `CO`); finding F-2. Alternative: drop the formula or rename the record to dodge the check. Reversible by: a W27 amendment making formula matching case-sensitive, then adding CO's record.
- DECISION: coverage re-take → dedicated development-only script; never `python -m benchmarks.m06.w27.coverage` (overwrites committed `coverage.json`, prints all-450 counts). Alternative: the brief's command with `--out`. Reversible by: none needed; the CLI is unchanged.
- DECISION: two `cubic_pr` routes vs W27-R24 (a)/(d) → L01 does not amend W27; the re-take's typed refusal is the registered result until a W27 Amendment 3 (finding F-1). Alternative: a private `provider_methods` override in L01. Reversible by: W27 Amendment 3, then WO-L01-3.
- DECISION: c_p range → C1's low NASA-7 range only (200–1000 K); reformer outlets refused. Alternative: add the high range now. Reversible by: a record-format ADR adding b_k of the high range (spec Q-6).
