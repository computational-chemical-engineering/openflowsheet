# OPT design: optimisation of revision flowsheets (0.4)

**Status:** design note, 2026-11-07, design lane (`architect`). **Brief:** `docs/briefs/OPT-architect.md`.
**Amended** 2026-11-07 by §9 (Amendment A, mid-build consult `docs/briefs/OPT-architect-consult.md`): A-1 phase-boundary
V1, A-2 zero subsystem, A-3 margins. Where §9 and earlier text differ, §9 governs.
**ADR:** `docs/adr/0071-OPT-revision-optimisation.md` (Proposed). **Builds on:** ADR 0031 (twin, qualification,
adjoint), ADR 0032 (M03 NLP bridge, Accepted), ADR 0052 (E01 assessment functionals, Accepted), ADR 0019/0020 (contract,
jobs), ADR 0007 (replay classes). **Read with:** ADR 0066 (F7, Proposed) D9–D11 and open item 4; ADR 0067 (F8) D6.
Anchors are on `main` at `848bf881`.

---

## 0. The decisions in one screen

| # | Decision | Rejected |
| --- | --- | --- |
| D1 | Admit flowsheets on the `revision_eo` route (surrogate-backed units included). `revision_coupled` is refused (no exact derivative of an external unit; M05's trust region is that route). `legacy_eo` is declared, refused typed, follow-up. | Admitting coupled units with FD or reduced-space derivatives |
| D2 | The optimisation is a separate **optimisation request** document (blueprint §4.1 "Study"), referencing the revision by id; the revision is untouched. Decisions name `role: fixed` specifications. | `role: decision` in the revision; objectives in the revision |
| D3 | A decision's variable is the `ProblemSpec` parameter its specification binds to, found by two **bind probes**; anything a specification may target, a decision may target (ADR 0032's "decisions on derived quantities"). | Mapping by id text; automatic specification swaps |
| D4 | One **NLP host protocol**; M03's SYN-001 path becomes `Syn001NlpHost` (bit-identical); OPT adds `RevisionNlpHost`. | A parallel revision-only copy of M03 |
| D5 | The NLP equality set on a revision is the **held-regime system**: the final converged region attempt's rows, free columns and label rows, selected by id from the one compiled problem; regime-pinned columns held at their certified values. | The full declaration minus alias rows (E01's sensitivity host) |
| D6 | **V1 is the production route, cold**: `bind_route` on the recorded route, `solve_route` from the registered initializer, no warm start; its bundle is an ordinary revision bundle of the candidate document. | Warm-starting V1 from Ipopt's state |
| D7 | Phase regimes are **held by admissibility rows** (true domain restrictions, ADR 0032 D4); a split's margin is the closure's own test at the converged state, and a row is built only where it equals that test (§9 A-3). An optimum on a regime boundary is a KKT point *of the held-regime problem*, said so in fields; V1 judges it on the phase-boundary form (§9 A-1). | Refusing PH-type splits (M03 Q4′); smoothing |
| D8 | New job operation **`optimize`** via `submit_job` (ADR 0019 Amendment 16); `validate(task="optimization")` lifts R-129 with an `optimization` member. Ends `completed` whatever the report status. | A new OPERATIONS row; F7's `submit_run` now |
| D9 | The record is an **optimisation record** (manifest + request + revision + report + per-start bundles); `reproduce` replays the **certification chain**, not the search. Runs on both architectures without Ipopt. | Bitwise re-run of Ipopt as the replay |
| D10 | R-860: OPT lifts the revision NLP host and the optimisation bindings; TR assessment objectives, discrete-regime enumeration and θ-decisions stay refused. | Folding a standalone assessment binding into OPT |

---

## 1. Problem and scope

