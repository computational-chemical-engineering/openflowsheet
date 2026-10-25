# S10 — verdicts on evidence (empirical validation: S10.A50–A53, VAL-1 and VAL-3)

**Lane:** design (`verdict`), package S10, after WO-S10-6. **Date:** 2026-10-25. **Branch:** `wp/S10`. The evidence is at
`43214f5c` (script, report and tests) and `02e8a7b1` (the VAL-1 data). **Authority:** `docs/derivations/S10-spec.md`
(SHA-256 `2079ea6c…b3bd`):
- §9.6: the bands, fixed before any data were transcribed;
- §3.3 and §3.7: the approximations VAL-3 measures;
- §15 A2-2: VAL-1 uses Table V's printed pressure;
- the §7.5 row for S10.A50–A53;
- §11, WO-S10-6.

Register: R-708 ("a result outside a band is reported 'not validated within band'… The band is not moved").

**Standing.** These are agent verdicts, numerical and procedural. They are not scientific review. Human numerical and
process-modeling sign-off is recorded separately, and nothing here claims it. This document does not set `reviewed`.
The companion verdict on the reference comparisons is `docs/reviews/S10-reference-verdicts.md`. §0 lists what was run.

## The verdicts

| # | Criterion (as registered) | Verdict |
| --- | --- | --- |
| 1 | **S10.A50, VAL-1.** Ternary methanol + ethanol + water, Table V of Kurihara et al. (1993), held out from every fit. Bubble T and y at the measured x and P. Bands: AAD(T) ≤ 1.0 K, AAD(y_i) ≤ 0.015, max \|Δy\| ≤ 0.05 | **MET: validated within band.** 38 rows at 101.3 kPa. AAD(T) 0.2097 K. AAD(y): 0.00565 (CH3OH), 0.00544 (C2H5OH). max \|Δy\|: 0.0210 and 0.0210. Reproduced by an independent implementation that does not use the provider |
| 2 | **S10.A51, VAL-2.** Isothermal binaries of Kurihara et al. (1995). Bubble P and y. Bands: AAD(ΔP/P) ≤ 3 %, AAD(y_i) ≤ 0.015 | **INSUFFICIENT EVIDENCE: pending.** No data were supplied, and nothing was computed. The two tests are skipped, not passed |
| 3 | **S10.A52, VAL-3.** CoolProp 8.0.0 reference EOS, pure components, T ∈ [300 K, T_b(101 325 Pa)]. Bands: Δh within 5 %, c_p^0L within 25 % | **NOT MET for one of six cells. Methanol Δh is "not validated within band":** its maximum deviation over the range is +5.72 % against 5 %. The other five cells are within band: CH3OH c_p^0L 19.7 %; C2H5OH Δh 3.59 % and c_p^0L 16.9 %; H2O Δh 1.65 % and c_p^0L 12.7 % |
| 4 | **S10.A53.** The fit-quality report, kept apart from validation | **MET for the fit-quality part.** `benchmarks/s10/fit-report.json` carries AAD(T) and AAD(y_1) per binary. The validation report is labelled "validation, not verification". **VAL-2's part is pending** |
| 5 | **Ruling (1): B-71, the reading of "within 5 %"** | **The maximum over the registered closed range. The spec's text supports it, and the methanol miss stands** (§3.3). The signed mean (+4.0 %) is not a reading the text admits |
| 6 | **Ruling (2): B-73, VAL-1 judged on y_1 and y_2** | **Endorsed.** The bands apply to the measured vapour fractions. Water's y is a closure, 1 − y_1 − y_2, not a measurement. **The choice is immaterial**, because the closure is also within band (AAD 0.00599, max 0.0308) |
| 7 | **Ruling (3): B-70, the script and report paths** | **Accepted.** A tooling choice with no scientific content. It follows the repository's S10 pattern, and `--check` reproduces the report without CoolProp |
| 8 | **§9.6: a miss is "stated in `uncertainty`"** | **Outstanding.** `records.yaml` still reads "not yet validated (S10 spec §9.6)". Changing it changes the records hash, which other records cite (finding F2) |

**Evidence class.** All of this is **empirical validation**.
- VAL-1 compares the model with measured data held out from the Λ fit.
- VAL-3 compares it with a reference equation of state. That EOS is itself a correlation of measurements.
- None of this is numerical verification, which is the companion verdict and §7, and none of it is optimality evidence.
- Package status: implemented and tested (`tests/test_s10_validation.py`: 7 passed, 2 skipped). Not reviewed, not
  released.

