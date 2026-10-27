# E01 track A — build decisions and facts

Design: `docs/derivations/E01-design.md` (ADR 0052 Proposed; R-850…R-862). One line per choice
(`DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`); facts as `FACT:`. Folded into
the single `reviewer` pass (§5.1).

Identity check per commit (§4.14, A1 at the branch base): `git diff --stat f8a68fed..HEAD --
src/openflowsheet/{compile,thermo,models,verify,orchestrator,numerics,application,adapters,graph,ir,run,units}
src/openflowsheet/{canonical,compiled,serialize}.py src/openflowsheet/studies/{trust_region,sensitivity.py,sweep.py,estimation.py}`
must be empty. (`main...wp/E01` also shows S11's own changes until S11 merges, so the base is E01's
merge commit `f8a68fed`.) A2 (`scripts/s11_identity.py`) runs the whole suite in two trees and is
I1's.

## WO-A1 (core)

- FACT (§4.2.3 memo, Q16): `ParametricTwin.__init__` passes one `symbols` mapping to every row of a pass, but
  `_build` makes a fresh pins mapping per row (same value objects); `_builds` (failure path only) rebuilds a row
  with a different pins mapping. `reference.row_values` passes one `symbols` and `spec.parameters` to every row.
  Verified by `tests/test_e01_a_core.py::test_the_twin_and_the_reference_pass_one_mapping_to_every_row_of_a_pass`.
  The memo is enabled.
- DECISION: memo key → identities of (variables, block outputs, algebra) plus the identities of the pinned *values*,
  previous pass's objects held so no id is reused. Alternative: the variables mapping's identity alone (§4.2.3's
  wording), which would hand `_builds`' culprit search a row built with other pins. Reversible by: `_Memo.row` key.
- DECISION: contributors given to `AssessmentProgram.build` → keyword-only `contributors=` (default: the
  `register_contributor` registry in `cost, lca, derived` order). Alternative: registry only (a test toy would
  pollute it). Reversible by: dropping the keyword.
- DECISION: request refusals of `evaluate`/`twin`/`linearize` → returned as `Refusal` (the union return), as `build`
  does; evaluation domain failures raise `TwinEvaluationError` (§4.2.3). Alternative: raise a typed exception.
  Reversible by: the three methods' returns.
- DECISION: `twin(())` → compiled over the first non-structural parameter (a `ParametricTwin` needs ≥ 1); its column
  is never exposed. Alternative: an artificial anchor θ in every program. Reversible by: `AssessmentProgram.twin`.
- DECISION: `linearize` → the decisions are always symbols of the twin (columns reported only for `symbolic`), so
  `∂/∂x` is taken at the decision values. Alternative: refuse decisions not in `symbolic`. Reversible by: `linearize`.
- DECISION: a held regime naming an entry the program lacks → `ASSESSMENT_REGIME_INADMISSIBLE` (detail "entries
  the program lacks"). Alternative: ignore the extra entry. Reversible by: `build`.
- DECISION: `select` when the held regime cannot be evaluated at `x` (`TwinEvaluationError`) → release every entry
  to the rule. Alternative: propagate the error. Reversible by: `select`.
- DECISION: the float path maps a complex power (negative base of `**(1/3)`) to `TwinEvaluationError`, as CasADi's
  NaN is. Other `TypeError`s propagate. Reversible by: `_float_rows`.
- DECISION: `view_of` molar masses → the `selectable_bases()` entry with the provider's id over the same component
  set (`RevisionFlowsheet` does not carry its basis). Alternative: a `molar_masses=` argument. Reversible by:
  `views._basis`.
- DECISION: `UnitRef.parameters` → the unit's `Contribution.parameters` keyed by full pin ids; `structure` → the
  unit object. Reversible by: `views._unit_ref`.
- DECISION: schema field names the note does not spell (item inputs, `utilities[]`, `materials[]`, `lca` exchanges,
  `derived` numerator/denominator, `defaults` keys) → named after the note's symbols (`schemas/assessment.schema.json`,
  `defaults.py`), `additionalProperties: false` throughout, `schema_version: "assessment-v1"`; `functional_unit`
  sits under `lca` as §4.11 lists it. Later WOs extend it. Alternative: an open schema until A4/B2. Reversible by:
  the schema file (no fixture yet).
