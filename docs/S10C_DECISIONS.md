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

## WO-1 decisions

- DECISION W1-1: where the dispatch resolves the form → one helper `equilibrium_form.composition_dependent(provider)` (one `describe()` per dispatching call; `None` and SYN-001 both `False`), called at the top of `band_temperature`, `outside_the_degeneracy_window`, `tp_state.enthalpy_flow`, and after the dormant early return of `single_phase_admissible`. `form_of(capabilities)` is public so callers holding a `describe()` can resolve without a second call. Alternative: thread a form object through the kernels' signatures. Reversible by: the helper and its four call sites.
- DECISION W1-2: the import cycle (`gamma_phi` needs `BandError`/`BandTemperature` from `saturation_band`, which dispatches to `gamma_phi`; `admission` needs `CascadeFailure` from `cascade`, which imports the kernels) → function-local imports with `# noqa: PLC0415` in `saturation_band` (2) and `equilibrium_form.admission` (1), the repository's existing idiom (`flash.py:466`). Alternative: move `BandError`/`BandTemperature` and `CascadeFailure` to a leaf module (touches frozen-adjacent SYN-001 modules more widely). Reversible by: moving the imports.
- DECISION W1-3: `Tsolve`'s details the note leaves open (§4.3), measured below → (a) the Newton step is taken from the **bracket end with the smaller `|g|`** (the lower on a tie), not from the latest evaluation; (b) the rule "`t' == t` → the adjacent double towards the root" is applied **before** the open-bracket test (in the note's order it is dead code: `t' == t` is a bracket end, never inside the open bracket, so it would always bisect); (c) the halving test compares the bracket width after this evaluation with the width two evaluations earlier, unknown ends counting as the domain ends. The root, the stop rule (adjacent doubles, smaller `|g|`, lower on a tie) and the budget are the note's. Alternative: the literal order (Newton from the latest point, bisect whenever `t'` is a bracket end). Reversible by: `_Point.temperature` / `_Point._step` in `gamma_phi.py`.
- DECISION W1-4: `ln_k`'s return shape → `(values, d_T, d_n)` with `d_T = ()` unless `"T"` is requested and `d_n = ()` unless every `n_<c>` is (a partial composition request is a `ValueError`), rows in the provider's order. `band_point` and `incipient_liquid` use a private `_ln_k` that takes the component tuple, so they call `describe()` once per point, not per evaluation. Alternative: always request every derivative. Reversible by: `_ln_k`.
- DECISION W1-5: a `below`/`above` constant-β point returns no `k_values` and no `liquid` (the `BandTemperature` contract: "below / above: no temperature"), only its position and evaluation count. Alternative: return the clamped iterate. Reversible by: `gamma_phi._band`.
- DECISION W1-6: `admission` is written in WO-1 (it is part of `equilibrium_form.py`, §4.1) and unit-tested there; WO-3 wires it into `column.validate` and owns G8. Its probe reports a non-`ok` vapour probe as the same "vapour ln phi is not identically zero" refusal with the status appended. Alternative: leave `admission` to WO-3. Reversible by: deleting the function and its two tests.
- DECISION W1-7: G1's PH-kernel digests record **every** `ph_state` call made while `tests/test_t05*.py` (T05 and T05b) run in-process, keyed by test node id and call index, rather than a hand-built list of registered cases; the pytest exit code is part of the digest. Alternative: enumerate the registered cases from `benchmarks/t05*/reference_values.yaml`. Reversible by: `ph_digests` in `scripts/s10c_identity.py`.

## Run log

- MEASURED (WO-1, W1-3; `PYTHONPATH=src:tests .venv/bin/python scripts/s10c_band_point_probe.py`): M-a (real records, 11 feeds x beta in {0, 0.1, 0.5, 0.9, 1}, 55 points) and M-b (the 13 E-2 states x beta in {0, 0.25, 0.5, 0.75, 1}, 65 points). Literal order (Newton from the latest evaluation; `t' == t` caught by the open-bracket test, so it bisects): M-a evaluations max 1205, median 99, wall median 3.19 ms, max 37.66 ms; M-b max 727, median 165, wall median 6.95 ms, max 33.52 ms. W1-3: M-a max 234, median 28, wall median 1.01 ms, max 9.41 ms; M-b max 82, median 49, wall median 1.64 ms, max 3.69 ms. Both variants: successive-substitution steps max 61 (M-a) and 29 (M-b), equal to the note's M-a/M-b; max |T - T_prototype| 4.94e-10 K (M-a, prototype printed to 9 decimals) and 3.98e-13 K (M-b, 12 decimals) against the design's independent bisection prototype (`measured.txt` §2-§3).
- MEASURED (WO-1, G1 at `a15452e6`; `PYTHONPATH=src .venv/bin/python scripts/s10c_identity.py`): `S10C-IDENTITY PASS n=858 changed=[]` — 52 column/cascade configurations, 3 `stage_a` digests, 803 `ph_state` calls of the T05/T05b modules (1075 tests passed in each tree). Mutation check: a one-ulp scaling of SYN-001's `tp_state.enthalpy_flow` makes it FAIL (S02.P1 and the `ph_state` digests change).
- MEASURED (WO-1, G2 at `a15452e6`): `git diff --stat ffcb387f..HEAD` is empty over `src/openflowsheet/{thermo,compile,numerics,verify,application}`, `src/openflowsheet/models/c1` and `schemas`; under `tests/` only the two new files `test_s10c_band_point.py`, `test_s10c_forms.py`.
- MEASURED (WO-1, Q7): no registered test counts `describe()` calls (every spy `describe` in `tests/` delegates; the full suite at `a15452e6`: 12495 passed, 3137 skipped, 192 deselected, exit 0, 39.6 min). `ruff check .`, `ruff format --check .`, `mypy` (249 files) clean.
