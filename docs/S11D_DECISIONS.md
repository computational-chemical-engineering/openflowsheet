# S11 build decisions — track D (Wilson)

Build-lane choices the units design (`docs/derivations/S11-units-design.md`, ADR 0051) left to the engineer, for track D
(`wp/S11-d`: D1–D6). One line each, as `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each is
isolated and revertible. Measurements go in the run log below.

## WO-D1: the γ–φ faces of the five K02/T05 units (§4.5)

- DECISION: where does the γ–φ branch sit in `lift_two_phase_stream`, `single_phase_enthalpy` and
  `stream_enthalpy_terms`? → the branch selects the blocks (and the K-block's inputs); the SYN-001 block statements move
  unchanged into its `else`, and the rows, ids, kinds and order stay one shared code path. Alternative: a branch at the
  top returning a γ–φ copy of each helper, which would duplicate ~60 lines of row construction. Reversible by: reverting
  the D1 commit's `tp_state.py` hunks.
- DECISION: `TPFlash._inlet_enthalpy` on a lifted γ–φ inlet → it returns `tp_state.stream_enthalpy_terms(..., None)`
  (the same construction, mixture blocks on the producer's split variables); K02's SYN-001 copy below is untouched.
  Alternative: a second in-module copy with mixture blocks. Reversible by: the one `if composition_dependent` block.
- DECISION: which `UnitEvaluation`s read the new fields? → those that named the SYN-001 constants
  (`reference_convention=REFERENCE_CONVENTION`, the mixer's `provider_id=PROVIDER_ID`); those that omitted
  `provider_id` still omit it, and those that copy the kernel's convention still copy it. Adding `provider_id` where it
  was absent would change SYN-001's answers. Alternative: `provider_id=self.property_provider` on every evaluation.
  Reversible by: the per-module replacements.
- DECISION: the PH flash's evaluate-time outlet-pressure check (`P_in − dP` in the domain) reads `domain["P"]` too, not
  only the `__post_init__` checks. Alternative: leave SYN-001's constants there. Reversible by: one hunk in
  `ph_flash.py`.
- DECISION: what is A68's "square contribution"? → each unit's rows, origins, row kinds, variables and block ids equal
  the SYN-001 construction with the same components, and the assembled feed → unit → sink flowsheet has the SYN-001
  flowsheet's equation and variable ids. By count neither is square: K02's pressure rows restate a feed's pressure
  (`FLASH-P` inlet, one `MIX-pressure` per inlet), measured 33 rows / 32 variables (heater → flash) and 16 / 15
  (mixer) on both bases. The test adds that every row vanishes within its `KIND_TOLERANCE` at the unit evaluator's
  state. Alternative: a count-square test on the unit alone. Reversible by: editing `tests/test_s11_gp_units.py`.

Not changed, reported: `ph_kernel.typed_failure`, `closure_failure` and `_state_failure` stamp SYN-001's
`REFERENCE_CONVENTION` on the valve's and the PH flash's typed failures, on Wilson too. `ph_kernel.py` is outside D1's
file list (§5.3); a failure carries no value, so no number is mislabelled, but the label is wrong. For D3 or I1b.

## WO-D4: `wilson-ig-v2` (§4.6) and `ADMITTED`

- (Superseded by the ruling below, `fc645bce`.) DECISION: which identity does a v2 result carry? → v1's: a request without `s` returns v1's object (the note), and a
  request with `s` is `dataclasses.replace` of v1's result, so `provider_id` is `wilson-ig-v1` on every v2 result, as on
  the forwarded flash, while `describe()` says `wilson-ig-v2`. Alternative: stamp `wilson-ig-v2` on results that carry
  `s` (a provider whose results disagree on their own id by request). Reversible by: one `replace(...)` in
  `evaluate_phase`. **Question for the design lane** (affects D5/D6): `tp_state` copies the flash's `provider_id` into
  `UnitEvaluation.provider_id`, so Wilson units on v2 would report `wilson-ig-v1` there.
- DECISION: the `derivative_singular` refusal names the first zero component in component order and carries v1's
  `provider_id` and convention. Alternative: name every zero component. Reversible by: the message line.
- DECISION: A75's "states of the S10/S10-C test grids" → every `{n, T, P}` mapping of `benchmarks/s10/
  reference_values.yaml` (19) and `reference_values_real.yaml` (31), plus a 72-state grid per record file (four T, three
  P incl. the bounds; interior, binary, pure, near-zero and dormant compositions), each in both phases with and without
  derivatives, and flash and `stability` at each. Alternative: record every state the S10/S10-C test modules pass.
  Reversible by: `_states` in `tests/test_s11_wilson_v2.py`.
- DECISION: s's derivatives against the reference (no registered A-tolerance) → S10's evaluate_phase rule, 1e-12 ×
  max(|want|, s_q) with s_q = R/T, R/P, R/n_tot. Alternative: no derivative comparison beyond A77. Reversible by: the
  test and the YAML's `tolerances`.
- DECISION: A77(iii) → only the (i, T) whose P_i^sat(T) lies in the records' P domain are asked (verification VA 350,
  VB 350, VC 390; real CH3OH 310 and 350, C2H5OH 350, H2O 350 and 390: 8 of 18); the other 10 are asserted refused
  `out_of_domain` by v1. Alternative: other temperatures per component. Reversible by: `SATURATION_TEMPERATURES` and the
  test.
- DECISION: A77(iv) → A46's `_fd_worst`/`FD_TOL` on C3's `additive-vapour` isentropic block over v2's vapour, 12
  compressions per record file. Alternative: none (the block is C's). Reversible by: deleting the test.
- DECISION: `_SCOPE` → the v1 clause kept verbatim (`test_s10c_forms` pins it) and "and wilson-ig-v2 (the same
  reference conventions)" appended, in its own commit (`f4465879`); kept because S10C-IDENTITY reproduced on it.
  Alternative: leave `_SCOPE`. Reversible by: reverting `f4465879`.

## Orchestrator ruling on D4's question 1 (`fc645bce`)

- DECISION: v2 result provider_id → wilson-ig-v2 (values bitwise v1). Alternative: keep v1's label. Reversible by:
  reverting that commit. Every `PropertyResult` and `FlashResult` of v2 (ok, v1's refusals, `derivative_singular`)
  carries `wilson-ig-v2`; `stability` returns v1's report (a `StabilityReport` has no provider id). A75/A78 compare
  v1's answer with the label swapped back (`float.hex`) and assert both labels. Supersedes D4's first decision above.

## WO-D2: the five builders' provider kwargs (§4.5)

- DECISION: how do the five builders pass the fields? → through A2's `_routing_fields(provider)`, which returns nothing
  when the bound provider describes itself as `syn001` (the bound provider is the basis's, so this is §4.5's
  `view.basis.provider_id != "syn001"`). Alternative: a second branch on `view.basis` in each builder. Reversible by:
  `d31f9160`'s five hunks.
- DECISION: the D2 test's revisions → one document per model, feed(s) → `U` → sink(s), built in code on the real Wilson
  records (the verification records are no basis), `MODEL_BASES` patched for the five only; the constructors' range
  checks are shown reading the bound domain by a valve outlet at 4e4 Pa (inside Wilson's P domain, outside SYN-001's)
  and a heater/TP-flash outlet at 290 K (the reverse). Alternative: GP-C1's shapes (D6's). Reversible by: editing
  `tests/test_s11_gp_binding.py`.

## WO-D3: `verify/gamma_phi_units.py` (§4.8)

- DECISION: the module's entry → a full `revision_checks`, table's `DECLARED_MIXTURE` branch argument for argument
  (it imports `table.Unit`, `MODEL_CHECKS`, `_envelope_material`, `_envelope_energy`) with the registry splits added,
  so that I1b's hook is one dispatch line; A73 pins the replica against `table.revision_checks` on A3's and B4's
  flowsheets. `degeneracy` and `split_checks` are exported for an I1b that prefers to wire the pieces into the table.
  Alternative: pieces only. Reversible by: I1b calling the pieces.
- DECISION: the degeneracy check's note → `BAND_NOTE` ("the band is models.syn001.saturation_band.degeneracy_distance,
  the implementation the units use (not an independent check)"), written as A3's `forms._SHARED`, whose own text names
  `single_phase_admissible` and would mislabel the band. Alternative: `_SHARED` verbatim. Reversible by: the constant.
- DECISION: §4.8's "max_i |Δv_i|, |Δl_i| ≤ τ_flow" under SYN-001's ids → `independent_split.<U>.<S>.total` keeps the
  vapour total's difference, and `.<c>`'s value is whichever of Δv_c, Δl_c is larger in magnitude. Alternative: new
  `.liquid.<c>` ids. Reversible by: the one `value=` line.
- DECISION: the stability check's numbers → value the other phase model's trial `tm` (the least of the two on
  `.closure`), tolerance the report's `epsilon`, verdict the provider's label (`verify.column`'s rule); a flowing phase
  has total > 0; `.closure` also needs min(V, L) ≥ −τ_flow; no `stability` method, or `UNKNOWN`, is `unsupported`.
  Alternative: one check per phase. Reversible by: `_admissibility`.
- DECISION: ADR 0013 D3's unresolved route (`fresh_flash_unresolved`) → not taken; §4.8 lists only the degeneracy
  substitution. Alternative: a γ–φ `split_route`. **Question for the design lane** (reviewer).
- DECISION: a degenerate flash-style split's products → read by the declared-phase rule, without SYN-001's
  `SPLIT_ENTHALPY_NOTE` (identity with the first pass; the value is the carried product in its own phase either way).
  Alternative: SYN-001's note. Reversible by: `degeneracy`.
- DECISION: A72's direct state and "VERIFIED" → the units' own evaluators at the azeotrope (the heater stores β = 0, a
  liquid-only split; δ = 0.0 for both splits), parsed with `WILSON_BASIS` monkeypatched to VA/VB/VC; VERIFIED read as
  every table row `pass`/`not_applicable` and every residual row within `KIND_TOLERANCE`. Alternative: a hand-made
  β = 0.5 split. Reversible by: the test.

## Run log

- D1 base manifests (`document_sha256` without `implementation_artifact.artifact_hash`, at `01f95c92`): equal after D1
  on all five (`test_a67_the_syn001_manifests_are_the_bases`).
- D1: `tests/test_k02_* test_t05_* test_t05b_* test_s10c_*` 2108 passed; `tests/test_s11_gp_units.py` 16 passed. Worst
  row / kind tolerance at the evaluator's state: real 1.9e-8 (heater, flash), 2.9e-8 (PH flash), 1.8e-9 (valve), 0
  (mixer); verification 5.2e-9, 6.6e-9, 1.8e-9, 0.
- D1 identity at `1b2a90e2` (clean): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 5, 14, 15] exited
  non-zero)`; `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`; `S10C-IDENTITY PASS n=858 changed=[]`.