## 0. The evidence judged, and its provenance

| Item | Produced by, where | SHA-256 (prefix) |
| --- | --- | --- |
| `benchmarks/s10/vle/kurihara1993_ternary.csv` (38 rows) | Double entry, at `02e8a7b1`: transcription A, and transcription B from the page image only. A and B are byte-identical, and the final file equals A (checked with `cmp`). The paper itself is not in the repository | `f92758f4…` |
| `benchmarks/s10/validation/val3-eos.json` | `scripts/s10_validation.py --emit-eos`, CoolProp 8.0.0 (its version and git revision are recorded) | `3d040eed…` |
| `benchmarks/s10/validation/report.json`, `docs/s10-validation-report.md` | `scripts/s10_validation.py --write`, `43214f5c`. The model side runs through the provider's `evaluate_phase` | `00a51336…`, `213168fd…` |
| `benchmarks/s10/fit-report.json` | WO-S10-3, `s10_records.py` (B-21) | `4c88d2d5…` |
| Model parameters | `benchmarks/s10/records.yaml` | `74dc4e54…` |

**What I ran.**
- `PYTHONPATH=src python3 scripts/s10_validation.py --check`: "OK: the report matches".
- `pytest tests/test_s10_validation.py`: 7 passed, 2 skipped (VAL-2).
- **An independent recomputation, without `openflowsheet` and without the build lane's script.**
  - My own Wilson γ and P^sat code reads `records.yaml`. Its γ matches IDAES's readback to 2.3e-16 and its P^sat to
    2.1e-15 (companion verdict, §0).
  - It solves the bubble point by bisection, and evaluates Δh and c_p^0L from the closed forms (3.5) and (3.6).
- **CoolProp 8.0.0, run directly** (`~/.cache/of-rca-6fec822/venv-xcheck`).
  - It reproduces every EOS value in the report to ≤ 5e-12 relative, and each T_b to every printed digit.
  - At each grid point it also gives the saturated-vapour and saturated-liquid compressibilities used in §3.4.

## 1. VAL-1 (S10.A50): validated within band

**Results.**

| Quantity | Report | Mine (independent) | Band |
| --- | --- | --- | --- |
| AAD(T) | 0.2097 K | 0.2097 K | ≤ 1.0 K |
| max \|ΔT\|, mean ΔT (calc − exp) | 0.862 K, +0.185 K | 0.8616 K, +0.1848 K | — |
| AAD(y_CH3OH), AAD(y_C2H5OH) | 0.00565, 0.00544 | 0.00565, 0.00544 | ≤ 0.015 |
| max \|Δy_CH3OH\|, max \|Δy_C2H5OH\| | 0.0210, 0.0210 | 0.0210, 0.0210 | ≤ 0.05 |
| y_H2O by closure: AAD, max (reported, not judged) | 0.00599, 0.0308 | 0.00599, 0.0308 | (≤ 0.015, ≤ 0.05) |

- My bubble temperatures equal the report's to 4.8e-8 K at every row.
- The worst rows are 16 (ΔT = +0.86 K), 15 (+0.68 K) and 6 (+0.62 K).
- The data span T = 339.7–368.0 K, x_1 = 0.015–0.865, x_2 = 0.009–0.914 and x_3 = 0.054–0.976.

**Checks on procedure.**
- *Pressure.* 101 300 Pa, Table V's printed 101.3 kPa, as pre-registered in A2-2 before WO-S10-6. Reading it as
  101 325 Pa would give AAD(T) 0.2136 K. That is immaterial, and reported only to show it.
- *Held out.* The Λ were fitted to Table II's three binaries only (§9.4, A2-1). Table V's ternary entered no fit.
- *Bands.* They equal §9.6's, and a test asserts it.

**Ruling (2), B-73.** §9.6 writes "AAD(y_i)" and "max |Δy|" for a dataset whose table prints y_1 and y_2 only.
- The water fraction is 1 − y_1 − y_2, so its "error" is −(Δy_1 + Δy_2). It carries no measurement of its own, and
  judging it would count the same two errors twice.
- So the bands apply to the measured fractions.
- Under either reading every band is met. So the reading was not chosen to rescue anything, and it changes no verdict.

