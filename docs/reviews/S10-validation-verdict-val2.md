# S10 — verdict on evidence (empirical validation: S10.A51, VAL-2)

**Lane:** design (`verdict`), package S10, WO-S10-8 step 3 (spec §19 A6-10). **Date:** 2026-10-25. **Branch:** `wp/S10`.
The evidence is at `9fadf32f` (script, report and tests; step 2) and `a15baa0a` (the transcription; step 1).
**Authority:** `docs/derivations/S10-spec.md` (SHA-256 `d55660ea2cc664d0…`):
- §9.6, VAL-2's row: AAD(ΔP/P) ≤ 3 %, AAD(y_i) ≤ 0.015, fixed before any data were transcribed (R-708);
- §17 A4-2 item 4: §7.5's row S10.A51;
- §19 (Amendment 6, `d42fcf08`), fixed blind before anything was computed: A6-3 the bubble pressure, A6-4 the
  aggregation and the verdict strings, A6-5 the inclusion, A6-7 the report (R-725–R-727).

**Standing.** This is an agent verdict, numerical and procedural. It is not scientific review. Human numerical and
process-modeling sign-off is recorded separately, and nothing here claims it. This document does not set `reviewed`.
The VAL-1/VAL-3 record, `docs/reviews/S10-validation-verdicts.md`, is archival and unchanged; its §2 ("insufficient
evidence: pending") is superseded for S10.A51 by this file.

**The reading is not reopened.** A6-4's aggregation (the binary is the unit, y_1 is judged, ΔP/P over the measured P,
inclusive comparison of the stored 10-digit values) was registered before any value existed. This verdict applies it as
written. §5 records why no alternative reading is entertained, and shows that the outcome does not depend on it.

## The verdicts

| # | Criterion (as registered) | Verdict |
| --- | --- | --- |
| 1 | **Data identity** (A6-1, A6-6; claim C1–C4). The three CSV files hash to `e1290279…90bb`; the transcription has not changed since step 1. | **Met.** Hash reproduced on all three files; the only commit touching them is `a15baa0a`. In addition, all 159 rows (477 values) were read against the 300 dpi page image of p. 680 by this verdict: no discrepancy (§1.2). |
| 2 | **Procedure** (A6-3). Closed form through one `evaluate_phase` call at P_eval = 101 325 Pa; n embedded in (CH3OH, C2H5OH, H2O) order; K_i = exp(lnφ_i); P_calc = P_eval·Σ n_i K_i; y_i = n_i K_i/S; refusal or non-finite value stops the run. Records `d4a39730…`. | **Conforms.** Read line by line (§2). No refusal, no non-finite value at any of the 159 states. |
| 3 | **Aggregation** (A6-4). r = (P_calc − P_exp)/P_exp; per-binary AADs over all three isotherms; 10-significant-digit storage; inclusive comparison of the stored values with 0.03 and 0.015. | **Conforms** (§2). |
| 4 | **Inclusion** (A6-5). All 159 points enter; none dropped by pressure, outlier or any other rule. | **Conforms.** 159 rows in `per_row`, in file order; 40 measured pressures below 30 kPa entered and were counted. |
| 5 | **Held out** (S10.A53.2). The 1995 data entered no fit. | **Met.** `fit-report.json` contains neither `1995` nor `kurihara1995`; every `wilson_lambda` provenance cites `38 (1993)`, none `40 (1995)`. |
| 6 | **methanol + water**, N = 52: AAD(ΔP/P) ≤ 0.03; AAD(y_1) ≤ 0.015. | AAD(ΔP/P) = 0.01086763935: **met**. AAD(y_1) = 0.004754833453: **met**. Binary: **`within band`**. |
| 7 | **ethanol + water**, N = 107: AAD(ΔP/P) ≤ 0.03; AAD(y_1) ≤ 0.015. | AAD(ΔP/P) = 0.00289894189: **met**. AAD(y_1) = 0.004075153801: **met**. Binary: **`within band`**. |
| 8 | **S10.A51, VAL-2** (A6-4): within band only if both binaries are within both bands. | **`within band`**. |