- D4: `tests/test_s11_wilson_v2.py` 23 passed. A76 worst relative error of s: 1.68e-15 (verification), 1.43e-15
  (real), limit 1e-13; A77(iv) worst scaled FD disagreement 1.09e-10 (FD_TOL 1e-6). The generator: 72 states, 347
  claims, `--check` matches; |s/R| ≥ 0.41 at every state.
- D4 identity at `f4465879` (clean, `_SCOPE` included): `S10C-IDENTITY PASS n=858 changed=[]`; `S11-IDENTITY FAIL
  n=54497 changed=[] (C branch shards [1, 5, 14, 15] exited non-zero)`, the failures (kept logs) exactly the known
  eleven: s05 a25, s07 a30, s10 a27, t08 a20, the six t08 c3, T08.A32; `S08-IDENTITY PASS n=52 changed=[S02.P1]
  p1_stage_a=EQUAL`.

- Ruling (`fc645bce`): `tests/test_s11_wilson_v2.py` 24 passed; with `test_s11_thermal_machines`, `_binding` 149
  passed, 5 skipped.
- D2 (`d31f9160`): `tests/test_s11_gp_binding.py` 18 passed; `test_k02_* test_t05_* test_t05b_*` and
  `test_s11_gp_units.py` 1408 passed; `test_s11_routing`, `test_t05_w1b_revision`, `test_m02_join` with it 106
  passed, 3 skipped. Identity at `d31f9160` (clean): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 5,
  14, 15] exited non-zero)`, the known eleven (kept logs).
- D3 (`5ee0bad8`): `tests/test_s11_gp_verifier.py` 10 passed (with `test_s11_verifier_forms` 19 passed, 3 skipped).
  A72: δ = 0.0 K on U-H.S2 and U-F.S2 (τ_T 1e-6), the heater's stored β = 0. A74 base: closure tm −2.2e-16,
  independent split Δ = 0.0 on every component; swapped CH3OH↔H2O v: Δ = ∓0.1296 mol/s (FAIL), closure tm −0.2145
  (FAIL), `material_balance.U-H.lifted_split.{CH3OH,H2O}` FAIL, residual rows `U-H:split:*` ±0.1296,
  `U-H:HEAT-equilibrium:*` ±0.0161, `U-H:HEAT-duty` 5380 W out of tolerance. A73 equal on 4 call sites (routing
  declared/undeclared, C-MW, C-EW: every `revision_checks` call of `verify_revision`).
- Identity at `5ee0bad8` (clean): `S11-IDENTITY FAIL n=54497 changed=[] (C branch shards [1, 5, 14, 15] exited
  non-zero)`, the same eleven failures as at `d31f9160`; `S08-IDENTITY PASS n=52 changed=[S02.P1]
  p1_stage_a=EQUAL`; `S10C-IDENTITY PASS n=858 changed=[]`.

## Handoff (after D1, D2, D3, D4)

- Done on `wp/S11-d`: D1 (`1b2a90e2`), D4 (`7d96e15f`, `6dcb7640`, `f4465879`), the provider-id ruling
  (`fc645bce`), D2 (`d31f9160`), D3 (`5ee0bad8`). Not pushed. D5 and D6 not started (not this engineer's).
- For I1b: `MODEL_BASES` gains Wilson's row for the five (the D2 test patches it); `verify.forms.Form` gains
  `gamma_phi_units.GAMMA_PHI_UNITS` and `table.revision_checks` dispatches the v2 basis to
  `gamma_phi_units.revision_checks` (same signature).
- Open for the design lane (reviewer): `ph_kernel`'s SYN-001 convention label on typed failures (D1 note, left
  alone per the orchestrator); ADR 0013 D3's unresolved route on γ–φ splits (not taken); D3's Δl-under-SYN-ids and
  stability-value choices above.
- Next: D5 (select v2; A79) then D6 (GP flowsheets; Q18 spike first).
