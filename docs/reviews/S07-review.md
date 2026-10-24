# S07 review (WO-S07-2a, 2b, NC2, NC3; the package's single `reviewer` pass)

**Reviewer:** design lane (`reviewer`), 2026-10-23. **Reviewed:** `wp/S07` at `6f8c83d6`: the near-critical
diff `2cd05bca..6f8c83d6` (`coolprop_heos.py` D1–D3, `iapws95.py` D5, `tests/test_s07_near_critical.py`,
`nc_scan.py`), read against design note `docs/design/S07-near-critical-saturation.md`, with the tier-A/B provider,
its tests and `docs/S07_DECISIONS.md` B-15…B-30, Q-B4 and F-6 as context. **Against:** ADR 0046; spec §6.3, §9.1,
§16.11, §18.3. **Rulings:** spec §19 (Amendment 3), S05 spec §17 (Erratum), register R-626.

## Verdict

**The implementation is sound and matches design §4.2 step for step. The two failing gates are bound errors, not
algorithm errors.** G3 asked for more agreement than the convergence rule promises, and G8 was a cost estimate.
Both are re-set in §19 from derivations, and the evidence for each is below. Before `tested`, the build lane does
findings 1–4 (test and script edits, no provider change) and WO-S07-NC4 under §19.4–§19.5. Merge still waits for
WO-S07-3 and G9, as planned. Nothing here asks for a change to `coolprop_heos.py` or `iapws95.py`.

