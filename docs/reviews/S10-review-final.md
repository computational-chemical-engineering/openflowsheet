# S10 final review (WO-S10-3 to WO-S10-6) and the batched rulings

**Reviewer:** design lane (`reviewer`), 2026-10-25.
**Reviewed:** `wp/S10` at `1274f81b`:
- WO-S10-3: `s10_saturation_points.py`, `s10_records.py`, `s10_reference.py --real`, the records, fit and points files,
  `docs/s10-rights-check.md`, and `tests/test_s10_records.py`;
- WO-S10-4/4b: the IDAES tool and comparison scripts, `benchmarks/s10/idaes/`, and `tests/test_s10_idaes.py`;
- WO-S10-5/5b: the same for DWSIM;
- WO-S10-6: `scripts/s10_validation.py`, `benchmarks/s10/validation/`, the report, and `tests/test_s10_validation.py`;
- `docs/S10_DECISIONS.md`, B-19 to B-74.

**Against:** `docs/derivations/S10-spec.md` §9 and Amendments 1–3 (§14–§16), R-711 to R-719, and the two verdict files.
**Brief:** `docs/briefs/S10-review-final.md`.
**Errata and rulings:** spec §17 (Amendment 4), register R-720 and R-721.

## Verdict

**Sound. Nothing is a must-fix.** The fit code implements §15 A2-1 as written. The real section of the generator
implements §9.7 and §16. Every committed record reproduces from its generator. No S10 file can reach a shipped path.
The harnesses are blind by construction.

Three things stand between S10 and `tested`, and all are small:
- **S-1:** the `uncertainty` string must change, with its hash cascade and a lineage test (ruling 2);
- **S-2:** the rights table must be brought up to date;
- **S-3:** the blindness tests must be completed.

The review's one substantive finding, **S-4**, is about the data, not the code. Table II does not determine the
individual methanol + ethanol Λ, and the choice moves ternary predictions by up to 0.46 K. It is disclosed in §17 and in
the new `uncertainty` string. It must not be "fixed" by looking at VAL-1.

**What I ran** (probe scripts are in the session scratchpad; none are committed):
- The six S10 test files: **237 passed, 2 skipped** (VAL-2).
- The `--check` runs:
  - `s10_reference.py`: 113 claims;
  - `--real`: 160;
  - `s10_records.py`: 25;
  - IDAES and DWSIM comparison: both recompute identically;
  - `s10_validation.py`: matches.
- **Fit robustness probe.** A2-1's procedure, through the script's own functions, on 79 variants of Table II:
  - each binary with one point left out (49 variants);
  - each printed y_1 moved by −0.001, 0 or +0.001 at random (10 per binary).
- **VAL-1 sensitivity probe.** The provider's VAL-1, with only the methanol + ethanol Λ replaced by the committed data's
  second minimum (on C), or by a mirror-basin minimum found under perturbation.
- **I11's attempt records**, and the outcome counts per linear solver in both runs of `idaes/qualification.json`.

## Findings, most severe first

**Must fix:** none.

**S-1. Should fix: `records.yaml:21` still says "not yet validated (S10 spec §9.6)", and that is false.**
- §9.6 requires the miss to be stated there, and `describe()` passes the string to every consumer.
- A consumer that reads only the provider does not learn of the 5.72 % methanol latent-heat error.
- Fix: §17 A4-3. It gives the exact string, the cascade, `records-lineage.json` and its reconstruction test, the edit to
  `test_s10_provider.py:158`, and the two text fixes in `s10_validation.py`'s `markdown()` (validation verdict F3).

**S-2. Should fix: `docs/s10-rights-check.md` describes the state before WO-S10-6.** It follows C12's format (rows,
vocabulary, per-file map), but its content is out of date:
- "Files checked" says the records are "not yet emitted".
- Row RC-03 omits `benchmarks/s10/validation/val3-eos.json`: 33 × (ΔH_vap, c_p) computed by CoolProp, plus three T_b.
- Row RC-06 says "Nothing yet". The repository now holds `kurihara1993_ternary{,.A,.B}.csv`, 38 rows of Table V.
- The per-file map lacks:
  - the three ternary CSVs (RC-06);
  - `kurihara1993_binaries.A/.B.csv` (RC-05);
  - `validation/val3-eos.json` (RC-03);
  - `validation/report.json`, which echoes every T_exp and y_exp of Table V (RC-06);
  - `reference_values_real.yaml` and both `inputs.json` (RC-07, derived).

Fix: update those rows and the map. Nothing ships either way, because none of these is `PACKAGED`.

**S-3. Should fix: blindness is enforced by construction but only partly tested.**
- Both tool scripts read only their `inputs.json`. Each state there holds exactly `{n, T, P}`. Neither script imports
  `openflowsheet` or names `reference_values` or `comparison.json`. All of this checked.
- `test_s10_idaes.py` has no blindness assertion.
- `test_s10_dwsim.py:103-107` checks only I1, and only the key `closed_form`.
- Fix: one test per tool. It asserts the source-text exclusions as DWSIM's test does, and that every
  `inputs.json` state's key set equals `{"n", "T", "P"}`.