Since the procedure conforms to §19 (rows 2–4), the verdict is not `blocked`.

**Verdict strings for WO-S10-8 step 5** (A6-4's exact strings, to be pinned by `validation_check`):
- VAL-2: `within band`
- methanol+water: `within band`
- ethanol+water: `within band`

**Evidence class.** VAL-2 is **empirical validation**: model predictions against measured data held out from the Λ
fit. A51.2–A51.5 in the same test file are **numerical verification** of the bubble-pressure procedure (P_eval
invariance, agreement with an independent closed form, the bubble condition, Λ-transposition sensitivity); they are a
precondition of this verdict, not part of it. Nothing here is optimality evidence. Package status for S10.A51:
implemented and tested (`tests/test_s10_validation.py`: 11 passed, 0 skipped, re-run by this verdict). Not reviewed, not
released.

## 0. The evidence judged, and its provenance

| Item | Produced by, where | SHA-256 (prefix) |
| --- | --- | --- |
| Transcription `benchmarks/s10/vle/kurihara1995_binaries{,.A,.B}.csv` | Two independent `opus-engineer` entries (A: text layer as draft, every value re-read on 300 dpi crops; B: 300 dpi image only), byte-identical (B-88, `a15baa0a`) | `e129027986fa9c15` (all three) |
| Records `benchmarks/s10/records.yaml` | `s10_records.py`, last changed `d6dd3c13` (uncertainty line only); Λ fitted to the 1993 isobaric binaries | `d4a39730ee24c592` |
| Model `src/openflowsheet/thermo/wilson_ig.py` | (3.3), (3.8), (3.10) | `4bcd8f4dc8115b6b` |
| Computation `scripts/s10_validation.py` (`read_val2`, `bubble_p`, `val2`) | Build lane, `9fadf32f` | `e55d04c94a06ae57` |
| Report `benchmarks/s10/validation/report.json`, `docs/s10-validation-report.md` | `s10_validation.py --write`, x86-64, Python 3.13.5 (B-89 MEASURED) | `0efa1c6da9419d7b`, `233e95c531c86b72` |
| Tests `tests/test_s10_validation.py` | Build lane, `9fadf32f` | `e9c8fdef490e17a3` |

**What this verdict ran** (worktree at `9fadf32f`, clean, x86-64, Python 3.13.5, mpmath 1.3.0; scratch scripts not
committed, their core is in Appendix A):
1. **Independent recomputation** from the CSV and `records.yaml` only, importing neither `s10_validation.py` nor
   `openflowsheet.thermo`. Route (a): binary64, the textbook binary Wilson form, which is (3.8) rewritten for two
   components. Route (b): mpmath at 50 digits, the general three-component (3.8) with the absent alcohol at x = 0.
   Both give P = Σ x_i γ_i P_i^sat and y_i = x_i γ_i P_i^sat / P. The routes agree to 4.2 × 10⁻¹⁵ relative in P and
   8.3 × 10⁻¹⁶ in y; the AADs from (a) and (b) agree to all 12 printed digits.
2. **Provider path against route (a)**: one `evaluate_phase` call per row at 101 325 Pa, built here, not through the
   script. `describe().components` = (CH3OH, C2H5OH, H2O); 0 refusals; worst difference 1.75 × 10⁻¹⁵ relative in P,
   4.4 × 10⁻¹⁶ in y. So the provider route is the model's bubble pressure at these states, as A6-3 argues.
3. **Against the committed report**: each binary's stored AAD_P and AAD_y equal `sig(·)` of route (a)'s values
   exactly; the below-bound counts agree (1, 1; 39, 39). Each `per_row` P_calc and y1_calc agrees with route (a) to
   2.2 × 10⁻¹⁰ relative and 5.0 × 10⁻¹¹ absolute, which is 10-significant-digit storage.
4. `pytest -q tests/test_s10_validation.py`: 11 passed. `s10_validation.py --check`: "OK: the report matches".
5. The page image (pdftoppm, 300 dpi, p. 680) against every CSV row (§1.2).
6. `git diff d42fcf08 9fadf32f` of the spec, `records.yaml` and `fit-report.json`: empty. The `BANDS` definition is not
   in the step-2 diff, so `BANDS["VAL-2"]` is the value fixed before step 2.

The computation followed the registration in time: Amendment 6 `d42fcf08` (14:24), transcription `a15baa0a` (14:31),
computation `9fadf32f` (14:38), all 2026-10-25.

## 1. The data

### 1.1 Identity

SHA-256 `e129027986fa9c15ebf8e00d5fa040497708cb0c7a9d483263eefe2ba98090bb` for all three files, 7504 bytes, 159 rows in
blocks of 14/20/18 (methanol + water) and 37/34/36 (ethanol + water) at 323.15/328.15/333.15 K. Unchanged since
`a15baa0a`.

### 1.2 Check against the print

Every row of Tables 2 and 3 was read from the 300 dpi rendering of p. 680, in print order (left, middle and right
column groups per isotherm), and compared with the CSV's P_kPa, x1 and y1. **159 of 159 rows, 477 of 477 values agree.**
The block sizes agree. The non-monotone pressures near the ethanol–water azeotrope and the y1 reversal at 333.15 K rows
12–13 are as printed (B-88 noted them).

*Limits of this check.* It is a third reading by an agent of the same model family as the two entries, not a human
reading and not a check of the paper. It rules out a transcription slip as the reason for any number below; it says
nothing about whether the 1995 measurements are right.

### 1.3 Coverage (facts, for the limitations)

| Binary | x_1 range | P_exp range (kPa) | Points with P_exp < 30 kPa |
| --- | --- | --- | --- |
| methanol + water | 0.1587–0.7808 | 29.119–72.832 | 1 (323.15 K, row 1) |
| ethanol + water | 0.0742–0.9583 | 20.333–47.060 | 39 (all 37 at 323.15 K; 2 at 328.15 K) |

A6-1 expected "the water-rich part of every isotherm" below the domain. For methanol + water that is not so, because
Table 2 has no point with x_1 < 0.159 (the build lane observed this in B-89's MEASURED line). Nothing in the verdict
turns on it; it bounds what VAL-2 covers (§7).

## 2. The procedure, against §19

Read in `scripts/s10_validation.py` at `9fadf32f`:
- **A6-3 step 1.** `t, x1 = float(r["T_K"]), float(r["x1"])`; `p_exp = 1000.0 * float(r["P_kPa"])`;
  `y1_exp = float(r["y1"])`. As registered.
- **Step 2.** `(x1, 0.0, 1.0 - x1)` for methanol + water, `(0.0, x1, 1.0 - x1)` for ethanol + water. As registered.
- **Step 3.** One `evaluate_phase` call, phase `LIQUID`, at `P_EVAL_VAL2 = 101325.0`. The property names come from
  `describe().components` (B-89(b)); for the committed records that tuple is (CH3OH, C2H5OH, H2O), checked in §0 item
  2, so the request is the registered one exactly.
- **Step 4.** `s = n[0]*k1 + n[1]*k2 + n[2]*k3` in the registered order; `P = p_eval * s`; `y_i = n_i k_i / s`. The
  judged y is the alcohol's slot; y_H2O is reported.
- **Refusal.** A status other than `ok` raises `Val2RefusedError`, turned into `SystemExit("VAL-2 refused at …")`;
  a non-finite value gives `SystemExit("VAL-2 non-finite at …")`. Both occur inside `build()`, which runs before either
  report file is written, so nothing is written. Neither occurred.
- **A6-4.** r and Δy_1 per point; AADs, maxima and signed means from the unrounded values, then `sig` (10 digits);
  `within_band` compares the stored AADs with `BANDS["VAL-2"]` = {0.03, 0.015} using `<=`; the binary verdict is
  `within band` only if both are true; VAL-2's only if both binaries' are. aad_y_water is against 1 − y_1,exp.
  "Below domain" is strict `<` on the unrounded pressure. Pooled and per-isotherm statistics are reported and enter no
  verdict.
- **A6-5.** The loop over rows has no filter; `per_row` has 159 entries in file order (checked by zip with the CSV).
- **A6-7 C1–C5.** Implemented before any provider call; C1 holds.

No departure from §19 was found.

## 3. The numbers

Route (a), binary64; the committed report carries the same values to its 10 digits.

| Binary | N | AAD(ΔP/P) | Band | AAD(y_1) | Band | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| methanol + water | 52 | 0.01086763935 (1.087 %) | ≤ 0.03 | 0.004754833453 | ≤ 0.015 | `within band` |
| ethanol + water | 107 | 0.00289894189 (0.290 %) | ≤ 0.03 | 0.004075153801 | ≤ 0.015 | `within band` |

Reported, not judged (A6-4):

| Binary | max \|r\| | mean r | max \|Δy_1\| | mean Δy_1 | aad_y_water |
| --- | --- | --- | --- | --- | --- |
| methanol + water | 0.02670 (333.15 K, row 3) | +0.01087 | 0.01703 (323.15 K, row 5) | −0.00429 | 0.004754833453 |
| ethanol + water | 0.02124 (323.15 K, row 1) | −0.00144 | 0.01543 (333.15 K, row 5) | −0.00262 | 0.004075153801 |

Per isotherm (reported, not judged): methanol + water mean r = +1.009 %, +1.126 %, +1.104 % and mean Δy_1 = −0.0078,
−0.0051, −0.0007 at 323.15, 328.15, 333.15 K; ethanol + water mean r = −0.154 %, −0.176 %, −0.103 % and mean Δy_1 =
−0.0015, −0.0015, −0.0048. Pooled over 159: AAD(ΔP/P) 0.5505 %, AAD(y_1) 0.004297.

**A misreading to guard against.** The largest single |Δy_1| (0.0170 for methanol + water, 0.0154 for ethanol + water)
exceeds 0.015. That is not a miss: §9.6's 0.015 is an AAD band, and VAL-2 has no maximum-deviation band (A6-4 rejected
adding one, R-708). Citing a maximum against the AAD band would move the band.

**How far the verdict is from flipping.** For methanol + water to miss, the sum of |r| over its 52 points would have to
grow by 0.995 (its AAD_P to rise 2.8-fold), or the sum of |Δy_1| by 0.533. For ethanol + water, 2.90 and 1.17 over 107
points. Last-bit differences between platforms (Q-A6.1) move these AADs by 10⁻¹⁵ or less; they can change the report's
bytes but not this verdict. No single-digit transcription slip remains to consider, since every value was checked
against the print (§1.2).

## 4. What the reported patterns show, and do not

These are observations on reported quantities. They enter no verdict.
- **methanol + water: a uniform positive pressure bias.** All 52 r are positive; the per-isotherm means are +1.0 % to
  +1.1 %. The y_1 bias shrinks as T approaches the 101.3 kPa isobar's temperatures (from −0.0078 at 323.15 K to −0.0007
  at 333.15 K). That trend fits an error that grows with distance from the fit temperatures. VAL-2 cannot attribute it:
  constant Λ, the fitted methanol P^sat, and the ideal-gas vapour are all candidates.
