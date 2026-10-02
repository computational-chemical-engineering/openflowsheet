# Brief — T06 amendment round 1 (Frank's answers + Phase M questions)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-26. **Branch:** `wp/T06`.
**Deliverable:** dated amendments to `docs/derivations/T06-corpus-spec.md`, ADR 0014 (Proposed) and
the register where a choice could later be undone; twin re-emitted if a registered value changes
(`--check` passes; give the new SHA); a ruling list in §4 of this file (per item: ruling, build-lane
change, acceptance test). No code; do not commit.

## 1. Frank's answers (2026-09-26; verbatim choices from the question tool)

- **Q3 — permuted component order: "Support it."** The builder maps any declared component order onto
  the provider's; STA-04 (C2 with components `[C, A, B]`) becomes a solved case rather than
  `components_unsupported`. Specify the mapping, where it lives (binding/revision layer; `thermo/syn001.py`
  stays byte-identical), identity consequences (label/`configuration_sha256`), what the certificate
  reports, STA-04's new expected outcome and class, and whether it becomes ensemble-eligible.
- **Q4 — non-SI units: "Convert them."** kg/s → mol/s via the component molar masses, °C → K, and any
  other units the Quantity machinery knows, the conversion recorded; unknown units still refused.
  This replaces W1's planned `DIM-01` typed refusal for convertible units. Specify it for both the
  legacy SYN-001 binding (today silently reads kg/s and degC as SI — F1) and the revision binding
  (today refuses `specification_unit_unsupported`), STA-03's new expected outcome(s), and the checks
  that prove a converted value equals its SI twin exactly or to a stated tolerance.
- **Q7 — the gate: "Point estimate."** ≥ 418/440 on both architectures; Clopper–Pearson reported.
  (Your spec's default; confirm nothing else moves.)
- Q2 and Q6 stay at their defaults (T07/T08).

## 2. Phase M questions (details in `docs/t06-measurements.md`, `docs/t06-measurements-m45.md`,
`docs/t06-reference-qualification.md`, `docs/T06_DECISIONS.md`)

- **M1:** on the legacy path, `solve_tear` raises (`SpecificationError`, out of domain) rather than
  returning a typed outcome when the registered initializer is out of domain (STA03-degC). With Q4's
  conversion the fixture no longer reaches it; is the raise itself acceptable, or should it be typed?
- **M4:** today's certificates carry no `shared_provider` limitation (clean C1 included); A17's "plus
  the always-present `shared_provider`" presumes D14 is implemented — does W7 (ADV-06) land before or
  after D14's implementation, and which chunk implements it?