- Temporal blindness (the qualification committed before the comparison) is established only by commit order, and the
  verdict audited it. No test can do that.

**S-4. Should fix, as disclosure (done in §17 A4-2); needs a decision for S10-C: the methanol + ethanol Λ are not
identifiable from Table II.**
- In the probe, every variant passes LAMBDA-CONV, -MIN and -⟨binary⟩, so the procedure is fail-safe.
- But the adopted methanol + ethanol minimum lies in three basins across the 21 variants:
  - θ*'s basin, with θ_12 from 0.40 to 0.71;
  - a mirror basin, with θ_12 from −0.43 to −0.50, which the committed data do not have;
  - C, in one variant, which needed 102 of the 200 iterations.
- Only θ_12 + θ_21 ∈ [0, 0.175] is stable.
- This matters downstream. Taking the committed data's second minimum, which is 2.1 × 10⁻⁵ (4.8 %) above Φ* in the
  binary objective, moves VAL-1's ternary bubble temperatures by up to **0.46 K** and y by up to 0.009. Both choices are
  within VAL-1's band, so the verdict stands.
- A2-6's "weakly determined" understates this. §17 A4-2 replaces it.
- **Do not re-select Λ by their VAL-1 performance.** VAL-1 is held out.
- My recommendation for S10-C: register a determination of this pair that does not use Table V, blind, before any
  column claim relies on ternary temperatures at the 0.5 K level.

**S-5. Should fix (done in §17): errata.**
- I11 (ESC-8; A4-1).
- A44's "text" is the verbose rendering (ESC-7, B-42; A4-2.1).
- LAMBDA-⟨binary⟩ cannot fail under A2-1 (A4-2.2): Gauss–Newton starts at θ_g and accepts only Φ(trial) ≤ Φ(θ), so
  Φ* ≤ Φ_g identically. The claim is true but is not evidence, and the test's `grid_margin_over_phi_star >= -1e-12` is
  vacuous too. A2-1's "the global claim keeps its margin" is corrected. No code change.
- §7.5's A50–A53 become four rows (A4-2.4).

**Notes** (no action needed unless stated):
- **N-1.** `s10_records.py:363-369`: the halving loop tests the trial at λ = 2⁻²⁰¹ before it breaks. A2-1 says "below
  2⁻²⁰⁰ the iterate stays". This is immaterial: the step taken is then below 10⁻³⁰, which ends the run either way, and
  LAMBDA-MIN certifies θ*.
- **N-2.** B-27's stop is "the line search shrank the step", not a stationarity test. LAMBDA-MIN (|∇Φ| ≤ 10⁻²⁰, Hessian
  positive) carries stationarity. Keep it; LAMBDA-CONV alone would not be enough.
- **N-3.** `wilson_ig.py:320-327`: `_checkout_records` accepts any `<X>/src/openflowsheet/thermo/` layout. The wheel
  (`PACKAGED`, package-data patterns kept equal by `test_t08_w4_package_data.py`) and the audited sdist (`MANIFEST.in`,
  T08.A43) carry no S10 file. **No shipped path can pick up S10 data**, and `test_a28` covers all of
  `benchmarks/s10`.
- **N-4.** B-19 imports the private `iapws95._saturation`. A rename fails `--check` loudly, so this is acceptable in a
  derivation script.
- **N-5.** The records' Λ provenance cites "S10 spec 9.4", while the solver is §15 A2-1's. Fold the fix into a later
  records change, which will add its own lineage step. A4-3 keeps its own edit to one line, so that the reconstruction
  stays a single-line substitution.
