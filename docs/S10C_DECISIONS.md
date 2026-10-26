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

## WO-2 decisions

- DECISION W2-1: where `ph_state` and `_closure_rows` resolve the form → `form_of(capabilities)` on the `describe()` each already makes (no extra call on the SYN-001 path); the composition-dependent rows are a separate `_liquid_k_rows`, so SYN-001's loop is untouched. Alternative: `composition_dependent(provider)` (one more `describe()` per call). Reversible by: the two dispatch lines.
- DECISION W2-2: `evaluations` of a §4.5 `ph_outside_domain` refusal → `2` (both domain-end enthalpies are computed before step 2), today's value. Alternative: count band-point or flash evaluations. Reversible by: `_region_route`, `_single_phase_route`.
- DECISION W2-3: the liquid/vapour route re-evaluates both ends of its interval (bitwise the values step 1/3 already hold, two `h` calls) and counts them as today's bracket does (`evaluations=2` at start), so §4.5 item 6's refusal and the bisection are one function `_single_phase_route`. Alternative: pass the known end values in. Reversible by: `_single_phase_route`'s signature.
- DECISION W2-4: the band route is today's `_band_route`, unchanged (it recomputes `band_point` at β = 0 and 1, deterministic and bitwise equal to steps 1–3's); its `None` return, unreachable after steps 2–3, maps to a typed `ph_ill_conditioned` with an explanatory line rather than a raise. Alternative: pass the band ends into `_band_route` (changes a SYN-001 signature). Reversible by: `_region_route`'s band branch.
- DECISION W2-5: the one-component `T_sat` bisection is a new `_pure_saturation` (K from `gamma_phi.ln_k` at the pure liquid; returns `below`/`above` so the no-sign-change side is known without another evaluation), leaving SYN-001's `_saturation_temperature` untouched; `_saturation_split` is reused unchanged and its `(lo, hi)` half-domain selects the liquid (`(T_min, T_sat)`) or vapour route. Refusals inside §4.5 are surfaced as `band end: …`, `saturation temperature: …`, `closure rows: …`, `<phase> enthalpy at T = … K: …`, `TP flash at T = … K: …`. Reversible by: those helpers.
- DECISION W2-6: `region._admissible` for γ–φ-IG (§4.10) → `gamma_phi.ln_k` at the liquid side's **normalised** composition `x` (not its flows), `incipient_liquid` at the vapour side's `y`; an empty side stays `(True, 0.0)` as in the SYN-001 rule; dispatch by `composition_dependent(provider)` after the pr-c1 test (one extra `describe()` on the SYN-001 branch, metadata only). Alternative: pass flows and let the provider normalise. Reversible by: `_gamma_phi_admissible`.
- DECISION W2-7: M3's mutant (A22) → `ph_state` with the dispatch disabled (today's temperature route through the provider's TP flash), `_closure_rows` replaced by `_liquid_k_rows` so only the route differs, and the band-route fallback removed (the fallback is the remedy under test). Measured: with the fallback kept the result is the same, 13/13 states `ph_not_converged` (the TP flash inside the bracket), so the choice does not change detection. Reversible by: the mutant in `tests/test_s10c_ph_kernel.py`.

## WO-2 run log

- MEASURED (WO-2, G4 at `3962f664`; `pytest tests/test_s10c_ph_kernel.py`): all 17 YAML `ph_targets` as registered (13 `ok`, 4 typed `ph_outside_domain`); worst `|T* − T_ref|` 5.12e-13 K (tolerance 1e-9), worst `|β* − β_ref|` 1.22e-15 (1e-10); TP-flash calls 0 on every real/ideal target, 1 on PH-N1/N2/N3. A15 (recorded, not gated) `evaluations` vs the generator's `evaluations_measured`: equal on 11 of 13 solved targets; PH-2T 55 (54), PH-NPL 47 (51).
- MEASURED (WO-2, G5 at `3962f664`): 13/13 E-2 states `ok`, route `band`; worst `|T* − T_ref|` 5.68e-14 K (tolerance 1e-10), worst `|β* − β_ref|` 1.44e-15 (1e-9); closure rows recomputed from `evaluate_phase` within FLOW/EQUILIBRIUM/ENERGY tolerances; 0 TP-flash calls. `evaluations` 48–55 (generator 48–55; E2-01 51 (52), E2-02 55 (52), E2-03 50 (52)). Wall time per E-2 `ph_state` median 0.117 s, max 0.143 s; G4 two-phase targets median 0.146 s (G9 bound 0.3 s; recorded here, G9 is WO-4's).
- MEASURED (WO-2, M3): today's TP-flash temperature route in place of §4.5 → 13/13 E-2 states `not_converged` / `ph_not_converged` (the provider's flash inside the bracket), with or without the band-route fallback; detected by G5.
- MEASURED (WO-2, G1 on the WO-2 source): `PYTHONPATH=src python scripts/s10c_identity.py` → `S10C-IDENTITY PASS n=858 changed=[]`.
- MEASURED (WO-2, G2): `git diff --stat ffcb387f` empty over `src/openflowsheet/{thermo,compile,numerics,verify,application}`, `models/c1`, `schemas`; under `tests/` only new files (WO-1's two, WO-2's `test_s10c_ph_kernel.py`, `test_s10c_region.py`).
- MEASURED (WO-2): `pytest tests/test_t05*.py tests/test_t05b*.py tests/test_s10_*.py tests/test_s10c_*.py tests/test_m02_wo8_region.py` 1975 passed; orchestrator-importing `tests/test_k03*.py`, `tests/test_m02*.py` 406 passed; `ruff check .`, `ruff format --check .`, `mypy` (249 files; the two new test files separately) clean.

