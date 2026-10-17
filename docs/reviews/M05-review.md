# M05 review (design lane, one `reviewer` pass) — `wp/M05` @ `7350684`

Date 2026-10-16. Subject: `git diff 32ceea50..7350684 -- src` (trust-region core: `studies/trust_region/`), the M05 test
files `tests/test_m05_*` and `tests/support/m05_replay.py`, the records under `benchmarks/m05/records/`, and build log
S1–S69. Authority: `docs/design/M05-trust-region.md` §6–§9, §13, rulings §16–§20. Brief: `docs/briefs/M05-review-brief.md`.
Rulings that change the design are in the note's §21 and in register entries R-430…R-435.

**Verdict: fix first.** One must-fix item, and it is small: a units error in a reported field. The fix folds into
WO-10. The trust-region core is sound.
- R-401's classification, including the radius in force after a rejected step, matches the rule and is pinned by
  F-15's fixtures.
- Basis v2's stencils, remainder form, direction and fallback match R-400 steps 2–9 exactly. The one-sided weights
  (−2, 1) and σ(4w₁ − 3w₀ − w₂)/(2t) are correct.
- R-405's refund and R-406's check budget are as ruled.
- P2, P2_A and P5 follow §7.4.
- G8's failure is a mis-specified gate, not a wrong answer (ruling 1).

## Must fix

**MF1. `noise_ratio` divides a gradient noise by a value curvature: REAL's committed 3592 should be ≈ 0.04.**
`study.py:985-986` implements R-400 step 10 literally (design note l.1784): `4ν̂/(t²|c_k|)`. But ν̂ = ‖ρ‖_∞/14 is
the noise of the **scaled forward gradient** G(η) (truths.py:486; §17.2: sd(G(η)) ≈ √2σ/η with G_kj = g_kj·m_j/s_k).
The noise of c_k needs the **value** noise σ_k = ν̂·η·s_k/√2, in output units. The formula drops a factor η·s_k/√2.
- **Scenario.** REAL's record, `runs[C1].basis.links["link:reactor"]`, holds c = (−1.2248e-3, 0.81206), t = 0.025,
  ν̂ = 6.8735e-4 at η = 2⁻¹⁴, and s = (0.25, 128) (`projection.output_scale` of S0's coupling (0.1684, 78.67)).
  - Recorded: noise_ratio = (3591.6, 5.42), which reads as "REAL's X curvature is pure noise".
  - Corrected, 4σ_k/(t²|c_k|): (0.0388, 0.0299). The curvature is resolved to about 4 %.
- **Also affected:** LOOP-R (0.141, 1.9e-4) and TR-E2-FD (0.065, 0.028).
- **Why it matters.** The field is reported and not judged, so no gate moves. But REAL's record is evidence that W24 and
  M07 will cite. A reader of 3592 would conclude that R-400 is unfit for the real reactor, which is the opposite of what
  the record shows.
- **Correction:** R-432 / §21.3.
  - Set noise_ratio_k = 4σ̂_k/(t²|c_k|), with σ̂_k = ν̂·η_sel·s_k/√2. This is one line in `_basis_block`, which needs
    the holder's output scales.
  - Re-take LOOP-R, TR-E2-FD and REAL.
  - Diff each re-take against the committed record with `noise_ratio` and `provenance` masked. That diff must show 0
    differences; any other changed digit is a finding.

## Should fix

**SF1. G10 for the five in-process records is in no gate tier.** The only check is `scripts/m05_wo8_runs.py --replay`,
run by hand. G5–G9 read the committed files.
- **Scenario.** Any commit after `7350684` that moves T*, a label or a count leaves every gate green while the records
  go stale. That includes WO-10 and MF1's fix.
- **Correction (R-435).** An `nlp`-tier pytest runs the replay of TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R and LOOP-S, about
  4 s each. It refuses unless `OMP_NUM_THREADS=1`. An environment-fingerprint mismatch is a failure that names the
  mismatch, never a pass. REAL's replay stays a script, since it needs the reactor environment and takes about 25 min.

**SF2. G8's strict `xfail` (`test_m05_wo8_gates.py:264-279`) and G9's at-bound rows judge Ipopt's offset.**
- Replace both with ruling 1's restated rows: a G8 that passes on the committed LOOP-S record, and G9 restated the same
  way.
- Keep a unit test of the inward-only branch. It already exists:
  `test_m05_study_loop.py::test_the_poll_polls_only_inward_at_a_bound_and_clips_at_the_box`.

## Notes

- **N1. The study's restart rule handles regimes differently in stage A and stage C** (`study.py:794` against
  `study.py:814`).
  - Stage A's restart candidates require `regimes_match`, as §7.3 says.
  - Stage C takes the best feasible poll point regardless of regime, and does not compare it with the previous best.
    This is §7.3's letter.
  - A regime-changed poll point would then restart stage C and end `FAILED(REGIME_CHANGED)`. No record reaches this.
  - *Needs a decision*, at the next touch: I would apply stage A's eligibility to stage C.
- **N2. A box exception other than `TruthRefused` leaves its key in flight** (`holders.py:661-679`). `flight.done` is
  never set, so a later request for that key in that holder waits forever, and its charge stands.
  - The current flow does not reach this, because TRF aborts and the retry builds new holders.
  - Correction: a `try/finally` that sets `done` and drops the in-flight entry.
- **N3. REAL's replay compares coupling records under T08 v2's floors, not bitwise** (`m05_replay.py:345-361`).
  - The replay runs in one environment with the reactor served from the store, so these floats should agree bitwise,
    apart from the timings.
  - It is not a gap for the claim, because the study record, which carries every decision-relevant float including the
    achieved coupling residuals, is compared bitwise.