## 2. VAL-2 (S10.A51): insufficient evidence

- The 1995 isothermal binaries (Kurihara, Minoura, Takeda and Kojima, *J. Chem. Eng. Data* 40, 679–684) have not been
  obtained and checked against §9.4's description (Q-N1 for that paper). No row is transcribed and nothing is computed.
- **The smallest measurement that settles it:**
  1. Obtain the paper and confirm it matches §9.6's description.
  2. Double-enter its isothermal binary tables as for §9.4 and VAL-1, with the diff empty before commit.
  3. Compute the bubble P and y at the measured (x, T) with the committed `records.yaml`.
  4. Judge against AAD(ΔP/P) ≤ 3 % and AAD(y_i) ≤ 0.015, with the bands unmoved.
- VAL-2 is the only test of constant-Λ extrapolation in temperature (§3.7). Nothing in VAL-1 or VAL-3 substitutes for
  it, because VAL-1 is isobaric at the fit's pressure.

## 3. VAL-3 (S10.A52): not validated within band for methanol Δh

### 3.1 Results (maximum |relative deviation| over the 11-point grid, signed mean in brackets)

| Component | Δh (band 5 %) | c_p^0L (band 25 %) | Δh cell | c_p^0L cell |
| --- | --- | --- | --- | --- |
| CH3OH (300–337.63 K) | **5.72 %** (+4.02 %) | 19.7 % (−14.3 %) | **not validated within band** | within band |
| C2H5OH (300–351.57 K) | 3.59 % (+1.83 %) | 16.9 % (−11.5 %) | within band | within band |
| H2O (300–373.12 K) | 1.65 % (+0.73 %) | 12.7 % (−6.8 %) | within band | within band |

- My closed-form Δh and c_p^0L equal the report's model columns to ≤ 5e-10 relative. That is the report's 10-digit
  rounding.
- CoolProp reproduces the EOS columns to ≤ 5e-12.
- The methanol Δh deviation rises monotonically, from +2.65 % at 300 K to +5.72 % at T_b. It is above 5 % at the two
  highest grid points (333.87 K and 337.63 K), and crosses 5 % between 330.11 K and 333.87 K.

### 3.2 Where the miss comes from