- **N-6.** `S10_DECISIONS.md` B-25 still says "181 × 181" (superseded by A2-1's 1801²). This is log text only.
- **N-7.** The IDAES initializer's "Cannot load a SolverResults object with bad status" occurs with both solvers.
  MUMPS also reaches optimal in 3 attempts. These are capability results, not a harness defect.
- **N-8.** The VAL-3 and validation tests check self-consistency and regeneration. The closed-form cross-check
  (Δh = R T² d ln P^sat/dT, ≤ 5 × 10⁻¹⁰) exists only in the verdict. A one-point pin in `test_s10_validation.py` would
  make it executable. Optional.

## Rulings (brief §4)

**1. The I11 errata.** Spec §17 A4-1 (six replacements, with inline markers at each corrected line). R-720, plus an
erratum line under R-717. No rule, selection or verdict changes.

**2. The `uncertainty` string.** Edit and re-emit with the hash cascade, made self-certifying by
`records-lineage.json` and a reconstruction test. The tool records are not touched. The exact string and the
eight-step procedure are in spec §17 A4-3, and the decision is R-721. I rejected recording the status elsewhere: it
leaves the provider describing itself falsely.

**3. Closing with VAL-2 pending.** **Yes, S10 may close as `tested`** after S-1 to S-3. `tested` attests verification.
CLAUDE.md requires validation to be distinguished, not completed. VAL-2 is `insufficient_evidence: pending`, not
`BLOCKED`. The exact manifest validation block and the test-count wording are in spec §17 A4-4, and the decision is
R-721. VAL-2 later runs as WO-S10-7.

**4. Build decisions.**

| Decisions | Ruling |
| --- | --- |
| B-19, B-20, B-21, B-22, B-23, B-28, B-29 | Ratified. B-19: see N-4. B-22's CIAAW molar masses make RC-08 unresolved for an unused field; that is Frank's call under Q-F3, not a defect. |
| B-24 to B-27, B-31 | Already ratified or amended (A2-1, A2-2, A3-3). B-25's text: see N-6. |
| B-30, B-32, B-33, B-34 | Ratified. B-33 is §7.3's own rule. B-34's literal changes under A4-3 step 7. |
| B-35, B-38, B-39, B-46 | Ratified. A40's readbacks (≤ 10⁻¹⁵ on h^L) verify B-38 and B-39. B-46 computes the selection and A43 before any difference exists, and the tests recompute them. |
| B-36, B-37, B-40, B-41 | Already ruled (A3-5). |
| B-42 | Ratified, and written into the spec (A4-2.1). |
| B-43, B-44 | Ratified. They follow A41's own quantities. |
| B-45 | Ratified. The prediction is exactly ∝ ε², so the scaling is exact, not a bound. |
| B-50 to B-54 | Already ratified (A3-6). On the orchestrator's doubt, see below. |
| B-60, B-61 | Ratified. They follow A3-6. |
| B-62 | Ruled by the reference verdict. A4-3 step 6 makes its provenance executable, if the substitution reproduces `28676a25…`. |
| B-70, B-71, B-73 | Ruled by the validation verdict. |
| B-72 | Ratified. With v = 0 the pure-liquid h is independent of P, so evaluating at 101 325 Pa is exact. CPMOLAR(Q = 0) is the right EOS counterpart. |
| B-74 | Ratified. The skips are honest skips with an assertion body, not placeholder passes. |

**5. General review.**
- **The fit code against A2-1.** It matches:
  - the binary64 grid of products m × 0.005, its tie rule, and ln γ^exp rounded from 50 digits;
  - the minimum-norm step with the 10⁻⁴⁰ cutoff, the halving, and the step-taken stop;
  - a central-difference Hessian with h = 10⁻¹⁵;
  - the secant search on C, LAMBDA-V1 for the water binaries only, and Λ rounded to 10 digits.

  The only deviations are N-1 and S-5's vacuous claim.
- **The generator's real section** implements §9.7 and §16:
  - the mid-band rule with T_up = min(T_dew, T_dew^γ(z));
  - ENV on IDAES's dew;
  - SMOOTH-I and SMOOTH-I-KH, CVT-*, and IDAES-DEW-I7;
  - the mapping's c_p^L coefficients R(b_0 − c), R b_1/10³, R(b_2 − 6d)/10⁶, … (derived from (3.5): correct).

  Every claim raises on failure.
- **Blindness:** see S-3.
- **The tests.** A31 and A34 and the recompute tests are genuine. A33's claim-presence test is genuine as far as it
  goes; the one vacuous claim is S-5's. For VAL-3, see N-8.
- **The rights table against C12's standard:** see S-2.
- **`PACKAGED`:** see N-3. None.

## Where the orchestrator was least sure

**The single start and the second minimum.** The procedure is robust in the sense that matters for correctness. It
descends from the grid's best point, so it cannot adopt a minimum above it. It refuses rather than guesses (CONV, MIN,
BOX). On 79 perturbed data sets it never refused, and the worst case took 102 of 200 iterations. It is **not** robust in
the sense of giving stable methanol + ethanol Λ (S-4). No other solver would give stable Λ either: the instability is the
objective's. A future data set whose minimum lies on C may need more than 200 iterations, because Gauss–Newton is
sublinear where J has rank 1. That would be a refusal, and a later amendment would answer it with a Newton polish.

**B-50.** The settings were committed in the harness before the tool ran on a registered state. Each expresses the model
or forbids a substitution, and the readbacks to ≤ 1.1 × 10⁻¹⁴ are the strongest evidence that they do. They also cannot
bias any classification. Every two-phase quantity is `NOT_COMPARABLE` on DWSIM's own residual, which comes from the
hard-coded 10⁻⁶ stop and not from a setting. What remains are I6's and I7's phase identities, which are O(1) decisions.
I see no reason to reopen B-50.

## Not examined

- The IDAES and DWSIM runs themselves (not rerun, per the brief).
- `dwsim_runtime` and the tool scripts' model construction beyond A40's and A45's readback tests.
- The transcriptions, and the tolerances, which the specifier owns.
- The provider code, except through A34 and VAL-1, because WO-1 and WO-2 were reviewed separately.
- The comparison scripts' internals beyond what the tests recompute.

These verdicts are an agent's review. No human numerical or process-modelling sign-off is claimed, and `reviewed` is
not set.