- **The pressure scale** (A6-13: Bridgeman and Aldrich 1964 against the project's IAPWS-95 water). A common
  multiplicative scale error would shift every r in both binaries alike. The two binaries' signed means differ by about
  1.2 percentage points (+1.09 % against −0.14 %), and that difference cannot come from a common scale factor. The scale
  itself is not measured here.

## 5. Alternatives rejected

These were rejected by §19 before the computation (A6-4, A6-5; R-726). This verdict does not reopen them; it records
them so a later session does not rediscover them as new options.
- **Pooled over 159 points** as the judged unit. Rejected because ethanol + water would dominate (107 of 159) and a
  methanol + water miss could pass. Reported: 0.5505 %, 0.004297.
- **Each (binary, T) isotherm judged.** Rejected as twelve tests on the paper's measurement runs, a distinction the model
  does not make. Reported: the largest isotherm AAD_P is 1.126 % and the largest AAD_y is 0.0078, so no isotherm would
  have missed either.
- **A maximum-deviation band.** §9.6 has none for VAL-2; adding one moves the band (R-708). See §3.
- **P_calc as the denominator, or |ln(P_calc/P_exp)|.** Rejected because the measured pressure is the model-independent
  reference and the band was written as ΔP/P. With |r| ≤ 0.027, either alternative changes every |r| by less than 3 % of
  itself, far from the 2.8-fold margin.
- **Judging only the points inside the records' P domain, or reporting that subset beside the judged AAD.** Rejected
  because it selects by composition and temperature, which is the extrapolation VAL-2 tests, and because a second AAD
  invites citing whichever is better. This verdict computes no such subset.
- **An outlier rule.** Rejected: the stated accuracies (± 0.03 kPa, ± 0.001 in y) cannot produce a miss, and a rule
  chosen after the computation would be a fit to the validation data.
- **Iterating in P** for the bubble point. Rejected by A6-3 for the closed form, which is exact under (3.10) and never
  calls the provider below its domain.
- **Correcting the transcription** after seeing the numbers. Not needed (§1.2), and only a design-lane amendment with
  page-image evidence could do it, reporting the verdicts before and after.

## 6. What would change this verdict

Reversing it takes a new, recorded design-lane decision justified by one of these:
- **Different records.** Any records change beyond the `uncertainty` line (a new Λ, P^sat coefficients or vapour model)
  voids this verdict. VAL-2 must be recomputed by A6-3/A6-4 and judged again. Successors in `records-lineage.json` that
  change only `uncertainty` (A6-9) do not affect it.
- **A change in the lnφ path** of `wilson_ig.py`. A51.10's independent closed form would catch it, and the verdict
  stands only while A51.10 passes.
- **A transcription amendment** (A6-5) or a published erratum to Tables 2–3. The amendment must report the verdicts
  before and after.
- **Evidence that the 1995 measurements are wrong**, for example an independent isothermal data set at these
  temperatures disagreeing by more than the stated accuracies.
- **Not** a byte-identity failure of the report on aarch64 (Q-A6.1). That is a report-identity question for the design
  lane, and it cannot move an AAD by 10⁻².
- **Not** a wish for a tighter or a maximum band. The band does not move (R-708).

## 7. What this verdict does not establish, and the limitations that travel

What it does not establish:
- **Constant-Λ extrapolation outside 323.15–333.15 K.** Between 333.15 K and the isobar's temperatures there are only
  the fit data (fit quality, S10.A53) and VAL-1's ternary at 101.3 kPa. Below 323.15 K nothing is validated, and the
  methanol + water y_1 trend in §4 argues against assuming it.
- **The methanol + ethanol pair, or the ternary, off the isobar.** VAL-2 has no data on either.
- **The dilute ends.** methanol + water is covered only for 0.159 ≤ x_1 ≤ 0.781, ethanol + water for
  0.074 ≤ x_1 ≤ 0.958. The infinite-dilution behaviour that governs stripping and the water-rich column end is not
  validated by VAL-2.
- **Pressures outside 20.3–72.8 kPa**, and in particular the upper part of the records' domain (up to 200 kPa), where
  the ideal-gas vapour is a weaker approximation than at these sub-atmospheric pressures.
- **A pressure domain below 30 kPa.** 40 of the 159 measured pressures lie below the records' bound. Within band there
  is a statement about the closed forms at those points; `describe().domain` is unchanged (Q-A6.3 is Frank's).
- **The vapour model separately from the liquid model.** With an ideal-gas vapour, any vapour non-ideality is absorbed
  into the fitted Λ. Agreement here can include compensating errors.
- **That the paper's pressure scale equals the project's** (A6-13). Not measured.
- **Independence from the fit data's laboratory.** The 1993 fit data and the 1995 validation data come from the same
  research group (Kurihara, Kojima and co-workers). The 1995 data are held out from the fit, but a systematic error
  common to both papers' methods would not show.
- **That the 1995 data are correct.** The transcription matches the print (§1.2); the print itself is not checked.
- **A portable result.** Computed on x86-64 only; Q-A6.1 (aarch64 byte-identity of the report) is open, though the
  verdict is insensitive to it (§3).
- **Review, release or a rights clearance.** Not reviewed, not released; RC-06 is unresolved, so the files are
  repository-only; shipping is Frank's (Q-F3). No human numerical or process-modeling sign-off is implied.

Limitations to carry into the manifest and the release report (consistent with A6-9's sentence and `not_established`
block):
1. VAL-2 `within band` on 159 held-out isothermal binary points at 323.15–333.15 K and 20.3–72.8 kPa, judged per binary
   (methanol + water AAD(ΔP/P) 1.09 %, AAD(y) 0.0048; ethanol + water 0.29 %, 0.0041). Empirical validation only.
2. Not established outside 323.15–333.15 K off the isobar, for methanol + ethanol or the ternary off the isobar, or at
   x_1 < 0.159 (methanol + water) and x_1 < 0.074 (ethanol + water).
3. 40 of 159 measured pressures lie below the records' 30 kPa bound, which is not extended.
4. methanol + water bubble pressures are over-predicted at every point, by 1.09 % on average (reported, not judged).
5. Fit and validation data share a laboratory; the paper's pressure scale against IAPWS-95 is not measured.

**Cross-check values for step 4** (A6-9's formats applied to the committed report; the report governs):
{V} = {V_MW} = {V_EW} = `within band`; {A_MW} = `1.09`, {Y_MW} = `0.0048`; {A_EW} = `0.29`, {Y_EW} = `0.0041`;
{N_LOW} = `40`.

## 8. Separate findings (on documents this verdict does not change)

- **F1, A6-8 row S10.A51.10's stated floor.** It gives the storage floor as 5 × 10⁻¹¹ relative in P. Ten significant
  digits give up to 5 × 10⁻¹⁰ relative (a value with leading digit 1); the worst measured here is 2.2 × 10⁻¹⁰. The
  registered tolerance, 10⁻⁹, still holds for any value by a factor of 2, so no test or verdict changes. A future
  amendment that tightens A51.10 should use the corrected floor.
- **F2, A6-1's coverage expectation.** "The water-rich part of every isotherm" below the domain holds for ethanol +
  water but not for methanol + water (§1.3). A6-3 and A6-5 do not depend on it. The consequence is the coverage
  limitation in §7.

## Appendix A. The independent closed form (route (a))

Parameters read with `yaml.safe_load` from `records.yaml`: `vapour_pressure_{a,b,c,d}` per component and
`wilson_lambda` entries {i, j} = Λ_ij. For alcohol `alc` and water:

```python
def binary64(alc, T, x1):
    x2 = 1.0 - x1
    L12, L21 = lam[(alc, "H2O")], lam[("H2O", alc)]
    s1, s2 = x1 + L12 * x2, x2 + L21 * x1
    lg1 = -math.log(s1) + x2 * (L12 / s1 - L21 / s2)
    lg2 = -math.log(s2) - x1 * (L12 / s1 - L21 / s2)
    p1 = x1 * math.exp(lg1 + lnpsat(alc, T))      # lnpsat: (3.3), theta = T/1000
    p2 = x2 * math.exp(lg2 + lnpsat("H2O", T))
    P = p1 + p2
    return P, p1 / P, p2 / P                       # P_bub, y_alc, y_H2O
```

r = (P − 1000·P_kPa)/(1000·P_kPa) and Δy_1 = y_alc − y1 per row; AADs are plain means over each binary's rows; the
verdict compares `float(f"{AAD:.10g}")` with 0.03 and 0.015 inclusively.