## WO-3 decisions

- DECISION W3-1: the specification-kind rule (§4.8) → an allow-list `column.GAMMA_PHI_KINDS` (refuse any end kind not in it), checked in `_column_refusal` through a new optional `form` argument after S10 and before `_inverse_refusal` (I1). After S2 it refuses exactly `INVERSE_KINDS`. Alternative: refuse `INVERSE_KINDS` by name; or a separate call in `validate` (would need `_column_refusal` split). Reversible by: the block before `return _inverse_refusal(spec)`.
- DECISION W3-2: the blocks' dormant test → `StreamState.is_dormant` (every flow exactly ±0.0, ADR 0001 D3.1), not the note's literal `sum(l) == 0.0`. They coincide for non-negative flows; `is_dormant` does not treat a mixed-sign iterate summing to zero as dormant. Alternative: the literal sum. Reversible by: `GammaPhiLnKBlock._evaluated`, `MixtureEnthalpyFlowBlock.values/jacobian`.
- DECISION W3-3: the probe is a module function `gamma_phi_blocks.probe_flows(count)` (looked up at evaluation time) so that S10C.A36 can monkeypatch it to `(2, 1, 1)`. Alternative: a constant. Reversible by: inlining it.
- DECISION W3-4: `validate`, `energy_precheck` and `declared_rows` each resolve the form with one `equilibrium_form(provider)` (one more `describe()` on the SYN-001 path, which §4.12 allows; G1 PASS). `admission` keeps its own `describe()` (WO-1's signature). Alternative: return the form from `admission`. Reversible by: the three call sites.
- FINDING F-W3-1 (design §4.7, "their derivatives … whatever the block returns"): over-claimed. The equilibrium row's direct entry `∂(v_i L − K_i l_i V)/∂l_i = −K_i V` reads the K-block's value, so at a dormant liquid it is the probe's K. The VAPOR regime pins those liquid columns and drops those rows, so nothing it solves for moves; `test_a36_…` asserts every row value and every other Jacobian entry bitwise unchanged under the `(2, 1, 1)` probe and that the moved entries are exactly `−exp(lnK_i^probe)·V`. On an exactly dormant liquid in a TWO_PHASE solve (e.g. a Stage-B opening with exact zeros on the L-block, WO-4) the probe fixes Newton's direction from that iterate, not a converged value. The same holds for the total condenser's bubble row at `V_2 = 0`. For the reviewer; no code change proposed.
- FINDING F-W3-2 (spec §5.4 prose vs YAML): the prose places the VAPOR H block at `(v_j, T_j)`; `blocks.fd_states` (and the generator's `fd_errors`) evaluate both H phases at the listed `n` (= `l_j`, or `v_2` for the condenser). The tests follow the YAML, which governs.
- NOT DONE (A35 record): C-MW's Newton iterations and observed order under M1 need WO-4's column solve; WO-4 records them (the mutant is `tests/test_s10c_blocks.py::M1Block`).

## WO-3 run log

- MEASURED (WO-3, G6 at `28f77e98`; `tests/test_s10c_blocks.py`, §5.4 stencils): FD vs block Jacobian, max relative error over the 44 `blocks.fd_states` — K 3.76e-8, H LIQUID 1.93e-8, H VAPOR 1.08e-8 (tolerance 1e-6; equal to the generator's `fd_floor_measured`); every stencil point in the provider's domain; `∂H/∂P` and its central difference exactly 0.0. Closed forms at the 12 `closed_form_states`: worst 3.11e-15 relative (tolerance 1e-12). A31 (Jacobian bitwise the provider's), A33/A34 (dormant convention, no dormant request) and A36 pass. M1: minimum relative error 0.499 over the 40 C-MW/C-EW block states (≥ 1e-2 required). M5: the counting spy sees the dormant request.
- MEASURED (WO-3, G8 at `6b6b1460`; `tests/test_s10c_refusals.py`): A50 (pr-c1-v1, pr-lib-v1, iapws95-v1, coolprop-heos-v1 — all constructible), A51 (three identity spies), A52 zero evaluations; A53 exactly one VAPOR probe at n = (1, 1, 1), T = 350 K, P = 1.15e5 Pa; A54 for each inverse kind at either end, `stage_band`/`saturation_temperature` not reached; A55 the cascade's S11 unchanged; A56 S03 A04 amended. C-MW with the real records validates (`None`).
- MEASURED (WO-3 at `6b6b1460`): G1 `S10C-IDENTITY PASS n=858 changed=[]`; G2 empty over the frozen paths, in `tests/` only new files plus the S03 A04 amendment; `pytest -q tests/test_s01_*.py tests/test_s02_*.py tests/test_s06_*.py tests/test_s03_*.py tests/test_s08_*.py tests/test_s10c_*.py`: 1227 passed (265.6 s); `ruff check .`, `ruff format --check .`, `mypy` (250 files) clean.
