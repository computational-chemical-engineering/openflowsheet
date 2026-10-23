# S06 — independent review (design lane, `reviewer`), 2026-10-23

Branch `wp/C11`, commits `7c5ea600..6053c736`, with `7c5ea600` itself included (WO-1, WO-2). Brief
`docs/briefs/S06-review.md`. Spec `docs/derivations/S06-spec.md` §0–§16. Read: `docs/C11_DECISIONS.md`; the source diff
(`rows.py`, `column.py`, `column_solve.py`); `homotopy.py`'s record; and the A05, A11, A13 and A14 tests plus A16's rule in
`scripts/s06_evidence_manifest.py`.

Ran: `pytest tests/test_s06_column_wo{1,2}.py tests/test_s06_evidence_manifest.py tests/test_c8_duty_only_warning.py
tests/test_m06_w27_scorer.py tests/test_t04_registry.py tests/test_t07_b3_policies.py` → 262 passed, 16 skipped (M06
archive absent), 1 xfailed (the I3 probe), 25 s. Two scratch probes, not committed: (a) U1 and U2's λ state against
`p(λ)`; (b) the V-sets' `x⁰` against the J cases'.

## Verdict

**Sound, with four should-fix items and no must-fix.** Every inverse row has the form `variable − parameter` and is
built through the existing `Expr` builders (`specification_row`, the new `scaled_definition_row`), so residual and
Jacobian are one function. A09's floor is 5.9e-11 on the new rows. `u⁰`'s formation, the I1–I6 refusals (exact
`Fraction` Gauss–Jordan; the one-row and one-direction cases checked), §8 items 2 and 4 (item 4's bound follows from the
row tolerances plus two roundings), and the §7.5 records all match the spec. **`lambda_state`'s source is correct.** At
the λ state, every continued slot column equals `p(λ)`: 0.0 on U1 and 1.1e-16 on U2 (probe a). Counts: must-fix 0,
should-fix 4, note 4.

## Findings

**F1 — should fix. §8 item 3 is decided before the defect clauses, so a defective state can come back as a scope
limit.** `src/openflowsheet/models/syn001/column_solve.py:1105-1112`. *Scenario:* the region returns `CONVERGED` at a
state whose rows exceed `KIND_TOLERANCE` (or whose pinned column is non-zero, or whose two-phase end has `V = 0`). If the
`temperature`-specified stage is single-phase there, `solve_column` answers the benign-looking
`CAPABILITY_UNAVAILABLE unsupported(temperature_specification_on_single_phase_stage:s)` rather than
`AcceptanceDefectError`. A genuine single-phase root passes every defect clause, so only a double fault changes answer,
and in a double fault the defect is the part that matters. The order was chosen so that A14's stubbed non-root shows
item 3. *Fix:* compute `acceptance_failures` first and raise on any; apply item 3 only to a clean state. In A14, stub
`acceptance_failures` to `()` for the unsupported probe, and add a probe in which both fail and the answer is a defect.
Ruled in spec §17.3 (R-610).

**F2 — should fix. A11's check of `value` is circular.** `tests/test_s06_column_wo2.py:590-600` rebuilds the λ state
with the same algorithm as `lambda_state` (`column_solve.py:931-948`): same opening, same trial filter, same overlay. A
wrong trial, a permuted or scaled `x`, or a wrong opening would pass. `zip(..., strict=False)` (`:598`) also hides a
length mismatch. *Fix:* assert, as §17.4 adds to A11, that each continued slot's column at the λ state equals `p(λ)`
within its row tolerance (it does, probe a), and use `strict=True`.

**F3 — should fix. A purity at a total condenser is offered but never evaluated.** `column.py:488-494`
(`product_total_id` → `D`) and the definition row at `d_c`. No J or V case declares it, A04 runs on M1 only, and A01
checks only `u`'s id. A wrong product id in `F·d_c − u·D` would pass the whole suite. *Fix:* the A04 clause in §17.4.

**F4 — should fix (cheap). The V-sets' `x⁰` can be checked against a reference.** The decision log's "Alternative: none
available" for A05 is false. §6's endpoint reads no inverse target, so each V-set's `x⁰` equals its J twin's (J1, J3, J4)
bit for bit on every common column. The worst deviation from the twin's `ref.cases.*.bubble_point` is 1.8e-5 of a
tolerance (probe b). *Fix:* the A05 clause in §17.4.

**N1 — note.** `lambda_state` (`column_solve.py:944`) takes the columns outside the homotopy's free set from the opening.
If the homotopy attempt pinned a column that the opening holds non-zero (a single-phase stage), the λ state would carry
the stale value. No registered set can reach this: the opening is all-two-phase, and the homotopy keeps its active set.

**N2 — note (spec, for the next amendment).** The guarantees are absolute in mol/s. The recovery bound `τ_mf/F_c` is
±0.031 at `F_c = 1e-6` mol/s and becomes vacuous below `τ_mf`. The purity bound grows like `τ_eq/(P·F)`. I3 refuses only
`F_c = 0`. This deserves a §14 item. Adding it changes the manifest's limitations and the harvest, so it is left to the
next amendment.

**N3 — note.** `saturation_temperature` (`column.py:586`) reads SYN-001's constants from `thermo/syn001.py` rather than
from the provider that `validate` receives. This is correct while the provider is SYN-001 only (§0). A configurable
provider would make I4's band disagree with the rows.

**N4 — note.** A16's rule (`scripts/s06_evidence_manifest.py:124`) covers the S02 and S01 suites, as the spec says. The
other users of `column.py` (C8, M06, T04, T07 above) are left to the merge gate. I ran them: they pass.

## Rulings (written as spec §17, register R-608 to R-610)

- **Q-S06-WO1-1 → re-register the probe, not a feed temperature (R-608).** The I3 probe becomes feed (0, 0.5, 0.5),
  reboiler recovery of A 0.9, at M1's feed state. M1's own admissible feed dominates it, so it is admissible with no
  computation. The rule is now explicit: every refusal probe is at its base's inlet state and passes R5 there. The
  build lane changes the generator row, re-emits the reference and drops the xfail.
- **Q-S06-WO2-1 → amend §10 as proposed (R-609).** J8's 0.182 is recorded, with its conditioning (`σ_min` 6.1e-4; A
  flows of about 1e-4 mol/s against the absolute floor) as the reason. The tolerance is unchanged. The manifest's
  deviation check becomes ≤ 1/10, except J8 ≤ 1/4.
- **§8 item 3's order → defects first (R-610)**, per F1.

## Not examined

`s06_reference.py` beyond the probe table (its `--check` was not run); the harvest envelope and `support-matrix.md`;
A01–A03, A06–A10, A12, A13 and A15 beyond their headers and run results; S02 internals already reviewed.
