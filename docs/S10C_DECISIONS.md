# S10-C build decisions

Build-lane choices the design note (`docs/derivations/S10C-design.md`, ADR 0049) left to the engineer. One line
each; each is isolated and revertible. Measurements go in the run log below.

## WO-1: the call-site inventory (design note §4.12)

`grep` for `"lnK"`, `lnK_`, `h_{`, `T_MIN`, `T_MAX`, `REFERENCE_CONVENTION`, `syn001_thermo` (and, added by this
inventory, `P_MIN`, `P_MAX` and the calls of the K/enthalpy consumers `_k_values`, `enthalpy_flow`, `_enthalpy_flow`,
`band_temperature`, `single_phase_admissible`, `outside_the_degeneracy_window`, `stage_band`,
`saturation_temperature`, `evaluate_phase`, `tp_state`, `ph_state`, `LnKBlock`, `EnthalpyFlowBlock`,
`property_method_refusal`) over the modules reachable from `ph_state` and `solve_column`: `models/syn001/{ph_kernel,
saturation_band, tp_state, cascade, cascade_solve, column, column_solve, column_blocks, blocks}.py` and
`orchestrator/region.py`. Lines are at `ffcb387f` (before WO-1's edits). Classes: **D** dispatch at the top (§4.12
table), with the WO that owns it; **N** no branch, the site calls a dispatching function; **R** never reached by the
γ–φ-IG form because a refusal precedes it; **O** out of S10-C's scope (§1), reached only from the S01 cascade (which
keeps S11) or from units other than the column.

| Site (`ffcb387f`) | What it reads | Class | Owner / note |
| --- | --- | --- | --- |
| `saturation_band._k_values` 101–114, `band_temperature` 144 | `lnK` | D | WO-1 (done): `band_temperature` → `gamma_phi.band_point` |
| `saturation_band.outside_the_degeneracy_window` 220–227 | `lnK` | D | WO-1 (done): β = 0 test only, K at the stream; β = 1 side `False` |
| `saturation_band.degeneracy_distance` 187–188 | `band_temperature` | N | — |
| `tp_state.enthalpy_flow` 102–109 | `h_<c>` | D | WO-1 (done): `gamma_phi.enthalpy_flow` (`n_tot h`) |
| `tp_state.single_phase_admissible` 159–170 | `h_<c>`, `∂h_<c>/∂T` | D | WO-1 (done): `gamma_phi.enthalpy_and_slope`; rest of the body unchanged |
| `tp_state.single_phase_admissible` 172, 191, 194 | `tp_state`, prescreen, band | N | — |
| `tp_state.tp_state` 217–250 | provider TP flash, `enthalpy_flow` | N | — |
| `tp_state.lnk_block_id` 350, `lift_two_phase_stream` 401–419, `single_phase_enthalpy` 364, `stream_enthalpy_terms` 514 | `LnKBlock`, `lnK_` keys, `EnthalpyFlowBlock` | O | K02 units' EO faces (§1) |
| `ph_kernel.ph_state` 250–, its saturation route 290 and `_ln_k` 474–494 | `lnK` | D | WO-2 (§4.5) |
| `ph_kernel._closure_rows` 196–227 | `lnK` | D | WO-2 (§4.5 step 4) |
| `ph_kernel` band route `big_f` 399, 411; 551, 582 | `band_temperature`, `enthalpy_flow` | N | reached through WO-2's band route |
| `ph_kernel` 662, 678 (unit-evaluator helpers) | `single_phase_admissible`, `tp_state` | N | — |
| `ph_kernel` 48, 623, 629, 692 | `REFERENCE_CONVENTION` (label of a `UnitEvaluation`) | O | unit evaluators (`PHFlash`, valve, …), not `ph_state` |
| `region._admissible` 700–722 (with `verify.checks.k_values` 720) | `lnK` | D | WO-2 (§4.10) |
| `region._split_enthalpy` 515, `_band_regime` 551–572, `_ph_closure` 619, `_kernel` 419– | `enthalpy_flow`, `tp_state`, `band_temperature`, `ph_state` | N | — |
| `cascade._k_values` 423–445 | `lnK` | D | WO-4 (§4.9: gains `liquid=`) |
| `cascade._enthalpy_flow` 448–457 | `tp_state.enthalpy_flow` | N | — |
| `column.validate` 630 | `property_method_refusal` (S11) | D | WO-3: `equilibrium_form.admission` (written in WO-1) |
| `column.validate` 666 | `T_MIN`, `T_MAX` | D | WO-3: `form.domain["T"]` |
| `column.validate` 667, 673–674 | **`P_MIN`, `P_MAX`** | D | WO-3: `form.domain["P"]` — *found by this inventory; the note names only T*. SYN-001's P box is 5e4–2e5 Pa; `wilson-ig-v1`'s is 3e4–2e5 (real) and 5e4–3e5 (verification) |
| `column.validate` 706 | `single_phase_admissible` | N | — |
| `column.energy_precheck` 1085, 1102–1103 | `_enthalpy_flow`, `T_MIN`, `T_MAX` | D | WO-3: `form.domain` (enthalpy already dispatches) |
| `column.declared_rows` 1168 (`enthalpy_block`), 1176 (`lnk_block`) | `EnthalpyFlowBlock`, `LnKBlock` | D | WO-3 (§4.7) |
| `column.declared_rows` `slot` 1324, 1398 | `lnK_<c>` output keys | N | `GammaPhiLnKBlock` keeps the `lnK_<c>` output ids |
| `column.profile_initial` 1623 | `band_temperature` | N | — |
| `column.profile_initial` 1659 | `_k_values` | D | WO-4 (§4.9: K at `z`) |
| `column._initial_state` 1705– | `declared_rows` blocks | N | through WO-3's blocks |
| `column.saturation_temperature` 587–595, `stage_band` 599–606, `_inverse_refusal` 931 | `syn001_thermo` closed forms | R | reached only for a `temperature` specification, refused for γ–φ-IG (WO-3, §4.8) |
| `column_solve._admissibility` 509, `_saturation_pairs` 537, `_bubble_temperature` 873 | `single_phase_admissible`, `band_temperature` | N | — |
| `column_solve.overall_closure` 730, 743 | `_enthalpy_flow` | N | — |
| `column_solve.sweep_flows` 844 (and `bubble_point_endpoint` 883–) | `_k_values` | D | WO-4 (§4.9 relaxed sweeps) |
| `column_blocks._bubble` 200, `_enthalpy` 278 | `band_temperature`, `enthalpy_flow` | N | — |
| `column_blocks._core_flows` 231 | `_k_values` | D | WO-4 (§4.9) |
| `blocks.LnKBlock` 51–109, `EnthalpyFlowBlock` 192–221 | `lnK`, `h_<c>` | N | SYN-001 blocks, unchanged; γ–φ-IG gets new blocks (WO-3) |
| `cascade.property_method_refusal` 397–420, `cascade.validate` 495, 531–539, 572; `energy_precheck` 622–638; cascade rows 721–816; `kremser_initial` 1064, 1090; `cascade_solve.admissibility` 444, `overall_closure` 507–521 | S11, domain constants, `LnKBlock`, `_k_values` | O | S01 cascade keeps S11 (§1; design note Q3) |

## Run log
