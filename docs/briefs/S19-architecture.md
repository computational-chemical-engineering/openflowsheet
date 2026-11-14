# S19 architecture pass: repo-wide layers, cycle cuts, splits, work orders, end gate

Design lane (architect), 2026-11-14. Measured at wp/S19 30cc5a61 (main d90b498f plus S19 setup) with cce-code-health
d542005, using `codehealth arch|scan --config <trial>` on a scratch trial config (scope `src/openflowsheet/*`, roots
`src`), never committed. Inputs: `docs/briefs/S19-digest.md`, `docs/briefs/S17-architecture.md` (its mechanics in
section 3 apply here unchanged), `docs/S17_DECISIONS.md` (D18, D19, D20). The interface changes this note needs are in
`docs/adr/0076-S19-interface-redesign.md` (proposed); this note cites them as I-n.

## 0. Decisions

1. **One repo-wide total order** (`repo-layers`, section 1) added beside S17's `application-layers` rule, which stays
   as is. Package = layer, except six module entries where a package genuinely straddles a layer. At adoption it
   records **12 repo violations + 2 application violations = 14**, **10 cycles, 79 cycle edges** (tool, trial config).
2. **Cycle 1 has one load-bearing edge.** `equilibrium_form -> cascade` (a lazy import of the `CascadeFailure` value
   type, equilibrium_form.py:130) is what fuses the syn001 kernels, the column/cascade family, the region solver and
   the verifier into one 17-module component. Moving that dataclass to a leaf removes 47 of the 79 cycle edges
   (simulated on the module graph, which reproduces the tool's 10/79 exactly at base).
3. **The column/cascade solve modules sit above the orchestrator.** `column_solve`, `cascade_solve`, `column_blocks`,
   `column_unit` drive the orchestrator's EO region solver (`solve_region`, `Continuation`, `eo_recovery_due`); they
   are plug-ins above their host, reached by the executor only through the unit interface. They keep their paths;
   the layer order lists them as module entries. Rejected: injecting the region solver into the column through the
   builder (threads a callable through compile/solve signatures of the most sensitive unit; no gain in correctness).
   Rejected: a path move to a `models/.../solved/` subpackage (test churn for four modules, legibility only).
4. **Moves by meaning, not by convenience.** A definition moves to another package only where it belongs there by what
   it is: the solve-record vocabulary `orchestrator.trace` becomes `numerics.trace` (numerics produces it); the
   lifted-split vocabulary (Regime, LiftedSplit, KIND_TOLERANCE, ...) becomes `models.lifted` (units declare it, the
   solver consumes it); the route-policy table `application.policies` becomes `orchestrator.policies` (it imports only
   orchestrator modules); K05's one-run pipeline `run.session` becomes `application.run_session` (it uses the binder).
   Everything else moves within its package.
5. **Splits before function steps for files of 1000 NLOC or more; function steps first below that** (section 4).
6. **End gate**: the orchestrator's proposal is accepted with two clarifications (section 6): health >= 9.0 is the
   binding criterion (it implies debt well below 1900), and `huge_file` includes the CoolProp data module.
7. Every structural step stays bitwise and API-preserving (re-export at the old path, S17 mechanics). Interface
   changes, including dropping every re-export, are ADR 0076 steps at the end. No shim survives the campaign.

## 1. The target architecture: `repo-layers`

Package import graph today (digest): application imports everything; the back-edges are models -> orchestrator (14,
all from the column/cascade family), numerics -> orchestrator (3, all `trace`), orchestrator -> verify (1), run ->
application (2), assessment -> application (1), assessment -> studies (1), messages -> registry (1).

**Order (top imports down; a module may import its own layer and any layer below):**

| # | entry | why here |
|---|---|---|
| 1 | `openflowsheet.application` | surfaces, facade, services; internal order by `application-layers` |
| 2 | `openflowsheet.run.session` | interim: K05 one-run pipeline, moves into application (I-4), entry then deleted |
| 3 | `openflowsheet.studies` | sensitivities, sweeps, NLP, trust region, surrogate: consume assessment and runs |
| 4 | `openflowsheet.assessment` | cost/LCA functionals of a solved flowsheet |
| 5 | `openflowsheet.studies.nlp.tolerances` | new leaf: M03's V-tolerances, read by assessment's V3 test (I-7) |
| 6 | `openflowsheet.adapters` | external models and experiment records |
| 7 | `openflowsheet.verify` | the verifier and certificate; above the solver it judges |
| 8 | `openflowsheet.run` | bundles, manifests, replay, comparison: read solve policies, used by the verifier |
| 9 | `openflowsheet.models.syn001.column_unit` | the column as a flowsheet unit (solves itself) |
| 10 | `openflowsheet.models.syn001.column_solve` | column compiled and solved via `orchestrator.region` |
| 11 | `openflowsheet.models.syn001.column_blocks` | column block openings (imports both solve modules) |
| 12 | `openflowsheet.models.syn001.cascade_solve` | cascade compiled and solved via `solve_region` |
| 13 | `openflowsheet.orchestrator` | execution plans, tear loops, EO regions, homotopy, recovery |
| 14 | `openflowsheet.run.solution_state` | the solution-state document the warm start reads (leaf) |
| 15 | `openflowsheet.models` | unit models, kernels, rows, flowsheets, lifted vocabulary |
| 16 | `openflowsheet.thermo` | property providers |
| 17 | `openflowsheet.graph` | structural analysis (generic) |
| 18 | `openflowsheet.numerics` | Newton, PTC, Anderson, linear solve, scaling, and (after I-1) the solve trace |
| 19 | `openflowsheet.compile` | problem spec, reference evaluation, CasADi backend |
| 20 | `openflowsheet.registry` | extension registry (consumes the message catalogue) |
| 21 | `openflowsheet.messages` | catalogue, render, diagnostic, audit |
| 22 | `openflowsheet.units` | units of measure, display conversion |
| 23-29 | `serialize`, `compiled`, `canonical`, `resources`, `_files`, `ir`, `openflowsheet` | foundation |

Choices between unrelated packages (no edge either way today) put the generic below the domain-specific, so the likely
future import is the permitted one: numerics and graph below models and thermo (a unit or provider may want Newton;
Newton never wants a unit); registry just above messages (anything above may consult it). A future import between two
unrelated packages that the order forbids is a reviewed config commit, as in S17.

**Paste-ready text** (one config commit, orchestrator; it also widens `[scope] include` to
`["src/openflowsheet/*"]`; the gate reads the config at the base, so this commit precedes the first S19 step):

```toml
[[architecture.layers]]
name = "repo-layers"
# S19 design note section 1. Package = layer; module entries where a package straddles a layer.
# Recorded at adoption (12), each with the step that removes it (section 4, table 4.1):
#   numerics.anderson|newton|ptc -> orchestrator.trace                 A5 (I-1, trace to numerics)
#   models.syn001.cascade|column -> orchestrator.region                A4 (lifted vocabulary to models)
#   models.syn001.column_blocks -> models.syn001.column_solve          B3 (column_solve split)
#   assessment.program -> studies.nlp.verification                     A6 (V-tolerances leaf)
#   messages.catalogue -> registry                                     A11 (freeze hook)
#   assessment.spec -> application.types                              A12 (schema check to foundation)
#   run.bundle -> application.policies                                 A13 (I-3)
#   run.session -> application.binding                                 A14 (I-4)
#   orchestrator.region -> verify.checks                               A15 (design lane, R-016)
order = [
    "openflowsheet.application",
    "openflowsheet.run.session",
    "openflowsheet.studies",
    "openflowsheet.assessment",
    "openflowsheet.studies.nlp.tolerances",
    "openflowsheet.adapters",
    "openflowsheet.verify",
    "openflowsheet.run",
    "openflowsheet.models.syn001.column_unit",
    "openflowsheet.models.syn001.column_solve",
    "openflowsheet.models.syn001.column_blocks",
    "openflowsheet.models.syn001.cascade_solve",
    "openflowsheet.orchestrator",
    "openflowsheet.run.solution_state",
    "openflowsheet.models",
    "openflowsheet.thermo",
    "openflowsheet.graph",
    "openflowsheet.numerics",
    "openflowsheet.compile",
    "openflowsheet.registry",
    "openflowsheet.messages",
    "openflowsheet.units",
    "openflowsheet.serialize",
    "openflowsheet.compiled",
    "openflowsheet.canonical",
    "openflowsheet.resources",
    "openflowsheet._files",
    "openflowsheet.ir",
    "openflowsheet",
]

[[architecture.forbid]]
name = "verifier-not-through-the-solver"
from = ["openflowsheet.verify"]
to = [
    "openflowsheet.orchestrator.region", "openflowsheet.orchestrator.executor",
    "openflowsheet.orchestrator.execution", "openflowsheet.orchestrator.homotopy",
    "openflowsheet.orchestrator.recovery", "openflowsheet.orchestrator.coupling",
    "openflowsheet.orchestrator.merge", "openflowsheet.orchestrator.attempts",
    "openflowsheet.numerics.newton", "openflowsheet.numerics.ptc", "openflowsheet.numerics.anderson",
]
reason = "R-016: the verifier shares no solve code (it may read structure: rank, splits, tear)"
```

Insert both blocks after the existing `application-layers` block. Adoption check (`codehealth arch` with the committed
config): 282 files; `application-layers` 2 violations (unchanged); `repo-layers` exactly the 12 above; the forbid rule
0; 10 cycles, 79 edges; one warning (`studies.nlp.tolerances` matches no module until A6). Each later new module gets
its entry in the config commit before its step (S17 section 2 rule); when I-1 and I-4 land, delete the
`run.session` entry and nothing else changes (`orchestrator.trace` needs no entry: its importers become
`numerics.trace`).

## 2. Cycles: which edges to cut, and how

Numbers after each cut are in table 4.1. "Leaf" means a new module whose closure imports nothing that reaches the old
module (the S17 downward-extraction rule; otherwise the re-export closes a new cycle and the gate fails).

**Cycle 1 (17 modules, 51 edges).** Three cuts dissolve it; two more remove its layer violations.
- A1 `equilibrium_form -> cascade` (lazy, :130): move `CascadeFailure` and the `FailureOutcome` alias it annotates
  (cascade.py:308-318 and the alias's definition) to leaf `models/syn001/cascade_failure.py`; `equilibrium_form`
  imports it at top level (the lazy import and its comment go); `cascade` re-exports. 79 -> 32 edges; the component
  splits into {gamma_phi, saturation_band} and {verify.checks, verify.saturation}, so cycles 10 -> 11.
- A2 `gamma_phi -> saturation_band` (:30): move `MAX_TEMPERATURE_EVALUATIONS`, `BandError`, `BandTemperature`,
  `Position` to leaf `models/syn001/band_types.py`; gamma_phi imports them there; saturation_band re-exports. Its lazy
  `gamma_phi` import (:261) stays lazy (moves are verbatim; hoisting it is a later refactor step).
- A3 `verify.saturation -> verify.checks` (:33, only `KIND_TOLERANCE`): move the verifier's `KIND_TOLERANCE`
  (checks.py:66) to leaf `verify/kind_tolerance.py`; checks re-exports. The solver's own `KIND_TOLERANCE`
  (region.py:184) is a separate object on purpose (R-016) and is not merged with it.
- A4 (violations, not cycle) `cascade`, `column` -> `orchestrator.region` for `Regime`, `KIND_TOLERANCE`: move the
  lifted-split vocabulary to `models/lifted.py` (region.py: `Regime`, `ClosureType`, `Branch`,
  `INADMISSIBLE_BRANCH`, `EQUILIBRIUM_TOLERANCE` if the closure needs it, `KIND_TOLERANCE`, `LABEL_KIND` (:982),
  `LiftedSplit`, `ZeroFlowForm`, `VapourOnlyForm`, `DormancyForm`, `StagedSplits`; lines 43-340 roughly). Retarget
  cascade.py:84 and column.py:126 only. STOP if the closure reaches any `orchestrator` module or
  `syn001_lifted_splits` (that SYN-001 builder stays in region).
- A15 `orchestrator.region -> verify.checks` (lazy :786, `k_values`): the solver's single-phase admissibility on the
  SYN-001 provider uses the verifier's own K-values. This is a phase-logic and independence question, not a move:
  design lane (Q3). Default ruling to implement: move the provider evaluation (the `lnK` request at the reference
  state and the `exp`, checks.py:642-648) into `models/syn001/equilibrium_form.py` as public `reference_k_values`
  returning `None` on a non-`ok` status; `verify.checks.k_values` keeps its signature and raises `VerifierError` on
  `None`; on `None` region raises a plain `RuntimeError` with the message text `k_values` uses today. Arithmetic is
  identical (same request, same `math.exp`); only the exception type on a provider failure in the solver path changes,
  so the step needs the fact "nothing catches `VerifierError` on the solve path" (grep, then the full suite).

**Cycle 2 (messages, registry; 6 edges).** Registry sits above messages (it merges extension entries into the
catalogue). A11 makes three cuts, one commit, design-lane review (initialization order):
- `registry.discovery -> messages.catalogue` (`_yaml_load`, :299): move `_yaml_load` to leaf
  `messages/yaml_io.py` as public `yaml_load`; catalogue re-exports the private name until I-19.
- `messages.audit <-> messages.catalogue` (both lazy): move the default validator that catalogue.py:274 takes from
  `audit` into catalogue's own module if its closure does not need `CATALOGUE`; otherwise audit's validator takes the
  catalogue as an argument. Fix the exact names at the base; STOP if neither holds.
- `messages.catalogue -> registry` (lazy hook :345): invert. The catalogue gets a module-level hook slot
  (`set_before_freeze(callable)`); `openflowsheet.registry` installs `before_catalogue_freeze` into it at import.
  Fact needed (Q4): every path that freezes a `_registry_first` catalogue has imported `openflowsheet.registry`
  first. Default if the fact fails: the slot is filled by the application's composition root (`local.py`,
  `serving.py`, `cli.py` already import registry) and a library-only freeze raises a typed error instead of silently
  freezing without extensions; that is a behaviour change, so it goes to the reviewer before it runs.

**Cycle 3 (verify.table, gamma_phi_units, thermal; 4 edges).** Part of split B5: what the two family modules import
from `table` (`Unit`, `ModelChecks`, `blocked_check`, `stream_notes`, `_unlifted_read`, `_nothing`, lines 170-348,
plus whatever the closure adds) moves to leaf `verify/table_kit.py`; retarget gamma_phi_units.py:65 and thermal.py:43.
The lazy family imports in table (:1681, :1728) then point down. -1 cycle, -4 edges.

**Cycle 4 (assessment.program, report, studies.nlp.verification; 4 edges).** A6, two leaves:
- `studies/nlp/tolerances.py`: the whole V-tolerance block `TAU_GROSS ... TAU_VERTEX_MULTIPLIER`
  (verification.py:81-88), kept together because they are one registered table (M03 §4.2.1). `assessment.program`
  imports `TAU_FEAS` from it (layer entry 5 makes that legal; the leaf imports nothing).
- `assessment/linearization.py`: `Linearization`, `Refusal` and `_feasibility_tolerance` (program.py:448-453 and the
  two classes). report.py:29 and verification.py:45 retarget to it. The lazy `program -> report` (:823) then points
  down and stays lazy. Order inside A6: the tolerances leaf first, with program.py:451's lazy import retargeted to it
  in the same commit (a listed importer); only then the linearization leaf, so the moved function carries the
  already-retargeted import verbatim.

**Cycle 5 (application revision_routes, revision_run, validation; 4 edges).** ADR I-10 (S17 D4). `traced_analysis`
moves down from revision_run with validation's structural stage (`StructuralAnalysis`, `_analysed`,
`structural_analysis`, `structural_refusal`, `_structural`, `structural_checks` and closure) into
`application/structural_stage.py`, placed between `revision_run` and `binding` in `application-layers`; the run path
receives the caller's `ValidationReport` instead of calling `validate` (revision_run.py:381). Design-lane review:
replay identity (the report's timestamp may be recorded; Q6).

**Cycle 6 (units, units.display; 2 edges).** I-6: `units/__init__.py` stops re-exporting display-conversion-v1
(:612-618); callers import `openflowsheet.units.display`, the module ADR 0075 named.

**Cycle 7 (column_blocks, column_solve; 2 edges).** Part of split B3: the names column_blocks.py:33 imports from
column_solve move into the new lower module(s) of that split; column_solve's lazy import (:1512) then points down.
-1 cycle, -2 edges, -1 violation.

**Cycle 8 (application contract, types; 2 edges).** I-9 (S17 D3): the error vocabulary to `application/errors.py`.

**Cycle 9 (studies.surrogate manifest, study; 2 edges).** A7: `MODEL_ID`, `Observation`, `SurrogateEvaluation`
(imported at manifest.py:76) move to leaf `studies/surrogate/records.py`; study re-exports; study's lazy
`build_records` import (:423) then points down.

**Cycle 10 (assessment.sizing, families; 2 edges).** A8: everything families.py:30 imports from the package
`__init__` (GRAVITY and the registration API, closure at base) moves to `assessment/sizing/core.py`; `__init__`
re-exports it and keeps the lazy `_load_builtin` (:602-608) unchanged, so built-in registration still happens on
first use, in the same order.

## 3. Splits of the large files (ranked; restructure mode, S17 mechanics)

Debt is unchanged by a split; health rises by the file-size penalty (large 1.0, huge 2.0) and duplication. Closures
are computed at the plan's base over top-level name references, as in S17 R3; each split STOPs and reports if a new
module's closure reaches a name that stays in the old file (that would be an upward import and a cycle).

| rank | file (NLOC, debt, health) | new modules (move sets) | stays | arch effect |
|---|---|---|---|---|
| B1 | orchestrator/region.py (2137, 415.6, 1.0) | after A4: `region_phase.py`: the phase-policy kernel `_KernelRefusedError` .. `_dropped` (472-963); `region_problem.py`: `_labels` .. `_units_and_items_disjoint` and `_LiftedOps` (964-1624); `region_attempts.py`: `_swapped_row_test` .. `_boundary_unit` (2559-2911) only if its closure does not reach `_solve_region` | result types, `syn001_lifted_splits`, screen, `solve_region`, `_solve_region` | 0 / 0; region below 1000 NLOC |
| B2 | models/syn001/column.py (1670, 352.9, 1.0) | `column_spec.py`: declarations (194-415), the specification (416-497), names (498-625); `column_validation.py`: spec §5 (626-1223); `column_rows.py`: declared rows (1224-1791) | regime forms, initializer | 0 / 0 |
| B3 | models/syn001/column_solve.py (1254, 101.1, 3.4) | `column_compile.py`: slots, region descriptors, compile (214-436); `column_acceptance.py`: §8 acceptance, products, closure, spec values (437-769); `column_endpoint.py`: §18.2 endpoint and S06 inverse records (770-1099). Retarget column_blocks.py:33 to them | the solve path (1100-end) | -1 cycle, -2 edges, -1 violation |
| B4 | models/syn001/cascade.py (1023, 118.9, 2.1) | `cascade_spec.py`: declarations, specification, names (123-391); `cascade_rows.py`: declared rows and problem (670-960); `cascade_init.py`: Kremser/Thomas initializer (1014-1201) | validation, regime forms, dormant answer | 0 / 0 |
| B5 | verify/table.py (1483, 120.1, 1.6) | `table_kit.py` (cycle 3 above); `unit_checks.py`: the K02, T05, T08 entries and `_ModelChecksTable` (349-1151); `split_checks.py`: admissibility, independent split, degeneracy (1260-1675) | flowsheet rows, `revision_checks`, `revision_phase_branch` | -1 cycle, -4 edges |
| B6 | studies/trust_region/projection.py (1343, 272.9, 1.0) | `projection_checks.py`: shape check, omitted rows (1063-1347); `projection_zero_flows.py`: exact-zero flows (1348-1757); helpers (906-1062) move with them only if both need them, into `projection_support.py` | the projection, `project`, `_assemble` | 0 / 0 |
| B7 | thermo/_coolprop_heos_fluids.py (4906, data, 8.0, huge) | one module per fluid group, each under 1000 NLOC; the old module re-exports the tables (if a generator writes it, change the generator instead; Q8) | | 0 / 0 |
| B8 | orchestrator/executor.py (1057, 60.4, 5.0) and verify/certificate.py (1088, 67.2, 4.9) | concept groups fixed at the base by the engineer from section headers, same rules | | to be fixed at the base |
| C* | assessment/cost/contributor.py (1028, 123.4, 2.8) | NOT a statement split: `_Planner` (207-1144) is one class. Function-first: turn the planner's stages (sizing, cost forms, escalation, bare module, capital chain, as its docstring orders them) into module functions in refactor mode; then move the module-level item helpers (79-206) to `cost/items.py` if the file is still over 1000 NLOC | | 0 / 0 |

Ranking: B1 and B3 first (cycle and violation removal, worst health), then B2, B5, B4, B6, B7, B8. B1 requires A4;
B3 must not precede A1.

## 4. Work orders

### 4.1 Cycle and layer steps, in order, with the numbers fixed before the runs

Simulated on the module graph (exact at base); the engineer confirms each with `codehealth arch` at the step's base and
STOPs on a difference. Mode: restructure (plan file, `ast.dump` identity) unless marked refactor or ADR.

| step | change | violations (repo+app) | cycles / edges |
|---|---|---|---|
| base | adoption | 14 | 10 / 79 |
| A1 | `CascadeFailure` leaf | 14 | 11 / 32 |
| A2 | `band_types` leaf | 14 | 10 / 30 |
| A3 | `kind_tolerance` leaf | 14 | 9 / 28 |
| A4 | `models.lifted` | 12 | 9 / 28 |
| A5 | `numerics.trace` (restructure: all statements move; orchestrator.trace re-exports; retarget numerics only) | 9 | 9 / 28 |
| A6 | `studies.nlp.tolerances`, `assessment.linearization` | 8 | 8 / 24 |
| A7 | surrogate `records` | 8 | 7 / 22 |
| A8 | sizing `core` | 8 | 6 / 20 |
| B5a | `verify.table_kit` (first commit of B5) | 8 | 5 / 16 |
| B3 | column_solve split | 7 | 4 / 14 |
| A11 | messages/registry (refactor mode, design-lane review) | 6 | 3 / 8 |
| A12 | `schema_errors` and its `_validator` closure from application.types to `openflowsheet/schema_check.py` (I-5; layer entry `openflowsheet.schema_check` just above `openflowsheet.serialize`) | 5 | 3 / 8 |
| A13 | `application.policies` -> `orchestrator.policies` (I-3; restructure, retarget run.bundle) | 4 | 3 / 8 |
| A14 | `run.session` -> `application.run_session` (I-4; ADR step) | 3 | 3 / 8 |
| A15 | region K-values (refactor, design lane) | 2 | 3 / 8 |
| A16 | units display re-export dropped (I-6, ADR step) | 2 | 2 / 6 |
| A17 | `application.errors` (I-9) | 1 | 1 / 4 |
| A18 | structural stage, run path takes the report (I-10) | 0 | 0 / 0 |

If the order changes, recompute the rows at the new base before the run; a row that differs is a miss (reset, report).

### 4.2 Phases and parallelism (at most two engineers at once; disjoint files; each in its own worktree)

- **W0 (orchestrator).** Config commit (section 1). Then the blocking fact Q1 (registry self-hash) before any models,
  thermo or orchestrator edit. Rebuild the test-impact map at the new base.
- **W1 (cycles).** Lane a: A1, A2, A3, A4 (models.syn001, verify, orchestrator.region head). Lane b in parallel: A6, A7,
  A8 (studies, assessment). Then A5 alone (touches numerics and 31 importers' module only by re-export).
- **W2 (splits).** Pairs on disjoint files: (B1 orchestrator) with (B6 studies); (B3, B2, B4 in that order, models)
  with (B5, B8-certificate, verify); then B7 with B8-executor.
- **W3 (function-level, refactor mode, per package group).** G1 orchestrator + numerics (most sensitive), G2 models,
  G3 studies, G4 assessment (contributor first), G5 verify + run, G6 thermo + graph + messages + units + adapters +
  registry + compile. Parallel pairs: (G1, G4), (G2, G3), (G5, G6). Order within a group: brain functions first, then
  files with health < 7.0 by debt, then the rest by debt.
- **W4 (interfaces, after Frank accepts ADR 0076).** A11-A18 that are ADR steps, then I-11 .. I-19, last the drop of
  every re-export (I-19). Then G7: application function-level work on the post-ADR layout.

**Splits first for files of 1000 NLOC or more** (opposite to S17), because: (1) a split is mechanically verified
(`ast.dump` identity) and cheapest on unchanged statements; after function steps the plan must chase new helpers;
(2) the 2000-line files do not fit an engineer's 150k context with tests and gate logs, and a function step on a
smaller file is reviewed on a smaller diff; (3) B3 and B5 also remove cycles, which narrows test selection for every
later step in those packages; (4) the brain functions (`_solve_region` 564 NLOC, `declared_rows` 425 NLOC) then stay
in a file that holds only their concept, so extracted phases land beside them. Exception: a file whose bulk is one
class (contributor.py) cannot be split by statements; function-first there. S17's reason for function-first (plans
fixed after the private set settles) does not apply here: the plans are computed at their own base.

## 5. Sensitivity map and review cadence

Tier S1, residuals, derivatives, phase logic, scaling: `orchestrator/{region,tear,splits,phase_contract,attempts,
homotopy,recovery,coupling,mass}.py`, `numerics/{newton,ptc,anderson,scaling,linear}.py`, `models/**` (rows, blocks,
kernels `tp_state, ph_kernel, gamma_phi, saturation_band, equilibrium_form, admission`, column*, cascade*),
`compile/casadi_backend.py`, `thermo/*` (formulas), `studies/{sensitivity,estimation}.py`,
`studies/nlp/{greybox,formulation,phase,boundary}.py`, `studies/trust_region/{projection,basis,truths}.py`,
`assessment/{blocks,program,linearization}.py`, `assessment/lca/inventory.py`.
Tier S2, certificates and replay identity: `verify/**`, `graph/certificates.py`, `studies/surrogate/conformal.py`,
`run/**`, `canonical.py`, `serialize.py`, `registry/{selfhash,snapshot,legacy}.py`, `thermo/cache.py` (exact keys),
`studies/nlp/replay.py`, `studies/trust_region/trf_state.py`, `application/revision_run.py`, A11, A15, I-10.
Cadence: S1 function-level steps, a `reviewer` pass every 3 accepted steps and before any step that changes the
control flow of a brain function in numerics or region is followed by another step on the same function; S2 every 4;
splits and leaf moves in S1/S2 every 4 (they are `ast.dump`-gated); all other files every 8 (S17's cadence). Design-lane
rulings before the run: A15 (R-016), A11 (initialization order), I-10 (replay identity).
Arithmetic rule for S1 extractions: an extracted function receives its operands and returns its results in the same
order of floating-point operations; no reassociation, no hoisting of a sum, no change of `sum()` versus a loop, no
NumPy for Python arithmetic. Bitwise identity of F0 and of every test result is the gate, not a tolerance.

## 6. End gate

Measured base (trial scan, 282 files, 100136 NLOC): debt 6370.9, health 7.3, brain 44, 42 files below 7.0 (33994
NLOC), size smells 14 (huge: region.py, `_coolprop_heos_fluids.py`), cycles 10, violations 14.

| criterion | proposal | settled | reason |
|---|---|---|---|
| repo debt | <= 1900 | **<= 1900** | -70 %, S17 did -65 % on application; in practice the health criterion binds first |
| repo health (NLOC-weighted) | >= 9.0 | **>= 9.0, binding** | health = 10 minus capped smell penalties minus size penalty per file. Application at 16.2 debt/kNLOC with four large files scored 8.49; without the size penalty about 8.8. 9.0 therefore needs roughly 10-13 debt/kNLOC, i.e. debt near 1000-1300 |
| brain functions | 0 | **0** | numerics' three solver loops and `_solve_region` are the hard part (S1) |
| files with health < 7.0 | 0 | **0** | |
| `huge_file` | none | **none, data modules included** | B7 splits the CoolProp data module (4906 NLOC) |
| import cycles (depth 4) | 0 | **0** | table 4.1 |
| layer violations | 0 | **0 on both rules and the forbid rules** | A15 and A11 are the two that can fail on a ruling; a miss stays a miss |
| behaviour | | **F0 identical, MCP digest identical, full suite green, CI green on both architectures** | |

Per package (NLOC share; base debt / health / brain -> target health; feasibility):
models 22 % 1343 / 6.8 / 9 -> 9.0, medium (B2-B4, `declared_rows`, `revision_flowsheet._read`);
studies 16 % 1258 / 7.1 / 11 -> 9.0, medium; application 19 % 302 / 8.5 / 0 -> 9.0, medium (needs local, types,
revision_run, store under 1000 NLOC: I-9, I-12); thermo 9 % 294 / 7.4 / 2 -> 9.0, medium (B7 alone +0.1 repo-wide);
orchestrator 8 % 975 / 5.9 / 5 -> 9.0, low-medium (B1, `_solve_region`, `check_agreement`, `couple`,
`build_execution_plan`); assessment 7 % 677 / 7.0 / 8 -> 9.0, medium; verify 7 % 378 / 6.0 / 2 -> 9.0, medium-high;
numerics 2 % 423 / 7.6 / 3 -> 8.5, low (three solver loops; reaching 9.0 here is not required for the repo figure);
run 1.5 % 258 / 7.3 / 3 -> 9.0, high (compare.py); graph, messages, units, adapters, registry, compile, top -> 9.0,
high. If the repo figure stalls below 9.0 after W3, report the measured figure as a miss with the per-package residue;
do not relax it.

## 7. Risks and open questions (each with a default)

- Q1 (fact, blocking for models/thermo edits) The registry self-hash (`registry/selfhash.py`) hashes the source files
  of an extension's implementation set; built-in descriptors come from generated package data
  (`registry/legacy.py`, `scripts/registry_builtin.py`). Does editing or splitting a built-in model module change
  `registry_sha256`, run manifests or F0? Experiment: a comment-only edit to `models/syn001/flash.py` in a scratch
  worktree, then `scripts/corpus_identity.py --check`, the generator's `--check`, and the MCP digest tests. Default:
  if only generated data changes, regenerate it in the same step through the committed generator and declare the
  file in the plan; if F0 or a manifest identity changes, stop and ask the design lane for an identity ruling.
- Q2 (fact) Persisted module paths: any artifact, schema or fixture that records a Python module path (pickles,
  `__module__`, `__qualname__`) would change under A5, A13, A14. Default: grep `schemas/`, `benchmarks/`,
  `tests/fixtures` for `openflowsheet.` paths before each move; F0 decides.
- Q3 (design lane) A15, the solver's use of the verifier's K-values (R-016). Default: the ruling in section 2.
- Q4 (fact) A11's freeze hook: which paths freeze the process catalogue without importing the registry. Default: the
  fallback in section 2, reviewed before it runs.
- Q5 (preference) New module names (`cascade_failure`, `band_types`, `kind_tolerance`, `models.lifted`,
  `numerics.trace`, `studies.nlp.tolerances`, `assessment.linearization`, `records`, `sizing.core`, `table_kit`,
  `yaml_io`, `schema_check`, split names in section 3). Default: these.
- Q6 (fact) I-10: is the run path's own `ValidationReport` (with its timestamp) recorded in a run artifact covered by
  the R0 identity? Default: if yes, the caller's report is passed and the R0 projection is checked unchanged on F0;
  if R0 changes, stop for a ruling.
- Q7 (preference) Module entries instead of a path move for the four column/cascade solve modules. Default: entries.
- Q8 (fact) Is `_coolprop_heos_fluids.py` generated? Default: if yes, split through the generator; if no, by hand.
- Q9 (fact) Whether the gate's public-API check can accept an ADR step that removes names. Default: the orchestrator
  adds an interface mode or an allow-list to the tool before W4; until then W4 steps run without the public-API tier
  and the reviewer checks the removed names against ADR 0076's table.
- Q10 (preference) Scope of the health gate for numerics (8.5 instead of 9.0 locally). Default: allowed locally, the
  repo figure still binds.
- Q11 (preference) Budget: W3 is roughly 5 times S17's function-level work (S17: 71 attempts for -553 debt on 18.6k
  NLOC). Default: proceed package by package and report the burn after G1 and G4.
- Not decided here: the legacy binder's future (ADR 0076, FQ1), and anything that changes a §2.1 signature or a §2.2
  schema (none is needed).