Exact Clapeyron gives ΔH = T (V^V − V^L) dP/dT. The model's (3.5) is R T² d ln P^sat/dT, which is exact Clapeyron with
an ideal-gas vapour and no liquid volume. So:

  Δh_model / ΔH_EOS = (slope of the fitted ln P^sat / slope of the EOS's) × 1/(Z^V_sat − Z^L_sat).

From CoolProp's own saturated densities:

| Component and T | 1/(Z^V − Z^L) − 1 | Reported Δh deviation | Share from the P^sat fit |
| --- | --- | --- | --- |
| CH3OH, 337.63 K (Z^V = 0.947) | +5.73 % | +5.72 % | −0.009 % |
| CH3OH, 300 K | +2.63 % | +2.65 % | +0.02 % |
| C2H5OH, 300 K and 351.57 K | +0.63 % and +3.59 % | +0.63 % and +3.59 % | ≤ 0.002 % |
| H2O, 300 K and 373.12 K | +0.18 % and +1.64 % | +0.19 % and +1.65 % | ≤ 0.01 % |

- The whole deviation is the model's ideal-gas vapour, with the zero liquid volume a small part. It is not the P^sat fit
  and not the transcription.
- So no refit can remove it. Only a vapour non-ideality term can, which is a new model version (Q-N5).
- §9.6 anticipated exactly this ("Δh_i ≈ ΔH_vap/Z^V_sat, a few percent high at 1 atm"; methanol's vapour is the strongly
  non-ideal one).
- The anticipation explains the miss. It does not excuse it, and the band records the weakness without certifying it
  (§9.6).

### 3.3 Ruling (1), B-71: "within 5 %" means at every temperature of the registered range

**The question.** §9.6 registers "Δh within 5 %; c_p^L within 25 %" over "T ∈ [300 K, T_b(101 325 Pa)]". B-71 applies
the band to the maximum deviation over the grid. Under the mean, methanol (+4.0 %) would pass.

**The reading the text supports is the maximum.**
1. *"Within" names no statistic.* A quantity given over a range is "within 5 %" when it is within 5 % at each point of
   the range.
2. *The same table names an average wherever it means one.* VAL-1 states "AAD(T) ≤ 1.0 K; AAD(y_i) ≤ 0.015", and VAL-2
   states "AAD(ΔP/P) ≤ 3 %". The specifier wrote AAD where an average was intended, and wrote no AAD for VAL-3. Reading
   an average into VAL-3 would add a word the author left out.
3. *The band's own reasoning is about the hot end.* §9.6 sets the band against "a few percent high **at 1 atm**", that
   is, at T_b, the top of the range, where 1/Z^V_sat is largest.
   - A mean over [300 K, T_b] dilutes that point with sub-atmospheric points where Z^V_sat → 1.
   - The mean therefore measures something other than what the band was set for.
4. *R-708 forbids the alternative in substance.* "Watch for: a band moved after a miss." Changing the statistic after
   the result is known, to one that turns the miss into a pass, moves the band.
   - The coordinator's caution applies in full here: the reading that would rescue the result is the one not admitted.
   - B-71's maximum is the stricter reading, and it is the reading the text supports, independently of the result.
5. *The grid does not decide it.* The deviation is monotone in T at the 11 points, as 1/Z^V_sat is along the
   saturation line, and both ends of the closed range are grid points.
   - So the grid maximum equals the deviation at T_b. Any grid that includes the registered endpoint gives 5.72 %.
   - A grid without T_b would contradict the closed interval §9.6 registers.

**Not admitted.**
- The signed mean (+4.0 %).
- The mean absolute deviation, which here equals the signed mean because every methanol deviation is positive.
- A sub-range ending below T_b.

On each of them, methanol Δh is "not validated within band", and it stays so.

**A description, not a verdict.** At the grid points from 300 K to 330.11 K, the methanol Δh deviation is ≤ 4.93 %. This
is recorded for Q-N5 and S10-C. It narrows nothing: the registered range is [300 K, T_b], and the verdict on it is the
miss.

## 4. A53, and ruling (3)

- **A53.** The fit-quality numbers stay in `fit-report.json` (WO-S10-3, B-21). They are never labelled validation, and
  the test asserts that the validation report carries the "validation, not verification" convention. VAL-2's entry is
  "PENDING".
- **The A50–A53 labels.** §7.5 registers A50–A53 as one row: "VAL-1, VAL-2, VAL-3 and the fit-quality report". The build
  lane's labels (A50 = VAL-1, A51 = VAL-2, A52 = VAL-3, A53 = fit quality) follow that row's order. I judge under them
  (finding F1).
- **Ruling (3), B-70.** §11 names neither the script nor the report path.
  - `scripts/s10_validation.py` and `benchmarks/s10/validation/` follow the S10 pattern (`scripts/s10_*_comparison.py`,
    `benchmarks/s10/<tool>/`).
  - Committing CoolProp's output (`val3-eos.json`, with version and git revision) lets `--check` and the tests run
    without CoolProp. A direct CoolProp 8.0.0 run reproduces that file (§0).
  - Accepted.

## 5. Alternatives rejected

- **The mean reading of "within"** (§3.3). The text does not support it, and it would turn a miss into a pass after the
  result was known.
- **Judging VAL-3 on a sub-range** that stops where methanol crosses 5 %. That narrows the registered range, which is
  forbidden (CLAUDE.md: "no relaxed checks, removed cases, or narrowed denominators").
- **Pooling VAL-3 into one verdict across components or quantities**, so that five of six cells "carry" the sixth. §9.6
  bands each quantity of each component.
- **Treating the miss as a defect of the P^sat fit and refitting.** §3.2 shows the fit contributes ≤ 0.02 percentage
  points. A refit would also be a post-hoc change to `records.yaml` after a validation miss.
- **Moving the band to 6 %**, on the grounds that §9.6 "anticipated" the weakness. R-708 forbids it. The anticipation is
  why the band was 5 % and not 2 %.
- **Judging VAL-1 on all three vapour fractions as the binding reading.** It double-counts. It is immaterial here, and it
  is reported.
- **Recording VAL-2 as `BLOCKED`.** No route was attempted and failed. The data are simply not yet supplied. It is
  pending, and its verdict is insufficient evidence.

## 6. What would change these verdicts

- **VAL-2's data**, transcribed and computed as in §2. A51 then gets a verdict. Nothing above changes.
- **A transcription error found in Table V.** VAL-1 is then recomputed on the corrected file. A file change takes a new
  double entry.
- **A change to `records.yaml`'s Λ, P^sat or c_p^ig.** That is a new model state, and VAL-1 and VAL-3 are rerun.
- **A model version with vapour non-ideality** (Q-N5, S10-C). That model is validated afresh under its own registered
  bands. It does not revise the verdict on `wilson-ig-v1`, whose methanol Δh miss stays recorded.
- **A design-lane erratum to §9.6's wording.** It would take a new, explicit decision recorded against R-708, and it
  cannot be motivated by this result. Applying it to this result would be moving a band after a miss.

## 7. Separate findings

- **F1.** §7.5 should give A50–A53 one row each. The build lane's mapping (§4) is the natural one.
- **F2. §9.6's "stated in `uncertainty`" is not yet done, and doing it has a provenance cost.** `records.yaml` says "not
  yet validated (S10 spec §9.6)".
  - The statement should name the methanol Δh miss (+5.72 % at T_b(101 325 Pa), from the ideal-gas vapour), VAL-1 within
    band, and VAL-2 pending.
  - `records.yaml`'s SHA-256 (`74dc4e54…`) is recorded in both tools' `inputs.json`, both comparison records,
    `reference_values_real.yaml` and `fit-report.json`. Editing the file therefore breaks those links the way B-62 did,
    with every evaluated value unchanged.
  - The design lane should rule how this is done, as one isolated, disclosed edit, before the edit is made. I make no
    choice here.
- **F3.** `docs/s10-validation-report.md` says "Maxima over the grid (B-70)". The grid decision is B-71. This is a
  generator text fix.
- **F4. VAL-3 is held out in a weaker sense than VAL-1.** The P^sat records were fitted to the same EOS's saturation
  pressures (§9.3).
  - VAL-3's Δh test therefore isolates the model-form error, through 1/(Z^V − Z^L) (§3.2). It is not a test against data
    the model never touched.
  - That is what §9.6 meant it to measure, but it should be read that way in the release report.
- **F5. Q-N5 now has its measurement.** Methanol needs Z^V_sat = 0.947 at 1 atm for Δh within 5 %, and the ideal gas
  assumes 1. Q-N5's default (the ideal gas stays for S10; S10-C's specifier rules) is unchanged by this verdict.