- **M6 (reference qualification, blind):** (a) register IDAES `constr_viol_tol = 1e-9` (measured: at
  1e-10 REF-04/05 end "Search Direction is becoming Too Small" with the unscaled violation stuck at
  1.02e-10 on Pa rows at 1e5–1.8e5 Pa — the double floor; REF-06 "Solved To Acceptable Level" at
  1.16e-10; rule 2 ≤ 1.5e-13 mol/s either way)? (b) PC-1 is defined only for DWSIM's ΔH_vap input — no
  IDAES variant: `not applicable`? (c) §9.4 does not give PC-2's feed — REF-04's feed (300 K, liquid)
  at 1.5e5 Pa was used; (d) REF-08's recycle guess in DWSIM/IDAES — (0.2, 0.6, 0.8) mol/s at 360 K
  from the representability probe (not this project's initializer); (e) IDAES initializers forced to
  MUMPS, other options IDAES defaults (tol 1e-6); (f) IDAES "converged" only on "Optimal Solution
  Found"; (g) DWSIM does not expose REF-07's extent — derived from its reported conversion of A, so B
  and C are the real check. Rule each.

## 3. Context

The `architect` is concurrently designing F4's recovery (`docs/briefs/T06-F4-recovery.md`); do not
design it. Frank's standing steers: fewest limitations; robustness with recorded fallbacks.

## 4. Rulings (the design lane fills this in)

*Filled in 2026-09-26 by the design lane (`specifier`). Normative text: `docs/derivations/T06-corpus-spec.md`
"Amendment 1" and every passage marked (A1); ADR 0014 "Amendment 1" (D1, D3, D6, D7, D8 amended; D9–D11
added); register R-076 … R-080 (R-066, R-068, R-071, R-072, R-074 annotated; R-075 reserved for ADR 0015).
Twin re-emitted: 313 claims (was 295), `benchmarks/t06/reference_values.yaml` sha256
`a22bc72c277e712650a367aee6c369f1e4ad59e5b153c2e7f7a63bc384f90f75`, 55 474 bytes, two emissions
byte-identical.*

**Frozen interfaces: Q3 and Q4 need none.** Q4 implements ADR 0001 D1.3–D1.4 (frozen), which already
prescribe these two conversions; the pre-A1 refusal contradicted D1.4. Widening the unit table
(`kPa`, `bar`, `kW`, `%`, …) *would* widen a frozen rule: spec Q11, Frank's, default not in v0.1.

| Item | Ruling | Build-lane change | Acceptance test |
| --- | --- | --- | --- |
| **Q3** component order | Map any permutation of the provider's `describe().components` onto it; refuse any other list (`components_unsupported`). Label, `configuration_sha256`, `constants_sha256`, `variable_ids`, trace and certificate are the unpermuted twin's; `revision_sha256` differs; the certificate reports nothing new; the declared order is kept in `input_mapping.declared_components`. STA-04 → `verified_at_reference` at C2's root; **not** ensemble-eligible (clause (e): a metamorphic restatement of NET-08) | **W1b**: one function in `models/revision_flowsheet.py`, called by `_read` and by the legacy binding (fixes F7); `input_mapping` on both bindings; test `_COMPONENTS == Syn001Provider().describe().components`; `thermo/syn001.py` untouched | A59 (STA-04 byte-identical to C2 under `T05b-v2` and `T06-revision-v1`), A60 (all six orders; four non-permutations refused), A61 (legacy `[C,A,B]`, `[B,A,C]` byte-identical to nominal; today `InnerSolveInconsistentError`) |
| **Q4** units | Convert by `unit-conversion-v1` = ADR 0001 D1.3–D1.4 only: `degC`→K (`v + 273.15`, one binary64 add) on a temperature target; `kg/s`→mol/s (`v / M_c`, one binary64 divide) on a one-component flow target, declared kind `molar_flow` or `mass_flow`. Specification values only (both roles); parameters stay SI. Else refused with the revision binding's codes. Records in `input_mapping` and `DIM-01`'s `PASS`; not in the certificate. Unknown or wrong-kind unit → `DIM-01 FAIL` → `INVALID`. STA-03 → `verified_at_reference` at NET-01's root, bit for bit; not eligible | **W1a**: the function in `process_runtime.units`; an id-keyed molecular-weight table (tests: equals `components.yaml`; `conversion_reactor.MOLAR_MASSES` equals it in order); readers R1 legacy binding (values and guesses), R2 `revision_flowsheet._read`, **R3 `verify/certificate.py::_revision_values`** (reads `float(entry["value"])` raw today), R4 `DIM-01`; both bindings' refusals (`unit_not_internal_si` withdrawn); legacy binding also refuses a parameter failing `check_quantity` | A55 (legacy: `DIM-01` message, flowsheet settings equal nominal's, trace + certificate byte-identical), A56 (revision path; and the `verify_bound` control: A02-360 with 86.85/84.85 degC byte-identical to A02-360), A57 (`degF`, `K` on a flow, `temperature` kind on a flow refused; `mass_flow` kind converts; `tests/test_t05_w11_cases.py` unchanged), A58 (converter bit patterns = `ref.closed_form.unit_conversion_v1.known_answers`) |
| **Q7** gate | Confirmed: `S ≥ 418` of 440 on `ref-x86-64` and CI aarch64, CP bound reported. Nothing else moves (N, `S_min`, ceiling, classes, CP table all re-pass) | none | A30 as registered |
| **M1** tear-path raise | **Typed.** `initial_recycle` raises `InitializerFailedError(SpecificationError)`; `solve_tear` catches exactly it → `INITIALIZATION_FAILED`, message `initializer_failed(SYN-001-tear-init-v2): <status>: <first line>`, trace one `solve_closed` event, `plan=None` | **W11** (review: design, K03) | A62 (450.0 K, 279.0 K, 400.0 K feeds; *measured* today: all three raise); every registered SYN-001 trace byte-identical |
| **M4** `shared_provider` | D14 is **already implemented** as `independence_qualifications` (one entry per `energy_balance.*`, `phase_admissibility.*`, `independent_split.*` check) plus a fourth statement — measured on six certificates. The spec's "limitation" wording (from K04 §8.2's text) was wrong. A17's limitations are exactly `[derivative_limitation]`. W7 has no dependency; no chunk implements D14 | none (W7 as specified); recommended: a K04 §8.2 erratum by the design lane | A17, A33 as amended |
| **M6 (a)** `constr_viol_tol` | **`1e-9`, uniformly** for every IDAES final solve (`tol` stays `1e-10`). `1e-10` is 3.4 ulps of a 2e5 Pa row (below the measured floor: stuck 1.02e-10–1.16e-10); `1e-9` is 34 ulps and ≥ 100× below every allowance (generator-checked) | **W8**: re-run the six IDAES records made at `1e-10` (REF-01/02/03/07/08, PC-2) blind at `1e-9`; rule 2 must still pass | A49 |
| **M6 (b)** PC-1 in IDAES | `not_applicable` (IDAES has no ΔH_vap input); a registered absence, outside V16's counts. PC-2 runs in **both** tools and both must `DISAGREE` | W8 records it | A51 |
| **M6 (c)** PC-2 feed | REF-04's feed at 1.5e5 Pa: (1,1,1) mol/s, 300 K, liquid; compared `S2.n` only. Our fixture `SYN-001-T06-PC2` (REF-04 with `P` 1.5e5 Pa and `outlet.T` 370 K) | W8 writes `SYN-001-T06-PC2` | A51; `ref.closed_form.reference_tool_settings.PC-2` |
| **M6 (d)** REF-08 tool guess | Accepted and registered: (0.2, 0.6, 0.8) mol/s, 360 K, `P_r` — the tools' own start, independent of ours | none | A49 |
| **M6 (e)** IDAES initializers | Accepted: MUMPS forced, other options IDAES defaults; MA27 nowhere | none | A49 |
| **M6 (f)** IDAES "converged" | Accepted: only "Optimal Solution Found"; "Solved To Acceptable Level" is non-convergence (§9.5 rule 2) | none | A49 |
| **M6 (g)** REF-07 DWSIM extent | Accepted and disclosed: `ξ = X_A · n_A,in / abs(ν_A)`; B and C carry rule 2; rule 4 compares all three outlets and the duty | record the disclosure in the result JSON | A50 |
| **F4 / WO6** | Revision path under **`T06-revision-v1`** (`T05b-v2` with only `eo_recovery = homotopy_or_sequential_restart`); NET-02 `verified_at_reference` under it, `BOUND_BLOCKED` under `T05b-v2`/`T05-W13` (control); rescued starts count, reported per case (`s_c^first + s_c^rescued`), CP bound also on `S^first` (not gated); `t06` gains NET-02 under `T06-revision-v1` and each path's policy id; R-074 closed by R-075 | design note WO1–WO9; W4 (registry), W6 (report), W9 (key) | A63, A64, A65, A66; A02 now under `T06-revision-v1` |
| **F6** | Registered as a finding and a build-lane diagnosis item **M8** (Q12): reproduce at C3 pass 4 / NET-02 pass 29, record the residual history, bracketing and floor; no change to `thermo/syn001.py` without a design-lane ADR; not blocking | M8 | M8's report to the design lane |

**STA-03 / STA-04 class and eligibility:** both change class to `verified_at_reference` and enter the
success denominator (28 → 30); **neither is ensemble-eligible** (amended clause (e), generator-checked);
the eligible set (22), `N = 440` and `S_min = 418` are unchanged.

**Findings (spec §18, items 6–10):** (6) the pre-A1 §8.5 / ADR 0014 D6 / R-071 contradicted ADR 0001 D1.4;
(7) the pre-A1 IDAES `constr_viol_tol = 1e-10` sat below its floor; (8) K04 §8.2's text disagrees with
the reviewed implementation (`independence_qualifications`) — erratum recommended; (9) F7, the legacy
binding's permuted-order crash, latent since K02; (10) no chunk implemented D14 because none was needed.
