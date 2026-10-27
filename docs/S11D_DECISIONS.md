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

## Run log

- D1 base manifests (`document_sha256` without `implementation_artifact.artifact_hash`, at `01f95c92`): equal after D1
  on all five (`test_a67_the_syn001_manifests_are_the_bases`).
- D1: `tests/test_k02_* test_t05_* test_t05b_* test_s10c_*` 2108 passed; `tests/test_s11_gp_units.py` 16 passed. Worst
  row / kind tolerance at the evaluator's state: real 1.9e-8 (heater, flash), 2.9e-8 (PH flash), 1.8e-9 (valve), 0
  (mixer); verification 5.2e-9, 6.6e-9, 1.8e-9, 0.
