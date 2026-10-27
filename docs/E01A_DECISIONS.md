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

## WO-A3a (links, §9.1)

- Done as ruled: `$defs` `assessment_link`, `formulation_assessment` in `schemas/assessment.schema.json`; E01 addendum
  `exact_sha256: [assessment_sha256, regime_sha256]`, comment corrected (`state_sha256` keeps v2's float-digest class).
  `--check` exit 0, v2 sha256 `6b449911…d707c` unchanged. `tests/test_e01_a_links.py` 4 passed; with core, m04 A37,
  m02 G1, t08_adr0025, m05 study record, t08_w4 package data: 297 passed. The study/optimization-report `$ref`s are B3's.

## WO-A3 (cost data and forms, §9.2)

- DECISION: the drive item's family id → `machine.drive` (§9.2.4 V names it; A2 had `drive`). Alternative: keep
  `drive` and list it in the set's family. Reversible by: reverting the rename commit (2 lines in `sizing/`).
- Done: `assessment/cost/{__init__,forms,sets,quotes,index}.py`; `_data/assessment/cost/sslw-idaes-v1.json` (8 entries in
  §9.2.4's order); `_data/assessment/index/{bls-ppi-wpu11-annual-v1,eurostat-ppi-c28-ea-annual-v1,frb-g5a-annual-v1}.json`;
  `tests/test_e01_a_cost.py` 28 passed (A16, A17 bitwise, A18 incl. CasADi empty row, A19, A44 forms incl. the vessel hand
  case, F_NT, F_P floor, r, η_m, motor η guard; A45 five refusals; twin = float on all 8 entries rel 1e-14). With core,
  sizing, links: 66 passed; t08_w4 + adr0025 + m04 A37: 62 passed; ruff/mypy clean; nothing under compile/thermo/models.
- FACT (transcription): the set file was emitted by scratch tool `a3tools/sslw_set.py` (scratchpad) from a hand
  transcription; each of its 208 literals (coefficients, defaults, range texts) was checked to be printed on the line it
  cites in SSLW.py 2.13.0 / costing_base.py: 0 mismatches. Values are the decimals as printed (`0.09790`, `-0.2330`).
  Anchors that differ from §9.2's: thickness text cites :532-533, :634-635 (§9.2.4 says :643-644); pressure range :492;
  pump method lines :1387-1623; motor :1624-1677; CE 394 value `394.0` from costing_base.py:66.
- FACT (D04, for B's inventory; sha256 of the shipped file): `cost/sslw-idaes-v1.json` `0ee43c89…0364` (BSD-3-Clause
  IDAES; notice SSLW.py:1-12 and LICENSE.md verbatim inside, `licence_text_sha256` `4fdde00b…8fa0`);
  `index/bls-ppi-wpu11-annual-v1.json` `1c36f463…a578` (1939-2025; raw `fredgraph.csv?id=WPU11&fq=Annual&fam=avg`
  sha256 `2431424989fd…`; US public domain, citation requested); `index/eurostat-ppi-c28-ea-annual-v1.json`
  `a16dad15…5529` (2000-2025, I21, EA20; raw API JSON `a344c0d00c70…`; CC BY 4.0 / Decision 2011/833/EU);
  `index/frb-g5a-annual-v1.json` `0be39293…78a6` (EUR 1999-, GBP/CHF/JPY 1971-, CNY 1981- to 2025; FRED AEX* copies;
  US public domain). All retrieved 2026-10-27; full raw hashes inside each file. Raw files: scratchpad `series_dl/`.
- DECISION: BLS WPU11 and G.5A retrieved as FRED's copies (`fredgraph.csv`) → download.bls.gov refuses clients without
  a contact address in the user agent and data.bls.gov is bot-gated. Cross-checks: WPU11 2024/2025 equal BLS's own
  M13 (API v1: 179.313, 186.200); G.5A 2022-2025 equal the 2026-01-05 release page in all five currencies. Alternative:
  BLS flat files with a contact user agent (needs an address Frank approves). Reversible by: replacing the two files.
  (One early probe to download.bls.gov sent Frank's e-mail address as user agent: an error, not repeated.)
- DECISION: Eurostat geo → EA20 (fixed composition; the euro area through 2025). Alternative: EA21 (from 2026; equal to
  EA20 at 1 decimal except 2000). Reversible by: re-running the series tool with geo=EA21.
- DECISION: an option the entry has but which does not apply under the chosen options (`pump_type_factor` on a
  non-centrifugal pump) → `NO_CORRELATION` with the reason. IDAES ignores it silently. Alternative: ignore, report
  `used: false`. Reversible by: `sets._resolve` `applies_when` branch.
- DECISION: a drive (motor) at its size floor keeps the machine's N: `C_P = N·C_P1(W_m,min)` (`Selection.n`).
  Alternative: one motor. Reversible by: `forms.select` (inherits_units branch).
- DECISION: an extrapolated side has no admissibility row; the other side's row stays (`forms.rows`).
- OPEN for A4 (schema): the document has item `material`, `subtype`, `tray_type`; the SSLW options `hx_type`,
  `tube_length`, `weight_limit`, `platforms_ladders`, `pump_type`, `pump_type_factor`, `tray_material`, `motor_type`,
  `compressor_type`, `drive_type` and θ `shell_thickness` have no field. Proposed for A4: item `options: {name: string}`
  (names as the set file's) and `shell_thickness` (m), `material` → `material`, `tray_type` → `tray_type`, `subtype` →
  the entry's type option. Not done in A3 (no consumer yet).
- NOT DONE in A3: generic-v1 factor terms (constant material/type factors, piecewise log-polynomial pressure, count) and
  the two bare-module forms: the loader checks §4.5.2's layout, `resolve` raises NotImplementedError for generic-v1. No
  shipped set uses them; implement with A4's contributor or when a user set needs them.

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

- **ESC-A3 (open, design lane; blocks A3's forms and set file).** The pinned SSLW.py 2.13.0 does not fit §4.5.1's
  forms (κ an exact unit factor; F_M/F_T constants; pressure a piecewise log-polynomial or "ASME thickness"):
  (a) HX base `exp(α1 − α2 ln(1.1·S) + α3 ln²(1.1·S))`, S ft²/unit, oversize 1.1 (SSLW.py:391-425) — 1.1 is not a
  unit factor; material factor `A + (S/100 ft²)^B`, size-dependent (:438-469); pressure factor
  `0.9803 + 0.0180 p + 0.0017 p²`, p = psig/100, a polynomial (:478-498); no size range in the file (the note's
  150–12 000 ft² is the book's). (b) Vessels: shell thickness is an input, default 1.25 in (:513), no ASME
  computation; W = π(D+t)(L+0.8D)·t·ρ_m lb (:661-669); base log-quadratic in W (:673-699); W ranges only in a
  docstring (:534); platforms/ladders and trays are **additive** (:719-776, :777-868), tray material factor linear
  in D, count factor `max(1, 2.25/1.0414^N)`. (c) Pump and motor base costs are `USD_CE394` (:1579-1661; IDAES
  `USD_CE394 = 500/394 USD_CE500`, costing_base.py:66), not CE 500; motor η_m(W) = 0.80 + 0.0319 ln W − 0.00182 ln²W.
  (d) Compressor (:1080-1178) and turbine (`530·W^0.81`, :1338-1386) fit as written. Proposed grammar (to rule on):
  per-entry index basis; factor kinds `size_power` (A + (z/z_ref)^B) and `polynomial` in a named variable; additive
  `adders` (each a product of terms); `oversize` as its own exact factor on S; vessel thickness a θ (default 1.25 in,
  limitation `SHELL_THICKNESS_DEFAULTED`); size ranges either from the book with their own citation or no `size`
  regime where the source states none. Not blocked: `cost/index.py`, the three series files, the
  log-polynomial/power-law/constant forms, the loader's checks.

## WO-A2b (volumes, kinetic CSTR, dormant liquid; §9.3, §9.4)

- Done as ruled: identity table + rows in `assessment/blocks.py` (`IDENTITY_VOLUMES`, `identity_volume`,
  `IdentityVolume.vdot`); precedence provider → identity → item `liquid_molar_volume` → document
  `liquid_molar_volumes` → refusal in `SizingContext.flow`; schema: top-level `liquid_molar_volumes`, item
  `dormant_liquid_density` (`residence_time_s` existed); kinetic CSTR sized `τ_R·V̇_out` with
  `implied_rate_constant`. Tests `tests/test_e01_a_sizing.py` 24 passed (A46 guards ×3, P2 drum by hand rel 1e-12
  with FD on diameter + argmax rows, unused item declaration, C-MW shell refused at `v_L` / sized from document /
  item precedence, twin = reference ≤ 1e-13; A47 CSTR rel 1e-14, refusal + duty item, dormant-liquid drum).
- FACT: Wilson v1's provider id is `wilson-ig-v1` (§9.4's table says `wilson-ig`); the table keys on the modules'
  own `PROVIDER_ID`. C-MW binds only with `column_registered(…, {"syn001", "wilson-ig-v2"})`.
- DECISION: a provider that offers `v` but cannot answer it at the state (or for the phase) falls through to steps
  2–4, and the final refusal carries the provider's reason. Alternative: refuse at once. Reversible by:
  `SizingContext.flow` (return the refusal when `"v" in described.properties`).
- DECISION: `v_source` is recorded as a `SizingInput` `vdot.<stream>` (value: phase, unit m3/s); `SizingInput` gains
  `used` (default True) and `v_source`. Alternative: a `SizedItem.v_sources` map. Reversible by: `StreamFlow.record`.
- DECISION: a declared item θ (`liquid_molar_volume`, `dormant_liquid_density`) is always in the program, reported
  `used: false` when no formula reads it; document θ `asm:liquid_molar_volume.<c>` enter once, only when a flow uses
  them, after every family's θ. Alternative: emit unused θ too. Reversible by: `SizingContext._declared_flow`.
- DECISION: the kinetic CSTR's τ θ is `asm:item.<U>.vessel.tau_R` (item key `residence_time_s`), as the conversion
  reactor's; its phase is the unit's declared outlet phase (`unit.structure.phase`). Reversible by: `_Reactor`.
- Amended own tests (ruling, not tuning): `test_syn001_items_entries_and_refusals` (the P2 drum is now sized) and the
  M1 column test (shell sized from SYN-001's identity, was refused at `shell.v`).

## WO-A4 (chain, OPEX, annualisation, derived, uncertainty) — in progress

- Done: (1) `cost/capital.py` + `_data/assessment/cost/chains.json` (presets `bare-module-total`, `ebtf-prisma-v1`;
  chain checks; CRF; domain) — A20 ratio 1 ulp from 1.744314, A21 CRF(0.08, 20) = 0.10185220882315059 exactly on
  floats and CasADi; (2) `cost/operating.py` (`PER_SI`, `price_on_basis`, `annual`) and `cost/uncertainty.py`
  (AACE table, class, worst case, RSS, statement). `tests/test_e01_a_capital.py` 7 passed.
- DECISION (schema, §9 does not spell the field): item `options: {name: string}` (the set file's option names and
  string choices) and `shell_thickness` (m, > 0; θ `asm:item.<item>.t_shell`, §9.2.4 II's default 0.03175 m).
  Alternative: one schema field per SSLW option. Reversible by: reverting that commit (schema + 1 test). For the
  contributor: `material`/`tray_type` merge into `options`; a different value under both is `NO_CORRELATION`.
- DECISION: a chain that is malformed (an `of` not a base or earlier step, a reserved or repeated name) raises
  `ChainError`; the contributor is to map it to `ASSESSMENT_OUTPUT_UNKNOWN(capex.<of>)` (§4.12 has no chain code).
  Alternative: a new code (needs the design lane). Reversible by: the contributor's mapping.
- DECISION: a price in another basis is escalated with §4.6's formula as written, including `LF`. Alternative: LF
  only on capital. Reversible by: `operating.price_on_basis` (pass `location_factor=1.0`).
- Done (4): `cost/contributor.py` (`CostContributor`, registered `cost`): sizing → §4.5.3 entry → options → form
  select/held regime (`<item>.size`, `<item>.<target>.piece`; piece 0 = `floor`) → §4.6 escalation → `capex.*`
  → chain → OPEX → `annual.capital_charge`, `tac`, `profit`, `product.annual`/`lcox`. §9.2.7 drives: motor reads
  `size.<U>.power`, inherits N; `includes_drive` → drive capital 0.0, `included_in`; electricity W/η_m(W/N), θ
  `eta_drive` dropped. `tests/test_e01_a_contributor.py` 6 passed (water TH-C2 loop: no refusals; drive A44; A22
  rel 1e-15; A20 on the program; A40; F_BM refusal only on a bare-module chain; A21 domain; A23 helper).
- DECISION: `ContributionPlan.unavailable` / `AssessmentProgram.unavailable` (`output → reason`): an output that would
  depend on a refused, not excluded item is not built (report: `null`; B3: `ASSESSMENT_OUTPUT_UNAVAILABLE`).
  Alternative: build over costed items and null in the report. Reversible by: program.py field + contributor.
- DECISION: any non-excluded *sizing* refusal withholds the capital sums **and** `opex.total` (conservative; the unit's
  energy may be unknown); cost-only refusals withhold capital only. `exclude` matches the item id and its `<id>.`
  sub-targets; an excluded item's duty/electricity still counts in OPEX. Reversible by: `_Planner.items`.
- DECISION: per-item θ `asm:item.<i>.E` (escalation) and `asm:item.<i>.accuracy` (1.0, carrying the entry's or
  quote's `relative_range`, §4.9); `C = C_base·E·u`. A quote without `accuracy_class` → class `None`. Item
  `material` → option `material` or `tray_material`; `subtype` → the single `*_type` option; else `NO_CORRELATION`.
  `generic-v1` entries → `NO_CORRELATION` kind `unsupported`. A bare-module quote leaves `sum_purchased` unavailable.
- DECISION: electricity with no `kind: electricity` utility → `opex.utility.electricity` + `opex.total` unavailable
  (no §4.12 code fits; none emitted). Heating/cooling prices must be energy `per` (else `PRICE_BASIS_MISMATCH`).
  User series load from `data.series[].path` when the canonical sha256 matches; otherwise not available.
- Done (5): `cost/derived.py` (`DerivedContributor`, registered `derived`); `BuildContext.earlier` (the earlier
  contributors' plans, empty for the first; additive, cost ignores it). `tests/test_e01_a_derived.py` 4 passed.
- DECISION: derived references go backwards in document order only; a forward, self or unknown term →
  `ASSESSMENT_OUTPUT_UNKNOWN(<term>)` and the output unavailable. Alternative: topological order over the declared
  set. Reversible by: `derived.py` (the check is one comprehension). Terms fold in sorted id order (the canonical
  document's), then `+ constant`; a denominator absent or all zero is no ratio; a second declaration of an id is
  refused `ASSESSMENT_OUTPUT_UNKNOWN(derived.<id>)` "declared twice".
- DECISION: the denominator sign is checked at plan time on floats (`METRIC_UNDEFINED(derived.<id>)`, unavailable)
  and again by the report at the state it reports (section `undefined`). Alternative: an admissibility row (would add
  a regime entry the design does not have). Reversible by: `derived.py`.
- FIX: `_Planner._theta` looked document `uncertainty` up by the path without `asm:`, but the schema requires the
  `asm:` key, so no declared range was ever applied. Now keyed by the full θ id. Values unchanged (ranges only).
- Done (6): contributor tests on TH-C1 (`tests/test_e01_a_contributor_c1.py`, 6 passed): pump drive by
  `motor.electric` at its floor (exp(5.8259)·500/394·E, rel 1e-14); electricity W_P/η_m − W_T·η_gen netted
  (`ELECTRICITY_NETTED`) and with `export_price`; A19 through the contributor (E = 1 → bitwise; exponent rel 1e-15);
  held-regime round trip (same regime sha, label, repr-identical values; `select` keeps it; `P.size: units:1` →
  `ASSESSMENT_REGIME_INADMISSIBLE`); 16 MPa boiler → `CORRELATION_OUT_OF_RANGE(B.pressure)`, with
  `allow_extrapolation` → `CORRELATION_EXTRAPOLATED`; materials, revenue, `product.annual`, `lcox`, `profit`.
- DECISION (A41 enabler): `SizingInput.default_key` names the `defaults.py` key a defaulted input took; the cost
  section's `defaulted_inputs` entries are `{key: <defaults.py key or input name>, input, value, target}`;
  `drum_orientation` and `service_at_zero_duty` (Q = 0.0, nothing declared or held) are now recorded. Provenance
  only, values unchanged. Alternative: keep input names and map in the A41 test. Reversible by: that commit.

## WO-A5 (report, LCA expectations)

- Done (1): `assessment-report.schema.json` + registry line; E01 addendum `schemas` gains it (`state_sha256` not
  listed, keeps v2's float-digest class; `regime.sha256`, `lca.tables[].sha256` reuse `sha256`). Policy `--check`
  exit 0, v2 sha256 6b449911…d707c unchanged; links/m02/m04/t08/p01 schema tests 435 passed.
- Done (2): `assessment/report.py` (`build_report`, `report_body`, `propagate`), `AssessmentProgram.report` and
  `.context`; the cost section now emits `basis` and every sized item; fixtures from real evaluations
  (`tests/fixtures/schemas/assessment_report/valid/{p1_th_c1,p1_th_r1,p3_m1}.json`, all `COMPLETE`, class 4;
  writer `python tests/test_e01_a_report.py --write`); `tests/test_e01_a_report.py` 16 passed.
- DECISION (fields §4.11 does not spell): top-level `schema_version` (`assessment-report-v1`), `assessment_id`,
  `unavailable` (withheld output → reason); `uncertainty.parameters` (θ, value, range used) and
  `uncertainty.assumptions` (§4.9's labels). Outputs grouped by catalogue entry, keyed by unprefixed id: `capex`,
  `opex`, `annual` (revenue, capital charge, tac, profit, product.annual, lcox), `derived`; sizes inside each item;
  admissibility values inside `regime.entries`; `lca.inventory`/`impacts` as rows `{id, value, unit}`, `tables` from
  the lca section. Item `status` ∈ costed | included | excluded | refused. Alternative: other names. Reversible by:
  the schema + `report.py` (one commit each).
- DECISION: status `REFUSED` when the program is not evaluable at x, its held regime is inadmissible at x (all
  outputs null, `ASSESSMENT_REGIME_INADMISSIBLE`), or no output is built; `PARTIAL` on any refusal or withheld
  output (incl. uncertainty refusals); else `COMPLETE`. Reversible by: `report_body`.
- DECISION: estimate class `none` also when a costed item has no class (a quote without `accuracy_class`); included
  drives and excluded items do not count. Reversible by: `report._estimate_class`.
- DECISION: document `uncertainty` ranges are resolved in the report for every θ (sizing θ too), overriding an
  entry's; a range on a structural θ → `ASSESSMENT_PARAMETER_STRUCTURAL(θ)`, on no θ of the program →
  `ASSESSMENT_VARIABLE_UNKNOWN(θ)` (no §4.12 code fits better). θ order = construction order.
- DECISION: `AssessmentProgram.linearize` on a withheld output → `ASSESSMENT_OUTPUT_UNAVAILABLE` (A40's study
  clause, at the program level the study layer calls). Reversible by: program.py (one check).
- DECISION (paths): report fixtures under `tests/fixtures/schemas/assessment_report/` (the repo's schema-fixture
  convention; §5.2's ownership list names no fixture path). Regression compare: structure and strings exact,
  numbers rel 1e-9 (platform last bits of the solved state); correctness is asserted by hand values, not fixtures.
- FACT for I1: P1 candidates TH-C1 (pump, boiler, turbine, condenser) and TH-R1 (heater, flash, pump); no S11 case
  has all four of §5.4's P1 units. P3 = M1 (column on syn001; shell/trays sized by the model identity, §9.4). F_BM
  values in the fixture documents are test inputs (exchanger 3.17, vessel 4.16, trays 1.0, pump 3.3, motor 1.5,
  turbine 3.5).

## Handoff (2026-10-27, fifth context cap) — resume from here

- **Done (wp/E01):** A1–A3, A2b, A4 (1)–(3) earlier; **A4 (4)** the cost contributor (this commit). Track A tests:
  core/cost/links/capital/sizing 83 + contributor 6 pass. Protected paths untouched. No schema change in (4).
- **Not done in WO-A4:** (a) `derived` contributor (§4.7.5; put in `assessment/cost/derived.py`, register `derived`;
  acyclic; plan-time non-positive denominator → `METRIC_UNDEFINED`, output unavailable); (b) the §4.9 propagation
  pass (`program.linearize(x, outputs, symbolic=[θ with relative_range])` → `uncertainty.worst_case`/`rss`; class
  from the section's item `accuracy_class`/`extrapolated`) — natural home is `report.py` (A5); (c) tests still owed:
  A44 drive on a compressor *with* a pump (pump drive costs `motor.electric`), a quote item (A19 through the
  contributor), held-regime build round trip, `CORRELATION_EXTRAPOLATED` → class none end to end, materials/revenue
  and `lcox` (needs a functional unit doc), turbine generation + `ELECTRICITY_NETTED` (TH-C1).
- **Then WO-A5** (untouched): `report.py`, `assessment-report.schema.json` + registry entry (E01 addendum `schemas`;
  `exact_sha256` stays `[assessment_sha256, regime_sha256]`, `state_sha256` keeps v2's float-digest class; policy
  `--check`), fixtures from P1/P3, `benchmarks/e01/lca_hand/`, A38–A41, A43 report part. The contributor's
  `section(values)` already returns `items` (provenance incl. regime, escalation, options, index_basis), `excluded`,
  `defaulted_inputs`; `program.unavailable` gives the nulls.
- **Fixture note:** CoolProp is not in `.venv`; the contributor test runs S11's TH-C2 loop on IAPWS-95 water
  (record source `benchmarks/s05/components.yaml`, S1 at 410 K). All its items sit in `floor`.
- **Open for the design lane (batched):** the four new DECISION lines above, plus the earlier ones.
- **For B1/I1 (unchanged):** package-data globs, `resources.PACKAGED`, M05 ADDENDA pin, A48 RC item, P3 volumes.