- **N4. `runs[].cold` includes the FD check's 21 cold points, which R-406 keeps outside the run cap.**
  - REAL's "C1 32 of 250" is therefore not the cap's use, which was 11.
  - G11's `run["cold"] ≤ 250` is conservative, so nothing is wrong. Say this in the manifest.
- **N5. A wrong label in a record passes the default tier as long as it is in the allowed set.**
  - Labels the code produces wrongly are caught by the F-15 fixtures, by G5b's ratio row and, once SF1 lands, by G10.
  - A default-tier re-derivation would close the record-level gap: each run's outcome and `final_step_ratio` from its
    recorded log and config, P5's pass from its rows, and `best` equal to the stable candidate. This is optional.
- **N6. P2_A labels a failed reference re-solve `PROJECTION_DISAGREES`** (S63). It is the safe failure, its source
  records why, and stage A's non-stable candidates go on to stage C anyway. Acceptable.
- **N7. S63's symbolic copy of M04's basis can drift from M04.** The J1–J3 equality test (≤ 1.9e-16) guards it. Keep
  that test in the default tier for as long as the copy exists.

## Rulings (§21; register R-430…R-435)

1. **At the bound (R-430).** A fixed distance is the wrong thing to *gate* on, and it is acceptable as §7.4's
   classification. Keep `AT_BOUND_SCALED` = 1e-6; there is no code change.
   - **R-404's rationale was wrong.**
     - The returned offset is μ_k/z_L at whatever barrier iterate passes Ipopt's termination test (tol 1e-8,
       `compl_inf_tol` 1e-8, monotone μ ≥ 1e-9; `trf_state.py:180-195`). It is not a fixed μ_final/z.
     - The three records have parent slopes within 15 % of each other: 3.4e-3, 3.4e-3 and 2.9e-3 per scaled unit, from
       the plus polls. Their offsets still span 33×: 5.3e-8, 1.10e-6 and 1.76e-6.
     - So the brief's "smaller slope, larger offset" does not explain them, and no distance fixed in advance separates
       a bound-active point from an interior one on a flat objective.
   - **The fixed rule's failure mode is conservative.**
     - A bound-active point read as interior has its outward poll clipped onto the bound. P5 then also judges J at the
       bound itself, which is more evidence at the cost of one coupled solve.
     - R-401's exemption is withheld, so the label becomes `TRF_EXIT_UNVERIFIED` and stage B is unchanged.
   - **The alternatives buy no better claim.**
     - Multipliers need TRF's internal Ipopt duals, and TRF is pinned (R-260).
     - A μ/z bound needs z_L before the poll.
     - Snapping to the bound moves the candidate off TRF's point.
   - **G8 and G9's last rows become:**
     - |T* − 653.15 K| ≤ δ_T = 0.5 K, as G5–G6 (d);
     - and P5's evidence contains the bound: either inward-only, or the minus point clipped to exactly 653.15 K,
       feasible and passed.
     - |d* − d_lb| and §7.4's reading are reported.
   - **G8 passes on the committed LOOP-S record**: 2.19e-5 K, the clipped minus point passed with 3.71e-9 ≤ 1.28e-5.
   - **No re-take** of LOOP-S or REAL for this ruling.
   - **Watch-for:** a parent with a zero noise floor. The clipped sub-resolution poll would fail P5 at every restart.
     C1's coupled parents clear this by more than 10³.
2. **R-408's premise (R-431).** θ_PMP = 6.55e-3 is the property EFs' affine error over the PMP's 20 K move (R-400 keeps
   them affine). Only the link EFs are exact under the promoted quadratic.
   - TRF corrects it with a θ-step, so `TRF_CONVERGED` (ratio 3.28e-6) is the expected label.
   - G8's other rows already accept it. P2_A agrees to 5.95e-14, so stage A still returns the surrogate-backed optimum.
   - The promoted basis is unchanged, and there is no re-take.
3. **Build choices (R-434).**
   - **Confirmed:** S33/S37, S36/S38, S39 (a)–(d), S41, S45, S46, S48, S53, S55, S56, S57, S59, S60, S61, S62, S63,
     S65, S66 (matches §5.2's real column), S67, S68 (a real content check; N3 is a note), S69.
   - **Superseded:** S54, by S61.
   - **Reversed:** S58, by R-432.
   - **S64:** handled by R-430.
4. **`extrapolated` (R-433).** The ledger count suffices, and no record field is added.
   - The ledger is anchored by `artifacts.ledger` (checked in the default tier) and compared entry by entry by REAL's
     replay.
   - M07 R-424 counts the final coupling iteration per certified state, which the record already carries per solve.
   - The data-edge flip calls for limitation wording in M05's manifest and W24 text, plus a cross-package note to M07:
     R-424's count at C1's state inherits the flip.
   - It is not a finding against the reactor, which flags correctly: a binary edge flag at an on-edge state flips at
     solver resolution.
5. **G10 in the `nlp` tier (R-435)**, as SF1.

**Re-takes:** LOOP-R, TR-E2-FD and REAL, for MF1 only, with everything else bit-identical. No re-take for G8.

## Not examined

- `projection.py` beyond the decision variable.
- `trf_state.py`'s log parser and filter reconstruction.
- `holders.py`'s Jacobian and memo paths.
- `parent.py`'s coupled-solve adapter, beyond `decision_path` and `surrogate_reference`.
- `truths.py`'s FD check, beyond ν̂.
- The schema and the numerical-policy addenda.
- The evidence scripts, beyond the comparators.
- The M03 code in the diff (`sensitivity.py`, `estimation.py`, `nlp/*`; see `docs/reviews/M03-review.md`).
- Nothing was run. Every number above is read from the committed records or derived from them.
