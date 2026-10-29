# E01 track B — build decisions and facts

Normative: `docs/derivations/E01-design.md` (ADR 0052; R-850…R-867), §4.8, §5.3, §6, §9. One line per choice:
`DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.` Facts carry their source (file hashes for
packages; URL and retrieval date for data). The design-lane ruling round is folded into E01's single `reviewer` pass.

## WO-B1 (rights, extra, adapter)

### Facts (retrieved 2026-10-27; no personal identifier sent; user agent `OpenFlowsheet-build`)

- FACT (pins): bw2data **4.7** (PyPI 2026-05-14; wheel sha256 `e88f1ccd8266fb7a8d1ecd14abfe163a4533b1cd4b4b88269a569da1f8a2021c`)
  and bw2calc **2.5.0** (2026-05-16; wheel `2c26420e223871a50d45532e63a1506116cfede0a8fc071cbd043fc347f4beee`): the
  newest releases at least two weeks old (bw2data 4.8 of 2026-10-19, bw2calc 3.1.0/3.0.0 of 2026-10-18/14 are too new).
- FACT (licences): bw2data 4.7 `licenses/LICENSE` sha256 `966d484abb7c9601d38b3797695be4ccd24199e95b3c43346fc668204ad622d5`
  (BSD-3-Clause text, "Copyright 2024 Chris Mutel"; METADATA declares no licence); bw2calc 2.5.0 `licenses/LICENSE`
  sha256 `e3e590114822c8f110f6b0333ef0649494287680c2cb950d333f977e85bee2c8` (BSD-3-Clause, "Copyright (c) 2023, Chris
  Mutel"; `License-Expression: BSD-3-Clause`). Read from `pip download --no-deps` wheels in the scratchpad.
- FACT (closure): `benchmarks/e01/brightway/lca-pip.lock` = 32 distributions over requirements.lock, resolved by
  `uv pip compile --exclude-newer 2026-10-13` with requirements.lock as constraints, hash-pinned. No bw2io, pypardiso
  or MKL. `docs/e01-lca-licences.json`: 40 closure rows, 0 failures; 18 rows hand-audited (licence file read, SPDX id
  recorded with the file's sha256, `scripts/e01_d04_inventory.py` `AUDIT`). None GPL-family; tqdm is MPL-2.0 AND MIT
  (used unmodified, as certifi under T07 E5). Nothing of the extra is redistributed.
- FACT (IPCC): AR6 WG1 ch. 7 PDF (`IPCC_AR6_WGI_Chapter07.pdf`, sha256 `470d2662…febfa9`), Table 7.15 p. 1017, GWP-100:
  CO2 1.000, CH4-fossil 29.8 ± 11, CH4-non fossil 27.0 ± 11, N2O 273 ± 130 — all four §4.8.5 values confirmed.
  Rights: front matter (sha256 `e564ba9b…09e6`) says "© 2021 Intergovernmental Panel on Climate Change", no open licence;
  www.ipcc.ch/copyright/ returned HTTP 403 to every client tried. Shipped per D8 as five factual values with citation.
- FACT (USLCI, §7 Q6): the release repository `FLCAC-admin/uslci-content` (releases v1.2026-09.0 … ) is MIT, LICENSE
  sha256 `a680c9d5b66a37c42f309e2adff0af18aac3f379ac0b2b7d4153bb4801624649` ("Copyright (c) 2017 uslci-admin"); no CC0
  or US-public-domain statement in its README, docs or release notes; www.lcacommons.gov did not resolve (DNS). Also
  Brightway's import of USLCI needs bw2io, which the extra excludes. **Not shipped**; the recipe stays documentation.
- FACT (EF 3.1): eplca.jrc.ec.europa.eu's developer page redirects to knowledge-for-policy.ec.europa.eu, which states
  no terms for the EF reference package. Terms not confirmed → **EF factors not shipped** (D8 default).
- FACT (Brightway precision, blocks A24/A25 at their registered tolerances): bw_processing 1.6 stores every
  processed `amount` as float32 (`bw_processing/utils.py:79`), and `LCA.score` comes back float32: on
  test-background-v1 the adapter gives q_E 0.5472782254219055 (= 9181805/2²⁴), q_H 0.18911290168762207,
  q_X 0.9018649160861969, relative errors −7.0e-10, −8.1e-9, −3.6e-9 against the hand rationals. **A24 (rel ≤ 1e-12)
  FAILS** in the scratch lca env; A25 (rel ≤ 1e-10) cannot pass on this path either. Evidence for a remedy: the same
  system fed to bw2calc 2.5.0 as float64 datapackages (`bw_processing.add_persistent_vector`, float64 `data_array`)
  reproduces the hand values to 6e-17. See ESC-B1.

### Decisions

- DECISION: where the lca lock lives → `benchmarks/e01/brightway/lca-pip.lock` (B-owned path). Alternative:
  `requirements-lca.lock` at the root, like coolprop. Reversible by: moving the file and its two references.
- DECISION: the audited env → `scripts/build-lca-env.sh [prefix] [python]`, a venv of the project interpreter with
  requirements.lock (no hashes; it has none) and the hash-pinned increment, the checkout on `sys.path` by a `.pth` line
  (no build backend in the env). Built and used only as a scratch venv in this session, never in `.venv`.
  Alternative: conda. Reversible by: the script.
- DECISION: D04 records → `docs/e01-lca-licences.json` (packages, made in the lca env with T07's own `inventory`
  plus the hand audit) and `docs/e01-data-licences.json` (every file under `_data/assessment/**`, A's included);
  checker `scripts/e01_d04_inventory.py --check` (A42). Alternative: extend `t07_licence_inventory.py` (T07's file).
  Reversible by: deleting the script and records.
- DECISION: table files carry `format` (`unit-score-table-v1` | `direct-factor-table-v1`); `test-background-v1.json`
  carries its Brightway description as a member `brightway` inside the hashed table. Alternative: two files.
  Reversible by: `scripts/e01_lca_data.py`.
- DECISION: refusal codes for tables §4.12 does not name: a malformed table → `LCA_TABLE_INVALID` (new code); an absent
  or wrongly listed table → `LCA_ACTIVITY_UNKNOWN(<table>)`. Alternative: map both to `LCA_TABLE_HASH_MISMATCH`.
  Reversible by: `tables.py`. (Design lane to confirm the new code.)
- DECISION: adapter signatures gain keywords the note leaves open: `table_id` (both builders), `si_per_unit`
  overrides and `source`; `write_description(project, description)` added for the synthetic background; the A25
  check copies the project and deletes the copy (stronger than deleting the scratch database). Reversible by:
  `brightway.py`.
- DECISION: rights label in the report → `"<class>; redistribution <allowed|forbidden>; <licence>"` (the report schema
  has one string). Reversible by: `Rights.label`.
- DECISION: mypy override for `bw2data.*`, `bw2calc.*` (as M03's for pyomo). Reversible by: pyproject.

### Escalations (open, design lane)

- **ESC-B1 (A24, A25 tolerances vs Brightway's float32).** The registered tolerances (1e-12, 1e-10) are below what
  Brightway's standard path can deliver (float32 data and score; measured above). Options: (a) the adapter assembles
  A, B and C in float64 from the project's stored exchanges and characterisation factors (bw2data keeps float64 in
  SQLite) and hands them to bw2calc as float64 datapackages — then A24 passes (6e-17 measured on a hand-built
  datapackage), but A25's check shares that assembly; (b) restate A24/A25 at float32 data precision (~1e-7 rel); (c)
  keep A24/A25 and record them failed. Preferred: (a) for `build_unit_score_table` (the table is what the program
  uses; float32 tables would put 1e-8 errors into every impact), and for `foreground_check` keep Brightway's own
  processing with A25 restated at float32 precision so the check stays independent of our assembly. Not implemented:
  it changes how a frozen table's numbers are produced. A24 is committed at 1e-12 and fails in the lca env.
- **ESC-B2 (packaging of `_data/assessment/**`).** Adding the package-data glob breaks
  `test_t08_w4_package_data.py::test_the_package_data_patterns_cover_exactly_what_is_packaged` unless
  `resources.PACKAGED` gains the path, and T08's rule is that every packaged path is a *symlink* to a single
  repository copy (`test_each_packaged_path_is_a_link_to_the_single_repository_copy`), with directory entries
  matched by the test's own `DIRECTORY_FILES`. `_data/assessment/` holds real files (A's and B's). Doing it right
  moves the data to a repository path (proposal: top-level `assessment-data/`, `_data/assessment` a link to it),
  adds `"assessment"` to `PACKAGED`/`DIRECTORIES` (and `REPOSITORY_PATHS`), adds one line to the T08 test's
  `DIRECTORY_FILES`, and amends T08.A32 (`test_t08_w2_inventory.py` `ATTRIBUTED_DATA`/`SHIPPED_DATA`, with NOTICE
  attributions for SSLW/IDAES BSD, PrISMa CC BY, Eurostat CC BY and IPCC). It crosses A's files and T08's tests, so it
  is left to I1 with a ruling; nothing was changed. Until then a wheel does not carry the assessment data.
- **ESC-B3 (rights leak through θ listing).** The report's `uncertainty.parameters` lists the value of every θ that
  carries a declared range; a user who declares a range on `asm:lca.q.<forbidden table>.…` would print a forbidden
  score. `report.propagate` is A's file; a redaction there (skip, or list by id only, every θ of a table whose
  rights forbid redistribution) is the fix. A28 passes on documents without such a range.

## WO-B2 (LCA contributor)

- FACT (P4 vs track A's hand superposition, A25 hand clause): `impact.climate_change_test.rate` 0.024320113943021117,
  `.annual` 700419.2815590082, `.per_fu` 1.3499723647198096 — relative difference **0.0** for all three against
  `benchmarks/e01/lca_hand/lca_hand.yaml` (tolerance 1e-12); inventory a_k within 1e-12; electricity net negative.
- FACT (A26): doubling every `amount` doubles rate, annual and per_fu bitwise. `∂h/∂x` equals
  `Σ_k (q_k·α_k)·∂φ_k/∂x` bitwise in construction order — CasADi's reverse sweep associates `(q·α)·∂φ`; the
  association `q·(α·∂φ)` differs by 1 ulp at `T.W` (1.4442064292114692e-07 vs …95e-07), so the test reads the
  design's formula left to right, with `∂φ_k/∂x` from the same program at `α_k = 1` exactly. `∂h/∂q_k = a_k` exactly.
- FACT (A27): 1 kg/s through an emission stream mapped to `ch4_fossil_air` gives exactly 29.8 kg CO2-eq/s.
- FACT (A28): with a `redistribution: forbidden` table the report and an export (document + report + `exportable`)
  carry its id and sha256 and none of its scores (byte search on `repr` and 12-character prefixes).
- DECISION (convention, track A's question 6): `a_k = amount·φ_k/SI(per)`, electricity net, as A5's expectations.
  §4.8.1's "the table activity's `si_per_unit` converts it" does not contradict it: the schema gives `amount` no unit
  of its own, so it is in activity units and only `per`'s SI factor enters; `si_per_unit` stays in the table for the
  adapter and documentation. No discrepancy to stop on. Alternative: `amount` in SI of the activity's product,
  divided by `si_per_unit` (needs a schema field). Reversible by: `inventory._alpha`.
- DECISION: a utility's φ comes from the cost plan (`ctx.earlier["cost"]`): the drive's consumption is the cost
  output `size.<U>.drive.power` (so W/η_m when the set has a motor), generation the turbine item's `−W·η_gen`, a
  heating/cooling utility `Σ|Q|` of its users; `plan_sizing` is re-run only to enumerate the items. Without a cost
  plan the utility exchanges are withheld. Alternative: re-plan sizing and drives inside the LCA contributor.
  Reversible by: `inventory.plan_inventory`.
- DECISION: exchange ids `utility.<u>.<activity>`, `material.<s>.<activity>`, `emission.<s>.<c>` (repeat → `.<j>`);
  θ ids `asm:lca.alpha.<k>`, `asm:lca.q.<table>.<m>.<activity>`, `asm:lca.c.<table>.<m>.<flow>`,
  `asm:lca.allocation.factor`; construction order utilities then materials, each in document order.
  Reversible by: inventory/impact.
- DECISION: `lca.categories` absent → every category of the listed tables (unit-score first). A category some used
  table lacks, or whose unit differs across tables, withholds that category (refusal `LCA_ACTIVITY_UNKNOWN` /
  `LCA_FLOW_UNKNOWN(<table>.<m>)`), never a silent zero. Reversible by: `impact._blocked`.
- DECISION (allocation forms §4.8.1 leaves open): `substitution` multiplies by nothing — the avoided activities are
  exchanges the document declares with a negative `amount` (the contributor never flips a sign itself); `mass` uses
  total stream masses of the FU connection and of `products` (default: materials with role product/co_product);
  `economic` uses the cost contributor's price θ with the flow matching the price's unit; a non-positive
  denominator at the planning state refuses every impact `ASSESSMENT_EVALUATION_FAILED(lca.allocation)`; a missing
  price or FU → `METRIC_UNDEFINED(lca.allocation)`. Alternative: substitution flips co-product exchanges.
  Reversible by: `impact.allocation`. (Design lane: the substitution sign is a semantic choice.)
- DECISION: `.annual` uses the cost plan's θ `asm:operation.hours_per_year`, else declares it (document or default);
  `.per_fu` divides by the FU stream's mass (kg/s) or, for `molar_total`, amount (mol/s). Reversible by: impact.
- DECISION: `per` that cannot measure the boundary quantity (a utility with a mass `per`, a material with an energy
  `per`) → `LCA_ACTIVITY_UNKNOWN(<path>.per)` and the impacts withheld. Reversible by: `inventory.technosphere`.
- DECISION: the contributor class lives in `lca/section.py` beside its section (the note names no file for it);
  it registers as `lca`. Reversible by: moving it.

## Orchestrator rulings (2026-10-27) and their implementation

- DECISION (ESC-B1, orchestrator ruling): the unit-score table is built on bw2calc's float64 path → the adapter
  assembles the technosphere, biosphere and characterisation matrices as float64 datapackages from the project's
  stored rows by bw2data 4.7's own rules (`SQLiteBackend.process` queries, flips, implicit production;
  `Method.process_row`, global-location CFs) and hands them to `bc.LCA(data_objs=…)`; `foreground_check` uses the
  same path (the ruling keeps A25 at 1e-10, which bw2data's float32 processing cannot meet). A24 at 1e-12 and A25 at
  1e-10 are not restated. Alternative: restate A24/A25 at float32 precision. Reversible by: `brightway.py`
  `_inventory_datapackage`/`_method_datapackage` and the two `bc.LCA` calls.
- FACT (A24, lca scratch env, bw2calc 2.5.0): q_E 0.5472782258064516, q_H 0.18911290322580646, q_X
  0.9018649193548387 — relative errors −6.2e-17, 2.2e-17, −9.5e-18 against §4.8.5's rationals, and bitwise equal to
  the shipped `test-background-v1` scores. `tests/test_e01_b_brightway.py` 3 passed (A24; the float64 matrices
  rounded to float32 equal bw2calc's matrices from bw2data's processed files entry for entry, with identical
  activity/biosphere dicts; `foreground_check` on a mixed exchange/emission set equals the hand superposition
  within 1e-12 and leaves no scratch project).
- DECISION: `bw_processing` (bw2calc's pinned dependency, 1.6 in the lca lock, D04-audited) is imported directly
  for `create_datapackage` and `INDICES_DTYPE`; mypy override extended. Alternative: reach it through bw2data's
  re-export. Reversible by: `brightway.py`, pyproject.
- FACT (for I1, from B1's extra, not this commit): `tests/test_m07_mr12_extras_v02.py::test_the_git_backed_measure_at_head`
  fails at a HEAD that carries the `lca` extra: `new_since_v0_1_1` is `['coolprop', 'lca', 'nlp']`, the tripwire
  pins `['coolprop', 'nlp']`. By design (S07 Ruling M): the next release specification adds an `MR12_AUDITS`
  entry and the tripwire's list; M07's test is not edited here.

- DECISION (ESC-B3, orchestrator ruling): the report withholds the value of a ranged θ that is a score of a table
  whose rights forbid redistribution → the impact planner records such θ (`ImpactPlan.restricted`, id → reason),
  the lca section carries them as `restricted_theta`, and `report.propagate` lists them as
  `{theta, withheld: "a score of table <id>, whose rights forbid redistribution", relative_range}`; the θ still
  propagates. `assessment-report.schema.json` `uncertainty.parameters[]`: `value` or `withheld` (oneOf), policy
  `--check` exit 0 (v2 sha256 6b449911…d707c unchanged). Alternative: leave to the reviewer. Reversible by: that
  commit (report.py, impact.py, section.py, the schema).
- OPEN (design lane, ESC-B3 residue): the interval and σ of an impact still carry `a_k·q_k·span` for a ranged
  restricted θ, and `a_k` is reported in `lca.inventory`, so one ranged θ lets a reader back out `q_k`; so does an
  impact with a single exchange from a forbidden table (`h = a_k q_k`). The ruling covers θ values only; nothing
  else was changed.

## WO-B3 (study integration)

- Done (1): `study.schema.json` gains optional top-level `assessment` and `optimization-report.schema.json`
  `formulation.assessment`, each a `$ref` to `assessment.schema.json#/$defs/…` (§9.1; the `$defs` came with A3a);
  policy `--check` exit 0, v2 sha256 6b449911…d707c unchanged; every existing study and optimization-report fixture
  validates (A38 study part); M02/M03/M04/M05 schema tests, links, T08 w4 package data pass.
- Done (2): `studies/assessment.py`: `assessment_sensitivity` (§4.10.1 steps 1–5), `revision_sensitivity_host`,
  `evaluation_context`, `trf_objective_from_assessment` (A37). `sensitivity.py` unchanged.
- FACT (A30 on TH-C1, P4's document; I1 repeats on the registered P1): wrapper vs central differences of re-solved
  states (step 1e-4·s_p, s_p = 673.15 K and 3e6 Pa), program evaluated at the re-solved state with the moved pin as
  a decision: `tac`/B.T_spec 7.132905868079 vs 7.132905937631 (rel 9.8e-9); impact rate/B.T_spec 5.115015250610e-6
  vs …290801e-6 (7.9e-9); `tac`/P.P_spec 1.706691596446e-3 (5.8e-10); impact rate/P.P_spec −1.418432143905e-10
  (2.9e-9). A31: forward−adjoint ≤ 6.2e-16 relative; host consistency 2.8e-17 (tolerance 1.4e-11). Base QUALIFIED.
- DECISION: an assessment output's scale in the wrapper → `max(|y(x*)|, 1)` unless the caller passes `scales`
  (§4.10.1 says "scale = declared" without naming where; §4.10.2's rule reused). Alternative: a required argument.
  Reversible by: `assessment_sensitivity`.
- DECISION: the augmented outputs are named `assessment:<id>` and appended after the request's own; the wrapper's
  blocks are outputs × the request's parameters in request order. A refused underlying request gives every entry
  `None`, the state-independent rows too (the state is not qualified). Alternative: report `∂G/∂p` for
  state-independent rows regardless. Reversible by: `_block`.
- DECISION (A32 reading): "never calls the wrapper" is tested at the wrapper's entry: with no assessment output
  nothing is linearized (spied) and the base result's document equals the direct `evaluate_sensitivity`'s; no
  study-document dispatch exists to route around it (study.py is not in B3's list). Reversible by: the test.
- DECISION: `revision_sensitivity_host` builds the evaluation context from the compiled metadata (as the executor
  does; `RevisionFlowsheet.context` is the structural one), and the alias elimination with the certificate's
  pressure-shifted second state (structural when it cannot be built). TH-C1 eliminates no row. Reversible by: it.

- Done (3, part 2, §4.10.2): `AssessmentBinding(program, outputs, output_scales)` (`.at` takes
  `max(|y(x₀)|,1)` at a state), `NlpFormulation.assessment`; `variables` now lists state names only,
  `assessment_outputs` the `assessment:<id>` ones; `FullSpaceNlp` raises `AssessmentOutputUnknownError` and
  readiness reports `ASSESSMENT_OUTPUT_UNKNOWN` before any solve; gray-box outputs, Jacobian `[G_x G_d]` (canonical
  CSC, the equality Jacobian's pattern guard), output scaling, Pyomo mapping, `adm ≥ 0` (scaling 1), `G(x₀)` initial
  values; readiness codes. `tests/test_e01_b_nlp.py`: 11 default-env + 2 nlp tests pass. G9: the M03 NLP fixture
  documents (wall times blanked) and the no-assessment Pyomo component list and objective are byte-identical before
  and after (scratch dump, `cmp` equal); `test_m03_nlp_greybox.py` 18 passed in the audited env (m05's `.venv-nlp`).
- DECISION (closure reading): an admissibility row is a gray-box output when some row of its regime entry has a
  structural nonzero in a column (state or decision) of `[G_x G_d]` where some bound output has one; rows in
  `program.admissibility_ids` order after the bound outputs in `program.output_ids` order. A floor item's rows can
  fall outside (its capex row is empty); V7 then catches a regime change post hoc. Alternative: every admissibility
  row (over-restricts an impact objective), or a trace of `out()` dependencies. Reversible by: `FullSpaceNlp._bind`.
- DECISION: the gray-box scale of an admissibility row is 1, because the program's rows are already `a/nominal`
  (§4.3.1); the nominal is recorded per row (`admissibility_nominals`) for the report. Alternative: `1/nominal` again
  (double scaling). Reversible by: `_bind`.
- DECISION: the output *variables* get Pyomo primal scaling `1/scale` too (the output rows get it per §4.10.2), so a
  `tac` of 1e6 is an O(1) primal. Alternative: leave them unscaled (factor 1). Reversible by: `build_model`.
- DECISION: readiness order — the four output/parameter codes after `UNKNOWN_VARIABLE`, `ASSESSMENT_REGIME_INADMISSIBLE`
  after `SIMULATION_NOT_READY` (it needs each start's certified state; "at the start" read as "at each start"). A θ
  decision gives `ASSESSMENT_PARAMETER_DECISION` (or `_STRUCTURAL`), not `UNKNOWN_DECISION`. The schema's two
  readiness-code enums gain the five codes (additive; §4.10.2 names the codes; separate commit). Reversible by:
  `READINESS_ORDER`, that commit.
- DECISION: the assessment twin's property-block calls since the start's `FullSpaceNlp` was built are added to the
  start's `property_calls` (0 without an assessment). Reversible by: `_evaluations`.

- Done (3, part 3, §4.10.3): `verify_candidate(…, closure=None)`: V6 values from `program.evaluate(x_sim, d)`
  (V6 detail `assessment_values`), V3 with the closure's rows as `adm ≥ 0`, V5 by the chain rule
  (`linearize(x_sim, d, closure, symbolic=decisions)` + M03's adjoint + `∂G/∂d·s_d`), V7 `select(x_sim, d,
  release=dormancy)` vs the held regime → `ASSESSMENT_REGIME_CHANGED(<entry>)`; `CHECKS` gains V7 (`M03_CHECKS` =
  the first six); `passed`/`StartEvidence.verified` need V7 where recorded; `formulation.assessment` via
  `assessment_record`/`start_closure` in both report paths; schema check lists accept V7 (3c). Commits f7a688a4
  (select), d99a5c8e (closure lift, inert), 9c7e78f8 (schema), then the part-3 commit.
- FACT (V5 vs central differences of re-solved states at M03 start 0, h = 1e-4·s_d; test contributor): `tac`/split
  fraction 0.8238545408546 vs 0.8238545830201 (rel 5.1e-8), `tac`/T_spec −2.236533001663 vs −2.236533115904
  (5.1e-8), adm.TOY.size.max 6.3e-8 and 9.2e-8; the pin-reading variant (`∂G/∂d ≠ 0`) 5.0e-8/5.1e-8, and its
  direct term equals `1e3·s_d₀/scale` within 1e-9. Test tolerance 1e-6 relative, set before the run.
- FACT (nlp env): objective `tac/|tac(x₀)|` on SYN-001 with M03's decisions and constraints: `KKT_POINT_VERIFIED`
  from all three starts, V1–V7 pass on each, report schema-valid; candidate `tac` 36260.03 vs scale 39297.33.
  G9 after part 3: the M03 NLP fixture dump is `cmp`-equal to the base.
- DECISION: `select` gains `decisions` and `release` (A's `program.py`, additive; default call unchanged). At a
  candidate, rows and the rule may read a moved pin (`Symbols.pin`), and a dormancy entry has no row, so the held
  regime would always be returned for it. Alternative: rebuild a program at the candidate (needs the private
  contributors) or test dormancy outside the program. Reversible by: revert f7a688a4 and `_regime_held`.
- DECISION: the closure's rows enter V3/V5 as constraints named by their row id (`adm.<entry>.<row>`, lower 0)
  after the formulation's, so they appear in `constraint_values`, `slacks`, the active set and the KKT gradients.
  Alternative: a separate record. Reversible by: `_assessment`.
- DECISION: an expression without an `assessment:` term gets M03's functional exactly (no direct term added); one
  with no state coefficient left contributes a zero host row; none at all → V5 `not_evaluated(state_independent)`.
  Reversible by: `_functional`, `_kkt`.
- DECISION: an assessment not evaluable at `x_sim` (evaluation error or refusal) → V3/V5/V6 `not_evaluated` with
  the reason, V7 still evaluated (`select` then releases the whole regime → fail). Reversible by: `verify_candidate`.
- DECISION: V7 is absent without an assessment (M03 documents byte-identical); `test_m03_nlp_status`'s
  unknown-check example changes from V7 to V8 (V7 is now a check). Reversible by: `M03_CHECKS`, that line.
- DECISION: `formulation.assessment.outputs` lists the bound outputs only (the rows' scale 1 is implicit; they are
  under `admissibility` with their nominal); without a certified start, the binding's scales and no rows;
  `regime_bounds_active` = closure rows with slack ≤ τ_feas and a V5 multiplier, at the candidate only. The record's
  closure is recomputed at the first certified start (`start_closure`). Alternative: list the rows under `outputs`
  too. Reversible by: `assessment_record`.

## Handoff (2026-10-27, after the ESC-B1/B3 rulings and WO-B3 part 1) — resume from here

- **Done (wp/E01 after 53ce3f55):** a7c4aa8b ESC-B1 (float64 Brightway path; A24 passes at 1e-12, rel ≤ 6.2e-17);
  76e4831b ESC-B3 (report withholds ranged θ of forbidden tables; schema `value`|`withheld`); 9b214095 WO-B3 (1)
  (study/optimization-report `$ref` links; `studies/assessment.py`: wrapper, revision host, TR hook).
- **Gates run:** `tests/test_e01_b_brightway.py` 3 passed in the scratch lca env
  (`$SCRATCH/venv-lca/bin/python -m pytest …`, SCRATCH = the session scratchpad); `test_e01_b_tables/lca` 28 passed;
  `test_e01_b_studies.py` 10 passed (A30 on TH-C1, A31, A32, A37, A38 study part); A's report/links tests pass;
  m02/m03/m04/m05 schema tests, t08 w4 package data, m07 journey a21 pass; policy `--check` exit 0; A42 PASS; ruff,
  mypy clean. Nothing under compile/, thermo/, models/ changed; no S11 file touched; nothing pushed.
- **Known failure, not B's to fix:** `test_m07_mr12_extras_v02.py::test_the_git_backed_measure_at_head` (the `lca`
  extra trips S07 Ruling M's tripwire; the release spec adds `MR12_AUDITS` + the list). Logged above for I1.
- **Next (WO-B3 part 2, §4.10.2), in the nlp env:** `NlpFormulation.assessment: AssessmentBinding(program, outputs,
  output_scales)`; `assessment:<id>` names in `QuadraticExpression.variables`, split in `FullSpaceNlp`, unknown →
  `ASSESSMENT_OUTPUT_UNKNOWN` before any solve; gray-box outputs = referenced outputs + admissibility rows in their
  regime closure (catalogue order); `evaluate_outputs`/`evaluate_jacobian_outputs` (hstack x|p, fixed canonical CSC,
  same pattern guard); scaling 1/scale (`max(|y(x₀)|,1)`, row nominal for admissibility); Pyomo mapping, `adm ≥ 0`;
  `optimization_readiness` codes; `assessment is None` → `output_names() == []`, `build_model` unchanged (A35, G9:
  M03 NLP fixtures bit-identical). Then **part 3 (§4.10.3):** V3 admissibility as constraints, V5 gradient via
  `linearize` + adjoint (as `assessment_sensitivity`), V6 from `program.evaluate(x_sim)`, V7
  `program.select(x_sim)` = held regime else `ASSESSMENT_REGIME_CHANGED(<entry>)`/`NOT_VERIFIED`;
  `regime_bounds_active`; `formulation.assessment` in the optimization report. A33–A36 run in I1 on P2.
- **Then WO-B4** (`benchmarks/e01/cost_hand/`): forms I–VII transcribed from the pinned SSLW.py (scratchpad
  `idaes_src/`, sha256 in E01A's log), not from the set file; mpmath at S_min, √(S_min·S_max), S_max, floor bounds
  and 1e-6 inside, P1–P3 sizes; A10–A12 hand cases with identity volumes; scripts never import openflowsheet;
  `benchmarks/e01/brightway/` P4 `foreground_check` expectation (lca env) and the IDAES cross-check script (§9.5).
- **Open for the design lane (batched):** ESC-B3 residue (interval/σ and single-exchange impacts still let a reader
  back out a restricted q_k); the wrapper's default output scale; A32's reading; earlier B1/B2 items (new code
  `LCA_TABLE_INVALID`, substitution sign, every DECISION line). ESC-B2 (packaging) is I1's.

## Handoff (2026-10-28, after WO-B3 part 2) — resume from here

- **Done (wp/E01 after 658dc0c0):** acfa1317 schema readiness codes (5 assessment codes, additive); d1165930
  WO-B3 (2) §4.10.2 (`formulation.py` `AssessmentBinding`/`_bind`/`output_values`/`output_jacobian`;
  `greybox.py` outputs, `_Names`, `assessment_admissibility`; `closure.py` `_assessment_theta`/`_outputs`/`_regime`).
- **Gates run:** `tests/test_e01_b_nlp.py` 11 passed (default env), its 2 nlp tests + `test_m03_nlp_greybox.py` 18
  passed in the audited env; m03 nlp formulation/status/isolation/schemas, e01_b_studies, e01_a_core, m05_readiness
  109 passed; ruff/format/mypy clean; t08 policy `--check` 0; `e01_d04_inventory.py --check` 0. G9 bit-identity:
  scratch script `$SCRATCH/b3/m03_dump.py <repo> <out.json>` (NLP fixture documents via
  `m03_schema_fixtures.nlp_documents()`, wall times blanked, + component list + objective) — base and after `cmp` equal.
- **nlp env:** no `.venv-nlp` in this worktree; use m05's:
  `scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>` with
  `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05` (~30 s for the greybox file).
- **Next, WO-B3 part 3 (§4.10.3), not started:** `verification.py` `verify_candidate` (line ~185) evaluates
  `formulation.objective.value(state)` and `constraint.expression.value(state)` (lines ~231–237) and V5 builds
  `OutputFunctional(output_id, expression.gradient(state), 1.0)` (`_functional`, ~368): with assessment names these
  KeyError today. Needed: augment the state with `assessment:<id>` = `program.evaluate(x_sim, d)` (V6); V5 chain rule
  `∂φ/∂y·(∇ₓG·X + ∂G/∂d)` via `linearize` + the adjoint, as `studies/assessment.py::assessment_sensitivity`; V3 adds
  the closure's admissibility rows as `≥ 0` constraints; V7 `program.select(x_sim)` vs held regime (dormancy exact) →
  `ASSESSMENT_REGIME_CHANGED(<entry>)`, `NOT_VERIFIED`; `CHECKS` gains V7 and the schema `$defs/check` enum gains
  "V7" (§4.11); `formulation_record` adds `formulation.assessment` (assessment_id, sha256s, regime_entries, outputs
  [{id, scale}] = `FullSpaceNlp.output_scales`, admissibility [{id, nominal}], `regime_bounds_active`) only when bound,
  so M03 fixtures stay byte-identical (re-run the dump). `solve_start` passes no binding into verification yet. Then a
  small solve test on the test contributor in `test_e01_b_nlp.py` (objective `tac/|tac(x₀)|`).
- **Then WO-B4** unchanged from the previous handoff (cost_hand forms I–VII from the pinned SSLW.py, mpmath; A10–A12;
  brightway `foreground_check` expectation in the lca env; IDAES cross-check script). Independent of track A's code.
- **Open for the design lane (batched):** the five part-2 DECISION lines above (closure reading and the floor caveat;
  admissibility scale 1; output primal scaling; readiness order; property_calls), plus the earlier ones.
- **Not B's:** `test_m07_mr12_extras_v02::test_the_git_backed_measure_at_head` (I1); packaging `_data/assessment/**`.

## Handoff (2026-10-28, after WO-B3 part 3) — resume from here

- **Done (wp/E01 after 843657ae):** f7a688a4 `select(x, decisions, *, release)` (A's program.py, additive);
  d99a5c8e closure lift (`assessment_twin`/`assessment_closure`/`AssessmentClosure`, inert); 9c7e78f8 schema check
  lists accept V7; 9ee9a087 WO-B3 part 3 (§4.10.3 V3/V5/V6/V7, `formulation.assessment`, tests). WO-B3 is complete
  in code; A33/A34/A36 on the registered P2 remain I1's.
- **Gates run:** `test_e01_*`, `test_m03_*`, `test_m05_readiness`, `test_schemas_p01`: 459 passed, 1 skipped (default
  env); nlp env (`scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt --
  tests/test_e01_b_nlp.py tests/test_m03_nlp_greybox.py`, W = the m05 worktree): 21 passed; G9 dump
  (`$SCRATCH/b3/g9.sh <tag>`, compares with `$SCRATCH/b3/m03_base.json`) IDENTICAL; `e01_d04_inventory.py --check`
  0; t08 policy `--check` 0; ruff/format clean; mypy clean on src (test-file mypy errors in test_m03_nlp_status are
  pre-existing; mypy's scope is src+benchmarks). Nothing under compile/, thermo/, models/; no S11 file; not pushed.
- **WO-B4 not started** (stopped at the context cap). Plan, unchanged from §5.3/§9.5: `benchmarks/e01/cost_hand/
  cost_hand.py` (pattern: `benchmarks/e01/lca_hand/lca_hand.py` — no `openflowsheet` import, mpmath 30 digits,
  writes `cost_hand.yaml`, `--print`), transcribing forms I–VII (§9.2.4) from the pinned
  `$SCRATCH/idaes_src/idaes/models/costing/SSLW.py` (IDAES 2.13.0; line anchors in §9.2.4 and E01A's FACT
  "transcription" — thickness :532-533/:634-635, pressure :492, pump :1387-1623, motor :1624-1677, CE 394 from
  costing_base.py:66), never from `_data/assessment/cost/sslw-idaes-v1.json`. Values at S_min, √(S_min·S_max), S_max
  per entry and range (turbine 10/100/1000 hp), each floor bound and 1e-6 relative inside, defaults per §9.2.4, and
  P1's sizes from track A's `p1_th_c1.json` report fixture (P3's when I1 names it). Then A10 (exchanger: ΔT_lm
  71.95947205233731 K, area 27.79342236620868 m²), A11/A12 hand cases with identity volumes (RT/P, Amagat; §9.4),
  the chain/CRF/escalation cases; `benchmarks/e01/brightway/` P4 `foreground_check` expectation (lca env,
  `$SCRATCH/venv-lca`) and the IDAES cross-check script (§9.5 A15: effective inputs, `cost_vessel` direct, tray
  rescale, pump/motor in USD_CE500). A14/A15 compare against these in I1.
- **Open for the design lane (batched):** the part-3 DECISION lines above (select extension in A's file; rows as
  named constraints; V5 functional rules; not-evaluable handling; V7 absent without an assessment and the V7→V8
  test example; `formulation.assessment.outputs` = bound outputs only), plus part 2's and the earlier ones.
- **Not B's:** `test_m07_mr12_extras_v02::test_the_git_backed_measure_at_head` (I1); packaging `_data/assessment/**`.

## WO-B4 (independent cost expectations)

- DECISION: A11's host is TH-R1's flash `D.drum` → TH-C1 (P1's fixture) has no flash; E01A names TH-C1 and TH-R1 as the
  P1 candidates. Alternative: wait for I1 to name a P1 with all four units. Reversible by: `a11_th_r1_drum` in
  `recorded_states.yaml` and `test_a11_*`.
- DECISION: A11/A12's solved-state inputs are written by `tests/test_e01_b_cost_hand.py --write-states` (S11 solve, the
  IAPWS-95 provider through S11's `saturation`/`phase_properties`, syn001's `V_MOLAR`, the document's molar masses; no
  assessment code) into `benchmarks/e01/cost_hand/recorded_states.yaml`; a test re-solves (rel 1e-9) and checks the
  fixtures' `state_sha256`. `cost_hand.py` reads the file as data. Alternative: transcribe values into the script.
- DECISION: registered `S_max` points are targeted at `S_max·(1−1e-14)` (and the 40 ft piece boundary and D maxima at
  ±1e-12) → binary64 rounding of a multi-step size must not cross into `units:2`, a discontinuous regime. The package's
  regime label is not asserted at an exact floor bound (cost continuous there). Reversible by: `cost_hand.py`.
- FACT (observation for the design lane, not numerics): the package refuses an explicit `pump_type_factor` on a
  non-centrifugal pump (`NO_CORRELATION`); IDAES ignores it (F_T = 1, SSLW.py:1570-1571). The expectations omit it.
- FACT: the note's F_NT(10), F_NT(19) are binary64 evaluations (1.0414 rounded: rel 1.0e-15 from the decimal value
  used in cost_hand); A21's CRF is the float value within 2 ulp (exact 0.1018522088231506168). The script asserts every
  §6.1/§9.6 number it recomputes (A10, A20, A21, A44 vessel/η_m/F_NT/r) at those tolerances; all agree.
- FACT (escalation): WPU11 2006/2023 annual 126.167/174.192 equal the means of BLS's monthly values (raw API files,
  sha256 a1ec04c4…1727, 62bfea28…f522) to 3 decimals: 126.16667, 174.19217.
- DECISION: A15's IDAES run uses a stand-in namespace for the unit model and solves each `var == expr` constraint for
  its free variable (`calculate_variable_from_constraint`), in a scratch venv (`$SCRATCH/venv-idaes`: the pinned wheel,
  pyomo 6.10.1, pint 0.26.2, pyyaml). The script sits in `benchmarks/e01/brightway/` as §5.3 places it.
- DECISION: the Brightway P4 expectation uses bw2calc on float64 bw_processing vectors written from §4.8.5 (no bw2data,
  no adapter code) → independent of the adapter's assembly. Alternative: record the adapter's `foreground_check`.

### WO-B4 gates (2026-10-28)

| Check | Result |
| --- | --- |
| A14 registered sizes (87 cases, 8 entries; package vs mpmath) | worst rel 2.29e-15 (limit 1e-10); regimes and 2 refusals match |
| A14 P-sizes (TH-C1, TH-R1, M1: 13 items; package and fixture purchased) | worst rel 1.01e-15 |
| A15 vs IDAES 2.13.0 (85 cases + 13 items) | package 1.00e-14, transcription 1.02e-14 (limit 1e-9); tray smooth_max +2.45e-9 rescaled |
| A10 / A11 / A12 | ΔT_lm, area rel ≤ 1e-13; drum D, L, V ≤ 2.2e-16, `L` controls; shell D_j² (5 trays), j* = 2, D, H, N_act 8 ≤ 1e-12 |
| Chain on P1 (E, TDC, EPC, CAPEX, CRF, tac) | ≤ 6.7e-16 against the fixture |
| A25 P4 rate vs Brightway (bw2calc 2.5.0) | 2.85e-16 (limit 1e-10); adapter `foreground_check` vs record ≤ 1e-12 (lca env) |

Disagreements between the two transcriptions, or with IDAES: none beyond 1.02e-14.

## Handoff (2026-10-28, after WO-B4) — resume from here

- **Done (wp/E01 after 30241187):** d8907283 `benchmarks/e01/cost_hand/` (cost_hand.py → cost_hand.yaml, `--check`;
  recorded_states.yaml) + `tests/test_e01_b_cost_hand.py`; 8742596b IDAES cross-check (`benchmarks/e01/brightway/
  idaes_crosscheck.{py,yaml}`); cd44133b Brightway P4 expectation (`foreground_p4.{py,yaml}`), A25 test, lca-env test.
- **Gates run:** `test_e01_b_cost_hand.py` 12 passed; with `test_e01_b_lca`, `test_e01_a_report`, `test_e01_a_cost`:
  69 passed (default env); `test_e01_b_brightway.py` 4 passed (`$SCRATCH/venv-lca`); `e01_d04_inventory.py --check`
  A42 PASS; ruff/format clean; mypy clean on the three new benchmark scripts. No full gate. Not pushed.
- **Re-runs:** if `cost_hand.yaml` changes, re-run `idaes_crosscheck.py` in `$SCRATCH/venv-idaes` (the test checks the
  case-file sha256); if `lca_hand.yaml` changes, re-run `foreground_p4.py` in `$SCRATCH/venv-lca`. If S11 solves move,
  `python tests/test_e01_b_cost_hand.py --write-states`, then `cost_hand.py`.
- **For I1:** A14/A15/A25 are in place on P1 = TH-C1 (+ TH-R1 for the drum) and P3 = M1; if I1 names another P1, add
  its fixture's items to `P_SIZES` in cost_hand.py and re-run both records. Most P-size items sit in `floor` (§9.7 risk).
- **Open for the design lane (batched):** the decision lines above, and the pump_type_factor observation.
- WO-B4 is complete. Nothing under compile/, thermo/, models/; no S11 file.

## WO-I1 (integration)

- DECISION: the single repository copy of the assessment data → top-level `assessment/{cost,index,lca}/*.json`, each
  `src/openflowsheet/_data/assessment/<kind>/<file>` a per-file link to it, seven file entries in
  `resources.PACKAGED` (S05's one-file pattern: repository path = package path, so `REPOSITORY_PATHS` and T08's
  "only the web shell sits elsewhere" test are untouched), per-directory globs in `pyproject.toml`. T08 tests amended
  as R-617 did: W4's packaged-file count 6 → 13; A32's `ATTRIBUTED_DATA` gains the six third-party files by hash, each
  with its strings in NOTICE (`E01_ATTRIBUTION`; IDAES BSD licence in full), controls (pre-E01 NOTICE, changed bytes)
  per file; `SHIPPED_DATA` gains the synthetic `test-background-v1.json`; L40's text names the six and
  `docs/support-matrix.md` is re-emitted. Alternative: `assessment-data/` + a `REPOSITORY_PATHS` entry (ESC-B2's
  proposal; amends the web-shell test). Reversible by: the packaging commit.
- DECISION: MR-12 for the `lca` extra → S07 Ruling M's pattern: the `HEAD` tripwire of
  `test_m07_mr12_extras_v02::test_the_git_backed_measure_at_head` lists `lca` beside `coolprop`, each without an
  `MR12_AUDITS` entry, and still expects `fail`; the measure is unchanged and the release specification supplies the
  entries (F-9). Alternative: an `MR12_AUDITS["lca"]` entry now — it needs a step-14 RC check id that does not exist,
  so the measure would still fail and the entry would be invented. Reversible by: the MR-12 commit.
