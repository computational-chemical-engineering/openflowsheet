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

- DECISION: which identity does a v2 result carry? → v1's: a request without `s` returns v1's object (the note), and a
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

## Handoff (after D1 and D4)

- Done on `wp/S11-d`: D1 (`1b2a90e2`), D4 (`7d96e15f` provider and reference, `6dcb7640` ADMITTED, `f4465879` _SCOPE). Not
  pushed. D2, D3, D5, D6 not started (not this engineer's).
- Open for the design lane: the v2 result `provider_id` question above; `ph_kernel`'s SYN-001 convention label on
  typed failures (D1 note).
- Next: D2 (binding kwargs) can start on this branch; D5 switches selection to v2 (A79 gate, revert plan Q24).