- DECISION: admissibility nominal of every `size` row → `S_max` (§4.3.1's example), set by the contributor.

## WO-A2 (sizing)

- FACT (§4.4.0 model ids, registry): `MODEL_ID` constants — thermal: `thermal.{heater,flash,mixer,valve}`,
  `thermal.{pump,compressor,turbine}` (`models/thermal/machines.py:78-82`); syn001: `syn001.{tp_heater,tp_flash,
  ph_flash,heat_exchanger,column,kinetic_cstr,conversion_reactor,adiabatic_mixer,stream_splitter,feed_source,
  product_sink,valve,component_separator,cascade}` and **`syn001.liquid_pump`** (the note's `syn001.pump` does not
  exist); C1: `c1.{tp_heater,tp_flash,reactor,reactor_standin,adiabatic_mixer,stream_splitter,feed_source,
  product_sink}`. Registered in `assessment/sizing/families.py::_TABLE`; `syn001.cascade` (absent from §4.4.0) falls
  to `NO_SIZING_MODEL`.
- FACT (ids read): duty `models.duty_id(U)` = `<U>.Q` (heaters, flashes, reactors, `syn001.heat_exchanger` as the
  hot side's sink); `<U>.Q_spec` the pinned duty (thermal heater Q mode, thermal flash, ph_flash); work
  `models.syn001.pump.work_id(U)` = `<U>.W` (also the thermal machines); streams `<S>.n.<c>`, `<S>.T`, `<S>.P`;
  saturated streams `<S>.sat.V`/`<S>.sat.L` (`models/thermal/state.py`); column (`models/syn001/cascade.py`)
  `<U>.stage.<j>.{v.<c>,l.<c>,T,P,Q}`, condenser duty `<U>.stage.1.Q`, reboiler `<U>.stage.<N>.Q`, stage 1 top;
  `ColumnStructure.{stage_count,condenser,reboiler,pressures}` via `UnitRef.structure.structure`. Ports: heater
  `inlet/outlet`, flash `inlet/vapor/liquid`, machines `inlet/outlet`, exchanger `hot_inlet/hot_outlet/cold_inlet/
  cold_outlet`, reactors `inlet/outlet`.
- FACT (§4.4.3 saturation routine, named): `models/thermal/kernel.py::saturation` (T_sat(P), dT_sat/dP) and
  `phase_properties(…, ("v",))` at (T_sat, P) per phase; no existing v_sat routine, so
  `SaturatedVolumetricFlowBlock` chains the two (`dv_sat/dP = ∂v/∂T·dT_sat/dP + ∂v/∂P`), as
  `SaturatedFlowBlock` does for h. Providers offering `v`: iapws95, coolprop-heos, pr-c1 (liquid only pure NH3),
  pr-lib (vapour only). **No `v`:** syn001, wilson-ig, wilson-ig-v2 (also their ideal-gas vapour).
- DECISION: block ids → ordinals `ASMVF_<k>` in construction order. Alternative: sanitised stream names (`U-FLASH`
  fails the backend token rule; sanitising can merge ids). Reversible by: `blocks.volumetric_block_id`.
- DECISION: a pure fluid's block requests only (T, P) derivatives, `∂v/∂n = 0` (intensive; the thermal blocks' rule);
  a mixture requests `n_<c>` too and refuses a missing one. Reversible by: `VolumetricFlowBlock.__init__`.
- DECISION: utility rule 2 compares `price.value / factor(per)` for energy `per`s only (§4.5.6), as stated — no
  escalation across currencies/years before WO-A4's basis exists; a utility without an energy price, `T_supply` or a
  ΔT_min is not an `auto` candidate. `T_return` absent → equal to `T_supply` (isothermal). Alternative: escalate first.
  Reversible by: `families._price_per_joule`.
- DECISION: utility temperatures and ΔT_min are per-item θ (`asm:item.<item>.T_supply|T_return|dT_min`), not shared
  `asm:utility.<u>.*`, so two items on one utility never collide in the functional spec's parameters. Alternative:
  one θ per utility with dedup. Reversible by: `families.exchanger_utility`.
- DECISION: a duty item is omitted when `<U>.Q_spec` is pinned at 0.0 even if `<U>.Q` is also a host variable (thermal
  flash). A study decision moving that pin later finds no duty item (§4.4.0's "not a decision" is not visible at
  build). Reversible by: `families._duty_item_needed`.
- DECISION: `N_act = ⌈N_tr/E_o⌉` with `E_o` read as its decimal repr (`Fraction(repr(E_o))`): 7/0.7 → 10, not
  binary64's 11. Reversible by: `families.actual_trays`.
- DECISION: column condenser/reboiler services are forced (cooling/heating) but kept as `service` entries with their
  sign rows; a column shell refusal does not remove them. The condenser/reboiler carry no phase-change limitation
  (no process streams). Reversible by: `families._Column.plan`.
- DECISION: a conversion reactor's outlet phase for `V̇_out` = the provider's TP-flash label at the planning state;
  two-phase or unanswered → `SIZING_INPUT_UNAVAILABLE(<U>.vessel.v)`. Alternative: a declared phase. Reversible by:
  `families._Reactor.plan`.
- DECISION: a pump whose inlet `v` is unavailable keeps `size.<U>.power` and refuses only `vol_flow`/`head` (the cost
  entry decides). The drum refuses whole when either product's `v` is unavailable. Reversible by: `_Machine`, `drum`.
- DECISION: `size.<item>.volume` of a drum is §4.4.4's `V = τ V̇_L/φ_fill` even when the vapour member controls D.
- DECISION: `SizedItem.duty`/`.power` carry builders (|Q|, consumed/generated electric power) for WO-A4's OPEX, not
  output ids (the catalogue has no such ids). Reversible by: `sizing.SizedItem`.
- Tests: `tests/test_e01_a_sizing.py` 15 passed (A9; A10 + utility auto/U-required; A13 ×3 bitwise on iapws95 liquid,
  pr-lib vapour mixture with n-derivatives, iapws95 saturated; SYN-001 items/refusals, area = formula at rel 1e-13,
  twin = reference ≤ 1e-13, FD gradient on 3 columns; TH-R1 drum (D, L, V, controlling) and pump (V̇, head, drive)
  by hand at rel 1e-12; TH-C1 boiler/condenser areas rel 1e-13, turbine, limitations; M1 column refusal +
  condenser/reboiler by hand; M1 shell D_j², j*, D, H on a `v` test provider). A11/A12 need B4's hand cases.

## Escalations (open)

- **ESC-A1 (schema identity partition; blocks green on 4 tests).** `schemas/assessment.schema.json` declares
  `applies_to.configuration_sha256` (§4.11 names it). T08's sha256 partition (`scripts/t08_numerical_policy.py`
  `schema_sha256_names`, `benchmarks/t08/numerical_policy_v2.yaml`) classifies every `*sha256*` property of every
  schema; `configuration_sha256` is classified only in M02's addendum, so it is now unclassified in v2. Failing:
  `test_m04_numerical_policy.py::test_a37_the_sha256_partition_follows_the_schemas`,
  `test_m02_schemas.py::test_g1_the_sha256_partition_holds_over_m02s_schemas`,
  `test_t08_adr0025.py::test_a1_the_policy_file_is_what_its_generator_emits` and `…a_tampered_policy_file_fails_its_audit`.
  (`report`'s schema at A5 adds `assessment_sha256`, `state_sha256`, `regime_sha256`.) Neither file is in E01's
  ownership (§5.1) and §4.14 did not list them. Proposed (M05/M04 precedent): an E01 addendum in `ADDENDA` with its
  own policy table classifying the assessment schemas' names, so v2's content does not move. Not taken: renaming the
  note's field, or editing v2 (moves a registered policy file). Owner to decide: I1 / design lane.
  (`test_m07_journey.py::test_a21_…` failed only on the uncommitted tree: it compares HEAD to the working tree.)

- **ESC-A1 ruled (orchestrator, 2026-10-27).** DECISION: E01 sha256 names (ESC-A1) → an E01 addendum in ADDENDA, as
  M04/M05 (`benchmarks/e01/numerical_policy_external.yaml`, id `E01-numerical-policy-external-v1`, schemas
  `[assessment.schema.json]`, `exact_sha256: []` — `configuration_sha256` keeps M02's class; A5 adds
  `assessment-report.schema.json` with `assessment_sha256`, `state_sha256`, `regime_sha256`, which the audit lets an
  addendum list only once a schema declares them). Alternative: rename the field. Reversible by: reverting that
  commit. v2 bytes unchanged (`--check`: equals, sha256 `6b449911…d707c`). Amended on purpose (ADR 0052):
  `tests/test_m05_study_record.py::test_the_m05_addendum_is_audited_after_m02s_and_its_partition_holds` pinned
  `ADDENDA` to `[m02, m05]`; now `[m02, m05, e01]`. **For I1:** add that node id to `AMENDED_TESTS`
  (`scripts/s11_identity.py`, S11's file, not edited here).
- **ESC-A2 (open, for A5/B2/I1).** `study.schema.json` and `optimization-report.schema.json` are in v2's own partition
  (no addendum names them), and v2's audit demands `declared == float_digests ∪ exact_sha256` there. §4.11's additive
  `assessment {assessment_sha256, regime_sha256}` in those two schemas will therefore fail `--check` unless v2 moves
  or the auditor learns that an addendum may classify names in schemas it does not own. Proposed: an E01-addendum key
  `classifies_in: [study.schema.json, optimization-report.schema.json]` whose names v2's audit subtracts — an auditor
  change, so a design-lane ruling. Not needed until those schemas are edited.

- **ESC-A4 (open, design lane).** (i) `syn001.kinetic_cstr` carries no volume parameter (Damköhler form,
  `kinetic_cstr.py:9`); §4.4.0 says "volume = its volume parameter". Taken: refusal `SIZING_INPUT_MISSING(<U>.vessel.
  volume)`; the duty item stays. Alternative: size it as the conversion reactor (`τ_R·V̇_out`, `residence_time_s`).
  (ii) A drum whose liquid product is dormant but which declares `liquid_molar_volume`: ρ_L = M̄_L/v_decl has no M̄_L
  (no liquid composition). Taken: the V member is refused `SIZING_INPUT_UNAVAILABLE(<item>.rho_L)` regardless.
- **ESC-A5 (open, for I1/B4).** No registered column basis offers `v` (syn001, wilson-ig-v2), so P3's shell and trays
  are refused `SIZING_INPUT_UNAVAILABLE(<U>.shell.v)` and A12's hand case has nothing to compare on a registered case;
  the condenser and reboiler are sized. The shell formula is exercised on M1's stages with a test provider answering
  only `v` (`test_column_m1_shell_formula_on_a_volume_test_provider`). Likewise P2 (SYN-001): the drum is refused.
  Needs: a column case on a `v`-capable basis, or a ruling that the ideal-gas vapour volume RT/P is the providers' `v`.

## Facts confirmed before WO-A3 (2026-10-27)

- FACT (Q7, pinned release): IDAES-PSE **2.13.0** (PyPI upload 2026-09-16, > 2 weeks old; latest). Wheel
  `idaes_pse-2.13.0-py3-none-any.whl` sha256 `2b67301afe6dc0c2f0e7342253ebcbab6e91607c0204d9bd663a2735f1ec85f9`
  (matches PyPI); obtained by `pip download --no-deps --only-binary=:all:` into a scratch dir, never installed.
  `idaes/models/costing/SSLW.py` (1770 lines) sha256 `362b0a22e78ad578c4ce6408224aa6193fc6330cb7041fc1d4aaee0e060b1184`;
  `idaes_pse-2.13.0.dist-info/licenses/LICENSE.md` sha256 `4fdde00bd663a045a688899c7e6924bd3b747204518e75540273c97f4bc98fa0`
  (BSD-3-Clause text, "IDAES PSE Framework Copyright (c) 2018-2026 … All rights reserved."; METADATA `License: BSD`);
  `idaes/core/base/costing_base.py` sha256 `cdd71f362a2b59e5c1ed4261e8811f7fc749d0999aba0d01d32ad1999b0bfc38`.
  SSLW.py's header notice (lines 1–12) is the verbatim notice for `sslw-idaes-v1.json`'s `source.notice`.
- FACT (Q7, coverage): SSLW 2.13.0 costs `cost_heat_exchanger` (HXType floating_head, fixed_head, Utube, Kettle_vap;
  10 materials; tube length 8/12/16/20 ft), `cost_vessel` / `cost_vertical_vessel` / `cost_horizontal_vessel`
  (10 materials; trays Sieve/Valve/BubbleCap, 5 tray materials; platforms and ladders), `cost_fired_heater`,
  `cost_compressor` (Centrifugal/Reciprocating/Screw; drives ElectricMotor/SteamTurbine/GasTurbine),
  `cost_fan`, `cost_blower`, `cost_turbine`, `cost_pump` (Centrifugal/ExternalGear/Reciprocating; motor
  open/enclosed/explosion_proof), `cost_pressure_changer`. Every day-one family of §4.4 has an SSLW entry
  (exchangers, drums/vessels, column shell + trays, pump + motor, compressor, turbine, reactor as vessel).
  Base: "Chemical Engineering base cost index of 500" (`USD_CE500`, SSLW.py:343).
- FACT (Q7, CE 500 → year): IDAES's own currency table (`costing_base.py:81–85`) gives CEPCI 2005 = 468.2,
  2006 = 499.6, 2007 = 525.4: **2006** is the year whose index is nearest 500. The note's default stands
  (`year_equivalent: 2006`, limitation `INDEX_BASIS_MAPPED`). CEPCI values are recorded here as a fact only, never
  shipped (D6).
- FACT (Q13, byte pins): no test pins the bytes or hash of `schemas/study.schema.json`,
  `schemas/optimization-report.schema.json` or `schemas/registry.json`. `registry.json` is checked structurally
  (`test_t08_w4_package_data.py` A48: sorted, one name per line, equals the schema directory and the published set):
  passes with `assessment.schema.json`. Pins that do bite: (i) T08's sha256 **property-name** partition (ESC-A1);
  (ii) `test_t08_w4_package_data.py::test_the_package_data_patterns_cover_exactly_what_is_packaged` will fail when B
  adds the `_data/assessment/**/*.json` glob unless `src/openflowsheet/resources.py` `PACKAGED` gains the path —
  `resources.py` is in no track's ownership (escalate at B1/I1); (iii) M07's R3 carry pathspecs include all of
  `src/openflowsheet` (`tests/test_m07_journey.py:796`), so the R3 carry identity of the release journey moves with
  any E01 source file — an RC-time fact, not a test failure. `AMENDED_TESTS` stays empty so far.

## Handoff (2026-10-27, context cap) — resume from here

- **Done:** WO-A1 (commits `66b71db0` schema+registry, `1ea9bb60` core). `tests/test_e01_a_core.py` 19 passed;
  ruff/format/mypy clean on `src/openflowsheet/assessment`. Protected-path diff vs `f8a68fed`: empty.
  Schema-touching suite (37 files): 2463 passed, 5 failed = ESC-A1's 4 + m07 A21 (passes once committed).
- **Not done:** WO-A2 (sizing), WO-A3 (cost data and forms). Pre-A3 facts above are confirmed; IDAES source is
  re-obtainable with the same `pip download` (hash above). Nothing of A2/A3 is started.
- **Next (A2):** `assessment/blocks.py` `VolumetricFlowBlock` (§4.4.3; read `thermo.PropertyProvider.evaluate_phase`
  and the S11 saturation routine, record the names), `assessment/sizing/__init__.py` (`FAMILIES`, `register_family`)
  and the families §4.4.1–§4.4.7 as `ContributionPlan` pieces using `program.Symbols`/`OutputDef`/`Theta` and
  `regimes.RegimeEntry`/`AdmissibilityRow` (pattern: the `Toy` in `tests/test_e01_a_core.py`). The size regime
  belongs to the cost entry (A3/A4), sizing outputs are `size.<item>.<q>`. Tests `tests/test_e01_a_sizing.py`:
  A9 (Underwood numbers), A10 (hand case in §6.1), A13; A11/A12 need B4's hand cases.
- **Next (A3):** `cost/forms.py`, `cost/sets.py`, `_data/assessment/cost/sslw-idaes-v1.json` (every number with
  `source_line` into SSLW.py 2.13.0; notice = SSLW.py:1–12), `cost/index.py`, the three series files (BLS WPU11,
  Eurostat C28 euro area, FRB G.5A) with licence text; read them with `importlib.resources.files("openflowsheet")
  .joinpath("_data", "assessment", …)` (not `resources.packaged`, which refuses unlisted paths). A16–A19.
- **API notes for A2+:** builders never branch on symbols; choices come from `ctx.regime.choice(id)` or the rule on
  floats via `ctx.evaluate(state, [OutputDef…], theta, blocks)`; admissibility rows are `AdmissibilityRow(row_id,
  build, nominal)` published as `adm.<entry>.<row_id>`; a refusal is `program.Refusal(code, target, detail)` in the
  plan, never raised.
