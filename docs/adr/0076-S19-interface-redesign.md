# ADR 0076: S19, interface redesign for the repo-wide layering (the D19 package)

**Status:** **Proposed** (design lane, 2026-11-14). Takes effect on `main` when Frank accepts it and S19's manifest is
`tested` with the `reviewer` pass done; S19 is built on `wp/S19`.
**Author:** design lane (`architect`). **Brief:** `docs/briefs/S19-A1.md`.
**Normative text:** this ADR (I-1 to I-19) and `docs/briefs/S19-architecture.md` (the layer order, the cuts, the step
numbers and the end gate this ADR serves).
**Builds on:** S17 D19 (Frank, 2026-11-13: outward-facing interfaces may be renamed and restructured, no compatibility
shims); the S17 design note section 6 (candidates D1-D10); S17 review 11's list of re-exports and private names.
**Amends:**
- ADR 0019 D1: the K06 `Application` facade over `LocalApplication` is retired (I-11). A pointer paragraph is added
  to ADR 0019 in the form of its earlier amendments.
- ADR 0060 (extension registry): the catalogue freeze is reached through a hook the registry installs, no longer by a
  lazy import from `messages.catalogue` (I-14). Discovery reads YAML through `messages.yaml_io.yaml_load`.
- ADR 0075 (units at the boundary): `openflowsheet.units` no longer re-exports `display-conversion-v1`; its one home is
  `openflowsheet.units.display`, the module ADR 0075 named (I-6). Editorial for ADR 0075; no behaviour changes.
- `docs/interfaces-frozen.md`: a paragraph for this ADR (build lane, with the commit that lands I-19).
**Does not amend:** plan §2.1 Protocol signatures (`CompiledProblem`, `PropertyProvider`, `Application`); plan §2.2
schemas; the MCP tool surface and its digest; HTTP routes; CLI commands and outputs; the error JSON (I-9 moves
Python definitions only); any numeric result. R-016 (verifier independence) is applied, not changed (I-15).
**Affected requirements:** plan §1.3 interface freeze (§2.1 `Application`: `LocalApplication` is declared to implement
it, signatures unchanged); R-016 (I-15); replay identity (I-10, Q-F3).
**Affected packages:** S19 (all of `src/openflowsheet`), with tests, scripts, benchmarks, examples and docs that import
moved names.

## Context

S17 refactored `application/` with bitwise, API-preserving steps and left re-exports at every old path, two cycles
and two layer violations for this package. S19 extends the work to the whole package tree. Its architecture note sets
a repo-wide layer order (`repo-layers`) that records 14 violations and 10 import cycles (79 edges) at adoption. Most
are removed by bitwise moves that keep the old path as a re-export; the rest need the old path gone, a definition
moved to the package where it belongs, or a call shape changed. Frank's directive is that the design be done well
now, with no shims left. This ADR lists every outward-facing change S19 makes.

"Outward-facing" here means a public name, module path or signature that code outside its module imports, including
tests, scripts, benchmarks and examples. Every item below changes import paths only, unless it says otherwise.

## Decisions

Each item states the change, the reason, and the callers to migrate (counted at the base of the step; the S19 digest
and the design note give the module edges).

### Moves by meaning (the layer order needs them)

- **I-1** `openflowsheet.orchestrator.trace` becomes `openflowsheet.numerics.trace` (whole module: `SolvePolicy`,
  `GlobalizationPolicy`, `Trace`, `SolveEvent`, `Checkpoint`, `fraction_string`, ...). Reason: the solve record is
  what Newton, PTC and Anderson produce; it imports only `compiled` and `numerics.linear`. Removes 3 violations.
  Callers: about 31 modules in src (application, adapters, models column/cascade solve, orchestrator, run, studies)
  and their tests.
