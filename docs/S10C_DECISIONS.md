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

## WO-4 decisions

- DECISION W4-1: where `cascade._k_values` resolves the form (§4.9) → `composition_dependent(provider)` at its top (one `describe()` per call, SYN-001 included); for γ–φ-IG `gamma_phi._ln_k` with the caller's component tuple (name-keyed, no second `describe()`), and a provider refusal (`BandError`) re-raised as the `RuntimeError` SYN-001's branch raises, same message shape, error chained. Alternative: thread a form through `sweep_flows`/`_core_flows`/`profile_initial` (signature changes), or let `BandError` escape. Reversible by: the branch at the top of `_k_values`.
- DECISION W4-2: `profile_initial` passes `liquid=z` unconditionally; SYN-001 ignores it, so its call is today's. Alternative: branch on the form at the call site. Reversible by: the one call.
- DECISION W4-3: the details §4.9 leaves open → (a) the final flows use `x̄^m`, the relaxed composition *after* the stopping sweep's update (they differ from `x̄^{m−1}` by ≤ ω·1e-10); (b) Stage B relaxes over the core only, `x̄⁰` from §6's Thomas solution on the core stages; (c) a `sweeps_exhausted` message appends `max |dx|` for γ–φ-IG (the cause string is unchanged). Alternative: `x̄^{m−1}` for the final flows. Reversible by: `bubble_point_endpoint`, `column_blocks._build`.
- DECISION W4-4: the relaxation is one helper, `column_solve.relaxed_compositions` (with `liquid_compositions` for `x̄⁰`), reading `SWEEP_RELAXATION` at call time, used by Stage A and Stage B; M4 is one `monkeypatch.setattr(column_solve, "SWEEP_RELAXATION", 1.0)` for both. Alternative: the loop written twice. Reversible by: inlining.
- DECISION W4-5: A42's reference state → `_initial_state` builds the definition columns (`r = φ v_2`, `d = v_2 − r`, `L`, `V`, `m` by `mix`) from the YAML flows, `T` and `φ`; then `D` and every `Q` are overwritten from `ref` (intermediate `Q` = 0.0), because `_initial_state` closes `Q` from the energy rows (which would make A42's energy rows vacuous). Alternative: assemble every column in the test. Reversible by: `reference_state` in `tests/test_s10c_columns.py`.
- DECISION W4-6: M2's mutant → `GammaPhiLnKBlock._evaluated` always returns the probe `(1,…,1)` at the input `(T, P)` with the dormant flag set, so values and Jacobian describe the same (composition-independent) function; injected by patching `column.GammaPhiLnKBlock`. Alternative: values at the probe, Jacobian at `l` (an inconsistent mutant). Reversible by: `M2Block`.
- DECISION W4-7: the "constructed Stage-B opening on a Wilson specification" → C-MW cannot serve (its fixed stages 2 and 20 force an all-two-phase core: `candidates(C-MW) == ()`, likewise C-EW), so the test builds a variant: the C-MW feed as a vapour 5 K above its dew point on stage 10, a cold liquid (0.1, 0, 0.3) mol/s at 300 K on stage 11, reboiler `duty` 500 W; one candidate `(0, 10)` (an L-block below the vapour feed). It is a build-lane test fixture, not a registered case. Alternative: a smaller reboiler duty (500 W was the first value tried whose stage 20 is admissible; with the 320 K, (0.05, 0, 0.15) cold feed it is `inadmissible_endpoint(20)`, 35.8 K). Reversible by: `stage_b_spec`.
- DECISION W4-8: A35 asserts only that the M1 solve returns a typed answer; the numbers are recorded below. Alternative: gate on the measured outcome. Reversible by: `test_a35_m1_record_on_c_mw`.
- FINDING F-W4-1 (OQ-2): the absent component's column flows are **not** exactly 0.0 at the converged answers (max 1.26e-18 mol/s on C-MW, 2.18e-22 on C-EW), far below the stage flow tolerances (≥ 1.3e-5). The endpoint's are exactly zero; Newton's steps introduce them. A41 asserts ≤ tolerance, as OQ-2 rules.
- FINDING F-W4-2 (G9, §7 Q6, for the reviewer): each dispatch is one `describe()` (45 μs on SYN-001, measured), and on four S02 columns (M1–M4) the SYN-001 path makes 1751 such calls in 0.85 s of solving (`band_temperature` 743, `_k_values` 692 (WO-4), `enthalpy_flow` 287): about 9 % of the solve. The S02/S08 suites stay inside G9's +10 % (below), with a thin margin. Not optimised (memoised form resolution is a separate decision per §7 Q6).

