# ADR 0025 — Replay comparison under `T08-numerical-policy-v2`: classes by construction, floors from registered thresholds, pivot-path diagnostics recorded and not compared

**Status:** **Accepted, 2026-10-02**, with its Correction of 2026-10-02, with T08's tested evidence (`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`): A1–A15 (`tests/test_t08_adr0025.py`) pass at `C` on both CI architectures and here, and T08.A45 is met under `T08-numerical-policy-v2`. Frank's decisions: the go-ahead (2026-10-01); Q4, a record is compared under the policy it records and an unknown policy is refused (2026-10-02, R-147); the K05 identity re-registered for recording v2, substitution only (2026-10-02, R-148). Proposed 2026-10-02: effective when committed with its work order (§10). Register R-146, R-147, R-148.
**Date:** 2026-10-02
**Author:** design lane (`specifier`). Brief `docs/briefs/T08-G1-replay-policy.md` (Frank's go-ahead, 2026-10-01).
**Trigger:** `docs/reviews/T08-verdicts.md` finding G1; `docs/t08-rc-record.md` F2 — the aarch64 replay of the 52-bundle RC set at `C` = `814e151`: 31 `MATCH`, 21 `MISMATCH` (`ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json`, sha256 `d716f857…`).
**Amends:** ADR 0007 D1 and D2.2 for records made under the new id (five field groups, §4 D2–D6); D2.1's premise (§4 D7); D4 (one refusal condition, D1.3). The frozen schemas `run-manifest` and `solution-certificate` (`numerical_policy_id`: `const` → `enum`, additive). T08.A45.
**Does not amend:** `K04-numerical-policy-v1` — its text, its data and the comparator's behaviour under it are frozen with every result registered under it. ADR 0007 D2.4, D2.5, D3, D5, D6, and D4's mode rules.
**Affected requirements:** D20, D14, A08 (as ADR 0007); T08.A45. **Affected packages:** K05 (`run/compare.py`, `run/replay.py`, `run/session.py`), K04 (the certificate's recorded id), T08 (RC job, support envelope).

## 1. Authority and scope

This ADR decides how two documents recorded under `T08-numerical-policy-v2` are compared, and which policy a replay compares under. It applies in `exact_replay` and in `compatible_reproduction` alike: ADR 0007 D2.5 binds R1 and R2 to one policy, on the measurement that two same-class runners differ in the last bits, and one-ulp perturbations change pivot sequences on one machine (ADR 0007 Context 3). A v2 that applied only across architectures would be the tighter same-class rule D2.5 rejects. The same-class *mode* rules are unchanged.

It is the "new ADR" that ADR 0007's *Changing this ADR* requires for a new class and for new floor rows.

Out of scope: every registered comparison made under v1 (the K03, K04, T06 and T07 fixture tests keep v1, W5); the K04 tolerance table; everything else in T08.

## 2. Decision in one sentence

Records made from now on carry `T08-numerical-policy-v2`. It differs from v1 in three ways, each applying a rule ADR 0007 already states where the comparator did not apply it:

- a value derived from floating-point state is compared for shape;
- a float's floor is the threshold its own quantity registers;
- a float rendered inside text is compared as the float it is.

It also moves the LU pivot-path diagnostics to "recorded, not reproducible", beside `nnz_L` and `nnz_U`. A replay of a record made under any other policy is refused, never reinterpreted.

## 3. Context, and the order of work

The 21 `MISMATCH`es contain six kinds of difference. The counts are bundles, and one bundle can carry several kinds:

| Kind | Bundles | Detail |
| --- | --- | --- |
| `certificate_id` | 19 | the only difference in 12 |
| near-zero duty in `solution-state.json` | 5 | `U-FLASH.Q` ×3, `U-FL2.Q` ×2 |
| certificate `limitations[].value` | 2 | 6 values |
| `linear.u_diag_min_abs` | 2 | |
| a solve-event `message` containing a float | 3 | 9 messages |
| `level_constants_sha256` | 1 | 6 events |

The x86-64 fresh replay was 52/52.

**Integrity.** D1–D7 below were fixed from earlier decisions and noise models before they were applied to these 21: ADR 0007's D1 rule, its D2.2 floor principle and its Context 3; ADR 0010 D7.2; ADR 0018 D2; ADR 0004 D3.4; blueprint [A08]; T03 review S4; T04 review N7. §7 applies them afterwards. No floor or tolerance was taken from a difference in the 21.

## 4. Decision

### D1. Identity, recording, dispatch, labels

1. **The new policy.** Its id is `T08-numerical-policy-v2`. Its data are `benchmarks/t08/numerical_policy_v2.yaml` (content §8), emitted by `scripts/t08_numerical_policy.py`, which has a `--check` mode (A1). v1 stays at `benchmarks/k04/reference_values.yaml`, byte-unchanged.
2. **Recording.** Every run manifest and certificate written by a build carrying this ADR records `numerical_policy_id = "T08-numerical-policy-v2"`. The id has one source, `run.compare.CURRENT_POLICY_ID`; the literal default at `verify/certificate.py:337` goes. In `run-manifest.schema.json` and `solution-certificate.schema.json`, `numerical_policy_id` becomes `{"enum": ["K04-numerical-policy-v1", "T08-numerical-policy-v2"]}`. Every existing document still validates.
3. **Refusal (amends ADR 0007 D4).** The integrity check runs first, as now. Then, before any rerun is compared: if the bundle's recorded `numerical_policy_id` is not `CURRENT_POLICY_ID`, the mode is `inspected_archived_results` and the verdict `NOT_RUN`. The reason is `recorded under numerical policy '<recorded>'; this build records and compares under '<current>' (ADR 0025 D1): an old policy is refused, never reinterpreted`. ADR 0005, 0009, 0010, 0012, 0015 and 0018 refuse an old solve policy the same way, and T08.A35's v0.0.0 bundle is refused the same way.
4. **The comparator's interface.**
   - `run.compare.differences` takes a **required** keyword `policy_id`, with no default; under v2 it also takes `variable_kinds` (D5).
   - A comparison registered under v1 passes `policy_id="K04-numerical-policy-v1"`. Under v1 the comparator behaves bit for bit as at `814e151`. That includes the places where it is stricter than ADR 0007 as written: `certificate_id`, `level_constants_sha256`, limitation values, and `u_diag_min_abs`'s unapplied ratio floor (G1a, G1b).
   - Each of those can produce only a spurious `MISMATCH`, never a spurious `MATCH`, so freezing them costs no false pass.
5. **Labels (G1d).** A float difference reads `<path>: <emitted> against <committed>, outside T08-numerical-policy-v2 (1e-09 relative / <floor> absolute, <floor source>)`. The word "interim" is gone.

### D2. Digests, and identifiers built from digests

The rule is ADR 0007 D1 row 3, applied by construction: a value computed from an R1/R2 float — a hash with such a float in its preimage, or a string built from such a hash — is compared for shape only. Noise model: a digest changes when any bit of its preimage changes, so no tolerance applies.

1. **`level_constants_sha256` is a float digest.** ADR 0010 D7.2 already says so: "a hash over a parameter vector that contains a solved float `p⁰`". Its shape is 64 lowercase hex, `""` or null, and null on one side requires null on the other.
2. **`certificate_id` is classed by how it was built, read off the committed document.**
   - **Digest form.** The committed id equals `"cert-" + committed.target_state_sha256[:12]` (`verify/certificate.py:1147`). This is every revision route, because `_run_identity` sets `plan_id` after the id is built. The emitted id must then equal `"cert-" + emitted.target_state_sha256[:12]`, and the value is not compared otherwise.
   - **Any other form.** The plan form `cert-<plan_id>` (K05's registered runs) is compared exactly.
   - v1's exemption keyed on `plan_id == ""` tested a field unrelated to how the id is built (G1a).
3. **Every `sha256` name is classified.** Each property name in `schemas/*.json` that contains `sha256` is listed in v2's data as a float digest or as exact. A1 refuses to emit while any such name is unclassified. The comparator has now missed three float digests that were added after its list (`compare.py:59`'s comment; G1); a closed partition is what stops a fourth.

### D3. Certificate limitation values

A `limitations[]` entry of kind `near_threshold` is a copy of one `CheckResult`: `{check: check.id, value: check.value, threshold: check.tolerance}` (`verify/certificate.py:265`).

- Its `value` is floored at its sibling `threshold`, which is that check's own tolerance. This is ADR 0007 D2.2's row for "any certificate `CheckResult.value`", applied to the copy as it already is to the original, `checks[].value`.
- `check` and `kind` are compared exactly. `threshold` is compared relative-only, as before.

Noise model: a residual check value is a difference of larger terms. Its round-off is about ε·Σ|terms|, whatever its own size, so a relative rule or a zero floor on it compares noise.

### D4. LU pivot-path diagnostics: recorded, not reproducible

1. **The class.** `linear.u_diag_min_abs` and `linear.u_diag_max_abs` (on solve events) and `regularity.u_diagonal_ratio` (on the certificate) move from R1/R2 to ADR 0007 D1's "recorded, not reproducible", beside `nnz_L` and `nnz_U`. They are checked for kind only:
   - each is a number (not a boolean), finite, and ≥ 0;
   - on one `linear` object, the emitted `u_diag_min_abs ≤ u_diag_max_abs`;
   - `u_diagonal_ratio ≤ 1`;
   - null on one side requires null on the other.
2. **Why, independent of this run.**
   - `splu` runs with `diag_pivot_thresh = 1` (ADR 0004 D1). The pivot in each column is the entry of largest magnitude, which is a floating-point comparison.
   - U — its pattern and its diagonal — is a function of that pivot sequence, not of the matrix alone.
   - ADR 0007 Context 3 measured the sequence changing under one-ulp perturbations on one machine: nine perturbations gave six distinct `nnz(L)` sequences. On that ground ADR 0007 took `nnz_L` and `nnz_U` out of the comparison. The diagonal of the same U has the same dependence and was left in.
   - D2.1's premise, 2.2e-14 relative on `u_diag_min_abs`, was a sample at states where the two pivot sequences happened to coincide.
   - Blueprint [A08] and ADR 0004 D3.4 already call the U diagonal "an inexpensive warning screen, not a rank-revealing test or a condition-number estimate". No tolerance bounds a change of pivot order, so a tolerance chosen here would be fitted to whatever run it was chosen on.
3. **What is compared instead.** The pivot-independent statements, all unchanged from v1:
   - each solve's `linear.residual_normalized` under its 1e-12 floor — a backward error, small for any stable pivot order (ADR 0004 D3.2);
   - the certificate's regularity `status` (R0, conditional on D2.4);
   - `rcond_1`, `one_norm` and `inverse_one_norm_estimate` under their D2.2 floors;
   - the SVD escalation's rank and singular values, where it ran.

   These are properties of the matrix. The U diagonal is a property of one factorization of it.

### D5. Solution-state variables and phase-branch flows

1. **Solution-state variables.** The floor of `solution-state.json` `variables.<id>` is `τ_kind` of the variable's **declared quantity kind**. `τ_kind` is ADR 0001 D6's acceptance rule `a + r·s`: the `KIND_TOLERANCE` map the region applies to rows (`orchestrator/region.py:162`), and the one ADR 0018 D2 already applies to columns.

   | Kind | a | r | s | Floor `τ_kind` |
   | --- | --- | --- | --- | --- |
   | `molar_flow` | 1e-9 mol/s | 1e-8 | 3 mol/s | 3.1e-8 mol/s |
   | `molar_flow_squared` | 3e-9 (mol/s)² | 1e-8 | 9 (mol/s)² | 9.3e-8 (mol/s)² |
   | `heat_rate` | 1e-5 W | 1e-8 | 1e5 W | 1.01e-3 W |
   | `temperature` | 1e-6 K | 0 | — | 1e-6 K |
   | `pressure` | 1e-2 Pa | 0 | — | 1e-2 Pa |

   - **A kind not in the table** (for example `dimensionless`, `work`, `pressure_drop`) is compared relative-only (floor 0), as v1 compares every unregistered float.
   - **Where the kinds come from.** The caller supplies them from the compiled problem it solved (`ProblemSpec.variable_kinds`). They are never inferred from a variable's name.
   - **Without them.** Comparing a `solution-state-v1` document under v2 without the kinds is itself a difference: `variables: declared kinds not supplied; T08-numerical-policy-v2 does not compare a solution state without them (ADR 0025 D5)`. A missing kind map fails; it never falls back to a default.
2. **Phase-branch flows.** In the certificate's `phase_branch.<key>` objects, `liquid[i]`, `vapor[i]`, `liquid_total` and `vapor_total` are molar flows in mol/s; their floor is 3.1e-8 mol/s. The phase labels (`"FLOWING"`, …) are R0 strings, compared exactly.
3. **Why τ_kind, independent of this run.**
   - **It is the threshold the quantity registers.** ADR 0007 D2.2's rule is that "the floor of a path is that threshold, and nothing else". The solver accepts a state whose rows of a kind are within `τ_kind`, and a duty or a flow enters its balance row with unit coefficient. So the converged value itself is determined only to `τ_kind`.
   - **It sits above the round-off bound.** K04 §7.4's absolute limit admits a certificate only when `n ε ‖Ĵ⁻¹‖₁ ≤ τ̂_min = 1e-8`. For every certificate inside that limit, the round-off-driven state difference is therefore ≤ τ̂_min in scaled units, which is ≤ `τ̂_min·s_kind ≤ τ_kind` in units.
   - **Measured on the RC set's 49 certificates,** the worst `n ε ‖Ĵ⁻¹‖₁ / τ̂_min` is 1.33e-3 (`SYN-001-T06-NET03`: n = 79, estimate 758.75 against its limit 5.70e5). That is read from the certificates' recorded regularity, not from any replay result. There, the floor is ≥ 750 times the bound.
   - **Below it, the solver's own acceptance cannot tell two values apart.** T06's S3 and ADR 0018 D2 judge a state in multiples of `τ_kind`.
   - **The relative part still applies.** 1e-9 relative governs every variable with |q| > `τ_kind`/1e-9.

### D6. Floats rendered inside text

1. **Scope.** The string value of every key named `message` or `cause`, at any depth, in any artifact: solve-event messages and the certificate's `branch_provenance[].cause`. Every other string is compared exactly, as before.
2. **Tokens.** A float token is a match of

       (?<![\w.+-])-?(?:\d+\.\d+(?:e[-+]\d+)?|\d+e[-+]\d+)(?![\w.])

   These are the forms Python's `repr` and `str` give a finite float — a decimal point, or an exponent with its sign — when the number is not glued to a word character, a point or a sign. Integers, `inf`, `nan`, identifiers, hex digests and version strings are not tokens. §8 registers ten example strings and their token lists, and A1 checks the pattern against them.
3. **Comparison.** The **template** is the string with every token replaced by `<f>`.
   - Templates are compared exactly. That is the R0 part: which branch spoke, which bound, which unit, which integer count.
   - Tokens are compared pairwise, in order, under D2.1 with floor 0, i.e. relative only.
4. **Why, independent of this run.**
   - ADR 0007 D1 assigns classes "by rule, not by enumeration". By its rule a string is R0 only when no floating-point value lies on its path.
   - A provider's domain message (`thermo/syn001.py:333`, `temperature {T!r} K outside [280.0, 440.0] K`) carries an R1/R2 trial value. So does ADR 0018 D5's project-authored `chord <ρ!r>`.
   - T03 review S4 (2026-09-24) identified the mechanism: a float in a string compared byte for byte is a false structural `MISMATCH` across the CI pair. T04 review N7 handed the inherited strings to ADR 0007, where they were never ruled.
   - A token is the rendered value of its float and carries that float's noise model, ε·κ̂ relative.
   - Its floor is 0 because the text gives it no kind. A near-zero float in a message therefore still mismatches, which is the visible direction.

### D7. Everything else is v1, and D2.1's premise restated

**Unchanged from v1:**

- the relative tolerance, 1e-9;
- `near_threshold_margin`, 10, and D2.4's treatment of verdict drift;
- every v1 floor row except the two `u_diag` rows;
- `checks[].value` and `escalation.sigma_min`, floored at their sibling `tolerance`;
- the `kappa_2` and `gamma_inf` comparability windows;
- the five counts;
- the root-anchored provenance and volatile keys;
- exact comparison of every other leaf, key set and list length.

**D2.1's premise, restated (amends ADR 0007).** The relative 1e-9 no longer rests on `u_diag_min_abs` (see D4). It rests on three things:

- ADR 0007 Context 2: 1–3 ulps on continuous quantities across the CI pair;
- ADR 0009 D3 as amended: ≤ 3.3e-13 inside the window;
- the noise model ε·κ̂ with κ̂ = 1/`rcond_1`. At the RC set, κ̂ ≤ 1/6.33e-5 = 1.6e4 (`SYN-001-T06-NET02`), so ε·κ̂ ≤ 3.5e-12, 2.5 decades inside 1e-9.

## 5. The comparison table (`T08-numerical-policy-v2`)

The rows are tried in order and the first match wins. "D2.1" means `|q − q'| ≤ max(1e-9·max(|q|,|q'|), floor)`. Null on one side must be null on the other for every float row.

| # | Path | Class | Compared how | Floor | Source | Against v1 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | root keys `environment`, `recorded_environment`, `current_environment`, `run_id`, `started_at`, `elapsed_seconds`, `hostname`, `parent_run_id`, `artifacts`, `manifest_sha256` | excluded | type only | — | ADR 0007 D1 row 5 | same |
| 2 | `property_calls`, `requested_evaluations`, `cache_hits`, `nnz_L`, `nnz_U` | count | int ≥ 0 | — | ADR 0007 D1 row 4 | same |
| 3 | `u_diag_min_abs`, `u_diag_max_abs`, `u_diagonal_ratio` | post-pivoting | D4.1 kind checks | — | D4 | **new class** |
| 4 | `state_sha256`, any key ending `state_sha256`, `level_constants_sha256` | float digest | 64 lowercase hex, `""` or null | — | ADR 0007 D1 row 3; ADR 0008 D2.1; ADR 0010 D7.2 | `level_constants_sha256` **new** |
| 5 | `certificate_id` | derived identifier | D2.2 | — | D2 | **changed** |
| 6 | `residual_inf_scaled` (window selector) | scope | number or null | — | ADR 0007 D2.2 | same |
| 7 | `kappa_2`, `gamma_inf` | R1/R2 in window | D2.1 where committed selector ≥ 1e-4, else number-or-null with matching nullness | 0 | ADR 0009 D3 | same |
| 8 | `message`, `cause` (string on both sides) | text with floats | template exact; tokens D2.1 | 0 | D6 | **new** |
| 9 | `limitations[i].value` where `limitations[i].kind == "near_threshold"` | R1/R2 | D2.1 | sibling `threshold` | D3 | **new** (v1: 0) |
| 10 | `value`, `sigma_min` with a numeric sibling `tolerance` | R1/R2 | D2.1 | sibling `tolerance` | ADR 0007 D2.2 | same |
| 11 | `solution-state.json` `variables.<id>` | R1/R2 | D2.1 | `τ_kind` of the declared kind (D5 table), else 0 | D5 | **new** (v1: 0) |
| 12 | `phase_branch.<key>.{liquid[i], vapor[i], liquid_total, vapor_total}` | R1/R2 | D2.1 | 3.1e-8 | D5 | **new** (v1: 0) |
| 13 | key `residual_inf_unscaled` / `merit` / `witness_max_diff` / `step_inf_scaled` / `residual_normalized` / `eta` / `constant_mismatch` / `rcond_1` / `solution_error_bound_scaled` / `inverse_one_norm_estimate` | R1/R2 | D2.1 | 3.10000e-8 / 5.33889e-17 / 1e-7 / 1.03333e-8 / 1e-12 / 1e-10 / 1e-2 / 1e-14 / 1.00e-8 / 0 | ADR 0007 D2.2 (v1 data, verbatim) | same (rows `u_diag_*` removed) |
| 14 | any other float | R1/R2 | D2.1 | 0 | ADR 0007 D2.3 | same |
| 15 | any other leaf; key sets; list lengths | R0 | exact | — | ADR 0007 D1 row 1 | same |

## 6. Alternatives rejected

- **Editing v1 in place.** It would change the meaning of every result registered under v1 (ADR 0007 D2.6; the brief).
- **v2 only in `compatible_reproduction`.** That is a tighter same-class rule, which ADR 0007 D2.5 rejects on measurement. Pivot changes also occur on one machine (Context 3).
- **Making the revision `certificate_id` R0 (plan-derived).** Two certificates of one plan at different states — ensemble starts, warm starts — would share an id. It also changes certificate identity, a frozen interface, and adds no check that D2.2's self-consistency rule lacks.
- **An ε-model floor for the state (c·ε·κ̂·s).** That is an invented floor: κ̂ moves with the state, so the floor would be a tolerance chosen per run. ADR 0007 D2.2 rejects floors that are not registered thresholds.
- **`τ̂_min · S_j` from the plan's column scales.** A variable computed outside an EO plan has no column scale, whereas the kinds cover every variable.
- **Comparing the U-diagonal screen decision (ratio < 1e-10).** The decision is not recorded on the event (finding F2) and is computed on the same pivot path. The cross-platform statement about conditioning is the regularity evidence, which stays compared.
- **A loose tolerance on `u_diag_*` (for example 50 % relative).** No tolerance bounds a pivot-order change; any number would be fitted to the run that produced it.
- **Messages exact (D1's enumeration).** The enumeration loses to D1's rule (D6.4).
- **Float-free messages at the producer (T03 S4's remedy).** Inherited texts come from providers and backends, and a structured field means a solve-event schema change. The template rule gives the same R0 protection. Recommended for project grammars later (Q2).
- **Comparing tokens for shape only.** That would drop an R1/R2 quantity to which D2.1 applies.
- **Re-judging the `814e151` bundles under v2.** That reinterprets a recorded policy (D1.3).
- **Fixing v1's three under-implementations in place.** It would change v1 outcomes after a verdict judged under v1 had been recorded. The defects err only toward `MISMATCH`.

## 7. The 21, judged under v2 after D1–D7 were fixed

This is a counterfactual. The 21 bundles recorded v1, so D1.3 refuses them, and **A45's FAIL at `814e151` stands**. The table says what v2 would decide about the same differences between two v2 records.

"Margin" is the largest |Δ| divided by the v2 tolerance on that path.

| Bundle | Differences recorded under v1 | Rule under v2 | v2 |
| --- | --- | --- | --- |
| `k05/SYN-001-high-recycle` | `u_diag_min_abs` 0.0448 / 0.0732 | D4 (kind) | MATCH |
| `g8/…-T06-NET02` | id; 3 limitation values | D2.2; D3, margin 1.15e-7 | MATCH |
| `g8/…-T06-NET03` | id; `U-FL2.Q` −3.97e-11 / 1.11e-11 W; `u_diag_min_abs` | D2.2; D5, |Δ| = 5.1e-11 W, margin 5.0e-8; D4 | MATCH |
| `g8/…-T06-NET10` | id; `U-FL2.Q` 2.67e-11 / 2.24e-12 W | D2.2; D5, margin 2.4e-8 | MATCH |
| `g8/…-A02-352-vapor-guess-410` | 4 messages; 6 `level_constants_sha256` | D6, tokens ≤ 2.2e-15 relative, margin 2.2e-6; D2.1 | MATCH |
| `g8/…-A02-360-liquid-guess` | id; 3 limitation values; `U-FLASH.Q` 1.6e-16 / −4.5e-15 W | D2.2; D3, margin 4.8e-9; D5, margin 4.6e-12 | MATCH |
| `g8/…-A02-360-vapor-guess` | id; `U-FLASH.Q` 3.8e-18 / 8.3e-19 W; 4 messages | D2.2; D5; D6 | MATCH |
| `g8/…-A02-360` | id; `U-FLASH.Q` −1.1e-16 / 3.9e-17 W | D2.2; D5 | MATCH |
| `g8/SYN-001-high-recycle` | id; 1 message, 576.9372132792676 / …677 | D2.2; D6 | MATCH |
| `g8/` NET09, NET11, STA03-degC, STA03-kgs, A02-340-two-phase-guess, A02-355-dew-guess-377, A02-355-dew-guess, A02-355-liquid-guess, A02-355, A02-365, all-liquid-310K, nominal (12) | id only | D2.2 | MATCH |

**None of the 21 would still fail.** That outcome was not a target:

- D2, D3, D5 and D6 are earlier decisions applied where the comparator had not applied them: ADR 0007's D1 rule and D2.2 floor principle, ADR 0010's digest class, ADR 0018's column `τ_kind`.
- D4 applies ADR 0007 Context 3 to the quantity that Context left in the comparison.

**Under v2, still fails:**

- a state variable apart by more than max(1e-9 relative, its `τ_kind`);
- any verdict, status or `result` word that moved with no near-threshold flag;
- a changed message template, or a token apart by more than 1e-9 relative;
- a plan-form id;
- any structural field.

The A14 controls exercise the first two of these in the RC job itself.

**One limit of this table.** The record lists only what v1 flagged. v2 adds one check v1 did not make: the self-consistency of a digest-form id. The code builds every such id that way (`certificate.py:1147`), but that cannot be confirmed from the record, which does not carry the emitted digests.

## 8. The policy file (content `scripts/t08_numerical_policy.py` emits)

`benchmarks/t08/numerical_policy_v2.yaml`, one top-level key `numerical_policy`:

| Key | Content |
| --- | --- |
| `id` | `T08-numerical-policy-v2` |
| `adr` | `ADR 0025` |
| `relative`, `near_threshold_margin`, `comparability_windows`, `exact_fields`, `unreproducible_counts` | v1's values, verbatim (read from `benchmarks/k04/reference_values.yaml`) |
| `floors` | v1's `floors` mapping, verbatim, **without** `u_diag_min_abs` and `u_diag_max_abs` |
| `self_floored` | `{value: tolerance, sigma_min: tolerance}` |
| `limitation_floors` | `{near_threshold: {value: threshold}}` |
| `post_pivoting_floats` | `[u_diag_min_abs, u_diag_max_abs, u_diagonal_ratio]` |
| `float_digests` | `names: [state_sha256, full_state_sha256, target_state_sha256, opening_state_sha256, level_constants_sha256]`, `suffix: state_sha256` |
| `exact_sha256` | every other `sha256`-bearing property name in `schemas/*.json`, sorted (at this ADR: `artifact_r0_sha256, check_policy_sha256, constants_sha256, content_sha256, lock_sha256, manifest_sha256, policy_sha256, request_sha256, revision_content_sha256, sha256, stdout_sha256, structural_sha256, token_sha256, variable_ids_sha256`) |
| `derived_identifiers` | `certificate_id: {digest_form: "cert- + target_state_sha256[:12]", digest_form_rule: "emitted equals its own digest form", other_forms: exact}` |
| `kind_floors` | the D5 table: per kind `{floor, a, r, s, why: "ADR 0001 D6 a + r*s; KIND_TOLERANCE"}` |
| `kind_floor_paths` | `{solution_state_variables: declared_kind, phase_branch_flows: molar_flow}` |
| `text_with_floats` | `keys: [message, cause]`, `token:` the D6.2 pattern, `token_floor: '0'`, and `examples:` the ten pairs below |

The registered token examples, each a string and its token list:

1. `H_S3_vapor: H_S3_vapor: temperature 52.11447523132472 K outside [280.0, 440.0] K` → `[52.11447523132472, 280.0, 440.0]`
2. `FSR1-e3f2d5372330-syn001-67e472816d4d-44f894ff62f9-T06-revision-v2-execution` → `[]`
3. `no trial accepted in 21 steps from alpha = 0.0009765625` → `[0.0009765625]`
4. `the attempt controller closed the attempt: a persistent phase wall, not an overshoot (§4.6)` → `[4.6]`
5. `hash 8e70 and 1e-05 and -4.530826668708299e-15 and 1e+16` → `[1e-05, -4.530826668708299e-15, 1e+16]`
6. `S3.T at U-FL2 SciPy 1.15.3` → `[]`
7. `x-1.5 and (-2.5)` → `[-2.5]`
8. `terminal_refinement(accepted): chord 0.5 at S3.T` → `[0.5]`
9. `value inf and nan` → `[]`
10. `P_in - dP = 99000.0 Pa outside [1000.0, 10000000.0] Pa` → `[99000.0, 1000.0, 10000000.0]`

These were run against the pattern while this ADR was written.

## 9. Acceptance evidence — numbered assertions

The comparator cases in A4–A11 test presence or absence of a difference, exactly; there is no numeric tolerance to argue. Every "none" pair sits ≥ 10× inside its v2 tolerance and every "difference" pair ≥ 10× outside it, so no outcome depends on how `max(rel·|q|, floor)` or its operands round. A difference is asserted by its path; the label is A13's.

| ID | Assertion | Expected |
| --- | --- | --- |
| **A1** | `python scripts/t08_numerical_policy.py --check` | Exit 0; byte-identical output. The generator refuses to emit unless: (a) each `kind_floors.floor` equals `a + r·s` computed in the script **and** equals both `verify.checks.KIND_TOLERANCE` and `orchestrator.region.KIND_TOLERANCE` (exact float equality); (b) each carried v1 entry equals v1's (exact), and v1 has no `floors` key that v2 lacks other than the two `u_diag` rows; (c) the pattern yields exactly §8's ten token lists; (d) `float_digests.names ∪ exact_sha256` equals the set of `sha256`-bearing property names in `schemas/*.json`, with the two disjoint. |
| **A2** | K04 A32's enumeration of schema float fields, parameterized over both policies | Under v2, extended to `solution-state.schema.json` `variables` and the certificate's `phase_branch` flows: every float field is classified (rows 2–14). Under v1: unchanged. |
| **A3** | Dispatch and refusal | (a) A bundle whose manifest records v1, replayed by this build with a rerun: `inspected_archived_results`, `NOT_RUN`, a reason containing `recorded under numerical policy 'K04-numerical-policy-v1'`, and `differences` empty. (b) The same bundle re-sealed with v2: compared, mode per ADR 0007 D4. (c) `differences(a, b)` with no `policy_id`: `TypeError`. |
| **A4** | `certificate_id` under v2. Fixtures: two certificates, `plan_id` non-empty, target digests t1 ≠ t2. | (a) ids `cert-t1[:12]` / `cert-t2[:12]` → none. (b) emitted id `cert-t1[:12]` with emitted target t2 → difference. (c) plan-form ids one character apart → difference. (d) committed digest form, emitted plan form → difference. (e) Under **v1**, case (a) → difference (v1 frozen, G1a). |
| **A5** | `level_constants_sha256` | Two distinct 64-hex values → none; `"XYZ"` → difference; null/null → none; null/hex → difference. |
| **A6** | Limitation values, `threshold` 1.01e-3 | The F2 pair −4.4157060619909316e-4 / −4.4157064985483885e-4 → none; 4.0e-4 / 4.0e-4 + 1.01e-2 → difference; `check` id changed → difference. |
| **A7** | Solution state, kinds `{U-FLASH.Q: heat_rate, S3.T: temperature, S3.n.A: molar_flow, S3.P: pressure, X.eff: dimensionless}` | (a) F2 pair `U-FLASH.Q` 1.6328084717631697e-16 / −4.530826668708299e-15 → none. (b) 0.0 / 1.01e-2 → difference. (c) `S3.T` 360 / 360 + 1e-7 → none; 360 / 360 + 1e-5 → difference. (d) `S3.n.A` 1 / 1 + 3.1e-9 → none; 1 / 1 + 3.1e-7 → difference. (e) `S3.P` 1e5 / 1e5 + 1e-3 → none; 1e5 / 1e5 + 1e-1 → difference. (f) `X.eff` 0.75 / 0.75·(1 + 1e-11) → none; 0.75 / 0.75·(1 + 1e-7) → difference. (g) kinds not supplied → exactly one difference, matching `declared kinds not supplied`. (h) a variable absent from the emitted map → difference. |
| **A8** | Phase-branch flows | `vapor_total` 0 / 1e-17 → none; 0 / 3.1e-7 → difference; label `FLOWING` / `ZERO_FLOW` → difference. |
| **A9** | Post-pivoting | F2 pair `u_diag_min_abs` 0.04477807556912964 / 0.0731916085271539 → none. Each → difference: emitted −1.0; NaN; `"0.1"`; `true`; emitted min 2.0 with max 1.0; `u_diagonal_ratio` 1.5; null / 0.1. |
| **A10** | Messages | F2 pair (`…52.11447523132472 K…` / `…52.114475231324604 K…`) → none. Each → difference: a token × (1 + 1e-6); `outside` → `inside`; one extra token; two plan ids one hex digit apart; `21 steps` / `22 steps`; `(§4.6)` / `(§4.7)`; `-0.5` / `0.5`. |
| **A11** | Carried rows are not vacuous | `residual_normalized` 1e-13 / 5e-13 → none, 1e-10 / 2e-10 → difference; `merit` 1e-18 / 2e-18 → none, 1e-10 / 2e-10 → difference; `step_inf_scaled` 1e-10 / 5e-10 → none, 0.5 / 0.6 → difference; `checks[].value` with `tolerance` 3.1e-8: 0 / 3.1e-9 → none, 0 / 3.1e-7 → difference; `rcond_1` 1.33e-4 / 1.33e-4·(1 + 1e-11) → none, 1.33e-4 / 1.5e-4 → difference. |
| **A12** | v1 is frozen | (a) Every comparator test present at `814e151` passes with only `policy_id="K04-numerical-policy-v1"` added; no expected value changes. (b) The F2 pairs — NET03's three, A02-352's message and `level_constants_sha256`, NET02's limitation triple — transcribed from `docs/t08-rc-record.md` F2: under v1 each yields the difference F2 records; under v2 none does. |
| **A13** | Labels | No difference text contains `interim`. Every float difference text contains the policy id and the floor value used. |
| **A14** | RC controls (CI, both replay runners) | Copies of RC bundles, mutated, then re-sealed with the project's own writers so `integrity_ok` is true (asserted first: a control that fails integrity tests the integrity check, not the comparator). **C1:** in `g8/SYN-001-nominal`, the first `heat_rate` variable of `solution-state.json` (in `variable_ids` order) moved by 10× its v2 tolerance → `MISMATCH` naming that path. **C2:** the same bundle's certificate `verification_status` set to `FAILED` (precondition: no near-threshold limitation) → `MISMATCH` naming it. **C3:** `k05/SYN-001-high-recycle` with one event's archived `u_diag_min_abs` × 0.6 → `MATCH`. C3 is the deliberate, visible blind spot of D4. |
| **A15** | Recording | A run by this build writes `numerical_policy_id = T08-numerical-policy-v2` in its run manifest and certificate. Both schemas accept v1 and v2 and reject `K04-numerical-policy-v3`. |

## 10. Build-lane work order

The design lane reviews W2–W4 before merge: they touch replay identity.

- **W1 — Policy data.** Write `scripts/t08_numerical_policy.py`, which emits §8's file and has `--check` (A1). Add `benchmarks/t08/numerical_policy_v2.yaml` to `resources.PACKAGED`, with the `_data` symlink and the `pyproject.toml` package data; T08.A43 then covers its bytes.
- **W2 — `run/compare.py`.**
  - Load both policies by id.
  - Make `policy_id` a required keyword of `differences`; add `variable_kinds`.
  - Leave the v1 path bit-identical (A12).
  - Implement rows 1–15 under v2, and D1.5's labels.
  - Add `CURRENT_POLICY_ID = "T08-numerical-policy-v2"`; `POLICY_ID` stays as its alias.
- **W3 — Recording and schemas.**
  - `run/session.py`, `application/revision_run.py` and `verify/certificate.py` take the id from `CURRENT_POLICY_ID`; delete the literal default.
  - Change the two schemas' `const` to `enum` (D1.2).
  - Add a T08/ADR 0025 note to `docs/interfaces-frozen.md` in the style of the T03/T04 notes (A15).
- **W4 — `run/replay.py`.**
  - Add the D1.3 refusal.
  - Add `Rerun.variable_kinds`. The code that reruns supplies it from the compiled problem it solved (`ProblemSpec.variable_kinds`, unioned over plan steps). A variable given two kinds is a defect: raise.
  - Pass the kinds when comparing `solution-state.json` (A3, A7g).
- **W5 — Existing call sites.**
  - Every other `differences(` call passes `policy_id="K04-numerical-policy-v1"`; registered comparisons keep v1.
  - A committed regression fixture whose regenerated document now differs **only** in `numerical_policy_id` is updated in that one field, in the same commit. Any other new difference is a defect, reported to the design lane.
  - Never edit fixtures recorded at another tag or by an agent run (`tests/fixtures/t08/v0.0.0-*`, `benchmarks/t07/v17/runs/**`).
  - K05 tests that build v1 manifests and expect a comparison build v2 manifests.
- **W6 — Tests.** Add `tests/test_t08_adr0025.py` for A2–A13 and A15, and parameterize K04 A32 (A2).
- **W7 — RC script.** In `scripts/t08_rc.py` `bundles-replay`: supply kinds; record each replay's `numerical_policy_id`; run A14's controls on both runners; check that each bundle records v2.
- **W8 — Envelope.**
  - `benchmarks/t08/support_envelope.yaml`, `reproducibility.statement`: replace "floats within `K04-numerical-policy-v1`" with "floats within the numerical policy each record names (`T08-numerical-policy-v2` for v0.1 records, ADR 0025)", and add `doc:docs/adr/0025-cross-platform-replay-comparison.md` to its evidence.
  - L07 `text`: append "LU pivot-path diagnostics (`u_diag_min_abs`, `u_diag_max_abs`, `u_diagonal_ratio`, `nnz_L`, `nnz_U`) are recorded and not compared across platforms (ADR 0025 D4)." Closes G1e.
- **W9 — Then.** Apply R-146 (§15). Cut a new `C` and run the RC job. A45 is re-judged by the verdict lane. The build lane does not call it.

Already written in this pass, uncommitted: ADR 0007's Amendment 1, and the release spec's Amendment R4 with the A45 row.

## 11. Migration impact

- **Schemas.** Two `const` → `enum` changes, additive. A design-lane ADR is required for a frozen interface (CLAUDE.md); this is it.
- **New records.** Run manifests and certificates now record v2. Regression fixtures change in that one field only (W5).
- **Records made under v1** — the 52 at `814e151`, every RC bundle before this change, and K05's archived examples — are refused at replay (`NOT_RUN`). Their recorded verdicts stand.
- **Not expected to change:** T08.A42's identity document (it carries no policy id; checked on `814e151`'s `identity.json`), A49's served digest, and B50's digests. A change there is a finding, not part of this migration.
- **Cost:** one new `C` and one RC job.

## 12. What this ADR does not establish

- **That A45 passes at a new `C`.** Only the run can show that. §7 is a counterfactual on v1 records.
- **That 1e-9 relative holds beyond the conditioning range measured.** The range is κ̂ ≤ 1.6e4 at the RC set. A case inside D2.4's band is re-registered; the rule is not relaxed.
- **That `inverse_one_norm_estimate` and `rcond_1` are free of path dependence across platforms** (Q1).
- **That every float in every text is found.** A float rendered with neither a point nor a signed exponent stays in the exact template.
- **That a `near_threshold` flag at the edge of D2.4's band cannot flip across platforms.** Such a flip changes the `limitations` list length, which is a `MISMATCH`.
  - In the RC set, the flagged value nearest an edge is 0.122 of its threshold (NET02, `PHF-equilibrium:A`), 22 % from the 0.1 edge.
  - The largest cross-platform change measured on a flagged value is 9.4e-7 relative.
  - The check values that are *not* flagged were not surveyed.
- **Bitwise reproduction** (ADR 0007 F1), **per-start ensemble agreement across classes** (L07), or **any third platform**.
- **Any validation.** This is numerical reproducibility of a solve, not correctness of the model.

## 13. Open questions, with recommended defaults

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Can Hager's 1-norm estimator take a different path on the other architecture? | needs a fact: for the RC set, the exact `‖Ĵ⁻¹‖₁` (dense, n ≤ 79) against the recorded estimate, on both classes | Keep both quantities R1/R2 under their v1 floors. A difference becomes a new ADR, never a relaxed floor. |
| Q2 | Should project-authored grammars (ADR 0018 D5's `chord <ρ!r>`, ADR 0005's) become float-free, as T03 S4 did for T03's? | needs the user's preference (a schema touch) | Yes, at the next solve-event schema change. Inherited texts keep D6. |
| Q3 | Is a variable of a kind outside the D5 table near zero in a registered bundle? | needs a fact: list the relative-only variables of the RC set with \|q\| < 1e-6 | Relative only. A resulting `MISMATCH` stands, and is cured by registering that kind's acceptance rule (ADR 0001 D6 style), never by a comparator floor. |
| Q4 | Refuse v1 records at replay, or compare them under v1? | needs the user's preference | Refuse (D1.3), on the "never reinterpreted" precedent. |

## 14. Findings (recorded, not acted on here)

- **F1 — Frozen schemas.** The frozen schemas pin `numerical_policy_id` as `const`, so any new policy needs this ADR's schema change (D1.2). It is made by this ADR, not silently.
- **F2 — `linear_suspect` is not recorded.** ADR 0004 D3.4 says a small-pivot event "is flagged `linear_suspect`". The flag is computed (`numerics/linear.py:224`) but not recorded on the solve event. This ADR does not depend on it (D4.3); ADR 0004 should either record it or drop the sentence.
- **F3 — A second literal of the policy id.** `verify/certificate.py:337` carries a second literal copy of the id. W3 removes it.
- **F4 — The envelope's reproducibility axis (G1e)** is contradicted at `814e151` for v1. W8 fixes it at the next `C`.

## 15. Register entry (text, applied with the commit)

**R-146 — Replay comparison policy `T08-numerical-policy-v2` (ADR 0025); records of another policy are refused at replay.**

| | |
| --- | --- |
| Date | 2026-10-02 |
| Decided by | design lane (ADR 0025, Proposed); brief `docs/briefs/T08-G1-replay-policy.md`, Frank's go-ahead 2026-10-01 |
| Normative text | `docs/adr/0025-cross-platform-replay-comparison.md`; ADR 0007 Amendment 1; T08 release spec Amendment R4 (A45) |
| Evidence | `docs/reviews/T08-verdicts.md` G1; `docs/t08-rc-record.md` F2 |
| Affected packages | K05, K04, T08 |

**Decision.** New records carry `T08-numerical-policy-v2`. It does four things:

- compares float-derived digests and ids for shape: `certificate_id` by how it was built, and `level_constants_sha256`;
- floors certificate limitation values at their thresholds, solution-state variables at their kind's `τ_kind`, and phase-branch flows at the molar-flow `τ`;
- compares message templates exactly and the floats inside them relatively;
- moves `u_diag_min_abs`, `u_diag_max_abs` and `u_diagonal_ratio` to "recorded, not reproducible".

Records made under v1 are refused at replay. v1 is frozen with its results.

**Rejected alternatives, and why.**

- Editing v1 in place: it changes registered results.
- A cross-architecture-only policy: ADR 0007 D2.5.
- A loose tolerance on the pivot diagnostics: it would be fitted to one run.
- Exact messages: D1's rule loses to its own enumeration otherwise.
- A plan-derived R0 certificate id: identity collision across starts.
- Re-judging the `814e151` bundles under v2.

**Watch for.**

- A new float-derived hash that is not in `float_digests`; A1 refuses it.
- A tolerance on `u_diag_*` reintroduced.
- A solution state compared without declared kinds.
- A v1 record compared under v2.

## Frank's answer to Q4 (2026-10-02) — D1.3 replaced

Frank chose **"compare under the old policy"**: a bundle recorded under another numerical policy is replayed and
compared **under the policy it records** (for v0.1's existing bundles, `K04-numerical-policy-v1`, whose code path stays
bit-identical — W2, A12), not refused. Reason: v1's known defects only ever produce false MISMATCHes, never false
MATCHes, so judging a record by its own policy is safe, and every committed bundle stays replayable. This replaces
D1.3's refusal and W4's "D1.3 refusal" item; a record naming a policy the code does not know is still refused
(`inspected_archived_results` / `NOT_RUN`, reason naming the unknown id). A45's FAIL at `814e151` stands: those
bundles recorded v1 and are judged under v1. Register R-147.

## Correction (2026-10-02, T08 review 3) — §11 and §15 after R-147 and R-148

*Transcribed by the build lane from `docs/reviews/T08-review-3.md` §C Ruling 2 (design lane, `reviewer`).*

1. **§11's "Not expected to change" is wrong for T08.A42.** The identity document carries no `numerical_policy_id`
   key, but it does carry K05's `structural_sha256`. `RunManifest.structural_document` covers
   `numerical_policy_id` directly, and also through `artifact_r0_sha256`, the certificate's R0 projection. D1.2
   therefore moves the following values:
   - **K05 identity document:** whole `7f32b143…` → `28dd8bf7…`; minus `t07` `9a7b4e6d…` → `29246e05…`; `t07` key
     `422aa7a5…` → `a96f17ed…`.
   - **K05's `structural_sha256`:** `915c97e8…` → `e62a59a6…`.
   - **The CLI's `solve`/`inspect` structural hash of SYN-001-nominal:** `af86adb8…` → `f9536122…`.
   - **The K05 schema fixtures:** the certificate hash, `manifest_sha256` and the structural hash.

   The move is a substitution only. With v1 recorded again at the id's sources, every old value is reproduced byte
   for byte (`tests/t08_v2_substitution.py`). Frank approved it on 2026-10-02 (R-148; release spec Amendment R5).

   Unchanged, as §11 said: T02's floats (`9a8a5baf…`), the keys `t02`…`t06`, `check_policy_sha256`, A49's served
   digest and B50's digests. The check §11 cited tested whether the document has the key, not what its hashes
   cover.
2. **§11's "Records made under v1 … are refused at replay (`NOT_RUN`)"** is replaced by Frank's answer to Q4.
   Such records are re-run and compared under `K04-numerical-policy-v1`, whose path is frozen bit for bit, and
   their recorded verdicts stand. Only a record naming a policy this build does not know is refused.
3. **§11's cost** becomes one identity re-registration (R-148), one new `C` and one RC job.
4. **§15's R-146 is entered at W9 as amended by R-147.** Its title ends "…; records are compared under the policy
   they name, and an unknown policy is refused at replay". Its sentence "Records made under v1 are refused at
   replay" becomes "Records made under v1 are compared under v1 (R-147)". Its rejected alternative "Re-judging the
   `814e151` bundles under v2" and its watch item "A v1 record compared under v2" stand.

## Accepted (2026-10-02)

Recorded by the build lane (brief `docs/briefs/T08-close.md`, item 8) with T08's tested evidence at `C` = `67c66d9`. A45's FAIL at `814e151` under `K04-numerical-policy-v1` stands (R4 1); v2 was adopted after it, and the manifest's limitations say so.