- **I-2** The lifted-split vocabulary moves from `orchestrator.region` to `openflowsheet.models.lifted`: `Regime`,
  `ClosureType`, `Branch`, `INADMISSIBLE_BRANCH`, `KIND_TOLERANCE` (the solver's), `LABEL_KIND`, `LiftedSplit`,
  `ZeroFlowForm`, `VapourOnlyForm`, `DormancyForm`, `StagedSplits` (final list = the closure at the step's base).
  Reason: units declare their splits in it, the region solver consumes it. Removes 2 violations.
- **I-3** `openflowsheet.application.policies` becomes `openflowsheet.orchestrator.policies` (`INNER_ROUTE`,
  `ROUTE_DEFAULT_POLICY`, `resolve_policy`, ...). Reason: the route-policy table imports only orchestrator modules,
  and the replay bundle reads it (run.bundle.py:219). Removes 1 violation.
- **I-4** `openflowsheet.run.session` becomes `openflowsheet.application.run_session`. Reason: K05's one-run pipeline
  (solve, verify, bundle) uses the binder (`structural_inputs`, run/session.py:101); its only callers are the CLI and
  revision_run. Removes 1 violation and the interim `run.session` layer entry.
- **I-5** `application.types.schema_errors` (and its private validator cache) becomes
  `openflowsheet.schema_check.schema_errors`. Reason: document validation against `schemas/` is foundation; the
  assessment spec needs it (assessment/spec.py:21). Callers: assessment.spec, application.coupled_run (2 lazy),
  application.validation (lazy), tests.
- **I-6** `openflowsheet.units` stops re-exporting the display-conversion names (units/__init__.py:612-618). Callers
  import `openflowsheet.units.display`. Removes cycle 6.
- **I-7** M03's V-tolerances `TAU_GROSS`, `TAU_FEAS`, `TAU_ACTIVE`, `TAU_KKT`, `TAU_SIGN`, `TAU_LICQ`,
  `TAU_VERTEX_MULTIPLIER` move from `studies.nlp.verification` to `openflowsheet.studies.nlp.tolerances`;
  `Linearization`, `Refusal` and the feasibility-tolerance reader move from `assessment.program` to
  `openflowsheet.assessment.linearization` (the reader becomes public `feasibility_tolerance`). Reason: assessment
  judges its inequalities with M03's `TAU_FEAS` without importing the NLP verifier; removes cycle 4 and 1 violation.
  Values unchanged; "imported, never redefined" still holds.

### Homes of the S19 leaves and splits become the only paths

- **I-8** Every module created by an S19 restructure step is the only path for the names it holds: `models.syn001.
  cascade_failure` (`CascadeFailure`, `FailureOutcome`), `models.syn001.band_types`, `verify.kind_tolerance` (the
  verifier's `KIND_TOLERANCE`; `application.admission` imports it there), `studies.surrogate.records`,
  `assessment.sizing.core`, `verify.table_kit`, and the split modules of design note section 3 (region, column,
  column_solve, cascade, table, projection, executor, certificate, the CoolProp data). Old modules keep only what they
  define. Private names that now cross modules become public where they are imported across modules (I-13).

### The application's own interfaces (S17 D1-D7)

- **I-9** (S17 D3) One error vocabulary: `ApiErrorCode`, `ApiError`, `SolveFailedError` (from types),
  `ApplicationError`, `api_error` (from contract) and validation's error constructors (`task_unsupported`,
  `nlp_solver_unavailable`, `optimization_request_missing`) move to `openflowsheet.application.errors`. Removes cycle
  8 and the `types -> contract` violation. `api_error` observes its caller's frame for the MSG audit: the call depth
  from every caller must stay the same (the move does not add a frame); the MSG audit test is the check.
- **I-10** (S17 D4) The structural stage (`StructuralAnalysis`, `structural_analysis`, `structural_refusal`,
  `structural_checks` and their closure, with `revision_run.traced_analysis`) moves to
  `openflowsheet.application.structural_stage`, below `revision_run`. The revision run no longer calls
  `validation.validate` (revision_run.py:381): its entry takes the `ValidationReport` its caller already holds
  (signature change of the run entry, internal to the application; the §2.1 `Application.solve` signature is
  unchanged). Removes cycle 5 and the last application violation. Design-lane review: replay identity (Q-F3).
- **I-11** (S17 D1) One application, one operation: `LocalApplication` is declared to implement
  `contract.Application` (§2.1, unchanged) and checked by a static conformance test; the K06 facade
  `transactions.Application`, `RevisionStoreView` and the alias `transactions.Operation` are deleted; the public
  `Operation` is `operations.Operation` only. Callers: 3 test imports (S17 count), docs.
- **I-12** (S17 D2) `LocalApplication` (local.py, 1777 NLOC, 77 methods) becomes a thin facade over per-family
  services: revisions and edits, validation and admission, jobs, artifacts and stream tables, audit and authorization,
  capabilities. `OPERATIONS` binds each operation to its service method. The facade keeps every public method name
  and signature (the Python API of `LocalApplication` is unchanged); the service classes are new public names.
  Reason: health (large file) and the change coupling S17 measured. Same rule for `types.py` (1531 NLOC),
  `revision_run.py`, `store.py`: split by concept to under 1000 NLOC with final names, no re-export.
- **I-13** (S17 D6, review 11) The builder kit is public: the pin readers and thermal signatures in
  `model_signatures` lose their underscore; `_column_owners` becomes `binding_common.column_owners`; `_defect`
  becomes `jobs.runner.defect_result`; `_basis_refusal` becomes `basis_refusal`. Tests stop importing private names
  (`_CONTEXT`, `_columns`, `_COLUMN`, `_declared_default` get public names or the tests use the public entry). The
  builder table stays a dict (`MODEL_BUILDERS`); its shape does not change.

### Low-level hooks

- **I-14** `messages.catalogue` gains `set_before_freeze(hook)`; `openflowsheet.registry` installs
  `before_catalogue_freeze` when imported; the catalogue no longer imports the registry. `messages.yaml_io.yaml_load`
  replaces the private `catalogue._yaml_load` for registry discovery. Behaviour: identical in every path that imports
  the registry before the first freeze (Q-F2); a freeze of a registry-first catalogue with no hook installed raises a
  typed error instead of importing the registry. Removes cycle 2 and 1 violation.
- **I-15** (design lane, R-016) `models.syn001.equilibrium_form.reference_k_values(provider, T, P, context)` (public,
  new) holds the provider evaluation that `verify.checks.k_values` performs today; the verifier keeps `k_values` and
  its `VerifierError`; the region solver calls `reference_k_values`, raises a plain `RuntimeError` with today's
  message text on a provider failure, and no longer imports the verifier. The same
  request and `math.exp` give bitwise the same K. The verifier and the solver share exactly what they share today;
  this ADR records that sharing instead of hiding it in a lazy import.

### Considered and not taken in S19

- **I-16** (S17 D7) Application subpackages by layer: not taken. The `application-layers` rule already enforces the
  order, and the path churn (every test, the test-impact map rebuild) buys legibility only. FQ3.
- **I-17** (S17 D8, D9, D10) One operation declaration generating Protocols and bindings; admission inside the job
  lifecycle; the CLI as a transport through `operations.dispatch`: deferred. None is needed by the layer order or the
  end gate, and D8 changes the §2.1 Protocols. FQ2.
- **I-18** (S17 D5) The legacy binder's public surface (`Binding`, `bind_revision`, `bind_revision_or_reason`,
  `legacy_admission`, `revision_probe`) is unchanged in S19; whether the legacy route stays supported is a semantics
  question for Frank (FQ1).

### No shims

- **I-19** Last step of S19: every re-export added by S17 or S19 is removed and every importer in `src/`, `tests/`,
  `scripts/`, `benchmarks/`, `examples/` and `docs/` is retargeted; the stale references S17 recorded are fixed
  (`messages/catalogue/refusals.yaml:1378` and `models/revision_flowsheet.py:19` naming `revision_binding`,
  `scripts/registry_builtin.py:134`, `scripts/s16_recall.py:70`); docs that name a moved module are updated.

## Alternatives rejected

- **Keep every old path as a permanent re-export.** Contradicts Frank's D19 ("no compatibility shims"), and a
  re-export from the old module keeps the old module on the import path of every caller, which is what closes cycles.
- **Dependency injection of the region solver into the column units** instead of module layer entries: changes the
  compile and solve signatures of the most sensitive unit for no correctness gain (design note section 0.3).
- **One big rename commit at the start.** It would make every S19 structural step start from changed import paths and
  invalidate the test-impact map for the whole campaign; moving first with re-exports, renaming last, keeps each step
  provable bitwise.
- **Moving `k_values` into the orchestrator.** The verifier would then import solver code, which R-016 forbids and the
  new forbid rule `verifier-not-through-the-solver` would reject.

## Consequences and migration impact

- Python imports change for the names above; nothing else does. MCP tool names, descriptions and digest, HTTP routes,
  CLI commands and outputs, schemas, catalogue codes and messages, run manifests, replay bundles and F0 are unchanged,
  and each is a gate of every W4 step.
- Each item lands in two halves: a bitwise restructure step during W1/W2 that keeps the old path (when the layer order
  allows a re-export), and an ADR step in W4 that retargets callers and removes the old path. I-4, I-6, I-9, I-10,
  I-11 and I-12 have no first half (the re-export would itself violate the order or the item changes a call shape).
- Test-impact map: rebuilt after I-19 (about 70 min).

## Acceptance evidence

- For every item: no import of the old path in src, tests, scripts, benchmarks, examples (`grep`), and `codehealth
  docs` reports no broken reference; the public-API difference of the step equals this ADR's list exactly (names
  removed, names added).