## WO-4 run log

- MEASURED (WO-4, G7 at `c1c92533`; `pytest tests/test_s10c_columns.py`, 11 passed, 13.3 s): A40/A45 C-MW and C-EW `CONVERGED` in Stage A (no reentry), signature TWO_PHASE on stages 2–20, `acceptance_failures == ()`, item 6 ≤ 1e-4 K; validate admits both feeds. Bubble-point sweeps (ω = 1/2): C-MW 38, C-EW 53 (design §4.9 measured 45 and 62 with its prototype).
- MEASURED (WO-4, A41/A43): worst `|Δ|/tolerance` — C-MW: T 5.67e-5 (stage 15), l 3.74e-5, v 3.88e-5, T_c 8.8e-8, D 2.2e-12, x_D 1.0e-7, Q_c 1.6e-9, B 0.0, x_B 2.1e-8, Q_r 2.2e-10; C-EW: T 2.14e-8 (stage 19), l 5.8e-10, v 6.3e-10, T_c 0.0, D 1.2e-11, x_D 7.2e-12, Q_c 1.2e-11, B 0.0, x_B 2.1e-11, Q_r 3.3e-10. Newton iterations 9 (C-MW) and 4 (C-EW); observed order over the last three steps 2.19 (C-MW: residual ∞-norm 1.28 → 3.04e-2 → 8.40e-6) and 2.03 (C-EW). OQ-1: C-MW's deviations are not all below 1e-3 of tolerance (5.7e-5 is), C-EW's are; no tightening proposed. Absent flows: F-W4-1.
- MEASURED (WO-4, A42): every declared row at the reference root, max `|row|/τ_kind` 1.73e-7 (C-MW, stage 19 energy) and 5.76e-8 (C-EW, stage 7 energy); gate 1e-4, the generator's floor claim 1.2e-6.
- MEASURED (WO-4, M2 / A44): the K-block at the probe gives rows at the root of 6.63e6 τ_eq (C-MW, stage 19 eq H2O: 0.616 (mol/s)²) and 2.84e6 τ_eq (C-EW, stage 19 eq C2H5OH: 0.264), as the spec predicts (0.62, 0.26); the mutated solves converge by Newton (6 iterations each) and are refused by §8 item 6 (`AcceptanceDefectError`, bubble/dew errors ≈ 0.15–1.7 K): detected.
- MEASURED (WO-4, A35, M1 on C-MW): Stage A's Newton takes 6 steps (residual ∞-norm 95 → 53 → 26 → 5.4 → 0.22 → 0.075) and stops `BOUND_BLOCKED` (observed order over the last three 0.34, against 2.19 unmutated); the phase-update recovery accepts no trial (21 steps, out-of-domain vapour enthalpies at stage 18); the homotopy stalls (`BOUND_BLOCKED` at λ = 3/4); Stage B runs; the answer is `HOMOTOPY_STALLED`, `homotopy_stalled(BOUND_BLOCKED)` (149 accepted steps in the trace).
- MEASURED (WO-4, M4): `SWEEP_RELAXATION = 1` → C-EW's endpoint `initialization_failed(s02-bubble-point-v1, sweeps_exhausted)` after 500 sweeps; with 1/2 it is built.
- MEASURED (WO-4, Stage B, W4-7's specification): candidate `(0, 10)` built in 57 core sweeps; every target row except the continued slots within its kind tolerance, the L-block duty slot within `ENERGY_TOLERANCE`, the L-block's vapour flows exactly `+0.0` (sign bit included), the absent component exactly 0.0, overall component balance `Σ feed − d − l_20` ≤ 3.3e-16 mol/s, branch σ(0, 10).
- MEASURED (WO-4, G9, workstation, `OMP_NUM_THREADS=1`): two-phase `ph_state` (the 4 real band targets and the 13 E-2 states, median of 3 each): median 0.136 s, max 0.184 s (target 0.3 s). `solve_column` wall, compile included: C-MW 0.58 s, C-EW 0.55 s (target 120 s). SYN-001 `pytest tests/test_s02_*.py tests/test_s08_*.py` (293 tests), five alternating runs each: merge base `ffcb387f` 39.8, 36.7, 39.2, 39.6, 38.1 s (median 39.2); branch 41.7, 42.3, 41.7, 41.4, 42.9 s (median 41.7): +6.6 % by median, +8.6 % by mean (target ≤ +10 %). See F-W4-2.
- MEASURED (WO-4, G1 at `17c19fe6`): `S10C-IDENTITY PASS n=858 changed=[]`.
- MEASURED (WO-4, G2 at `c1c92533`): `git diff --stat ffcb387f..HEAD` empty over the frozen paths; under `tests/` only new files plus the S03 A04 amendment (WO-3).
- MEASURED (WO-4 at `c1c92533`): `pytest -q tests/test_s01_*.py tests/test_s02_*.py tests/test_s06_*.py tests/test_s03_*.py tests/test_s08_*.py tests/test_t05*.py tests/test_s10_*.py tests/test_s10c_*.py`: 2612 passed (394 s); `ruff check .`, `ruff format --check .` (882 files), `mypy` (250 files) clean; `tests/test_s10c_columns.py` also mypy-clean on its own.

## WO-6 (review must-fix F1): G3 against its registered references

`tests/test_s10c_band_references.py`: S10C.A01–A06 over all 103 points of `ref.band_points` (23 states), the two
`ref.theorems.T2` states, and A61. Expectations and tolerances only from `benchmarks/s10c/reference_values.yaml`.
A60 is a manifest command (WO-5's generator), not a test: it takes 75 s.

- DECISION W6-1: A05's vanishing `tm` is evaluated at the implementation's returned `T_d` (as `test_s10c_band_point.py` did), not at `ref`'s `T`; A01 already ties the returned `T` to `ref` within 1e-9 K, and the spec's floor (50-digit `tm*` at the transcription's `T_d`) is stated for the computed point. Alternative: evaluate at `ref`'s `T`. Reversible by: the state in `test_a05_the_liquid_trial_vanishes_at_every_inside_dew_point`.
- DECISION W6-2: A02's spy wraps `gamma_phi._Point.temperature` (class attribute, `pytest.MonkeyPatch.context`) and forwards every call with its arguments unchanged; each point is solved once per module through `saturation_band.band_temperature` and cached for A01–A06. No production field is added (E3). Alternative: call `gamma_phi.band_point` directly. Reversible by: `_solved`.

## WO-6 run log

- MEASURED (WO-6, `pytest tests/test_s10c_band_references.py`): 347 passed (0.9 s). Over the 103 points: worst `|ΔT|` 5.68e-13 K, `|Δx|` 4.19e-14, relative `|ΔK|` 2.22e-13 (the YAML's `measured_floors.band_point` to three digits); temperature solves equal `iterations_measured` at all 103 points, max 61 (BP-R02, β = 1).
- MEASURED (WO-6, mutations; each a temporary edit of a committed file, run against the named test, restored by `git checkout`; tree clean after): slowed contraction (`x^m` damped by 0.1) → A02 68/103 fail; an extra temperature solve at β = 0 → A02 23/103 fail; absent-component K × 1.001 → A01 77/103 fail (every point with an absent component); MB1 (`DELTA_BETA` = 1e-8) → A01 54/103 fail; MB3 (`k_values` at the feed composition) → A06 62/103 fail; `below`/`above` swapped → A03 8/12 fail; `below`/`above` carrying the clamped T → A03 8/12 fail; the temperature solve accepting `|g| < 1e-4` → A04 2/2 fail; returned T + 1e-9 K → A05 (dew) 20/20 fail; provider `tm` + 2e-12 → A05 (T2) 2/2 fail; a comment appended to `benchmarks/s10/records.yaml` → A61 1/2 fail.
- MEASURED (WO-6, A60): `python docs/derivations/scripts/s10c_reference.py --check` → "118 claims hold; reference_values.yaml matches", exit 0, 75 s.

## WO-5 decisions

- DECISION W5-1: the work package id in the manifest → `S10c`, at `evidence/S10c/<commit>/manifest.json` (the design's WO-5 row says `evidence/S10C/…`). The frozen manifest schema admits `work_package` `^[PKTMSR][0-9]{2}[a-z]?$` and `tests/test_evidence_manifests.py` requires the directory name to equal it; `S10C` validates neither. T05b and M07a are the precedent. Alternative: a schema ADR admitting an upper-case suffix. Reversible by: `PACKAGE` in `scripts/s10c_evidence_manifest.py` (and regenerating).
- DECISION W5-2: the ledger entry "S10C, `depends_on: [S10, S08]`" (design WO-5; the brief) → **not added as a package entry**: the frozen ledger schema's `package_id` is `^[PKTMSR][0-9]{2}$`, which neither `S10C` nor `S10c` matches, and T05b/M07a have no package entries either. S10-C is recorded in a comment under the S10 entry (dependencies S10 and S08, the manifest directory; S10's status unmoved). Escalated to the design lane: a package entry needs a ledger-schema ADR (frozen interface, plan §2.2). Alternative: cite the S10c manifest in S10's `evidence` (S10's status rank unchanged; mixes packages). Reversible by: the comment in `docs/requirements.yaml`.
- DECISION W5-3: the U02 restatement ("library-level support (S10-C); flowsheet selection not offered") → the rows the design names (`support_envelope.yaml` harvest entries of the S10 manifests `c4f3751e`, `f974cc87`, `f6f27c3f`, e.g. limitations[5] "no column, PH-flash or flowsheet claim") are harvest entries, and HG(b) (R-617) says the harvest only appends, so they are **not edited** (B-87's way). The restatement is the S10c manifest's first found limitation, harvested E to U02 with `wilson-ig-v1` and "library-only" in its note. `LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"]` stays `"S10"` (the package whose harvest items carry U02). The `unsupported` U02 row itself names no provider's column or PH refusal and is unchanged. Alternative: edit the old notes with an HG(b) exception. Reversible by: that one harvest entry.
- DECISION W5-4: how the generator judges the rows no test names → an explicit `CITATIONS` map (function → assertions) read from each test's docstring (A10–A14, A20–A22, A43, A45; A56 is S03's amended A04 test); name citation (`test_aNN_[aNN_]…`) only for `tests/test_s10c_*` files; A07 by G1 alone (spec: "covered by G1"); A15 ("recorded, not gated") by the generator's own `ph_state` call per PH target, recording `evaluations` beside `evaluations_measured`; A60 by the generator's `--check` (exit 0 and its "matches" line). Added required checks: `S10C.suite` (every `test_s10c_` node, including WO-1's uncited band-point, forms and region tests), `S10C.suites` (S01, S02, S06, S03, S08, T05/T05b, S10) and `S10C.G1-flowsheets` (review F6: `tests/test_t02_identity.py`, `test_t06_identity.py`, `test_t06_w14_identity.py`, `test_t07_identity.py`, `test_t08_w1_d2_replay_identity.py`, `test_t08_w1_identity_substitution.py`, `test_t08_w2_edge_identity.py`; T05/T05b's run with `test_t05`). G2 checks the frozen paths against `git merge-base main HEAD` (as S08's), since `main` was merged into the branch after `ffcb387f`, plus the test-edit allow-list (S03 A04, `test_m07a_harvest.py`). Alternative: rename the tests to cite by name; leave F6 to the full gate. Reversible by: `CITATIONS`, `REQUIRED_CHECKS`.

## WO-5 run log

- MEASURED (WO-5, manifest `evidence/S10c/8f38f9636e55aaf25d140f932a17e5111c6e7704/manifest.json`, generated at `8f38f963` from a clean tree, 745 s): `tested`, 46 of 48 checks pass (gate and CI `unsupported`). Nodes: `S10C.suite` 716 passed; `S10C.suites` 2243 passed (S01 138, S02 187, S06 179, S03 310, S08 106, T05/T05b 1075, S10 248); `S10C.G1-flowsheets` 57 passed (F6); G1 `S10C-IDENTITY PASS n=858 changed=[]`; A60 "118 claims hold; reference_values.yaml matches"; G2 empty over the frozen paths, edited tests only `tests/test_s03_s11_refusal.py`; ruff, format, mypy exit 0. Per assertion: A01, A02, A06 103 nodes each, A05 22, A03 12, A30/A31 44, A56 6.
- MEASURED (WO-5, A15, recorded not gated): `ph_state` evaluations equal the transcription's `evaluations_measured` at 11 of 17 targets; PH-2T 55 against 54, PH-NPL 47 against 51; the four refusals (PH-OB, PH-OA, PH-1OB, PH-N2) take 2 and register no count.
- DECISION W5-5 (harvest classes of the `8f38f963` manifest, build-lane draft for design-lane review; S10's B-84/B-86/B-91 for `wilson-ig-v1` items, S08's W5-9 and S09's for the kinds of item): limitations[0] (nothing about a real mixture), [1] (fixture record sets), [7] (the restatement: library-level support, flowsheet selection not offered; W5-3), [12] (numerical verification, not validation; W4-7 a fixture) → E to U02; [2] (no column claim beyond C-MW/C-EW: uniqueness, openings, ternaries, kinds, flowsheet use) → E to U02, U04, L19, L20; [3] (T5 binaries only) and [8] (E4: P1–P3 for the committed sets only) → E to U02, L19; [4] (constant-β convergence measured, not proved) → E to U02, L20; [5] (G7 tolerances an acceptance image), [6] (no self-generated expectation), [9] (requirements empty, ledger comment; W5-2), [10] (gate, CI, G9), [11] (review), [13] (harvest follows) and checks `S10C.gate`, `S10C.ci` → P. Every E note names `wilson-ig-v1` and "library-only". Alternatives: [12] → E to L18 (S08's way for SYN-001); [2] without L20. Reversible by: editing those entries before merge, then `t08_support_matrix.py --emit`.
- MEASURED (WO-5, harvest; `pytest -q tests/test_m07a_harvest.py tests/test_t08_*.py tests/test_requirements_ledger.py`: 579 passed, 2 skipped): 16 entries (14 limitations, 2 non-pass checks), 112 lines appended, 0 deleted; the old envelope a byte prefix of the new (HG(b), R-617). `HARVEST_SIZE` (56, 794, 95) → (57, 808, 97), pinned in `tests/test_m07a_harvest.py`. `--emit` regenerated `docs/support-matrix.md` (S10c: E 8, P 8); `--check`: 0 problems.

## S10-C diag: C-MW's aarch64 `HOMOTOPY_STALLED` (CI run 40275276182)

Build-lane facts for the design lane (§7 Q4: typed outcome recorded, no tuning). Script `scripts/s10c_cmw_diagnose.py`
(observation-only spies; answer bitwise unchanged under them). aarch64 record: dispatch run 40285056440 on scratch branch
`wp/S10C-diag` (job `s10c-diag`, `ubuntu-latest` and `ubuntu-24.04-arm`, artifacts `s10c-diag-*`).

- MEASURED (sweeps): bitwise identical on local x86-64 (Haswell OpenBLAS kernel), CI x86-64 (AVX-512) and CI aarch64 —
  38 sweeps, last `max|ΔT|` 1.101e-10 K, last `max|Δx|` 6.24e-11, `x_K` 220287be…, `x⁰` df415fd9… (0 of 282 columns
  differ). The sweeps' stop rule, the band point and the profile are not where the machines part.
- MEASURED (first divergence): inside Stage A's first Newton solve, from its first linear solve (residual after step 1
  76.08204046654282 local, …648461 on both CI runners). It turns material on the **absent component** (C2H5OH; 60 free
  columns, exactly `+0.0` at `x⁰`, exact Newton step zero). While all 60 sit at zero, any step whose roundoff direction
  points out has `α_max = 0` and R-064 releases them (`d := 0`); a step whose 60 roundoff entries are all `≥ 0` is taken
  as is and lifts them to ~1e-15 mol/s. From then on they are no longer exactly on the bound, R-064 cannot release them,
  and each step's `α_max` is capped by roundoff-sized absent flows landing on zero.
  - local x86-64: lift at iteration 5; one cap, α_max 0.828 (stage 20 `l.C2H5OH`) at iteration 7; `CONVERGED` in 9.
  - CI x86-64: lift at iteration 5; caps 0.294 (stage 2 `l`), 0.972 (18 `l`), 0.99994 (19 `v`); `CONVERGED` in 10
    (final state differs from local: `6f8b7a0e…` vs `b69d2a2a…`; worst A41 ratio 8.1e-7 vs 5.7e-5).
  - CI aarch64: lift at iteration 2; cap 0.186 (stage 1 `r.C2H5OH`) at 3; at 4 `α_max = 0`, `BOUND_BLOCKED` on
    `COL.stage.1.r.C2H5OH` (value 0.0, not a watched variable: no phase update). Edge 3's homotopy stalls at
    λ = 2045/2048 (`resolution`, 23 trials, 11 rejected, inferred `phase_boundary_on_path(COL.stage.17)`); Stage B runs
    with 0 candidates (`candidates(C-MW) == ()`, W4-7); answer `homotopy_stalled(BOUND_BLOCKED)`, worst 739.7 on B.
  - BLAS threads: no effect, bitwise, on all three (`OPENBLAS_NUM_THREADS` 1, 2, 8, 48, unset locally; 1 and unset on
    CI). OpenBLAS kernel does: locally `OPENBLAS_CORETYPE=Prescott` and `=Sandybridge` end `HOMOTOPY_STALLED` (Sandybridge:
    α_max 0.057 at iteration 3 on stage 7 `v.C2H5OH`, then `phase_disappeared(COL.stage.20, vapor, COL.stage.20.v.C2H5OH)`);
    `Nehalem` `CONVERGED` in 8 (other hash); `Haswell` = default.
- MEASURED (how close x86-64 is; 320 local solves, 40 seeds × 8 perturbations of 1–4 ulps: `x⁰` every column ±1 and ±1…4
  ulp; profile ±1…2 ulp; 10 % of sweep bubble temperatures, sweep K values, Newton step entries, or `math.exp`/`log`
  results in the Wilson/γ–φ/cascade modules (1 % and 10 %) ±1 ulp): **160 end `HOMOTOPY_STALLED`** (156
  `homotopy_stalled(BOUND_BLOCKED)`, 4 `(STAGNATION)`), 55 fail the first solve and are recovered by edge 3, only **105
  converge directly**. 215 first solves end `BOUND_BLOCKED` at iterations 2–10, every blocker a C2H5OH flow (199 read
  as `phase_disappeared`). By kind (fails/40): x⁰ 25 and 19, sweep T 27, sweep K 25, libm 23 and 24, Newton step 16,
  profile 1 (most profile perturbations sweep to the same bitwise `x⁰`). The sweep count is 38 in all 320. x86-64 passes
  by the sign pattern of roundoff, not by margin.
- MEASURED (causal check, scratch harness only, not a remedy): the same 320 solves with the absent component's Newton
  direction set to exactly 0 every step: **320/320 `CONVERGED` in 9 iterations**, worst A41 ratio 1.3e-7.
- FINDING F-D-1 (C-EW passes on aarch64 for the same reason it would anywhere): it converges in 4 iterations, the first 3
  released (60 absent CH3OH columns, `d := 0`) and the 4th final; no step is taken after a lift. F-W4-1's absent flows of
  1.26e-18 mol/s at C-MW's answer are this lift.
- ESCALATION (design lane; touches R-064, not decided here): candidate remedies — (a) apply R-064's release on every step,
  not only at `α_max = 0` (R-064 "Watch for" names this; needs its inertness proof, affects every region solve and the
  identity gate); (b) a component absent from every inlet of a column as a structural zero (flows pinned `+0.0`, rows
  dropped; R-064 rejected pinning absent components as a form in general — a column- or case-scoped form needs an ADR);
  (c) register C-MW/C-EW on a two-component record set (removes the absent component; a new registered case per §7.1);
  (d) keep the typed outcome as an aarch64/BLAS-kernel limitation (Q4 default) — then A40/A41/A42 are
  platform-dependent, which R-627's classes do not cover. A roundoff threshold on outward directions is R-064's rejected
  alternative and is not proposed.

## R-782 (absent-component release)

Build lane, work orders WO-R1/WO-R2 of `docs/derivations/S10C-absent-component.md` §5. Local x86-64 workstation (Haswell
OpenBLAS kernel), `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`; the suite as one pytest process per test file, 44 in
parallel (the note's §4.6 set-up).

- RUN (WO-R1, detector `scripts/s10c_release_detector.py` on `b3151d65` + the plugin): plain suite 13217 passed, 12
  failed, 3137 skipped; under `-p s10c_release_detector` the same counts and the **same failed set** (the 12 are
  `test_t01_structural.py`, which fails when its file runs alone: test order, as §4.6 found). `DETECTOR acting_tests=12
  acting_iterations=180 released_calls=384`. **D equals §4.6's 12 tests**: `test_s10c_columns.py` A35 (C-MW, 11
  iterations), A40–A45 [C-MW] and [C-EW], A44 [C-MW] and [C-EW] (1 each, `|Z*| = 60`, max `d` 6.22e-15 and 3.84e-22);
  `test_t05b_contract.py` B08/B10 [SC-3] (1, `|Z*| = 8`); `test_t06_f4_edge3.py` G3 [SC-3] (2, `|Z*| = 8`);
  `test_t06_w20_counters.py` A93 [THM-08-3] (1, 6), [THM-08-12] (2, 5 and 6), [THM-09-4] (1, 10);
  `test_t07_interrupt.py` `test_interrupt_at_every_record` (151, 10) and `test_interrupt_at_record_k[THM-09-4]` (7, 10).
  Every acting entry is roundoff (largest 6.22e-15).
- RUN (WO-R1, T06 ensemble at `f9122cc7`, detached clean tree, outputs outside the repository): nominal `r782-pre`
  440 starts, `SUCCESS` 434, `F-BUDGET` 3, `F-FALSE-SUCCESS-CAUGHT` 3; `holdout1` 440, `SUCCESS` 436, `F-BUDGET` 2,
  `F-FALSE-SUCCESS-CAUGHT` 2. No generation or process errors.
- RUN (WO-R2 step 1, G-R1/G-R4): `tests/test_k03_r782_release.py` 5/5 and B33c i–v pass; (i) and (v) fail on
  `f9122cc7` (the tests see the change). Full suite on the step-1 tree: the failed set is WO-R1's plus exactly
  `test_a93_run_1s_budget_starts_record_the_cap` ×3 and `test_interrupt_at_record_k[THM-09-4]` (§4.7 items 3–4), and
  `test_m07_journey` A21, which refuses an uncommitted `newton.py` (carry identity; passes once committed, below).
  `S10C-IDENTITY PASS n=858 changed=[]`; `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL` (registered line).
- RUN (WO-R2 step 2, G-R5, measured on this workstation): A93 uncapped `SUCCESS` in 245 / 279 / 424 property calls
  (THM-08/3, THM-08/12, THM-09/4); capped at the test-local 100: `BUDGET_EXHAUSTED`, `property_calls` =
  `requested_evaluations` = 100 on all three. T07 THM-09 start 4: 94 records / 49 plan events / `CONVERGED` uncapped;
  24 / 14 / `BUDGET_EXHAUSTED` at the test-local cap. `test_t07_interrupt.py` 16/16, `test_t06_w20_counters.py` all pass.
- RUN (at `e88f72a9`): full suite 13225 passed, 12 failed (WO-R1's `t01_structural` file-alone set, unchanged), 3137
  skipped. ruff check, ruff format, mypy (250 files) clean.
- RUN (G-R2, local x86-64): 320-solve perturbation campaign 320/320 `CONVERGED`, first Newton solve 9 iterations in all
  320, worst A41 ratio 1.2949e-7. `OPENBLAS_CORETYPE` default/Prescott/Sandybridge/Nehalem: 4/4 `CONVERGED` in 9,
  worst 1.2941e-7 / 1.2941e-7 / 1.2938e-7 / 1.2946e-7 (`COL.stage.15.T`). Absent flows at the answer: C-MW 60/60
  C2H5OH columns and C-EW 60/60 CH3OH columns exactly `+0.0` (C-EW `CONVERGED` in 4, worst 2.1396e-8, unchanged).
- RUN (G-R6, `pytest tests/test_s02_*.py tests/test_s08_*.py`, alternating `f9122cc7` / `e88f72a9`, 3 each): before
  35.0, 34.8, 35.0 s; after 34.5, 34.5, 34.7 s; median change −1.2 % (≤ +2 %).
- RUN (G-R7 local half, T06 ensemble at `e88f72a9` against WO-R1's, by record, wall times excluded): nominal 13 of 440
  moved — `F-BUDGET` → `SUCCESS` THM-08/03, /12, THM-09/04; `SUCCESS` → `SUCCESS` STA-02/01, /03, /14, THM-07/13,
  THM-08/14, /17, THM-09/11, /14, /15, /16 (`SUCCESS` 437, `F-FALSE-SUCCESS-CAUGHT` 3); holdout 13 of 440 moved —
  `F-BUDGET` → `SUCCESS` THM-09/24, /35; `SUCCESS` → `SUCCESS` NUM-03/26, STA-02/22, /23, /27, /30, /36, /38,
  THM-07/34, THM-08/28, /37, /38 (`SUCCESS` 438, `F-FALSE-SUCCESS-CAUGHT` 2). **Equal to note §4.6's table; no
  regression.** WO-R3 (CI dispatch, aarch64 G-R3, CI half of G-R7) is the orchestrator's.
- RUN (WO-R5, R-785, local x86-64): A41 asserts the 60 absent flows `== 0.0` per case (IEEE equality, sign not
  asserted; the message names each nonzero variable). `pytest -k a41` 2/2 pass (C-MW, C-EW). Scratch mutation (not
  committed) setting one absent flow to `1e-300` before the assertion: 2/2 fail with
  `AssertionError: {'COL.stage.5.v.C2H5OH': 1e-300}` (C-MW shown).