**Build.** Optimise a stored revision flowsheet with Ipopt (M03's audited full-space PyNumero gray box) over continuous
decisions that are the revision's own fixed specifications, with objectives and inequality constraints over state
variables, decisions and E01 assessment outputs (cost, LCA). The result is a local candidate whose truth is a certified
production re-solve, recorded with its evidence, replayable, and reachable from Python, CLI, HTTP and MCP. Day-one
flowsheets: every revision that binds on `revision_eo` (all S11 corpus flowsheets bind there: TH-R1, TH-C1, TH-V1, M1,
M1-recycle, M4, J1–J8, C-EW, C-MW, C-MW-stripper; measured 2026-11-07, `select_route`).

**Out of scope.** X12 economics documents (NPV objectives); X24 synthesis/LOA (OPT only provides the NLP subproblem
entry, §4.15); M05 trust-region changes; global optimality; discrete regimes (number of parallel units, utility choice,
phase regime as a decision); assessment parameters θ as decisions; exact Hessians; optimisation of transient, batch or
superstructure problems; a standalone assessment-report binding (§7 Q3); re-running Ipopt as part of replay (§7 Q4);
MSG/ST/X02/X05 internals; any change to the `ProcessRevision` v1 schema.

## 2. Constraints and invariants

### 2.1 Mathematics

For one start with held regime ρ (§4.2), primal z = (x_F, d): x_F the free columns of the held system, d the decisions
(parameters). The NLP is

  min f(x, d)  s.t.  F_ρ(x_F, x_H; d) = 0,  g_L ≤ g(x, d) ≤ g_U,  a_ρ(x, d) ≥ 0,  a_A(x, d) ≥ 0,  z_L ≤ z ≤ z_U

with x_H the held columns (constants), F_ρ the held system (square in x_F for fixed d, regular at the certified start),
g the user's constraints (quadratic in names), a_ρ the phase-regime admissibility rows (§4.7), a_A E01's assessment
admissibility rows. f, g are quadratic expressions in state ids, `decision:<spec>` and `assessment:<id>` outputs
(E01 D1: y = G(x, d; θ, ρ_A), gray-box outputs with exact Jacobian). No penalty term ever (ADR 0032 D4, R-189).

**The truth** (ADR 0032 D3, R-188, unchanged): the candidate is the decision vector; feasibility, constraints, regimes
and KKT are judged on the certified production re-solve at those decisions. Ipopt's status is recorded and is neither
sufficient nor necessary. Claims: local, first order, for the held regime; `global_optimality: false` always.

### 2.2 Conventions

- Units: every decision box, start, scale and value in the request and the record is in the internal SI unit of the
  specification's kind (ADR 0001 D1.1, `schemas/units.json`). Objective sense is stored as `minimize` (§4.3).
- Ids: state ids are the bound `ProblemSpec.variable_ids` (as `inspect_structure` and the stream table publish them);
  decisions are revision specification ids; nothing is matched on id text (R-019).
- Orderings: decisions in request order; starts in §4.3's order; held rows in the region's row order followed by label
  rows in attempt order; free columns in `spec.variable_ids` order; outputs as E01 §4.10.2, then phase rows in
  `RegionResult` split order.
- Canonical JSON and SHA-256 as ADR 0002 for every record member.

### 2.3 What stays bit-exact, what may move

- **Bit-exact:** every existing record, key, bundle and replay; F0 `scripts/corpus_identity.py --check` M1–M9 at every
  WO's last commit; the 35 M9-frozen legacy files are not edited; M03's SYN-001 `OptimizationReport` for the A32
  reference formulation (`as_document()` canonical bytes) before/after WO-1 and at the end; every `solve` job bundle.
- **Within stated tolerance:** OPT's own floats against analytic or independent values (§6 numbers).
- **New tolerances:** none. OPT reuses `TAU_REGIME = 1e-4`, `TAU_ALIAS = 1e-8` (`studies/sensitivity.py:78-81`),
  `TAU_GROSS`, `TAU_FEAS`, `TAU_ACTIVE`, `TAU_KKT`, `TAU_SIGN`, `TAU_LICQ` (`studies/nlp/verification.py:72-79`),
  `TAU_DISTINCT = 1e-6` (`greybox.py:115`) and `IPOPT_OPTIONS` (`formulation.py:66`: `tol 1e-10`, `max_iter 500`,
  `max_wall_time 120`, `bound_relax_factor 0`, limited-memory history 6, MUMPS).

### 2.4 Frozen interfaces

Plan §2.1 Protocols and the `CompiledProblem` interface do not change. Contract changes are ADR 0019 **Amendment 16**
(§4.13) and additive schema members (§4.13). `compile/` does not change (E01 D2).

### 2.5 Evidence classes

Optimality evidence (local KKT at a certified point) is reported apart from numerical verification (the certificate)
and from assessment evidence (E01's class/accuracy statement); the report's `claims` say which. F8's later
`run-evidence.json` gets `optimality.claim: local` (ADR 0067 D6).

### 2.6 Parallel and machine contract

Single process per job; starts are sequential in 0.4 (independent, so a later process pool changes nothing in the
record). No MPI, no GPU. TRS2 ≤ ~36 busy cores applies to the build lane's test runs. Ipopt single-threaded (MUMPS
without OpenMP threads, as audited; `greybox.openmp_runtimes()` recorded).

### 2.7 Platforms

The audited Ipopt closure is linux x86-64 only (`docs/m03-ipopt-audit.md:34`). OPT runs only where the G-A10 audit has
a `PASS` inventory for the running platform. Everywhere else (aarch64 CI leg, macOS, Windows) every optimisation path
ends in the typed `NLP_SOLVER_UNAVAILABLE` naming the platform; replay of an optimisation record (§4.9) needs no Ipopt
and runs everywhere.

## 3. Decisions and rejected alternatives

**D1 — admitted routes.** `revision_eo` is admitted: one `solve_eo` region over every row-authoring unit
(`orchestrator/revision.py:354`), compiled residual and exact Jacobian, K04 certificate. Surrogate-backed units are on
this route with derivatives; V1's certificate carries `SURROGATE-DOMAIN:<unit>`, so a candidate outside a surrogate's
domain fails V1 and is never verified (honest without extra machinery). `revision_coupled` is refused
`OPTIMIZATION_ROUTE_UNAVAILABLE(revision_coupled)`: an external unit has no exact derivative, so V5's KKT check cannot be
made and the full-space bridge has no Jacobian rows for it; that is R-924's exclusion case (unverifiable), and M05's
trust region is the route for it (hint names it). `legacy_eo` is refused `OPTIMIZATION_ROUTE_UNAVAILABLE(legacy_eo)` in
0.4 as *declared, not built*: only `role: free` and SYN-001-legacy documents land there, the revision binder covers
every user flowsheet in the corpus, and the same host would serve it later (its certified solve is also one region
result). *Rejected:* FD Jacobians for external units (R-010); a reduced-space bridge over nested coupled solves
(ADR 0032's rejection stands, and it pre-empts M05).

**D2 — where the formulation lives.** A separate `optimization-request` document (§4.3) holds decisions, objective,
constraints, starts, the assessment and the options; the job body names the stored revision. This is blueprint §4.1's
*Study* object ("revision reference, decisions, objectives, constraints, scenarios, budgets"), F7's input row
"revision (+ economics document)" and D9's "OPT objectives and constraints are programs". The revision stays a
simulation document: its id, its SHA, every `solve` of it and every recorded refusal are unchanged. `role: decision` in a
revision stays refused by the binder (`specification_role_unsupported`, `models/revision_flowsheet.py:541`).
*Rejected:* decisions as `role: decision` specifications. The specification schema makes `value` and `bounds` exclusive
(`schemas/specification.schema.json` `oneOf`), so a decision could not carry both its start and its box; the binder
would have to learn a new role; two sources (revision and request) would disagree about boxes. *Rejected:* objectives in
the revision (ADR 0032 D6's "schema migration", and a v1 change the roadmap excludes).

**D3 — decision ↔ parameter.** A decision names a `role: fixed` specification. Its NLP variable is the single
`ProblemSpec` parameter that specification's value becomes (feed `F.T_spec`, duty `H.Q_spec`, `SP.split_fraction`,
`P.efficiency`, column `S02.stage.1.reflux_ratio*`: measured on TH-R1, M1). It is found by effect, not by name: bind the
document with the specification's value set to the box's lower and then upper bound (§4.2.2); exactly one parameter may
change, to the written value bitwise, and nothing else in the binding may change. This is the same document edit V1
makes, so the forward map d ↦ parameter is the re-solve's by construction. **ADR 0032's open item "decisions on derived
quantities" is ruled here:** a decision is a specification, so whatever a specification may target a decision may
target. On v1 that is the binder's targets (stream n/T/P, outlet T/P, duty, instance parameters); when the F-wave's
derived-quantity specifications land (target-architecture §2 item 13) they become decision targets with no OPT change,
including their opening refusal `specification_degenerate(<spec>)`. A quantity the base revision does not specify needs
that specification in the revision first (a change-set); OPT never swaps specifications. *Rejected:* parsing parameter
ids from specification paths (R-019); automatic specification swaps (they change the structure V1 certifies).

**D4 — one host protocol.** M03's closure, gray box and verification read SYN-001 through seven calls
(`Syn001TearProblem`, `with_pinned`, `solve_certified`, `syn001_sensitivity`, `split_regimes`/`declared_regimes`,
`flowsheet.provider.describe().domain`, `compile_problem(flowsheet.spec())`; `closure.py:52-73`, `formulation.py:444-470`,
`verification.py:212-233`, `greybox.py:433-446`). They become one protocol (§4.1) with two implementations.
*Rejected:* a revision-only copy of ~2 000 lines of closure/gray-box/verification (two truths to maintain, and E01's
outputs would have to be wired twice).

**D5 — the held-regime system.** On `revision_eo` the region solves, per attempt, *its rows over its free columns,
everything else held*, plus label rows `T_out − T_label` (`orchestrator/region.py:935-965`); a single-phase lifted split
pins its absent phase's flows and drops its equilibrium and definition rows (`LiftedSplit.pinned/dropped`, `:193-231`);
`ZERO_FLOW` and dormancy forms swap energy rows for label rows. K04 certifies exactly that function. The NLP's equality
set must be the same function, so it is the final converged attempt's system, recorded by the region (§4.2.1).
*Rejected:* E01's `revision_sensitivity_host` (full declaration minus alias rows, `studies/assessment.py:359`): on a
single-phase lifted split both trivial branches are exact roots of every row (R-010), so that system is not the one
certified and its regime is not represented.

**D6 — V1 cold on the production route.** V1 re-solves the candidate *document* with the recorded route's binder
(`bind_route`, R2.5: never re-routes), the job's solve and check policies, the registered initializer and
`warm_start=None`. Independence is the point: a re-solve started at Ipopt's state could reproduce Ipopt's root on a
flowsheet with several steady states; from the production initializer V2's gross-error comparison exposes that.
*Rejected:* a warm start from Ipopt's state (couples V1 to the optimizer); solving at the parameters without a document
(the candidate must be a revision the user can commit and re-solve, gate G16).

**D7 — phase regimes held by admissibility rows; the PH-type margin.** A held single-phase regime is a true domain
restriction of the held-regime model; ADR 0032 D4 requires true domain restrictions as constraints, and E01 D3 already
holds assessment regimes the same way. So each single-phase lifted split of the held system contributes one inequality
row a_ρ ≥ 0 (§4.7); TWO_PHASE splits are held by the flow bounds V, L ≥ 0 already present (D4). **[Amended, §9 A-3: every margin is the
closure's own test at the converged state; the premise that follows holds for ideal K only (D-12).]** The **PH-type margin**:
at a converged lifted state the region's closure judges admissibility by the TP stability test at the split's converged
(T, P) and feed composition, whether the split was answered by its PH closure or its TP flash; therefore
`tp_margin(provider, n_feed, T, P)` (`studies/syn001.py:79`) is the PH-type split's regime margin too, for C ≥ 2. For
C = 1 on the π = C + 1 plateau it is 0 and refuses, which is correct. M03's Q4′ refusal stays for any split passed
without a margin. *Rejected:* refusing PH-type splits (every duty-specified heater and flash is PH-type, so the main use
case would be refused); smoothing the regime switch (E01 D3); letting Ipopt cross regimes and relying on V4 alone (sound
but leaves every boundary optimum `NOT_VERIFIED` with no way for the user to say "stay liquid").

**D8 — the application operation.** `submit_job({operation: "optimize", body})` — the pattern of `experiment` and
`surrogate_study` (ADR 0019 Amendments 4 and 5): no new OPERATIONS row, the six job tools' schemas gain one branch.
`validate(task="optimization")` returns a `ValidationReport` when an `optimization` member is given and the solver is
available. *Rejected:* F7's `submit_run` (0.7, Proposed); a synchronous `optimize` operation (minutes of work behind a
read/execute call without cancellation).

**D9 — replay the certification chain.** `reproduce` on an optimisation record checks integrity, re-runs every recorded
start and V1 bundle through the existing `reproduce_bundle`, and recomputes V2–V7 from the re-solved states. The search
(Ipopt's iterates) is recorded evidence, not identity. This runs on aarch64 and without the extra. *Rejected:* bitwise
Ipopt re-run as the replay (x86-64 only, L-BFGS control flow on float comparisons is not R0, and it would replay the
search rather than the claim).

**D10 — R-860.** Lifted: the revision-flowsheet NLP host; the CLI/HTTP/MCP binding *of optimisation* (assessment outputs
appear in the optimisation report). Kept, unchanged: `ASSESSMENT_OUTPUT_IN_TRF` (M05, out of scope);
`ASSESSMENT_PARAMETER_DECISION` (θ are prices, factors and correlation data, not design variables; a θ decision would
need its own V1 semantics); optimisation over discrete regimes (X24's MINLP; OPT reports `regime_bounds_active` and
`phase_bounds_active` with multipliers so a user re-runs with another regime); E01's R-871 closure limitation. The
standalone assessment report/sensitivity binding is not OPT's (§7 Q3).

## 4. The design

### 4.1 The host protocol (`studies/nlp/host.py`, new; WO-1)

```
class NlpHost(Protocol):
    kind: Literal["syn001-tear", "revision-eo"]
    require_every_start: bool                  # SYN-001: True (M03 D6); revision: False (§4.5)
    def model_record() -> {model_version, constants_sha256}
    def domain() -> {"T": (lo, hi), "P": (lo, hi)}          # provider's declared domain
    def certify(decisions: Mapping[str, float]) -> CertifiedPoint
        # production solve from the registered initializer + certificate; never raises for a
        # failed solve (outcome codes as CertifiedSolve); carries the bundle reference when the
        # host writes bundles (revision) or None (SYN-001)
    def held_system(point) -> HeldSystem       # §4.2.1; SYN-001: all rows minus its two alias rows, no labels
    def regimes(point) -> RegimeRecord         # signature + per-split (kind, regime, margin)
    def sensitivity(point, parameters, outputs) -> SensitivityResult   # M03/ADR 0031 on held_system
    def twin(decision_ids) -> ParametricTwin   # compiled once per (spec, decision ids), cached by the host
    def phase_rows(point) -> PhaseRows | None  # §4.7; SYN-001: None
```

`CertifiedPoint = {outcome, message, state, certificate, signature, bundle_ref | None, parameters}` where `parameters`
are the decision parameters exactly as the binding holds them. `Syn001NlpHost` wraps today's functions verbatim; every
M03 module takes a host where it took a `Syn001Flowsheet`; `optimize(formulation, flowsheet)` keeps its signature and
builds the SYN-001 host inside, so no caller changes. Proof of inertness: gate G2.

### 4.2 The revision host (`studies/nlp/revision_host.py`, new; WO-2)

Constructed from `(document, route="revision_eo", solve_policy, check_policy, decision map, record sink | None)`.

#### 4.2.1 Held system

`RegionResult` gains one in-memory field `final_system: AttemptSystem | None` (`orchestrator/region.py:402`), set when
the region returns `CONVERGED`: `AttemptSystem = {rows: tuple[str,...], free: tuple[str,...], held: Mapping[str, float],
labels: tuple[(row_id, t_out, t_label), ...], signature: AttemptSignature}` — exactly the arguments the converged
attempt passed to `_region_problem` and the values it held. It is never serialised (like `opening`); no bundle member
changes (G1). `HeldSystem` (in `studies/nlp/host.py`) is that record plus the plan's eliminated alias rows. Assertions
at construction: `len(rows) + len(labels) == len(free)`; `rows ∩ eliminated = ∅`; `free ∪ held.keys() =
spec.variable_ids` disjointly.

Evaluation (shared by `FullSpaceNlp` and `SensitivityHost`): the full state vector is assembled once per call with held
columns at their certified values (exact floats); the twin's or the compiled problem's full residual/Jacobian is
evaluated and selected by **precomputed index arrays** built from ids once per start (never by position across
problems, never per call by id lookup); label rows are appended analytically (value `x[t_out] − x[t_label]`, Jacobian
`+1`, `−1` at those columns if free; decisions never appear in labels).

`SensitivityHost` gains `system: HeldSystem | None = None` (`studies/sensitivity.py:189`). With `None` every path is
today's (bit-identical, G2/G3). With a system, `evaluate_sensitivity` selects rows/columns exactly as above, the
alias-elimination row set is the system's, and Q-checks run on the selected square system.

#### 4.2.2 Decision map (bind probes)

For each request decision `(specification_id, lower, upper, scale, unit)`:
1. The specification exists in the revision with `role: fixed` and a `value`; else `UNKNOWN_DECISION`.
2. `unit` equals the SI unit registered for the specification's `kind`; else `DECISION_UNIT_NOT_INTERNAL`.
3. For v ∈ (lower, upper): copy the document; set that specification's `value` to v and, if its `unit` differs from
   the SI unit, its `unit` to the SI unit; `bind_route("revision_eo", doc_v)`. A binder refusal →
   `DECISION_NOT_CONTINUOUS(<spec>, <binder code>)`.
4. Compare with the base binding: `spec.variable_ids`, `spec.equation_ids`, `flowsheet.configuration_sha256`, the label,
   `row_units` and every parameter value. Exactly one parameter may differ, and its value must equal v bitwise; else
   `DECISION_NOT_CONTINUOUS(<spec>)`. Two decisions mapping to one parameter → `DECISION_NOT_CONTINUOUS` on the second.
The map `{spec_id → parameter_id}` is recorded in the report (`revision.decision_parameters`). Cost: 2 binds per
decision, no solve.

**Writing decisions into a document** (starts, candidates, V1, probes): exactly step 3's edit. The candidate's
change-set (§4.8) carries the same edits as `commit_change` edits.

#### 4.2.3 Bounds (ADR 0032 D4, extended)

Over the free columns, by `spec.variable_kinds`: temperature and pressure → `domain()`; molar_flow → `[0, ∞)` **[amended, §9 A-2: on the
revision host a structurally zero subsystem is held at 0 with its rows, an unresolved one is bounded `[0, ∞)`; "exactly
zero at the start → unbounded, `zero_at_start_pinned_by_regime`" stays for the SYN-001 host only]**; heat_rate →
unbounded; **any other kind** (C-MW has one `dimensionless` column) → the bound K03's Newton core applies to that kind in
the production solve, reason `k03_kind_bound(<kind>)`, or unbounded with reason `no_declared_bound(<kind>)` if K03 has
none. Decisions → their box. The `raise ValueError` for unknown kinds (`formulation.py:579`) stays for the SYN-001 host.

#### 4.2.4 Regimes

`RegimeRecord = {signature: final AttemptSignature (lifted regimes, then dormancy items), splits: [(unit, streams, kind
TP|PH, regime, margin)]}` with `margin` **[amended, §9 A-3]** the closure's own test at the converged state: 1 − the region's
single-phase admissibility value for LIQUID/VAPOR, the smaller phase flow over N0 for TWO_PHASE, `None` for `ZERO_FLOW`. Q4′ (`studies/sensitivity.py:812-847`) changes in one
place: a PH-type split **with a margin** is judged as Q4 judges a TP split; one without a margin is refused as today. No
existing caller passes a PH-type split with a margin (SYN-001 passes only TP; E01 passes none), so every existing record
is unchanged (G1–G3).

### 4.3 The optimisation request (`schemas/optimization-request.schema.json`, new; WO-3)

```
{ "request_format": "openflowsheet-optimization-request-v1",
  "problem_id": <id>,
  "revision_sha256": <sha> | absent,                 # if present must equal the stored revision's
  "decisions": [{"specification_id", "lower", "upper", "scale", "unit"}],   # 1..64, finite lower < upper, scale > 0
  "objective": {"sense": "minimize" | "maximize", "expression": <expr>, "scale": number > 0 (default 1)},
  "constraints": [{"id", "expression": <expr>, "lower": number|null, "upper": number|null}],  # ≥ one bound finite
  "starts": {"include_revision": bool (default true), "explicit": [[number…]…], "halton": int ≥ 0 (default 0)},
  "assessment": <assessment.schema.json document> | null,
  "options": {"max_iter": int (default 500), "max_wall_time_s": number (default 120)},
  "hessian": "limited-memory" (default; anything else → HESSIAN_UNAVAILABLE) }
<expr> = {"text": string, "constant": number, "linear": {<name>: number}, "quadratic": [{"a": <name>, "b": <name>, "coefficient": number}]}
<name> = <state variable id> | "decision:<specification_id>" | "assessment:<output_id>"
```

- **Sense and scale:** the formulation stores `minimize` of `s·expr/scale` with s = +1 or −1; the record keeps the
  request's sense (`revision.objective_sense`) and the report's objective `text` is `"-(…)/scale"` when negated. E01's
  `ASSESSMENT_OBJECTIVE_UNSCALED` applies to the scaled objective.
- **Starts, in order:** (0) the revision's own values, if `include_revision` (outside the box → `START_OUTSIDE_BOUNDS`
  naming start 0); then `explicit` in order (each inside the box, else `START_OUTSIDE_BOUNDS`); then `halton` points
  k = 1…m of the unscrambled Halton sequence, dimension j using the j-th prime (2, 3, 5, …), point
  `lower + u·(upper − lower)`, computed by the radical-inverse in binary64 (no RNG). Total 1…32, else
  `TOO_MANY_STARTS`.
- **Decision names** in expressions bind to the decision primal; `decision:` of a specification that is not a decision →
  `UNKNOWN_VARIABLE`.
- Canonicalisation and `request_sha256` as ADR 0002; non-canonical numbers refused as the revision reader refuses them.

### 4.4 Formulation and gray box (WO-4)

`NlpFormulation` is built from the request through the decision map (decision ids = parameter ids; `Decision` boxes and
scales from the request; `QuadraticExpression` names translated: state ids unchanged, `decision:<spec>` → parameter id,
`assessment:` unchanged). `FullSpaceNlp(host, formulation, point, start)`:
- primal = held system's free columns (spec order), then decisions; equality rows = held rows then labels;
- twin from `host.twin(decision_ids)` (compiled once per optimisation, reused across starts: same function);
- outputs = E01's assessment outputs and admissibility rows (`formulation.py:482`, unchanged rules), then the phase rows
  (§4.7), each output block from its own twin; Jacobian columns restricted to the primal;
- scaling: K03 column scales for free columns, decision scales, K03 row nominals for held rows; label rows nominal of
  the temperature kind; outputs as E01 §4.10.2;
- initial point: the start's certified state on free columns and the start's parameters;
- counters as D1; evaluation errors → rejected trial point (Q-F4), unchanged.
Pyomo model build (`greybox.py:238`) is unchanged except that it iterates over the host-provided output blocks.

### 4.5 Readiness

Two phases, one reason table (M03's codes and order, plus the new ones marked †):

| Phase | Checks (in order) |
| --- | --- |
| **Static** (no solve; `validate` and the job's `resolve` stage) | request schema; `REVISION_MISMATCH`†; revision binds (`REVISION_UNBOUND`† with the binder's code); route (`OPTIMIZATION_ROUTE_UNAVAILABLE`†); `UNKNOWN_DECISION`; `DECISION_UNIT_NOT_INTERNAL`†; `DECISION_NOT_CONTINUOUS`†; `BOUNDS_UNDECLARED`; `START_OUTSIDE_BOUNDS`; `TOO_MANY_STARTS`†; `UNKNOWN_VARIABLE`; `ASSESSMENT_OUTPUT_UNKNOWN`; `ASSESSMENT_PARAMETER_STRUCTURAL`; `ASSESSMENT_PARAMETER_DECISION`; `HESSIAN_UNAVAILABLE`; `NLP_SOLVER_UNAVAILABLE` (extra, adapter importable without importing it, audit `PASS` **for this platform**) |
| **Start** (job `starts` stage) | per start: certify (cold, production route; bundle written); then Q3 (`DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS`), sensitivity qualification at the start, `ASSESSMENT_OUTPUT_UNAVAILABLE`, `ASSESSMENT_REGIME_INADMISSIBLE`, `ASSESSMENT_OBJECTIVE_UNSCALED`, `REGIME_MARGIN_UNDEFINED`† (a held split or declared thermal regime with no margin, §4.7) |

On the revision host a start that fails the start phase is **not run** and is classified `SOLVER_FAILED` with reason
`START_NOT_CERTIFIED(<k>, <code>)`† by the existing pure `classify_starts` (no Ipopt status, V1 not passed); the
formulation is ready iff ≥ 1 start passes. If none passes: `UNSUPPORTED` with `SIMULATION_NOT_READY` and every start's
reason. SYN-001 keeps "every start" (`require_every_start`). A static failure is `UNSUPPORTED` with every failing
reason, as M03 §8.7. The assessment binding's scales are taken at the first start that passes (E01 rule).

### 4.6 Verification on the revision host (WO-4)

At each start Ipopt returns (whatever its status), with d̂ its decisions:
- **V1:** write d̂ into the candidate document (§4.2.2), `certify` it (D6); **[amended, §9 A-1]** passed on basis `certificate`
  (`VERIFIED`) or `phase_boundary_form` (clauses e1–e6). The candidate's
  parameters p (read from its binding) are d̂ bitwise (§4.2.2 guarantees it) — asserted.
- **V2:** Ipopt's x_F against the re-solved state on free columns, `TAU_GROSS` as M03; held columns compared exactly.
- **V3:** bounds, user constraints, E01 admissibility rows and phase rows on the re-solved state (`TAU_FEAS`).
- **V4:** the re-solve's attempt signature equals the start's held signature exactly (else
  `PHASE_REGIME_CHANGED(<unit>)`† → `NOT_VERIFIED`); every split margin ≥ `TAU_REGIME`, except a split whose phase row
  is active (§4.7), which is recorded in `phase_bounds_active` instead. **[Amended, §9 A-2/A-3: plus the zero-subsystem
  clause (`ZERO_SUBSYSTEM_CHANGED`) and the guarded rows' closure-identity clause; margins as A-3; only a guarded
  split's active row exempts.]**
- **V5:** reduced-space KKT from `host.sensitivity` on the re-solve's held system (adjoint), independent of Ipopt's
  multipliers, with the user constraints, bounds, E01 rows and phase rows as the candidate active set (`TAU_ACTIVE`).
- **V6:** values from the float reference path (`compiled` residual, `program.evaluate`), unchanged.
- **V7:** E01's held-assessment-regime check, unchanged.
Classification and aggregation: `classify_starts` unchanged (Amendment 1). Candidate and `distinct_local_solutions`: M03
rules (`greybox.py:714-734`). `regime_note` (E01 N5) is set when `regime_bounds_active` or `phase_bounds_active` is
non-empty: "KKT point of the held-regime problem; the physical derivative across the boundary is one-sided".

### 4.7 Held-regime admissibility rows (WO-5)

Built as a functional program (E01 D2: `RowBuilder`s against `Algebra`, compiled as a `ProblemSpec` through the
unchanged `ParametricTwin`; never solved, never certified), by the revision host from the start's `RegimeRecord`:

| Held regime | Row a ≥ 0 (kind, nominal) |
| --- | --- |
| lifted split LIQUID (TP or PH type) | `Σᵢ nᵢ − Σᵢ nᵢ·exp(lnKᵢ(n, T, P))` over the split's feed flows n at its T, P (molar_flow; K03 nominal) |
| lifted split VAPOR | `Σᵢ nᵢ − Σᵢ nᵢ·exp(−lnKᵢ(n, T, P))` (molar_flow) |
| lifted split TWO_PHASE | none: held by `V, L ≥ 0`; margin = smaller phase flow / N0 (§9 A-3) |
| `ZERO_FLOW` split, dormancy item | none: V4's exact-dormancy check |
| thermal port declared liquid / vapour | `T_sat(P) − T` / `T − T_sat(P)` with the kernel's saturation block (temperature; nominal 1 K) |
| thermal port declared wet (two-phase) | none: held by its `sat.V, sat.L ≥ 0` flows |

`lnK` is the provider block the split's equilibrium rows use (the same derivative path); the row is the bubble/dew test
multiplied through by the feed total, so it is defined at any flow and has no division. **[Amended, §9 A-3:]** a LIQUID/VAPOR
row is built only where it equals the closure's test at the start (*guarded*); otherwise the split is admitted
*unguarded* (`regimes_unguarded`; V4 by margin alone). `REGIME_MARGIN_UNDEFINED(<unit>)` at the start phase now means a
held split whose margin is `None` (not ZERO_FLOW), or a declared port whose `T_sat` raises at the start's P. Q4 gains a *held* mode:
`host.sensitivity(..., held=units)` records Q4 `pass` with `held: true` for those units instead of refusing
`PHASE_BOUNDARY`; only V5 passes `held`, and only for splits whose phase row is active at the candidate. Without
`held` Q4 is today's. Report: `phase_bounds_active: [{unit, row, slack_scaled, multiplier}]`.

### 4.8 Records and identity (WO-4 writes, WO-6 stores)

`optimization_sha256 = sha256(canonical({"format": "openflowsheet-optimization-v1", "request_sha256",
"revision_sha256", "route", "solve_policy_sha256", "check_policy_sha256"}))`. Run ids:
`opt-<optimization_sha256[:16]>-s<k>` (start solve) and `-r<k>` (V1 re-solve), the same in the library and the job.

```
<record>/optimization-manifest.json   format, optimization_sha256, the five inputs above, members {path: sha256},
                                      environment (solver versions, platform, audit; non-structural)
<record>/optimization-request.json    the canonical request
<record>/revision-document.json       the canonical base revision
<record>/optimization-report.json     OptimizationReport.as_document()
<record>/starts/<k>/start/            the certified start solve's bundle (run_revision_session; failure bundle if not)
<record>/starts/<k>/optimizer.json    Ipopt: options, return status, iteration count, final primal (free ids + decisions),
                                      objective, unscaled violations, counters, per-iteration rows
                                      (iter, obj, inf_pr, inf_du, mu, alpha_pr) ≤ max_iter
<record>/starts/<k>/candidate-revision.json   the document at d̂ (absent if Ipopt returned no point)
<record>/starts/<k>/resolve/          V1's bundle (run_revision_session of the candidate document)
<record>/starts/<k>/verification.json the V1–V7 record (CandidateVerification.as_document())
```

Classes (ADR 0007): manifest inputs, members' SHAs, statuses, codes, classifications, active sets, signatures: R0. Ipopt
trajectory, iteration counts, counters: recorded, not reproducible. Floats of verification: R1/R2. The report's
`candidate.change_set` is a `change-set.schema.json` document (edits = §4.2.2's, `expected_revision` = the base revision
id, `idempotency_key = "opt-" + optimization_sha256[:32]`); committing it is the user's act (§7 Q7). Every bundle under
`starts/` is byte-for-byte what `run_revision_session` writes for that document (it is that function), so a `solve` of
the committed candidate revision reproduces the V1 certificate (G16).

### 4.9 Replay (WO-6)

`reproduce({bundle_artifact_id: <record id>, rerun})` and CLI `replay <dir>` dispatch on the manifest `format`; the
existing run-bundle path is untouched. Steps: (1) integrity of every member against the manifest (missing, tampered,
unexpected) and of the manifest's identity; (2) with `rerun`: `reproduce_bundle` on every `start/` and `resolve/` bundle;
(3) with `rerun`: recompute V2–V7 from each re-solved state (and V1's outcome from (2)) and compare with
`verification.json` (R0 exact; floats under ADR 0007 D2, each float of `verification.json` floored at the tolerance of
the check whose verdict it feeds (D2.2's principle, as `check.value`): V2 `scaled_difference_inf` at `TAU_GROSS`; V3
`slacks`, `active_set[].slack`, `constraint_values`, V4 `splits[].margin` and phase-row values at `TAU_FEAS`; V5 and
`kkt` `stationarity_residual_inf`, `objective_gradient_scaled`, `constraint_gradients_scaled` at `TAU_KKT`,
`multipliers` at `TAU_SIGN`, `licq_singular_values` at `TAU_LICQ` times the largest; V6 `objective` relative only.
Outcomes, active sets and classifications stay exact (R0) under the near-threshold rule. No new tolerance. [OPT review
M1, 2026-11-08] An active-set flip within 1e-9 relative of a threshold is
`verdict_changed_near_threshold`, F8 D8's rule); (4) the report's classification/aggregation recomputed by
`classify_starts` from the recorded evidence. One `ReplayReport` (schema unchanged): `integrity` over all members,
`differences` prefixed `starts/<k>/<member>: `, verdict `MATCH` iff every part matches. Without `rerun`:
`inspected_archived_results`. No Ipopt, no extra needed.

### 4.10 The job operation `optimize` (WO-6)

- **Body** (`optimization-request.schema.json#/$defs/optimize_body`): `{revision_id, request, policy_id = "default",
  check_tolerances = {}, max_property_calls = null}` (solve_body's members plus `request`).
- **Admission:** schema; `NLP_SOLVER_UNAVAILABLE` → `ApiError unsupported`, `detail.code = nlp_solver_unavailable`,
  pointer `/operation`, no job created. Everything else is decided in the body.
- **Stages** (fixed list, progress `completed` = stage index, `total` = 4): `resolve` (revision, route, policies,
  decision map, static readiness), `starts` (one progress event per start, `stage: "starts:<k>"`), `optimize` (per start:
  Ipopt, V1, V2–V7; `stage: "optimize:<k>"`), `record` (report, manifest).
- **Ends:** `completed` whatever the report status (`UNSUPPORTED` from readiness included), answer in
  `job_result.optimization`; `failed(operation_error)` only for defects and `unsupported(<code>)` cases that arise after
  admission (the extra vanished: `nlp_solver_unavailable`); `VerifierError` → `failed(verifier_refused)`.
- **Outputs**, in order: `optimization_report`, `optimization_manifest`. Every other file is an artifact of the job
  (`<job_id>:optimization/<path>`; bundles registered as `<job_id>:optimization/starts/<k>/start` etc. with their kinds).
- **Cancellation and budgets:** `check()` at stage and start boundaries, inside every production solve (existing
  `Trace.record` hook), and in Ipopt's intermediate callback (`greybox._Iterations`, which returns `False` → Ipopt
  `User_Requested_Stop`, then `JobInterrupted` is raised). Per-start Ipopt `max_wall_time` =
  min(`options.max_wall_time_s`, remaining job wall time). An interrupted job ends `cancelled`/`timed_out` with **no**
  report and no manifest output; per-start files already written stay as artifacts (as `surrogate_study`). Retry and
  idempotency: existing rules; `retryable: false` on every body error.
- **Artifact kinds** (`jobs/model.py ArtifactKind`, additive): `optimization_request`, `optimization_report`,
  `optimization_manifest`, `optimizer_record`, `candidate_revision`, `candidate_verification`.

### 4.11 `validate(task="optimization")` (WO-3; lifts R-129, amends R-191/ADR 0032 D6)

Input gains optional `optimization` (the request). Order: task check; `task == "optimization"` → solver probe first
(unavailable → `ApiError unsupported`, `nlp_solver_unavailable`, pointer `/task`, before the revision is read — U05's
place); missing `optimization` → `ApiError invalid_request`, pointer `/optimization`; then the revision's own simulation
validation; then the static readiness (§4.5) as checks `OPT.<CODE>` — request schema at stage `schema`, solver/route/
assessment binding at `capability`, the rest at `structural_analysis`, evidence class `structural`. Status:
`READY_FOR_OPTIMIZATION` iff the revision is `READY_FOR_SIMULATION` and every static check passes; `DRAFT` if the
revision is `DRAFT`; else `INVALID`. Validation solves nothing (blueprint §4.3); the start phase is the job's.
`tests/test_t08_w2_unsupported.py::test_u05_…` is amended on purpose (code `nlp_solver_unavailable`), listed in
`AMENDED_TESTS` citing ADR 0071.

### 4.12 Surfaces

- **Python:** `studies.nlp.revision.optimize_revision(document, request, *, directory, solve_policy, check_policy,
  check=None, progress=None) -> OptimizationOutcome(report, record_dir, points)` — the library entry the job body calls
  (as `solve` calls `run_revision_session`); `LocalApplication.submit_job` / `validate` as above.
- **HTTP/MCP:** `POST /v1/jobs` and the six job tools (new branch); `validate_revision` (new member).
- **CLI:** `openflowsheet optimize REVISION --request FILE --out DIR [--json]` (direct library run, no project);
  `validate REVISION --task optimization --request FILE`; `replay DIR [--rerun]` detects an optimisation record.
- **Descriptions:** `descriptions/validate.md` and the job tools' text name the new branch and member (part of the
  surface link).

### 4.13 Contract amendment and the surface chain

**ADR 0019 Amendment 16** (next free on `main`, `wp/MSG`, `wp/ST`, `wp/X02`; 13 = ST, 14 = X05, 15 = X02). Contents:
`job.schema.json` `operation` enum `optimize`, `job_request.oneOf` branch, `job_result.optimization` (`$ref`
optimization-report, or null; present iff the operation is `optimize` and a report was produced), the artifact kinds;
`validate` input member `optimization`; new `schemas/optimization-request.schema.json`; additive optional members of
`optimization-report.schema.json`: top-level `revision` `{revision_id|null, revision_sha256, route, request_sha256,
optimization_sha256, objective_sense, decision_parameters, solve_policy_sha256, check_policy_sha256}`, `$defs/start`
`{start_record, resolve_record, held_signature, phase_bounds_active, candidate_revision_sha256}`, `$defs/candidate`
`{change_set, candidate_revision_sha256, resolve_record, phase_bounds_active, regime_note}` (any already present is
reused), and the new reason codes if `$defs/reason` enumerates codes. Nothing else in the frozen list changes.

**Surface-chain link (R-457).** `main` has c_1–c_3 (`scripts/m07a_rc.py:161`); `wp/MSG` (R-934) and `wp/X02` (R-950)
each add a `c_4` on their branches; `wp/ST` adds none. **Rule for whoever merges later, OPT included:** link indices are
assigned in merge order on `main`. The second branch to merge renumbers its link to the next free index, rebases its
strip on the merged list (its strip removes only its own additions), and re-measures its digest D on its merge tree;
the chain test then judges every link in order. OPT's link is `c_{n+1}`, n = links on `main` at OPT's merge, strip
`strip_opt` (removes `optimize`, the branch, the result member, the artifact kinds, the `validate` member, and restores
the two description texts from the previous link's files). **Amendment numbers** are claimed by the ADR's docs commit on
`main` (as 13 and 15 were); 16 is OPT's from this commit. **Catalogue codes** (ADR 0058 C3): OPT's new codes are listed
in ADR 0071; whichever of OPT and MSG merges second registers them in the catalogue file.

### 4.14 Performance

Per Ipopt iteration: one twin residual and one twin Jacobian (plus line-search residuals), output twins likewise; index
selection by precomputed arrays (O(nnz)); the twin compiled once per optimisation. Per start: one cold production solve
(start) and one (V1), one sensitivity factorisation (Q-checks) and one (V5). Memory: CSC Jacobians, ≤ 500 iteration rows.
Expected scale: ≤ 300 columns (C-MW 297 × 297) → seconds per start for the solves, Ipopt time dominated by twin
Jacobians; WO-4 records the timings (`docs/OPT_DECISIONS.md`) for TH-R1, M1 and C-MW. Starts are independent, so a later
process pool over starts needs no record change (not built; TRS2 rule).

### 4.15 Later absorption

- **F7 (0.7):** run kind `optimization` = inputs `{revision, optimization_request}`, form `nlp`, route `nlp-ipopt`,
  result `optimization-report`, task `optimization`. ADR 0071 asks F7 to admit `job_operation: "optimize"` in D10 with
  E-F7-8's rule: `submit_run(optimization)` creates exactly the job `submit_job({operation: "optimize"})` creates, so
  OPT's records stay byte-identical; until then F7 open item 4's default holds. F7 D9 functional programs later replace
  the quadratic `<expr>` by a program reference (additive request field).
- **F8 (0.7):** every `start/` and `resolve/` bundle is an ordinary revision run and follows F8's bundle v2 when revision
  runs do; the optimisation manifest gains `run_kind`/`documents` additively; `run-evidence.json` `optimality.claim:
  local`.
- **X24:** `optimize_revision` is the NLP subproblem (revision with integer choices fixed). It is deterministic and
  free of job concepts; `OptimizationOutcome.points` holds the certified states and held systems in memory for X24's
  linearisations. X24 decides its own records.

## 5. Work orders

Rules: branch `wp/OPT`; Opus engineers (Sonnet for schema fixtures, docs and the manifest); ≤ ~150k context each;
every WO ends with its acceptance check, F0 (G1) and the tests it touches; the audited-env tests run with
`scripts/m03_nlp_check.sh` (`.venv-pyomo`), never in the default gate (deselected `nlp` marker). Open choices are logged
in `docs/OPT_DECISIONS.md` as isolated commits; numerics-changing choices stop for the design lane.

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **WO-1** | `NlpHost` protocol + `Syn001NlpHost`; M03 closure/formulation/greybox/verification take a host; `optimize()` signature unchanged | — | G1, G2, G3 |
| **WO-2** | `RegionResult.final_system`; `HeldSystem`; `SensitivityHost.system`; Q4′ PH-with-margin; `RevisionNlpHost` (certify via `bind_route`/`solve_route`, cold, bundles; decision map; bounds; regimes; twin cache) | WO-1 | G1, G3, G4, G5, G6 |
| **WO-3** | `optimization-request.schema.json` + fixtures; request → `NlpFormulation` (sense, scale, names, starts incl. Halton); static readiness table; platform-aware solver probe; `validate` lift + U05 amendment; new codes | WO-1 (can run beside WO-2) | G1, G11, G18 |
| **WO-4** | Gray box over held systems with multiple output blocks; V1–V7 on the revision host; report `revision` members; record writer; `optimize_revision`; benchmarks `benchmarks/opt/` (OPT-A1, A2, A2b, N1) with mpmath scripts | WO-2, WO-3 | G1, G2, G7, G8, G9, G17 |
| **WO-5** | Phase admissibility rows (lifted + thermal); Q4 held mode; `phase_bounds_active`, `regime_note`; OPT-A3 | WO-4 | G1, G2, G10, G9 rerun (N1 becomes KKT) |
| **WO-5b** | §9.6: A-2 zero subsystem, A-3 closure margins (two isolated commits) | WO-5 | §9.6 |
| **WO-5c** | §9.6: A-1 phase-boundary V1 | WO-5b | §9.6 |
| **WO-6** | Job operation `optimize` (body, stages, cancellation, budgets, artifacts, result); Amendment-16 schemas; replay dispatch (`reproduce`, CLI); CLI `optimize`; committed fixture record (OPT-A2, ≤ 2 MB JSON); surface link | WO-4 | G1, G11, G12, G13, G14, G15, G16 |
| **WO-7** | Cost (OPT-C) and LCA (OPT-L) gates vs E01 hand models; user doc page; `evidence/OPT/<commit>/manifest.json`; full gate before merge | WO-5, WO-6 | G19, G20, G21 |

## 6. Verification gates

Analytic cases use the SYN-001 ideal provider (components A, B, C; liquid cp and lnK from the SYN-001 derivation's
coefficient table) on small revisions authored under `benchmarks/opt/flowsheets/` from existing S11 unit models. Each
case's script (`benchmarks/opt/<case>.py`) computes its expectation with mpmath (dps 30) from the coefficient table,
independently of the provider code; the case file records constants chosen so that interior decisions sit ≥ 10 % of the
box from either end and single-phase states ≥ 10 K from their bubble point.

| Gate | What, how, tolerance |
| --- | --- |
| **G1** | F0 `scripts/corpus_identity.py --check` M1–M9 PASS at each WO's last commit. |
| **G2** | M03 regression: SYN-001 A32 report canonical bytes identical before/after WO-1 and at WO-4/WO-5 ends (only members recording wall-clock time may be masked; the WO names them, ≤ 3); `scripts/m03_nlp_check.sh` PASS; default-gate `tests/test_m03_*` unchanged. |
| **G3** | E01 regression: `tests/test_e01_*` pass unchanged; M03/E01 sensitivity results byte-identical with `system=None`. |
| **G4** | Held system on TH-R1, TH-C1, TH-V1, M1, M1-recycle, J1, C-MW: square, disjoint, alias rows excluded; the compiled problem's residual selected by the held system equals the converged attempt's final residual **bitwise**; twin vs compiled within `TAU_CONSISTENCY_*` (existing guard). |
| **G5** | Decision map: TH-R1 `SPEC-H-Q`→`H.Q_spec`, a `parameters.split_fraction` spec→`SP.split_fraction`, M1 feed T; refusals: non-SI unit, a probe that changes `configuration_sha256` or two parameters, a binder refusal → `DECISION_NOT_CONTINUOUS`/`DECISION_UNIT_NOT_INTERNAL`. |
| **G6** | Held-system sensitivities on TH-C1 (E01's two pins) and M1 (feed T, reflux ratio): dy/dp vs central differences of certified production re-solves, step 1e-4·scale, within the tolerance E01's A30/A31 test uses; Q4′ with a PH-type heater split QUALIFIED. |
| **G7** | **OPT-A1** (1 decision, active inequality): feed (A,B,C liquid, n_F) → heater (decision Q) → sink; min Q/Q_s s.t. T_out ≥ T_min. Expect Q* = n_F Σ zᵢ ∫_{T_in}^{T_min} cp_{L,i} dT, multiplier λ* = (n_F/Q_s) Σ zᵢ cp_{L,i}(T_min) (of the constraint as written, objective units per kelvin). Status `KKT_POINT_VERIFIED`; \|Q−Q*\| ≤ 1e-7·Q*; \|λ−λ*\| ≤ 1e-4·λ*. |
| **G8** | **OPT-A2** (2 decisions, interior + active): feed → splitter (decision r) → branch 1 heater (decision Q) → sink; branch 2 → sink; min Q/Q_s + c·(r n_F − n*)²/n_s² s.t. T_out ≥ T_min. Expect r* = n*/n_F − Δh n_s²/(2 c Q_s n_F), Q* = r* n_F Δh, Δh as G7. All 3 starts (revision, one explicit, halton 1) `KKT_POINT_VERIFIED`, `distinct_local_solutions = 1`; \|r−r*\| ≤ 1e-6; \|Q−Q*\| ≤ 1e-6·Q*; \|f−f*\| ≤ 1e-8·max(1, \|f*\|). **OPT-A2b**: the same problem with the heater's outlet-T specification as the decision (TP-type split) gives the same r*, Q* within the same tolerances. |
| **G9** | **OPT-N1** (negative): OPT-A1 with T_min above the bubble point, started liquid. Before WO-5 → `NOT_VERIFIED`, reason `PHASE_REGIME_CHANGED(<heater>)`; after WO-5 → `INFEASIBLE_REPORTED` (the held LIQUID regime cannot reach T_min; no start is verified across a regime change). Plus route refusals: an M02 coupled flowsheet (`benchmarks/m02/c1-loop-real.json` class) and a `legacy_eo` document → `UNSUPPORTED`, `OPTIMIZATION_ROUTE_UNAVAILABLE`. |
| **G10** | **OPT-A3** (phase boundary, WO-5): OPT-A1 maximising T_out (min −T_out/T_s) with no T bound and a Q box whose upper end exceeds the duty to the bubble point → optimum at the bubble point Σ zᵢ Kᵢ(T_b, P) = 1 (mpmath root). \|T−T_b\| ≤ 1e-6 K; `phase_bounds_active = [heater]`; `regime_note` set; `KKT_POINT_VERIFIED`. **[Amended, §9.5: plus V1 basis `phase_boundary_form`, the multiplier λ*, \|Q−Q*\| ≤ 1e-7·Q*.]** |
| **G11** | Default install (and aarch64 CI): after `validate(task=optimization)`, `submit_job(optimize)`, `optimize_revision` and CLI `optimize`, `pyomo`/`cyipopt` not in `sys.modules`; `validate` and `submit_job` → `ApiError unsupported nlp_solver_unavailable`; library → `UNSUPPORTED` report; platform-not-audited path tested by a monkeypatched platform. |
| **G12** | Job ≡ library: the `optimize` job's record (inline executor and spawned worker) equals `optimize_revision`'s byte for byte on the same machine (OPT-A2). |
| **G13** | Replay: `reproduce(rerun=true)` on OPT-A2's record → `MATCH` (x86-64); the committed fixture record → `MATCH` on the aarch64 CI leg; one tampered byte in `candidate-revision.json` → integrity failure; an edited verification float beyond D2 → `MISMATCH`. |
| **G14** | Cancellation/budget: cancel during start 1 of 3 → `cancelled`, no report/manifest outputs, start-0 files present as artifacts; `wall_time_s` exhausted inside Ipopt → `timed_out` within one Ipopt iteration + one stage. |
| **G15** | Surface chain: served list with OPT; `strip_opt` returns the previous link's digest; the chain test passes with every link. |
| **G16** | Candidate = simulation: commit the report's change-set; a `solve` job of the new revision gives a certificate whose R0 content equals the V1 certificate's. |
| **G17** | Performance record (not a pass/fail threshold): per-start wall time, Ipopt iterations, twin calls for TH-R1, M1, C-MW in `docs/OPT_DECISIONS.md`. |
| **G18** | Request schema: round-trip fixtures; one test per static readiness reason; Halton points k = 1…4 in 2-D equal (1/2, 1/3), (1/4, 2/3), (3/4, 1/9), (1/8, 4/9) within 1 ulp, computed by the standard radical inverse (`f ← f/b; u ← u + f·digit`). |
| **G19** | **OPT-C** (cost): TH-C1 with E01's TAC program; one decision (box chosen so the optimum is interior, else a bound-active case with the bound multiplier's sign checked; recorded). Independent optimum by golden-section over certified production re-solves with TAC from `benchmarks/e01/cost_hand/cost_hand.py` at each state: \|d−d_gs\| ≤ 1e-5·scale; TAC at the candidate equals `cost_hand` at the certified candidate state within 1e-9 relative. `KKT_POINT_VERIFIED`, V7 passed. |
| **G20** | **OPT-L** (LCA): minimise GWP100 (E01 shipped IPCC factors, synthetic background) s.t. net power ≥ W_min on TH-C1; independent: bisection on W(d) = W_min over certified re-solves; \|d−d_root\| ≤ 1e-6·scale; GWP at the candidate equals `benchmarks/e01/lca_hand` at that state within 1e-9 relative. |
| **G21** | Full gate (`scripts/gate.sh`) once before merge, read before pushing; CI green on x86-64 and aarch64. |
| **G10a–G10d, G22–G24** | §9.5 (Amendment A); G9, G13, G16, G17 extended or rerun there. |

## 7. Risks and open questions (each with a default)

**For Frank (preferences; plain words):**

| # | Question | Default (work proceeds on it) |
| --- | --- | --- |
| Q1 | Should a user be able to mark a specification as a decision inside the flowsheet document itself, or only in the separate optimisation request? | Only in the request; the flowsheet document is unchanged and `role: decision` keeps its refusal. |
| Q2 | Flowsheets with an externally run or co-simulated unit cannot be optimised exactly; flowsheets on the older "legacy" route could be, with a little more work. Include the legacy route in 0.4? | Standard route only in 0.4; legacy route next (typed refusal until then); co-simulated units stay with the trust-region study. |
| Q3 | Should cost and LCA reports and their sensitivities be available from CLI/HTTP/MCP on their own, outside an optimisation? | Not in OPT; a small follow-up package. |
| Q4 | Should "replay" of an optimisation also re-run the optimiser and compare, or only re-check the certified answer? | Only re-check the certified answer (works on every machine); optimiser re-run is a later option. |
| Q5 | Limits: at most 32 starting points per optimisation, 500 iterations and 120 s per start by default. | As stated; users raise iterations/time in the request. |
| Q6 | Should the optimiser's answer be saved as a new flowsheet revision automatically? | No: the result carries a ready change-set that the user (or agent) commits. |
| Q7 | **[Replaced, §9.7]** An optimum exactly on a boiling/condensing point is verified and flagged; saved and simulated normally, that design's own check says "unverified" (two states meet there). Verified-with-flag, or found-but-not-verified? | Verified, with the flag. |
| Q8 | The audited solver exists for Linux x86-64 only. Audit it for ARM (aarch64) too? | Not in 0.4; ARM gets the typed "solver unavailable" and full replay. |
| Q9 | (§9.7) Should ordinary simulations judge an exact boiling-point state the same way, so a saved boundary design certifies normally? Needs its own ADR on K04. | Not in 0.4; follow-up. |

**Facts (measured in the WO named):**
- F1 (WO-2): the region's final attempt system reproduces the certified residual bitwise for every corpus flowsheet
  (G4). If a flowsheet's region re-opens after closure so the last attempt is not the certified one, stop and escalate.
- F2 (WO-2, reviewer) **[answered: half false, D-12; ruled by §9 A-3]**: D7's claim that the closure judges PH-type splits by the TP test at the converged (T, P). If the
  closure's admissibility for a PH-type split differs, the margin must follow the closure's test; escalate.
- F3 (WO-4): Ipopt bitwise determinism between inline and spawned execution (G12). If it fails, escalate before
  weakening G12.
- F4 (WO-5): the thermal port state carries a saturation block usable as a row and `sat.V/sat.L` flows; if not,
  thermal held regimes get `REGIME_MARGIN_UNDEFINED` and are listed as a limitation.
- F5 (WO-4): convergence of L-BFGS on C-MW (297 columns) within the default 500 iterations; if not, record and propose a
  default in `docs/OPT_DECISIONS.md` (no gate depends on it).

**Risks.** Regime drift makes boundary optima `NOT_VERIFIED` until WO-5 lands (G9 pins it). Merge order with MSG/X02/ST
on `job.schema.json`, the catalogue and the link index (§4.13 rule). The `validate` description change is an
agent-surface change for the next release's V17 carry (R-129 history). E01's over-restrictive closure (R-871) applies to
assessment objectives unchanged.

## 8. Records

- ADR 0071 (Proposed) with draft register lines; `docs/OPT_DECISIONS.md` (build lane, created at WO-1);
  `evidence/OPT/<commit>/manifest.json`. Status vocabulary: `implemented`, `tested`; `reviewed` only by the reviewer.

---

## 9. Amendment A (2026-11-07, mid-build consult after WO-5)

**Why.** Three premises failed under measurement on `wp/OPT` (brief `docs/briefs/OPT-architect-consult.md`; log
`docs/OPT_DECISIONS.md` D-12, D-36, D-37 and the WO-4b/WO-5 C-MW entries): (1) a phase-boundary optimum cannot pass V1,
because the declaration's Jacobian is singular there by construction; (2) "a flow exactly zero at the start → unbounded"
lets Ipopt drive structurally absent component flows negative (C-MW: `DomainError` on ~99 % of residual calls);
(3) TWO_PHASE splits and non-ideal providers have no margin, so V4/Q4′ fail on every C-MW start. Where this section and
earlier text differ, this section governs; the earlier text carries an in-place pointer and is quoted here verbatim.
**Unchanged:** ADR 0032 D1–D6 as ADR 0071 amends them, R-188, R-189, F0 (G1), M03's bytes (G2), E01 (G3), K04 and every
ordinary `solve` certificate, every tolerance. No new tolerance is introduced.

### 9.1 A-1 — Phase-boundary candidates: V1 on the phase-boundary form (D-37)

Replaced (§4.6 V1): "write d̂ into the candidate document (§4.2.2), `certify` it (D6); `VERIFIED` required."

**Fact (D-37).** OPT-A3's candidate (Q̂ = Q* − 2.7e-7 W, |T − T_b| = 9.1e-10 K) re-solves cold with every residual
converged, but its certificate is `UNVERIFIED`: regularity `ILL_CONDITIONED`, rcond₁ ≈ 2.27e-6·ΔQ/W on both sides of Q*,
`RANK_DEFICIENT` at ΔQ = 0. The row a/N0 is within `TAU_ACTIVE` only for |ΔQ| ≲ 1e-2 W, where the certificate already
fails, so §4.7's V4 exemption and Q4 held mode were unreachable for lifted splits.

**Why the declaration is singular there, and only there.** A lifted split's equilibrium rows are homogeneous in the
incipient phase's flows: on the single-phase branch every one of them holds identically (R-010's trivial branch, §3 D5).
Linearised on that branch, their block over the incipient flows is singular exactly when the incipient phase can
appear — when the phase test reaches 1, i.e. a_ρ = 0 — and its smallest singular value is proportional to a_ρ.
(Illustration, heater style, r_i = v_i·L − K_i·l_i·V: at v = 0, ∂r/∂v = L(I − κ1ᵀ) with κ_i = K_i x_i, determinant
Lⁿ(1 − Σ K_i x_i); the l- and T-blocks carry a factor v or V and vanish.) This is the transcritical crossing of the
trivial and the two-phase branch. It occurs at every bubble/dew boundary of every lifted split whatever the flowsheet, so
no certificate on the declaration's Jacobian can verify a boundary point and no tolerance could change that. The physical
state is nevertheless unique and regular in the held regime: the regime pins the incipient flows at 0, V ≥ 0 excludes
the other branch, and the singular direction is exactly the pinned one.

**Decision.** V1 passes on one of two bases.
1. **`certificate`** — the certificate is `VERIFIED` (today's rule, unchanged).
2. **`phase_boundary_form`** — all of (e1)–(e6) hold at the cold re-solve x̂:
   - (e1) the re-solve converged and its certificate is `UNVERIFIED` with a `rank_limitation` whose status is
     `ILL_CONDITIONED` or `RANK_DEFICIENT`;
   - (e2) the re-solve's attempt signature equals the start's held signature (V4's first clause, evaluated here);
   - (e3) the boundary set A is non-empty: A = the *guarded* (A-3) lifted splits held LIQUID or VAPOR whose phase row
     has |a/N0| ≤ `TAU_ACTIVE` at x̂, the row evaluated on the float reference path exactly as V3 evaluates it;
   - (e4) for each s ∈ A, with P_s = `s.pinned(regime_s)` and D_s = `s.dropped(regime_s)`: |P_s| = |D_s|; every column of
     P_s is `== 0.0` at x̂; D_s contains no alias-eliminated row and P_s, D_s are ids of the matrix below;
   - (e5) the boundary form B (below) screens `NO_RANK_LOSS_DETECTED` with the unchanged `screen`
     (`verify/regularity.py:156`: `TAU_ILL`, `TAU_SCALED_MIN`, the absolute limit at B's dimension, the identity
     refusal armed with the same pairing identities as the certificate's call);
   - (e6) the certificate's own grading function, `grade(checks, policy=…, regularity_status=B.status,
     regularity_reason=B.ill_conditioned_reason, derivative_ok=…)` (`verify/certificate.py:257`), called with the
     certificate's own checks, check policy and derivative evidence, returns `VERIFIED`. So every other check of the
     certificate must have passed (residual rows, labels, aliases, the fresh-flash categories as the certificate judged
     them, bounds, derivative witness), and a non-registered policy can never pass this way.

   Any clause failing → V1 `fail`, `CERTIFICATE_NOT_VERIFIED` (unchanged code), the first failing clause in the detail.

**The boundary form B.** Take exactly the matrix the certificate screened — `assemble_target(target, x̂, zero_flow)`
(`verify/regularity.py:375`) with the certificate's own `target` (`BoundDeclaration` at x̂) and `zero_flow` tuple
(ZERO_FLOW splits and dormant outlets, built as `verify_bound` builds them, `verify/certificate.py:783-789`) — and delete,
for each s ∈ A in `RegionResult` split order, the rows D_s and the columns P_s by id, and the same rows of the scaled
residual. Nothing is appended (single-phase regimes have no label rows). With A = ∅, B *is* the certificate's matrix and
its screen document equals the certificate's `regularity` document byte for byte (gate G10a): that identity ties the new
path to K04.

**Rejected.**
- *The converged attempt's whole Newton system* (the engineer's (a) as worded): it would also replace the declaration by
  the attempt's form for every other split, every ZERO_FLOW/dormancy swap and every label row — i.e. stop judging the rest
  of the flowsheet on the declaration. B departs from K04 only along the one direction that is singular by construction;
  any other singularity still fails.
- *(b) `NOT_VERIFIED` at every boundary:* gives up a well-posed, regular, residual-accurate answer because of how the
  equilibrium rows are written; the "stay liquid" use case of D7 would be unreachable.
- *(c) certify a point stepped back into the interior:* the retreat a `VERIFIED` certificate needs (here ΔQ ≈ 0.01–0.1 W,
  problem-dependent through the conditioning) puts |a/N0| above `TAU_ACTIVE`, so the retreat point is not a KKT point (V5
  fails) and G10's 1e-6 K breaks; it would need a new ε-KKT status.
- *A boundary form inside K04 for every solve:* changes ordinary certificates, outside OPT's authority (§9.7 Q9).
- *Piecewise regularity with the TWO_PHASE regime as second piece (coherent orientation):* the TWO_PHASE attempt keeps
  the same lifted rows, so it is singular at V → 0 as well (measured: Q* + 1e-3 W, two-phase, `ILL_CONDITIONED`).

**What is claimed, in fields.** The V1 bundle stays the ordinary revision bundle; its certificate stays `UNVERIFIED`;
nothing in K04 or the bundle changes. V1's detail gains `basis` (`certificate` | `phase_boundary_form`) and, for the
second, `certificate_status`, `target_regularity` (the certificate's regularity document) and `boundary_form: {splits:
[unit…], rows_removed, columns_removed, regularity: <screen document>}`. The revision candidate gains
`certificate_basis` (always present), and the report's `claims` gain `numerical_verification: certificate |
phase_boundary_form` (numerical verification stays reported apart from optimality evidence, §2.5). `regime_note`
(already set whenever `phase_bounds_active` is non-empty) gains, for this basis: "the simulation certificate of this
design is UNVERIFIED (rank limitation at the phase boundary of <units>); its regularity is judged with those splits
held". The user doc (WO-7) states the consequence: committing the change-set and solving gives an `UNVERIFIED`
certificate whose R0 content equals V1's (G16 extended).

**Scope and declared limits.** Lifted splits held LIQUID or VAPOR with a guarded row. Not thermal ports (their rows have
no such bifurcation; a rank-limited port candidate fails V1 as today). Not TWO_PHASE-held splits at V → 0 or L → 0 (the
TWO_PHASE form is singular there: `NOT_VERIFIED`, declared). Not the gap where the certificate is rank-limited but
|a/N0| > `TAU_ACTIVE` (`NOT_VERIFIED`; a converged Ipopt boundary candidate sits ~1e-11 in a/N0, measured).

**Placement.** New pure module `src/openflowsheet/studies/nlp/boundary.py` (the clauses and B; returns
`RegularityEvidence` and the clause verdicts). It imports `assemble_target`, `screen` and `grade` and edits none of
them; nothing under `verify/` or `orchestrator/` imports it (an AST test asserts it), so no ordinary certificate can take
this path (G1 proves it on the corpus). Cost: one sparse LU and `onenormest` on a ≤ 300-square matrix per boundary
candidate. **Replay (WO-6):** `reproduce` recomputes (e1)–(e6) and B from the V1 bundle's final state and compares the
screen document under D2's float rule; a recorded `phase_boundary_form` whose recomputation fails a clause is `MISMATCH`.

### 9.2 A-2 — Structurally zero flows are held, not unbounded (§4.2.3)

Replaced (§4.2.3): "molar_flow → `[0, ∞)`, except a flow exactly zero at the start → unbounded, reason
`zero_at_start_pinned_by_regime` (unchanged rule)".

**Fact.** On the revision host every regime-pinned column is already held (D5), so no free column is "pinned by regime";
the free columns exactly zero at a start are structural zeros (C-MW: the feed carries exactly zero C2H5OH, so every
ethanol flow of the column is 0.0). Unbounded, Ipopt drives them negative and the twin refuses. Bounding them `[0, ∞)`
is the true domain but degenerate: the equalities force them to 0, so the feasible set has no interior in those
coordinates, Ipopt's bound push moves them off 0, and at the candidate those bounds are active with an identically zero
reduced gradient (dx_Z/dd ≡ 0), so V5's LICQ test fails.

**Decision** (revision host only; `Syn001NlpHost` keeps its rule, G2). At each certified point the host computes the
**zero subsystem** (Z, R):
- Z = the free columns of kind `molar_flow` whose value is `== 0.0`;
- R = the held rows r (label rows excluded) such that every entry of r's exact Jacobian over the free columns outside Z
  and over the decision parameters is `== 0.0`, and at least one entry over Z is non-zero. Free-column entries come from
  the compiled problem's Jacobian at the point (the evaluation the held system already selects, §4.2.1); decision
  entries from the twin's parameter Jacobian at the point.
- |R| = |Z| > 0 → the held system becomes rows − R, free − Z, held + {z: +0.0}, labels unchanged; the start record gets
  `zero_subsystem: {status: "held", columns: [...], rows: [...]}`. The other free `molar_flow` columns keep `[0, ∞)`.
- |R| ≠ |Z| → no reduction; every column of Z is bounded `[0, ∞)`, bound reason `zero_at_start_unresolved`;
  `zero_subsystem: {status: "unresolved", columns, rows}`. (Declared limit: one non-structural exact zero disables the
  reduction for that start; a matching-based refinement is a follow-up if a case needs it.)
- Z = ∅ → nothing changes; the path is inert (G23 (c) proves it by bytes).

**Why it is exact.** With J[R, ¬Z] = 0 and |R| = |Z| the held Jacobian is block lower-triangular, J = [[J_RZ, 0], [·,
J_rest]]. The held system is regular at the certified point, so J_RZ is nonsingular; with ∂F_R/∂d = 0 also,
dx_Z/dd = −J_RZ⁻¹·0 = 0. Holding Z at 0 and dropping R therefore changes neither the root nor any first derivative the
NLP, V5 or the Q-checks use. The structural assumption (that R's rows vanish identically when x_Z = 0, not only at the
point) is never trusted for the truth: V1 re-solves the full production system, V2 compares held columns exactly (a
non-zero ethanol flow in the re-solve fails V2), and V4 re-derives (Z, R) at the re-solve:

**V4 gains one clause:** the re-solve's (Z, R), by the same rule, equals the start's as id sets; else
`ZERO_SUBSYSTEM_CHANGED` → `NOT_VERIFIED` (new catalogue code).

**Rejected:** unbounded (measured failure); `[0, ∞)` everywhere (degenerate interior-point face; V5 LICQ failure by
structure); deleting the component from the problem (not exact when a decision or a reaction can introduce it — the row
test is local and checked); Ipopt `fixed_variable_treatment` with lb = ub = 0 (leaves rows with a zero Jacobian in the
equality set).

### 9.3 A-3 — Margins follow the closure; rows are built only where they equal it (§4.2.4, §4.7, D7; D-12, D-36)

Replaced (§4.2.4): "with `margin = tp_margin(provider, feed flows, T, P, context, components)` at the split's own
converged T and P for both kinds (D7), `None` for `ZERO_FLOW`."
Replaced (§4.7, after the table): "A held regime with no row in this table and no bound that holds it →
`REGIME_MARGIN_UNDEFINED(<unit>)` at the start phase."
Qualified (§3 D7): "therefore `tp_margin(provider, n_feed, T, P)` (`studies/syn001.py:79`) is the PH-type split's
regime margin too, for C ≥ 2" — true for ideal K only.

**Facts.** F2 was half false (D-12): on `pr-c1-v1` the closure decides single-phase branches by `classify`, and on a
composition-dependent K (γ–φ) VAPOR by the incipient-liquid ΣW (`_gamma_phi_admissible`, `orchestrator/region.py:779`).
And the closure never tests TWO_PHASE: `_admissible` returns `(True, 0.0)` for it (`region.py:754`) and the screen
reports it unchanged (`region.py:1680`); a TWO_PHASE attempt is held only by its flow bounds. C-MW's 19 TWO_PHASE stages
therefore had margin `None`, which failed V4 and V5 on every start although start 1 passed V1, V2, V3, V6.

**Decision — one rule: a split's margin is the closure's own test at the converged state.**

| Held regime | Margin |
| --- | --- |
| LIQUID / VAPOR, any provider, TP or PH type | 1 − value, value from the region's own `_admissible(provider, context, split, regime, state, ε)` (`region.py:741`; ideal: Σ x K or Σ y/K over the side's composition; γ–φ: Σ x K(x) or the incipient-liquid ΣW). Exposed by a public wrapper beside it (pure addition; the closure keeps calling `_admissible`). The call raises, or the provider's value is not of the form "admissible iff value ≤ 1 + ε" (F8) → `None` |
| TWO_PHASE | min(Σ_{c ∈ split.vapor} x_c, Σ_{c ∈ split.liquid} x_c) / N0 over the side columns of kind `molar_flow`; N0 = K03's registered `molar_flow` nominal (the one D-35's rows use). No `molar_flow` column on a side → `None` |
| ZERO_FLOW | `None` (unchanged; V4's exact-dormancy check) |

For ideal K the LIQUID/VAPOR margin is `tp_margin`'s −s1/−s2 (same function; last-bit differences only). The SYN-001
host keeps `tp_margin` (G2). Q4′'s code is unchanged: it judges the margins it is given (G3 untouched).

**Rows (§4.7).** A LIQUID/VAPOR split gets its D-35 row only if, at the certified start, |a/Σn − margin| ≤ 1e-10 (Σn the
row's feed total) — the row *is* the closure's test there; the split is then **guarded**. Otherwise (γ–φ VAPOR, where
ΣW is implicit; `pr-c1-v1`; no `LnKBlock` fed by its (T, P)) it is **unguarded**: no row, admitted, listed as
`regimes_unguarded: [unit…]` in the start record and the candidate, and judged by V4's margin alone — D7's "sound"
V4-only route, admitted with a declared limit (R-924). Its boundary optima cannot be reached as held-regime KKT points
(Ipopt crosses, V4 reports `PHASE_REGIME_CHANGED`). V4 re-checks the identity at the candidate for every guarded split
(same 1e-10; failure → V4 fail, detail `phase_row_not_closure_test(<unit>)`).

**`REGIME_MARGIN_UNDEFINED(<unit>)`** at the start phase now means only: a held split whose margin is `None` (other than
ZERO_FLOW), or a declared thermal port whose `T_sat` raises at the start's P (D-36's port clause, unchanged).

**V4** (with A-2's clause): every split with a margin needs margin ≥ `TAU_REGIME`, except a guarded split whose row is
active (§4.7, unchanged). TWO_PHASE and unguarded splits have no exemption.

**Rejected:** `None` and refuse (D-12/D-36 as built: refuses C-MW and every γ–φ column although the closure's test is
available); `tp_margin` everywhere (revert of `8f7f34b5`: not the closure's test for γ–φ VAPOR or `pr-c1-v1`, and void
for TWO_PHASE, which the closure does not test — F2's own rule says the margin follows the closure); a TWO_PHASE margin
min(s1, s2) (not what the closure uses; wrong test for γ–φ).

### 9.4 A-4 — Gate semantics after WO-5 (brief item 4)

Confirmed: G7, G8, G10, G19 and G20 are tolerance gates on analytic or independent values; no gate pins an OPT report's
bytes across work orders. The byte gates are G1 (F0), G2 (M03 SYN-001 report), G3 (E01, `system=None`), G4's bitwise
residual selection, G12 (job ≡ library at one commit) and G13 (replay); WO-5's phase rows touch none of them. WO-5's
A1/A2/A2b/C0 differences (A1 Q bitwise; A2 r 4.6e-11, Q 1.9e-10 rel; C0 Q 1.0e-11 rel) are expected and pass. The one
OPT-report byte check this amendment adds is A-2's inertness proof, G23 (c).

### 9.5 Gates changed and added

| Gate | What, how, tolerance |
| --- | --- |
| **G10** (amended) | As §6, plus: \|Q − Q*\| ≤ 1e-7·Q*; V1 basis `phase_boundary_form`; the V1 bundle's certificate `UNVERIFIED` whose limitations are one `rank_limitation` and possibly `near_threshold` items, nothing else; B `NO_RANK_LOSS_DETECTED`; V5's multiplier λ of the row as written (a/N0 ≥ 0) with \|λ − λ*\| ≤ 1e-4·λ*, λ* = N0 / (T_s·n_F·Σᵢ zᵢ Kᵢ ∂lnKᵢ/∂T), Kᵢ and ∂lnKᵢ/∂T at (T_b, P) by mpmath (dps 30) from the coefficient table (independent of cp; λ* > 0 in G7's sign convention). The `xfail(strict=True)` is removed. |
| **G10a** (new; default env, no Ipopt) | Anchor: B with A = ∅ equals the certificate's `regularity` document byte for byte (canonical JSON) at OPT-A1's and OPT-A3's V1 states and at the certified starts of TH-R1, M1 and C-MW. |
| **G10b** (new; default env) | Mechanism: certify OPT-A3's flowsheet at Q* − ΔQ, ΔQ ∈ {1, 0.1, 0.01, 1e-3} W, and at Q̂. The certificate's rcond₁/ΔQ lies within 5 % of its value at 1 W (measured 2.27e-6/W); B with A = {heater} is `NO_RANK_LOSS_DETECTED` at every point and its rcond₁ lies within 1 % of its value at 1 W. |
| **G10c** (new; default env) | Negatives: (i) a re-solve at Q* + 1e-3 W (TWO_PHASE) judged against OPT-A3's revision start → V1 fail at (e2); (ii) OPT-A3's candidate under a non-registered check policy → V1 fail at (e6); (iii) OPT-A3's candidate with A forced empty → V1 fail at (e3); (iv) no module under `verify/` or `orchestrator/` imports `studies.nlp.boundary` (AST). |
| **G10d** (new; default env) | VAPOR symmetry, certify level (OPT-A3v): the OPT-A1 flowsheet with an A, B, C vapour feed and a cooler duty Q_v at which the held VAPOR split's row has 0 < a/N0 ≤ 1e-7 (bisection on Q, recorded; dew point Σ zᵢ/Kᵢ(T_d, P) = 1 by mpmath, \|T − T_d\| ≤ 1e-6 K): the certificate is rank-limited, (e1)–(e6) hold with A = {cooler}. |
| **G22** (new; audited env) | C-MW (the G17 request): zero subsystem `held` with \|Z\| = \|R\| (recorded); twin `DomainError` count 0 on every start; all 19 TWO_PHASE stages have margin ≥ `TAU_REGIME` at each certified start; ≥ 1 start `KKT_POINT_VERIFIED`. Per-start status and V-check results recorded in `docs/OPT_DECISIONS.md`. A failure is escalated with the failing V-check and its numbers; no `xfail` without a design-lane ruling. |
| **G23** (new; default env) | Zero subsystem: (a) at C-MW's certified start every entry of J[R, ¬Z ∪ decisions] is `== 0.0`, and the reduced held system's residual equals the converged attempt's residual on the remaining rows bitwise; (b) dy/dd of three C-MW state outputs through the reduced and the unreduced held system agree within 1e-10 relative; (c) inertness: Z = ∅ for OPT-A1, A2, A2b, A3, C0, N1, and their reports at A-2's commit equal those at `wp/OPT` `826cc4c4` byte for byte with only G2's named wall-time members masked; (d) unresolved path, static level: a start where a zero flow is moved by a decision (C-MW with its feed's C2H5OH flow specification as a decision, box [0, 0.1] mol/s — or, if that is not a specification, any corpus flowsheet with a zero-valued fixed flow specification) → `zero_subsystem.status = unresolved`, those columns `[0, ∞)` with reason `zero_at_start_unresolved`. |
| **G24** (new; default env) | Margins: (a) OPT-A1/A2/A3 LIQUID splits: closure margin and `tp_margin` agree within 1e-12 absolute at their certified starts, rows guarded; (b) C-MW's 19 TWO_PHASE margins equal min(phase flow)/N0 recomputed independently from the state, bitwise; C-MW's single-phase held splits (if any) classified guarded/unguarded by the identity test, recorded; (c) a γ–φ VAPOR-held split (a corpus flowsheet if one has it, else a one-flash revision on the S10-C γ–φ provider) → unguarded, start admitted, `regimes_unguarded` names it, margin = 1 − ΣW; (d) a LIQUID split whose closure value is perturbed by 1e-9 (monkeypatch) → unguarded. |
| G9 | Rerun after WO-5c; expectation unchanged (`INFEASIBLE_REPORTED`). |
| G13 (extended, WO-6) | Also an OPT-A3 record → `MATCH` on x86-64 with B recomputed; an edited boundary-form rcond₁ beyond D2 → `MISMATCH`. The committed aarch64 fixture stays OPT-A2. |
| G16 (extended, WO-6) | Also OPT-A3: the `solve` job of the committed candidate gives an `UNVERIFIED` certificate (`rank_limitation`) whose R0 content equals V1's. |
| G17 | Rerun (record) after WO-5b for TH-R1, M1, C-MW. |

### 9.6 Work orders

| WO | Content | Depends | Acceptance |
| --- | --- | --- | --- |
| **WO-5b** | A-2, then A-3, as two isolated commits. A-2: zero subsystem in the revision host's held system, the bound rule, V4's clause, record fields, `ZERO_SUBSYSTEM_CHANGED`. A-3: public closure-value wrapper in `orchestrator/region.py`, TWO_PHASE flow margin, guarded/unguarded rows, D-36 narrowed, `regimes_unguarded`, V4's identity clause; D-12's code replaced (not reverted to `tp_margin`). | WO-5 | G1, G2, G3, G23 (at A-2's commit), G24, G22, G7/G8/G9 rerun, G17 rerun |
| **WO-5c** | A-1: `studies/nlp/boundary.py`, V1 bases, report fields (`basis`, `certificate_basis`, `claims.numerical_verification`, `regime_note` text), OPT-A3v flowsheet and its mpmath script, λ* in OPT-A3's script; G10's `xfail` removed. | WO-5b (the guarded notion) | G1, G2, G10, G10a–G10d, G9 rerun |
| WO-6 (delta) | Replay recomputes A-1's clauses and B, and A-2's V4 clause; G13, G16 extended. WO-6's core does not depend on Amendment A and may start now; the deltas land after WO-5c. | WO-4; WO-5c for the deltas | as §5 plus the extensions |
| WO-7 (delta) | User doc: boundary candidates and `certificate_basis`; declared limits (TWO_PHASE-side boundaries, unguarded regimes, unresolved zero subsystems, the rank-limited-but-inactive gap); the manifest lists G10a–G10d and G22–G24. | as §5 | as §5 |

### 9.7 Questions, facts and risks (each with a default)

- **Q7, replaced (Frank; plain words).** "Sometimes the best design sits exactly on a boiling or condensing point — for
  example 'heat this liquid as much as possible without it starting to boil'. The optimiser now finds and verifies such
  an optimum and flags it in the report. The catch: if you save that design and run it as an ordinary simulation, the
  simulator's own check calls it 'unverified', because two physical states meet exactly there; the optimisation report
  says so in advance. Report such optima as verified-with-that-flag, or only as found-but-not-verified?" **Default:
  verified, with the flag** (A-1).
- **Q9 (Frank / K04's owner; scope).** "Should ordinary simulations judge an exact boiling-point state the same way, so
  a saved boundary design certifies normally?" It changes ordinary certificates and needs its own ADR on K04.
  **Default: not in 0.4; follow-up.**
- **F6 (fact, WO-5c).** At OPT-A3's candidate every certificate check other than regularity passes ((e6) holds). If one
  fails (likeliest: a fresh-flash phase check at T_b), stop: G10 stays `xfail(strict=True)` with the failing check named,
  and escalate.
- **F7 (fact, WO-5b).** C-MW's zero subsystem resolves (\|R\| = \|Z\|) and the cold re-solve at a candidate keeps its
  ethanol flows `== 0.0`. If not, record the counts or the non-zero values and escalate; meanwhile the `unresolved` path.
- **F8 (fact, WO-5b).** The value semantics of `_pr_admissible` (`pr-c1-v1`). If "admissible iff value ≤ 1 + ε", the
  LIQUID/VAPOR rule applies; otherwise margin `None` → `REGIME_MARGIN_UNDEFINED` for its held single-phase splits,
  declared. **Default: `None` until read.**
- **Risks (declared limits, documented in WO-7):** TWO_PHASE-side boundary optima are `NOT_VERIFIED`; unguarded regimes'
  boundary optima are `NOT_VERIFIED` (`PHASE_REGIME_CHANGED`); the zero subsystem is all-or-nothing per start; a
  candidate in the rank-limited-but-inactive gap is `NOT_VERIFIED`. Each is honest and fail-safe; none loosens a check.

### 9.8 Dispositions of build decisions

D-12: superseded by A-3 (code at `8f7f34b5` replaced, not reverted). D-36: narrowed by A-3. D-37: ruled by A-1.
D-38: stands. D-35: stands (rows, ids, nominals, V4's exemption by V3's active set), with A-3's guarded condition.