- Full suite green; `scripts/corpus_identity.py --check` (F0) identical; MCP digest tests green; ruff and mypy clean;
  CI green on both architectures before the merge.
- `codehealth arch` at the end of S19: 0 violations on `repo-layers`, `application-layers` and every forbid rule; 0
  cycles at depth 4.
- I-10: the R0 projection of every F0 run unchanged. I-11: a static conformance test that `LocalApplication`
  satisfies `contract.Application`. I-14: the MSG audit and catalogue tests unchanged, plus a test that a library-only
  freeze without the hook raises the typed error. I-15: bitwise-identical K on the SYN-001 provider over the F0 states.

## Frank questions (value judgments; each has a default so work proceeds)

- **FQ1** Does the legacy binder route stay supported? Default: yes, unchanged in S19; its retirement would be its own
  package with a semantics ADR.
- **FQ2** D8, D9, D10 (operation declaration, admission placement, CLI as a transport): default, deferred to a later
  package.
- **FQ3** Application subpackages by layer (S17 D7): default, no.
- **FQ4** New names (`numerics.trace`, `models.lifted`, `orchestrator.policies`, `application.run_session`,
  `schema_check`, `studies.nlp.tolerances`, `assessment.linearization`, `application.errors`,
  `application.structural_stage`, the service class names of I-12): default, as written; renames are cheap before
  I-19 lands.

## Open questions that need a fact (with defaults)

- **Q-F1** Can the gate's public-API check accept an ADR step that removes names? Default: an allow-list naming this
  ADR's items is added to the tool before W4; until then W4 steps run without that tier and the reviewer checks the
  diff against this ADR's list.
- **Q-F2** Does every path that freezes a registry-first catalogue import the registry first? Default: grep and the
  full suite decide; if not, the application's composition roots install the hook (I-14's typed error covers the
  rest), reviewed before it runs.
- **Q-F3** Is the run path's own `ValidationReport` (with its timestamp) inside the R0 identity of a run? Default: if
  yes, I-10 passes the caller's report and the R0 check on F0 decides; if R0 changes, stop for a design-lane ruling.
- **Q-F4** Do persisted artifacts or fixtures record Python module paths of moved classes? Default: grep `schemas/`,
  `benchmarks/`, `tests/` fixtures before each move; F0 decides.

## What this ADR does not establish

It does not change any numerical method, tolerance value, phase rule, certificate rule or identity rule; it does not
decide the legacy binder's future; it does not touch a §2.1 signature or a §2.2 schema.
