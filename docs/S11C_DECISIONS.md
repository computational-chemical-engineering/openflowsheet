# S11 track C — build decisions (WO-C1…C3)

Normative design: `docs/derivations/S11-units-design.md` (ADR 0051 Proposed; R-813…R-821). One line per open
choice; the evidence is in the named test or module. Batched for the package's single `reviewer` pass.

## WO-C1 (kernel, state, blocks, references)

- DECISION C1-1: B2's `UnitEvaluation.owned` is not on `wp/S11` (it is on `wp/S11-b`), and `models/__init__.py` is track B's file → `models/thermal/state.py` bridges it as `ThermalEvaluation`, a subclass with B2's exact field and its failed-evaluation rule, selected only while the base lacks the field. Alternative: edit `models/__init__.py` or wait for B2. Reversible by: deleting the `else` branch once B2 merges (the conditional already picks `UnitEvaluation` then).
- DECISION C1-2: S11.A43/A44 at grid points where CoolProp's quality is exactly 0 or 1 → the kernel may land in the adjacent single-phase regime (in-tree and CoolProp IAPWS-95 differ by ~1e-12 relative in h_sat; measured: water β=0 at 1 atm lands LIQUID 4.4e-12 K below T_sat); such a point passes iff the regime is the adjacent one and |T − T_sat| ≤ 1e-5 K. Alternative: compare regimes literally (an ill-posed comparison at a boundary). Reversible by: `_agrees` in `tests/test_s11_thermal_kernel.py`.
- DECISION C1-3: S11.A46's "≤ 1e-6 relative" is judged in scaled units, relative to max(|∂F/∂x|, |F/x|) → entries whose elasticity is ≥ 1 get the literal relative test; entries far below their output's scale (liquid dh/dP, dilute-vapour dh/dP, the pump's dHs/dP_I) are below the difference quotient's rounding at a 1e-6 step (measured up to 2.9e-2 literal-relative, ≤ 4.4e-7 scaled) and are pinned by identities to 1e-9 (dh/dP = v − T dv/dT; dHs/dP_I = −n T_s (dv/dT)_I). Alternative: a larger FD step (contradicts A46's step). Reversible by: `_fd_worst`.
- DECISION C1-4: S11.A46 at P = p_σ(647.0 K)(1 − 1e-6) → the central quotient is at the provider's Maxwell floor (≈ 1.5e-12/h relative; one-sided stencils add near-critical truncation, −2.6e-5 at 1e-5), so no admissible step reaches 1e-6; the criterion there adds the measured floor |D(h) − D(h/2)|, itself bounded ≤ 1e-4, and the plain criterion holds at 1e-4 below the top. Alternative: drop the top-end state. Reversible by: `test_a46_saturated_flow_block_at_the_top_of_the_range`. (Escalated as Q-C1 for the design lane.)
- DECISION C1-5: the closure solve's first iterate (§4.2 fixes the method, not the start) → the secant point of the bracket ends, else the midpoint; the isentropic solve starts from T_I (§4.3). Alternative: midpoint. Reversible by: `kernel._solve`.
- DECISION C1-6: refusal statuses → `phase_regime_mismatch` and `isentropic_state_two_phase` are `unsupported` (as `inadmissible_phase`); `carried_split_missing` is `error` (a defect, §4.1). Alternative: `out_of_domain`. Reversible by: `kernel.Mismatch.failure`, `state.carried_fraction`.
- DECISION C1-7: S11.A42's CoolProp pressures must lie in the provider's saturation range (its T_lo bounds it) → CO2 1.5/3/6 MPa, R134a 0.1/0.5/2 MPa, N2 0.2/0.5/2 MPa. Alternative: none (1 MPa CO2 and 0.1 MPa N2 are refused `no_saturation`). Reversible by: `SATURATION_PRESSURES` in the reference script.

## WO-C2 (heater, valve, mixer, flash)

- DECISION C2-1: a saturated outlet's owned columns and every typed refusal name a stream, which `evaluate` (keyed by port) cannot know → each thermal unit is built with its port → stream map and a per-stream declared form, as B2's `ColumnUnit` is built with its streams; `contribute` refuses another wiring. Alternative: owned keyed by port, translated by the traversal. Reversible by: the `streams`/`forms` fields and `common.check_wiring`.
- DECISION C2-2: `declared_equations()` and the manifest describe the instance's configuration (the mode's one specification row; `sat-T`/`sat-split` only when an outlet is saturated), all `unconditional` within it. Alternative: one model-level list with the alternatives folded into a `TH-spec` family (the `syn001.heat_exchanger` precedent). Reversible by: `declared_equations` in heater/valve/mixer.
- DECISION C2-3: what the four (and C3's machines) share lives in a new module `models/thermal/common.py` (ports, stream faces, saturated rows, inlet enthalpy, outlets, manifest), inside track C's package. Alternative: duplicate it per unit module. Reversible by: inlining.
- DECISION C2-4: the mixer authors K − 1 rows beyond its own unknowns (`TM-pressure:<k>` for every inlet, as K02's `MIX-pressure`), which fix upstream pressures in a flowsheet; A50's "square" is asserted as rows = unknowns + K − 1 for it. Alternative: none within §4.4. Reversible by: `_check_face`.
- DECISION C2-5: dormant labels → heater and drum at (T_I, P_I − ΔP), valve at (T_I, P_spec), an all-dormant mixer at the first inlet's (T, P); saturated dormant outlets carry β = 0.0 and owned V = L = 0.0. Alternative: none stated in §4.4 beyond "the inlet's T and the outlet P". Reversible by: each unit's dormant branch.
- DECISION C2-6: thermal manifests → `package: S11`, `evaluation_cost_class: moderate`, `thread_safety` from the provider's `describe()` (CoolProp is `not_thread_safe`). Alternative: copy SYN-001's `cheap`/`not_thread_safe`. Reversible by: `common.manifest`.

## WO-C3 (isentropic variants, machines)

- DECISION C3-1: `kernel._solve` reset `previous` to infinity after a bisection forced by the Newton point leaving the bracket, against R-600 (S05's rule, which §4.2/§4.3 name: `previous` is the last raw Newton correction, infinity only after a non-positive slope) → fixed to R-600. Measured on a 40 × 40 (P, h|s) water grid (11 200 kernel outcomes): 7 liquid floor states (residual noise ≈ 6e-13 in s near T_t) went from `not_converged` to converged (root residual ≤ 1e-12 T dg/dT), 2 converged liquid states moved within the floor (≤ 3.1e-15 relative), all others bit-identical; C1/C2 tests unchanged. Found by C3: the pump block's FD stencil at (1 kPa sat. liquid → 3 MPa) hit it. Alternative: avoid such states in the tests (hides a defect). Reversible by: the one-line `previous = step` in `_solve`; `test_solve_keeps_the_newton_correction_through_a_bisection`.

## Open questions for the design lane

- Q-C1 (C1-4): A46 asks for a central difference within 1e-6 of the saturation range's ends at a 1e-6 relative step and
  a 1e-6 agreement. At the top end (water, p_σ(647.0 K)) the provider's Maxwell floor makes that unattainable at any
  admissible step. Default taken: the measured floor is added there (bounded ≤ 1e-4). Needs: confirmation, or a
  restated A46 clause for the range ends.

## Handoff after WO-C2 (2026-10-27; context cap reached, C3 not started)

Branch `wp/S11-c` (worktree `.claude/worktrees/s11-c`). Commits: 90dd308b (C1 references), 7340f4cb (C1 kernel),
9ec97a45 (C2 units). Not pushed. No shared file touched; `scripts/s11_identity.py` not triggered.
Gates: `tests/test_s11_thermal_kernel.py` 66 passed / 52 skipped without CoolProp, 118 passed with it;
`tests/test_s11_thermal_units.py` 37 passed (no CoolProp needed). `s11_thermal_reference.py --check` OK with CoolProp,
SKIP without. CoolProp for references/tests: `PYTHONPATH=<scratchpad>/cp:$PWD/src:$PWD` (8.0.0, pip --target).

**Next: WO-C3 (machines)** — files `models/thermal/machines.py`, the variants in `blocks.py`,
`tests/test_s11_thermal_machines.py`; acceptance S11.A50 (machines), A53–A55.
- `blocks.IsentropicEnthalpyBlock` implements only `pure-single/single` (`VARIANTS`); add `pure-sat/single`,
  `pure-single/sat`, `pure-sat/sat` per §4.3 (inputs n, P_I, P_O for sat inlets; β_s and its P derivatives from
  `kernel.Sat` (`value`, `along`), dHs/dn = the intensive bracket) and `additive-vapour` (Wilson, inputs n_1..n_C).
  `kernel.isentropic_temperature` is the single-phase inner solve (start T_I; `isentropic_state_two_phase` on the
  wrong side). FD test helper `_fd_worst` (scaled criterion, C1-3) is in the kernel test; reuse it.
- `additive-vapour` needs `wilson-ig-v2` (WO-D4, not on this branch): `ADDITIVE_VAPOUR` identities are in
  `models/thermal/__init__.py`; build it against the Protocol, test with D4 merged (or log as deferred to C3b).
- `machines.py`: one class configured pump/compressor/turbine (families TPU/TCO/TTU). Copy `heater.py`'s shape and
  `common.py` helpers; W column `models.syn001.pump.work_id(U)` (kind heat_rate, R-043); pump/compressor work row
  `models.rows.work_row(W, eta, (PFs_<U>.Hs,), (inlet key,))`; turbine `thermal.rows.expansion_work_row`;
  `F-energy` = `energy_row((inlet,), (outlet,), source=W)`; F-P = `specification_row`; saturated turbine outlet via
  `common.saturated_rows`. Return `work=` (duty None) in `ThermalEvaluation`.
- Evaluate (§4.4): inlet β exact for a saturated inlet (pump β=0, compressor/turbine β=1), else
  `inadmissible_phase(inlet, LIQUID|VAPOR)`; bounds as the SYN-001 pump (`pressure_fall(pump)` out_of_domain; mirror
  for the turbine); W = n(h_s − h_I)/η or η n(h_s − h_I); outlet by `kernel.declared_state(..., "h")`.
- Turbine `isentropic_phase` ∈ {vapor, vapor_liquid}, default the outlet's form; refuse `vapor` with a saturated
  outlet (`specification_unsupported(<U>.isentropic_phase)`, §4.4 table); pump inlet vapor / compressor inlet liquid /
  turbine liquid-liquid refusals likewise at construction.
- References already in `benchmarks/s11/thermal_reference.yaml`: `units.A53_turbine`, `A54_pump`,
  `A55_compressor` (CO2: needs CoolProp, skip without), `A55_dry_fluid` (n-Pentane sat. vapour 1→3 bar: CoolProp's
  isentropic state is SATURATED — Q19 answered: n-Pentane is in the S07 table, tier B; log it in C3).
- Block id `PFs_<U>` obeys the backend token rule: test unit ids without hyphens.
