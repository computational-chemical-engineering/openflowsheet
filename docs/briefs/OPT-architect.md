# Architect brief: OPT — the NLP optimiser on revision flowsheets (0.4)

Status: brief, 2026-11-07. Roadmap `docs/roadmap/roadmap.md` §0.4 ("OPT: the optimiser on revision flowsheets ·
nothing · architect"); ADR 0057 (roadmap) assigns ADR 0032's "decisions on derived quantities; the NLP route inside LOA"
to OPT's ADR; ADR 0056 row "already planned": optimisation of revision flowsheets "lifts E01's typed refusals, R-860,
R-129". One architect pass, then the build lane, then one reviewer pass.

## The question

How does OpenFlowsheet optimise a **revision flowsheet** (the user's own process document, solved through the existing
revision routes) with Ipopt, so that the result is a certified, recorded and replayable candidate, reachable from
CLI/Python/HTTP/MCP with cost and LCA objectives — and which work orders and gates build it in 0.4?

## Why it needs the architect

It joins three finished pieces that were deliberately kept apart (M03's study-level NLP closure, E01's assessment
functionals, the revision run/job/bundle path) and opens a new application operation on a frozen interface. Wrong
choices here leak into F7's run kinds (ADR 0066) and X24's LOA (NLP inside a master problem).

## Current state (recon digest, anchors on main `48322e82`)

**NLP exists as a library only (M03, ADR 0032 Proposed, R-186…R-191, R-210…R-212):**
- `src/openflowsheet/studies/nlp/closure.py:935` `optimize(formulation, flowsheet, *, solver_probe=audited_solver) ->
  OptimizationReport` — readiness check, typed UNSUPPORTED unless ready, lazy adapter import. `:678` classify_starts,
  `:732` OptimizationReport (status = highest classification of its starts, R-212).
- `studies/nlp/greybox.py:645` multistart Ipopt over a full-space PyNumero grey box, limited-memory Hessian (R-187);
  the only module importing pyomo/cyipopt for NLP.
- Problem form today: the fixed SYN-001 `Syn001Flowsheet`; `formulation.py:91` QuadraticExpression, `:148` Decision,
  `:182` InequalityConstraint, `:271` NlpFormulation, `:361` assessment_twin. Objective/constraints are quadratic
  expressions of state variables or `assessment:<id>` outputs.
- Certification `studies/nlp/verification.py` (V1–V6: re-solve, bounds, regimes, KKT from M03 adjoints). No NLP bundle
  or replay path exists.
- Packaging: `pyproject.toml:65` optional `nlp` extra (pyomo 6.10.1, cyipopt); `scripts/build-m03-ipopt-env.sh`,
  `scripts/m03_nlp_check.sh`; the default gate deselects `nlp`-marked tests. Audit `docs/m03-ipopt-audit.md:34` PASS
  (linux x86-64 only). R-190: Ipopt only behind G-A10 and the extra; CasADi-bundled Ipopt rejected.
- M05 trust region (`studies/trust_region/`, ADRs 0038–0040) for the external-reactor loop C1; refuses assessment
  objectives (`studies/assessment.py:407`).

**Revision runs:** `application/revisions.py:58` Revision, `:79` RevisionStore; `application/binding.py:552`
`bind_revision_or_reason`; `application/revision_run.py:782` `run_revision_session(route, document, directory, *, run_id,
policy, check_policy, …, warm_start, experiments, on_iteration) -> RunManifest`, `:503` solve_route, `:224`
select_route; `application/coupled_run.py:662` solve_coupled. Bundles `run/bundle.py:53/121`, replay
`run/replay.py:173`, certificate `verify/certificate.py`. The revision schema already has a `decision` role (review
roadmap: "OPT needs no v1 change").

**Jobs and surfaces:** `application/operations.py:293` OPERATIONS is the only routing table (MCP, HTTP generated from it;
CLI `application/cli.py`). `application/jobs/model.py:29` JobOperation = solve | reproduce | experiment |
surrogate_study; runner `jobs/runner.py:538`. `validate(task="optimization")` returns typed `unsupported` (R-129, R-191;
`application/local.py:471-476, 1554-1559`; test `tests/test_t08_w2_unsupported.py::test_u05_…`). Frozen interfaces:
`docs/interfaces-frozen.md`; changes by an ADR 0019 amendment (13 = ST/ADR 0068 and 15 = X02/ADR 0070 are taken on
unmerged branches; `wp/MSG` also changes the surface — check the next free amendment and surface-chain link across
main, `wp/MSG`, `wp/ST`, `wp/X02` and state the rule for whoever merges later).

**Cost and LCA (E01, ADR 0052 Accepted, R-850…R-862):** post-solve functionals y = G(x, d; θ, ρ) outside
CompiledProblem (D1); regimes never smoothed (D3: max/min/abs/ceil excluded); shipped cost forms (D5); LCA as a frozen
linear map (D7). Code `assessment/program.py:459`, `assessment/cost/*`, `assessment/lca/*`, glue
`studies/assessment.py:179, :359` (revision_sensitivity_host). R-860 lists the typed refusals OPT is to lift (TR
objectives, revision-flowsheet NLP host, bindings, regime enumeration — say which OPT lifts and which stay).
No economics document exists; it is X12 (0.8, target-architecture §9.7: "NPV as an OPT objective references both
documents").

**F7 (ADR 0066, Proposed):** run-kind table row `optimization | revision (+ economics) | nlp | nlp-ipopt |
optimization | implemented iff OPT on main, else declared`; open item 4 default: `optimization` keeps OPT's own job
path until OPT adopts `job_operation: run`.

## Constraints and invariants

- ADR 0032 D1–D6 and R-188 stand: the candidate is the decision vector; feasibility, constraints and KKT are judged on
  the **re-solved certified simulation**, never on Ipopt's status. True domain bounds, never penalties (R-189).
  Distinguish numerical verification (KKT at a certified point) from optimality evidence (local only; no global claim).
- Residual and Jacobian/adjoint describe the same function at the same state. Exact caches on exact inputs.
- Every existing record, key, bundle and replay stays bit-identical: F0 `scripts/corpus_identity.py --check` M1–M9
  must pass; the 35 M9-frozen legacy files are not edited.
- Default install stays without pyomo/cyipopt (R-190); without the extra, optimisation ends in a typed unsupported
  result, never a placeholder.
- No placeholder success paths; unimplemented capabilities return explicit unsupported results.
- Machine: TRS2, 48 cores, ≤ ~36 busy; gates in CI on x86-64 and aarch64 (Ipopt audit is x86-64 only — say what
  aarch64 does).

## Already decided, not open

- OPT is in 0.4 and needs an architect pass (roadmap, Frank). Ipopt via the M03 grey box is the solver (R-186 rejected
  reduced space, hand-transpiled Pyomo and CasADi nlpsol). Economics documents are X12, not OPT. Synthesis/LOA is X24.
- Capability over restriction (R-924, R-927): admit what can be verified, with declared limits, rather than refusing
  wholesale.

## Genuinely open — decide these

1. Which revision flowsheets and routes are admitted in 0.4 (steady-eo only? coupled/external units?), and how the
   grey box gets the residual/Jacobian/adjoint of a bound revision instead of SYN-001's hand form.
2. Decisions and objectives in the document: the `decision` role, bounds, objective and constraint expressions over
   states and E01 assessment outputs (cost, LCA) — where they live (revision vs a separate optimisation request) and
   what this does to run identity.
3. The application operation: a new `job_operation` (e.g. `optimize`) via `submit_job`, the lift of R-129's validate
   refusal, the result schema (reuse `optimization-report.schema.json`?), the ADR 0019 amendment and surface link.
4. Records and replay: what the optimisation bundle holds (starts, iterates, the certified re-solve's own bundle), what
   `reproduce` replays, and how F8/F7 later absorb it.
5. Multistart policy, budgets and cancellation within the job lifecycle (ADR 0020).
6. Which R-860 refusals OPT lifts; ADR 0032's "decisions on derived quantities".

## How it will be verified

The design must name gates the build lane can run: an analytic or independently computed optimum on a small revision
flowsheet (not a self-generated fixture), KKT verification on the re-solved certificate, a cost and an LCA objective
against E01's hand benchmarks (`benchmarks/e01/`), replay MATCH of the optimisation record, F0 identity, the
default-install refusal, and both CI legs. Existing tests: `tests/test_m03_nlp_*`, `test_e01_b_nlp.py`,
`test_e01_integration.py`.

## Deliverable

`docs/design/OPT-revision-optimisation.md` (design note with work orders ≤ ~150k context each and numbered gates) and
`docs/adr/0071-OPT-revision-optimisation.md` (Proposed; amends ADR 0019 and ADR 0032 as needed; register lines drafted
unnumbered). Batch questions for Frank (plain words, with defaults) in the note. Commit on **main** (docs-only, named
paths, message `docs: OPT design + ADR 0071`, with the session's Co-Authored-By / Claude-Session lines from your prompt).
Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; at most targeted reads and small probes; no full gate (another engineer runs one).

## Out of scope

X12 economics documents, X24 synthesis/LOA, M05 trust region changes, X02/X05/MSG/ST internals, global optimality,
style.