## 8. What these verdicts do not establish, and the limitations that travel

**Not established.**
- **VAL-2:** constant-Λ extrapolation in temperature is untested.
- **Anything beyond the datasets' ranges** (§0 item 4). VAL-1 covers 101.3 kPa, 339.7–368.0 K and Table V's
  compositions. VAL-3 covers the three pure components on [300 K, T_b(1 atm)].
- **Freedom from systematic error shared with the fit.** Table V comes from the same laboratory, apparatus and paper as
  the Table II binaries the Λ were fitted to. Systematic errors common to both are not tested by VAL-1.
- **The source document itself.** The paper is not in the repository. The transcription rests on a double entry with an
  empty diff (A = B; B from the page image only).
- **The absence of a second liquid phase in the real mixtures** (§0 item 5), any excess enthalpy (h^E = 0 by
  construction), any column, PH-flash or flowsheet claim, and any rights to ship the data (Q-F3 is open).
- **Numerical verification.** That is the companion verdict and §7.

**Limitations that must travel into the manifest, `records.yaml`'s `uncertainty` and the release report.**
1. VAL-1: validated within band, 38 held-out ternary rows at 101.3 kPa (AAD(T) 0.21 K, AAD(y) ≤ 0.0057,
   max |Δy| 0.021).
2. VAL-2: pending. No data, no verdict.
3. VAL-3: methanol Δh **not validated within band**, +5.72 % at T_b(101 325 Pa) against 5 %. The cause is the ideal-gas
   vapour (Z^V_sat = 0.947), so energy balances with methanol vapour near 1 atm carry about a 6 % latent-heat error. The
   other five VAL-3 cells are within band. All c_p^0L deviations are negative, down to −19.7 % (methanol).
4. "Within" is read as the maximum over the registered closed range (ruling 1). The mean was not admitted.
5. The `uncertainty` string is not yet updated (F2).
6. These are agent verdicts. No scientific review, and no human numerical or process-modeling sign-off, is claimed.
