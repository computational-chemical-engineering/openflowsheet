# Brief — verdict: release gates V11–V20 at the release candidate `C`

**To:** `verdict` (design lane). **From:** build lane. **Branch:** `wp/T08`.
**Deliverable:** `docs/reviews/T08-verdicts.md` in **exactly the table shape of release spec §R3.3** (one table,
columns `Gate | Verdict | Failing clauses | Travelling limitations | Basis`, ten bare rows `V11`…`V20` in order;
BLOCKED rows read `Vnn (x): <missing input>`; clause and limitation ids only in their own columns), followed by the
reasoning per gate and what the verdicts do not establish. `scripts/v0_1_gate.py --rc <C>` must parse it (run it).
Do not commit; write no code. Never set `reviewed`.

**Budget.** Frank is near his weekly usage limit. Judge from the records; re-run nothing heavy.

## Criteria (registered; never re-read after the result)

`docs/derivations/T08-release-spec.md` §4 (V11–V20 clause by clause, with each gate's verdict rule) and §9's
assertion rows, **as amended** (Amendments R2, R3 at the end; in-place markers); the build-first spec (with its
Amendments 1–3) for V13 (e) and V14 (b); ADR 0021 (D1–D5, Proposed revision 1 and 2, the D3 row: **V14 (b) FAIL
accepted by Frank 2026-09-29**). Plan §4.3 and blueprint §14.3 as the spec cites them.

## Evidence

- **The RC record** `docs/t08-rc-record.md` at `C` (the session gives `C` and the CI run id in its message; per-step
  results with record sha256s; records under `evidence/T08/<C>/artifacts/rc/`, git-ignored).
- **Verdicts already given:** `docs/reviews/T08-verdict-V14b.md` (V14 (b) FAIL), `docs/reviews/T08-verdict-V13e.md`
  (B40–B49 MET; B50 then amended by Frank, R-134 — re-confirm at `C`).
- **Reviews:** `docs/reviews/T08-review.md`, `T08-review-2.md`, `T08-description-review.md` (+ addendum).
- **Ledger and envelope:** `docs/t08-gate-ledger.md`, `benchmarks/t08/support_envelope.yaml`,
  `docs/support-matrix.md`, `docs/recovery-edges.yaml`, `docs/t08-a30/`.
- **Earlier package verdicts carried per spec §4:** `docs/reviews/T06-verdicts.md` (V16), `docs/reviews/T07-verdicts.md`
  (V17; carried across U05 by Frank, R-133).
- **V19:** `docs/v02-real-chemistry-dossier.md` and `benchmarks/t08/v19/` (the reactor on its released `main` @
  `6089593`; Amendment R3 8 rulings). Items still open with Frank: the property database's sources, the 4TU dataset's
  use during curation, citing the MSc report and 2D draft, his K_NH3 check — judge V19 by its rule on that basis
  (needs_frank items are what they are; do not fill them).
- History: `docs/T08_DECISIONS.md` (grep).

## Report

The ten rows (verdict and failing clauses), the gate script's output on your file, and the main things the verdicts
do not establish. Numerical verification, empirical validation and optimality evidence stay distinct.