**What I re-ran** (scratch venv, CoolProp 8.0.0, x86-64, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`):
- `test_s07_near_critical.py` + `test_s07_broad.py`: 3118 passed and 2 failed, the two being N3[R22] for densities
  and for pressure. This is the build's result.
- **An independent check of every fallback root.** On G1's grid, the 343 points where only the fallback gives a
  root were compared with CoolProp's own QT saturation, a different solver of the same EOS used here for review
  only. ρ' agrees to ≤ 4.1e-10 and ρ'' to ≤ 4.5e-10 (Deuterium at θ_min), and p_σ to ≤ 3.3e-13. None is unsolved.
  The highest θ at which the fallback runs is 4.46e-3, and the polish takes at most 8 iterations.
- **R22 at θ_min.** The plain root and the forced-fallback root differ by 1.10e-8 in ρ''. Both have residuals at the
  noise: F1 ±6.0e-14, F2 ±1.3e-13. CoolProp's QT root lies between them, 4.1e-9 from one and 6.9e-9 from the other.
  K jitters by 2.1e-13 over 64 ulp of ρ'' for R22, against 1.6e-14 for R21. Then |Δp_σ|/p_σ = (k''/Z'')·|Δρ''|/ρ''
  = 5.9e-4 × 1.10e-8 = 6.5e-12, exactly the measured miss.
- **A17 step scans for F-6** (the h-scan in the table). The miss divided by scale, at FD step h/x:

  | case | h/x = 1e-8 | 1e-7 | 1e-6 | 1e-5 | 1e-4 | reading |
  | --- | --- | --- | --- | --- | --- | --- |
  | R22 `L_corner`, h in P | 2.1e-11 | 6.6e-11 | 5.6e-11 | 4.5e-11 | 2.1e-11 | independent of h: value noise |
  | R22 `L_corner`, s in T | 7.5e-11 | 4.5e-11 | 5.2e-11 | 5.8e-11 | 2.9e-11 | independent of h: value noise |
  | PropyleneGlycol `S_dense`, cp in T | 2.1e-13 | 2.2e-13 | 1.1e-11 | 1.1e-8 | 1.3e-5 | ∝ h³: stencil truncation |

  In every case the derivative is consistent with the values. An inconsistency would grow linearly in h.
- **k sign changes, in double.** I counted sign changes on a 401-point grid of (0, ρ_max], at nine θ from 5e-3 down
  to 1e-6, and checked the branch of every N5 answer. Results are in findings 5 and 6.

## Findings (most severe first)

1. **N3's bounds are tighter than the convergence rule allows. Must fix, by §19.2.**
   `tests/test_s07_near_critical.py:40` and `nc_scan.py:161-162` set N3_NEAR = 1e-8 and N3_PRESSURE = 1e-12.
   R-595's floor clause accepts a final correction of up to √ε = 1.49e-8. At the floor, two accepted roots differ by
   up to about 2√ε. A bound below that measures one fluid's evaluation noise, not the algorithm. R22's noise is 13×
   R21's (K jitter above). That is F-6's cancellation fluid, at the same order as its A03 floor.
   **Fix:** densities ≤ 3e-8 for θ_min ≤ θ < 1e-2. p_σ ≤ 1e-10 for θ < 1e-2 and ≤ 1e-12 for θ ≥ 1e-2. The 1e-11 bound
   for θ ≥ 1e-2 stays. The derivation is in §19.2.
2. **G8's 400 jets was an estimate. Should fix, by §19.3.** `nc_scan.py:159`. The design priced bisection at about
   350 jets, and the bound left 15 % of margin over that estimate. The measured worst is 414 (Cyclopentane):
   104 for the spinodals, 255 in the inner roots, 9 for the polish. Cost is not correctness. The path is rare and
   cached per exact T, and the plain path gains no jet.
   **Fix:** use a tripwire of 500. Record the hard bound set by the loop limits, 6906 jets plus 100 for the failed
   plain Newton. Q4, the safeguarded Newton, stays deferred.
3. **N5 does not pin the branch. Should fix.** `tests/test_s07_near_critical.py:152-159` asserts only `ok`,
   (∂v/∂P)_T < 0 and cp > 0. A D3 root on the wrong branch, for example a stable vapour root returned for a LIQUID
   request, would pass all three. D3 changes the bracket from (ρ', ρ_max] to (0, ρ_max], so the branch is exactly
   what could go wrong.
   **Fix:** also assert ρ > ρ_c for LIQUID and ρ < ρ_c for VAPOR. I measured all 123 × 7 × 4 states, and every one is
   on its branch today.
4. **The identity proof is not reproducible from the repository. Should fix.** N2 (`:72`, `:104`) compares
   `_solve_saturation` with the test's own call of `_maxwell_newton`, which is true by construction. The bitwise
   proof against the pre-change code was made with scratch scripts `recplug.py` and `cmp.py` (S07: 35 718 calls;
   S05: 38 010 calls). Neither script is committed, and the S07 digest is not recorded.
   **Fix:** commit both under `docs/derivations/scripts/s07_measurements/`. Record both digests (sha256 of the
   records) in the decisions log and in the manifest's G2 and G7(b) items.
5. **"Never a wrong root" holds only where the isotherm has a single loop, and CO2 has an inner loop at θ = 1e-3.
   Should fix, in NC4 and the spec.** The claim is in design note §4.2 *Termination* (`:114`) and Q1.
   - **The evidence.** CO2 is tier A. At θ = 1e-3, k changes sign at ρ/ρ_c = 0.873, 1.101, 1.123 and 1.137.
     Ammonia and o-Xylene do the same at 3e-3 to 5e-3, where k(ρ_c) > 0, so step 1 refuses them. M4 sampled k only
     at ρ_c, so it missed the CO2 loop.
   - **How a wrong root gets through.** Step 1 passes, because k(ρ_c) < 0. If a step-3 bisection midpoint
     (`coolprop_heos.py:652-669`) lands in the inner stable wiggle, ρ_lb is the inner spinodal. A spurious Maxwell
     pair between the wiggle and the vapour branch then passes every check of steps 4–7, including `:713`.
   - **Exposure today.** None. CO2's plain Newton converges at that θ, and the forced fallback there gives the plain
     root, because the midpoint sequence happens to avoid the wiggle. All 343 fallback-only points agree with QT, as
     above.
   - **Not asked: a code guard.** It would need a global stability (tangent-plane) test on the isotherm, which the
     plain path does not have either.
   - **Fix:** §19.1 states the claim as conditional. §19.5 widens G4's 50-digit set to cover the fallback's actual
     run set, and adds R22.
6. **C-strip as written cannot pass at θ = 1e-6. Must fix before NC4, by §19.4.** The defect is in design note
   §5.3(iii). Near T_c the unstable region is about θ^½·ρ_c wide, while a 401-point grid of (0, ρ_max] has a spacing
   of about 0.0075ρ_c. In double precision the grid finds no sign change at T_c(1 − 1e-6) for 20 of 123 fluids.
   **Fix:** §19.4 adds a 401-point grid on the generator's 50-digit [ρ'', ρ'] at each C-strip temperature. At
   T_σ,max, 1e-4 and 5e-5, every fluid has exactly two changes, and its spinodal pressures lie inside the box's
   pressure band, so the D3 root is unique there.
7. **θ_min's "4× margin to the floor" is fluid-dependent. Note: keep 5e-5, and pre-register the remedy (§19.1).**
   - **R22's margin is 1.35×, not 4×.** At θ_min its root spread is 1.1e-8 against √ε. No answer depends on that
     margin. Below T_σ,max the saturation only brackets strip states, and a failed polish there falls back to D3,
     which gives the same root to within 2.2e-12 (M6). At T_σ,max, where Psat and Tsat need the saturation, R22's
     spread is 2.9e-10, a margin of 51×.
   - **The risk is N1 at θ_min for R22 on aarch64.** If it fails there, the registered remedy is θ_min = 7e-5
     (margin 2.2×). It is not a looser convergence rule, and it is not 1e-4, which would put the registered strip
     controls on the threshold.
8. **A17's single-step check cannot tell noise from inconsistency. Note.** The test (`test_s07_coolprop.py:876`) is
   S05's rule. At h = 1e-6·x it passes a log-derivative error of up to 5e-5, and its floor mixes value noise with
   stencil truncation. §19.6 adds an h-scan record for any fluid whose floor exceeds 1e-11, which is what showed
   F-6 to be harmless. The test itself is not changed.

**Examined and sound:**
- **Design conformance.** D1–D3 match §4.2 exactly (steps 1–7, the bounds 52/64/2^−26, and B-26/B-27).
- **Seeds.** D2 checks seeds by arithmetic alone and adds no jet.
- **Fallback termination.** Every loop has a fixed bound, and NaN gives `None`.
- **Densities stay positive.** The bracketed Newton bisects toward 0 and never past it, so no `_jet` call can see a
  non-positive density. B-30's propagation is therefore the ordinary `_jet` failure.
- **Residual/Jacobian consistency.** The D3 and fallback answers use the same p(ρ, T), `_at` and Clausius-Clapeyron
  as every other state.
- **The cache.** It is keyed on the exact T. Plain answers stay bitwise unchanged after fallback calls, which the
  record shows, so CoolProp is history-independent.
- **The D3 strip in both providers.** It is reached only where the saturation is `None`. It is unique outside the
  box under C-strip, as finding 6 notes. For S05 it applies only above about 647.0954 K, where the loop's pressure
  range is ≲ 1e-5·p_c, well inside [22.0, 22.2] MPa.
- **Tier-B labelling.** Tier B is labelled self-consistent (A34, §16.5.1). Only N4/G4, still to do, will give the
  near-critical roots an independent expectation, and finding 5 widens it.

**Not examined:** the generator (unchanged since R-625), packaging and the extra's lock (R-624), A26–A28 and the
guard's G1–G4 beyond confirming that the fallback reaches CoolProp only through `_jet` after them, T08's C3 harvest
(WO-S07-3), and aarch64.

## Rulings (normative text in spec §19; register R-626)

- **G3:** the bound was wrong. Re-set per finding 1.
- **G8:** the bound was wrong. Re-set per finding 2.
- **θ_min:** right. Keep it, with the remedy pre-registered (finding 7).
- **B-15:** confirmed, with the measured reason given in §19.6.
- **F-6:** the tier-B A17 stop line becomes the test's 1e-10, with an h-scan record above 1e-11.
- **B-18 and B-22:** confirmed. A10/A11's wording is amended.
- **B-19, B-20, B-21, B-23, B-24:** confirmed.
- **B-25:** confirmed. It is test-only, and production computes θ by the stated formula.
- **B-26, B-27, B-29, B-30:** confirmed.
- **B-28:** confirmed. G7(c) was mis-worded in the design note.
- **Q3 and Q5:** no objection.
- **The S05 manifest's A33: needs a decision.** My default is to carry `8cab0e15`'s S05 evidence (S05 suites,
  `s05_reference.py --check`, and the record digest) as an S05 section of S07's manifest, with no new S05 manifest.
  The S05 change ships inside wp/S07, and S05's merged manifest stays authoritative for S05's own scope.
- **WO-S07-NC1:** discharged by §19 and the S05 Erratum.
