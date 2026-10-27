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
