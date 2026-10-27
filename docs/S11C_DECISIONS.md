# S11 track C — build decisions (WO-C1…C5)

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
- DECISION C3-2: a saturated isentropic variant whose beta_s falls outside [0, 1] (the isentropic state is single-phase) → the same code `isentropic_state_two_phase` (a `DomainError` in the block, `isentropic_state_two_phase(<U>)` in the evaluate), since §4.3/§4.4 name one "wrong side" refusal; the detail says the state is single-phase. Alternative: a new code (`isentropic_state_single_phase`). Reversible by: `blocks.isentropic_state`.
- DECISION C3-3: `additive-vapour` is implemented in `IsentropicEnthalpyBlock` against the `PropertyProvider` Protocol (VAPOR s and h at e_j, T and P derivatives only, as §4.3/§4.6 state v2 answers) and admitted by identity (`ADDITIVE_VAPOUR`); with `wilson-ig-v2` absent (WO-D4), it is verified on a test-local constant-c_p ideal gas that claims the Wilson identity: Hs against the closed-form isentrope (≤ 1e-11), A46 FD worst 1.8e-10 at 20 states, the dormant probe rule. The block's `component` argument takes a tuple for this variant. Alternative: defer the variant to D4. Reversible by: the `additive-vapour` branch of the block. Re-test on v2 at D4/D5.
- DECISION C3-4: the additive-vapour (Wilson) compressor and turbine (§4.4: inlet face via `tp_state.single_phase_enthalpy`, vapour h-inversion, `stability()` on the outlet) need `wilson-ig-v2` (WO-D4) → `ThermalMachine` admits the identity (`admitted_identity(..., additive_vapour=True)`) and then refuses it at construction, typed `specification_unsupported(<U>.provider)` naming D4/D5; no rows, no evaluate, never a placeholder success. The pump on Wilson stays `provider_not_admitted(thermal.pump)`. Alternative: write the Wilson evaluate now against the Protocol and test it on a fake (the block's math is done, C3-3; the outlet inversion and stability are D1/D5 surface). Reversible by: the `ADDITIVE_VAPOUR` branch of `ThermalMachine.__post_init__`; D4/D5 wire it.
- DECISION C3-5: machine bound codes (§4.4 "follow the SYN-001 pump's") → `pressure_fall(pump)`, `pressure_fall(compressor)`, `pressure_rise(turbine)`, status `out_of_domain`, as the SYN-001 pump and valve name theirs. Alternative: the unit id in the parentheses. Reversible by: `ThermalMachine._bound_code`.
- DECISION C3-6: A55's dry fluid → n-Pentane (S07 table, tier B; Q19), saturated vapour 1 → 3 bar: `isentropic_state_two_phase(U1)`; the `pure-sat/sat` state agrees with CoolProp's PS flash (beta_s 4.7e-15 relative, T 1.3e-12 K). Alternative: none needed.
- DECISION C3-7: §4.4's machine bind refusals are also enforced at construction (`SpecificationError`, `specification_unsupported(<U>.inlet|outlet|isentropic_phase)`, `efficiency_outside_interval`), as C2's heater does, so a directly built unit cannot hold one; `isentropic_phase` on a pump or compressor is refused the same way. A turbine with a vapour outlet may declare `isentropic_phase = vapor_liquid` (`pure-*/sat`; tested at eta = 0.3 and 0.1). Alternative: leave them to C4's binder only. Reversible by: `ThermalMachine.__post_init__`.

## WO-C4 (binding)

- DECISION C4-1: where the one `_PARAMETER_KINDS` entry (`outlet_vapor_fraction` → `dimensionless`, units design §2.4) goes → after `efficiency`, away from the table's end where I1's sixteen column entries go (R-825; no key collides, so the risk is only textual). Alternative: append. Reversible by: moving the line.
- DECISION C4-2: the thermal builders do not call `instance_contract`, whose converse of R4 refuses a `vapor_liquid` outlet of any model that is not an `outlet`-style lifting model in `SPLIT_RULES` → `thermal_binding` reads parameters and wiring itself with the binder's codes (`parameter_unsupported/missing`, `port_unwired`, `port_direction_unsupported`, `port_multiplicity_unsupported`) and reuses `revision_binding`'s private `_column`, `_pin`, `_pinned`, `_missing_choice_hint`. Alternative: teach `instance_contract` the pure-fluid form (track A's file; I1b). Reversible by: the helpers `_parameters`/`_wired`.
- DECISION C4-3: the turbine's `isentropic_phase` ("a choice given as `syn001.heat_exchanger` takes `specification`") → not expressible: the exchanger chooses by which pin is set, a revision parameter is a numeric Quantity, and §2.4 admits one new parameter name only. The builder leaves it at its default, the outlet's form; a parameter `isentropic_phase` is `parameter_unsupported`; the §4.4 row "`isentropic_phase = vapor` with outlet `vapor_liquid`" is enforced at construction only (C3-7). Escalated as Q-C2. Alternative: a numeric code parameter (a new interface). Reversible by: `_machine`.
- DECISION C4-4: the heater's optional parameters `pressure_drop` (default 0) and `outlet_vapor_fraction` have no `ModelSignature` field → read by the builder, unlisted (as track B's `column_binding` leaves the column's optional parameters); the one-of is reported as `specification_missing(<U>.specification)` / `specification_conflict(<U>.specification)` (the choice's options plus the parameter), the missing hint ending "; or give the parameter outlet_vapor_fraction (a vapor_liquid outlet)". Alternative: a signature field (frozen `ModelSignature`, served by `list_models`). Reversible by: `_heater`.
- DECISION C4-5: the §4.4 refusals come from the units' construction refusals (C2, C3-7), translated `SpecificationError("specification_unsupported(...)\n<hint>")` → `RevisionError("unsupported", code, hint)`, so code and hint have one source; the heater's one-of and a Wilson machine's non-vapour port (L-GP-2) are the builder's own, before construction. Every other construction refusal (`efficiency_outside_interval`) stays the binder's `value_outside_model_domain`, as the SYN-001 pump's. Alternative: re-state each check in the binder. Reversible by: `_construct`.
- DECISION C4-6: parameters → `thermal.mixer` none (the K02 mixer's zero-only `pressure_drop` is not carried; §4.4 says only "adiabatic"), `thermal.valve` none, `thermal.flash` requires `pressure_drop` (as `syn001.ph_flash`), the machines require `efficiency`. Alternative: the mixer accepts `pressure_drop = 0`. Reversible by: the signatures.
- DECISION C4-7: configuration → `{"specification": <pin or parameter name>}` for the heater plus each material port's form (`LIQUID|VAPOR|SATURATED`) for all seven, so a form or mode change moves the label (tested). `BASES`: the two pure-fluid bases; compressor and turbine gain `wilson-ig-v2` at D5. Reversible by: `_port_forms`, `BASES`.
- DECISION C4-8: the C4 identity run showed branch shard 13 failing on `test_t07_global_state::test_g20` (a C1/C2 defect: the two `@cache`s `models/thermal/common.py:_artifact_hash` and `models/thermal/kernel.py:_limits` were never registered with G20) → both entered in `tests/data/t07_global_state_allowlist.json` with their justification and the per-line count 33 → 35, as S05 and S07 registered theirs. Alternative: drop the caches (an `_artifact_hash` per manifest call). Reversible by: that commit.

## Open questions for the design lane

- Q-C1 (C1-4): A46 asks for a central difference within 1e-6 of the saturation range's ends at a 1e-6 relative step and
  a 1e-6 agreement. At the top end (water, p_σ(647.0 K)) the provider's Maxwell floor makes that unattainable at any
  admissible step. Default taken: the measured floor is added there (bounded ≤ 1e-4). Needs: confirmation, or a
  restated A46 clause for the range ends.

- Q-C2 (C4-3): the turbine's `isentropic_phase` cannot be stated in a revision (no string-valued parameter; §2.4 adds
  one parameter name). Default taken: the outlet's form; a wet isentropic state with a vapour outlet is reachable by
  direct construction only. Needs: accept the restriction, or name the encoding (a parameter name and its values).

## Open observations for the reviewer (C3, C4)

- O-C3-1 (C1 kernel, not changed): the `h` closure at 22.85 MPa, h* ≈ 47.8 kJ/mol (supercritical, near the
  pseudo-critical line) returns `not_converged`: the root sits at the provider's LIQUID/VAPOR label switch at T_c
  (S05 §4.2), where the labelled h is discontinuous. 4 of 11 200 grid outcomes (C3-1's grid); before and after C3-1.

- O-C4-1 (R4, not changed): a revision declares one phase per port, so a revision's `thermal.mixer` cannot take a
  liquid and a vapour inlet together (`port_phase_ambiguous(<U>.inlet)`); S11.A56's first case stays a
  direct-construction case. C6's TH-R1 (both inlets liquid) is unaffected.

## Handoff after WO-C3 (2026-10-27; C3 done, C4 not started)

Branch `wp/S11-c` (worktree `.claude/worktrees/s11-c`), not pushed. C3 commits: 36ea9175 (kernel `_solve` R-600
fix, C3-1), c673ebf8 (isentropic variants, C3-2/C3-3), 1e602650 (machines, C3-4..C3-7). No shared file touched;
`scripts/s11_identity.py` not triggered (only `models/thermal/*` and S11 thermal tests).
Gates (no-CoolProp | CoolProp 8.0.0): `test_s11_thermal_kernel.py` 70 passed 52 skipped | 122 passed;
`test_s11_thermal_units.py` 37 | 37; `test_s11_thermal_machines.py` 58 passed 2 skipped | 60 passed.
pure-single/single proved bit-identical (values and Jacobians, 20 states + dormant) across the C3 block rewrite.
A46 FD worst (20 states each): pure-sat/single L 3.4e-7, V 3.0e-10; pure-single/sat 1.2e-9; pure-sat/sat 1.5e-9;
additive-vapour 1.8e-10 (test-local ideal gas). A53/A54/A55 against CoolProp ≤ 1.4e-12 relative, ≤ 1.4e-10 K.

**Next: WO-C4 (binding)** — `application/thermal_binding.py`, `tests/test_s11_thermal_binding.py`, and one
`_PARAMETER_KINDS` entry (`outlet_vapor_fraction` → `dimensionless`, units note §2.4) in `models/revision_flowsheet.py`.
- R-825 (S11-design §10.6) gives I1 sixteen *column* entries in the same table and rejected B3 "because the file is
  track A's"; it does not cover `outlet_vapor_fraction`, so there is no semantic conflict. Track A is merged, so the
  remaining risk is textual: add the one entry apart from where I1's sixteen go, and log it (C4-1).
- Builders construct `ThermalHeater/Valve/Mixer/Flash` (C2) and `ThermalMachine(machine=...)` (C3) with
  `streams` (port → stream ids) and `forms` (stream id → LIQUID|VAPOR|SATURATED from the declared
  `phase_capability`); constructors already raise every §4.4 refusal as
  `SpecificationError("specification_unsupported(<U>.<what>)\n<hint>")` — the binder maps them to
  `Unbound("unsupported", ...)`; Wilson compressor/turbine raise `specification_unsupported(<U>.provider)` (C3-4).
- Turbine `isentropic_phase` arrives as a choice like `syn001.heat_exchanger`'s `specification`.
