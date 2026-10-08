# ADR 0032 — M03: the general NLP bridge is a full-space PyNumero gray box over the parametric twin, solved by an audited cyipopt with Ipopt's limited-memory Hessian, and judged only on the re-solved, certified simulation

**Status:** Proposed, 2026-10-08; Amendment 1 the same day (below). Accepted when M03's evidence manifest is `tested` for A31–A41 and A47 of the specification (A35–A40 in the audited environment) and the design-lane review of WO-7 and WO-8 has closed its must-fix items. If the [A10] audit fails, D1–D4 stay Proposed, D5 and D6 are accepted on A31–A34 and A41, and A35–A40 are recorded `BLOCKED`.
**Date:** 2026-10-08
**Author:** design lane (`specifier`); brief `docs/briefs/M03-specification.md`.
**Normative text:** `docs/derivations/M03-studies-spec.md` §8, §9, §10, §11 (A31–A41).
**Builds on:** ADR 0031 (the twin, the qualification, the adjoint); ADR 0003 D5.4 and Q3; ADR 0006 D1.5, D2.4 and R-135; R-129.
**Amends (additively):** `pyproject.toml` gains an optional extra `nlp` (only after D5's gate and Frank's N1); the schema list gains `optimization-report` (plan §2.2's `OptimizationReport`).
**Reverses:** nothing. R-129 stands.
**Affected requirements:** A06 (M03's bridge, tested separately from M05's), W24 (M03's part), D16 (the optimization closure), D04 and A10 (a new binary closure, audited before use), blueprint §10 ("a penalty is not … constraint satisfaction"; "local stationarity is not global optimality"), §6.3.
**Affected packages:** M03 (builds it), M05 (must not claim trust-region guarantees from this bridge, plan L271), T08-style release gates (the extra's notices).
**Register:** R-186 (D1), R-187 (D2), R-188 (D3), R-189 (D4), R-190 (D5), R-191 (D6); Amendment 1: R-212 (D3, D6).

## Context

Blueprint [A06] names the default general NLP bridge: `CompiledProblem` wrapped as a PyNumero `ExternalGreyBoxModel`, exposing variables, residuals, the sparse Jacobian and an optional multiplier-weighted Hessian to cyipopt, "without reliable Hessians, explicitly configure a supported approximation", and no hand-transpiled second model. The compiled Hessian is `absent` (ADR 0003 D5.4). CasADi's bundled Ipopt is in the METIS 4.0 closure and may not be used (ADR 0006 D2.4, ADR 0003 Q3). On 2026-10-08 (a probe, not the audit): PyPI offers no binary cyipopt for linux/CPython 3.13, the host has no system Ipopt, and Pyomo 6.10.1's wheel carries no `libpynumero_ASL`, which `PyomoNLPWithGreyBoxBlocks` needs because it builds an `AslNLP` for the non-gray-box part. Pyomo's cyipopt interface forces `hessian_approximation = limited-memory` when a gray box has no Hessian.

## Decision

**D1. Full space, over the twin.** The gray box's inputs are the 47 state variables and the decisions; its equality constraints are the kept rows, evaluated with ADR 0031's twin with the decisions symbolic; its Jacobian is the twin's exact `[Fₓ Fₚ]`. Pyomo holds only the declared objective and inequality constraints (linear or quadratic in named variables), the bounds and the scaling. Decisions inconsistent with the eliminated alias rows are refused before any solve. Each Ipopt iteration costs at most one twin residual and one twin Jacobian plus line-search residuals, and the counters are recorded.

**D2. Hessian policy.** The exact Hessian stays `absent`. The adapter configures `hessian_approximation = limited-memory`, history 6, and records it; a request for an exact Hessian is refused `HESSIAN_UNAVAILABLE` before any solver call; no finite-difference, Gauss–Newton or zero Hessian is supplied. The report's `second_order` is `"not_assessed"`, or `"vacuous_at_vertex"` when the active set has as many members as there are decisions, LICQ holds and every multiplier is strictly positive. ADR 0003's trigger T5 does not fire.

**D3. The candidate is the decision vector; the truth is the re-solved, certified simulation.** For every start: re-solve at the returned decisions with the production solver (V1, `VERIFIED` required); a gross-error comparison of Ipopt's state (V2); bounds and inequalities evaluated on the re-solved state (V3); regimes and margins unchanged and ≥ `τ_regime` (V4); a reduced-space KKT check built from M03's adjoint sensitivities at the re-solved state, independent of Ipopt's multipliers and measures (V5). Statuses `KKT_POINT_VERIFIED`, `NOT_VERIFIED`, `INFEASIBLE_REPORTED`, `SOLVER_FAILED`, `UNSUPPORTED`; Ipopt's return status is recorded and never sufficient. Each start is classified (V1–V5 pass → `KKT_POINT_VERIFIED` whatever Ipopt returned; else Ipopt status 0 or 1 → `NOT_VERIFIED`; else status 2 → `INFEASIBLE_REPORTED`; else `SOLVER_FAILED`), and the report's status is the highest of its starts' in the order `KKT_POINT_VERIFIED` > `NOT_VERIFIED` > `INFEASIBLE_REPORTED` > `SOLVER_FAILED` (Amendment 1). Without an optimizer's state V2 is `not_evaluated`, so no candidate is verified without one. Three registered starts give `distinct_local_solutions`; `claims.global_optimality` is always `false`.

**D4. True domain restrictions, never penalties.** Decisions carry their declared box; temperatures and pressures the property provider's declared domain; molar flows a lower bound of 0 except a flow that is exactly zero at the verified start (pinned there by its regime's own rows; a bound would be degenerate and break LICQ), which V2 and V4 then police. `bound_relax_factor = 0`. Inequalities are constraints with bounds; no penalty term is ever added.

**D5. Distribution: an optional extra behind an [A10] gate.** The bridge's Ipopt comes from a separately distributed package, never from CasADi's wheel. Before any `nlp` code merges, `docs/m03-ipopt-audit.md` records gate G-A10 (specification §9: the loaded-object inventory, no CasADi METIS-closure object, METIS ≥ 5 if any, no HSL and MUMPS as the linear solver, no GPL-without-exception or restrictive object, the default install unchanged, reproducible pins, a verdict). The extra `nlp` is declared only after a `PASS` and Frank's answer on the licences (N1). Without it, every optimization request is `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)` naming the audit; no other optimizer is substituted without a new ADR (N2).

**D6. The optimization closure is study-level.** `optimization_readiness` returns `READY_FOR_OPTIMIZATION` only when the formulation closes (decisions are pinned inputs with finite boxes and starts inside them, alias-consistent, every referenced variable exists, the Hessian policy is the approximation, the start solves and certifies) **and** an audited NLP solver is importable; otherwise `unsupported` with every failing reason. `Application.validate(task="optimization")` keeps R-129's typed `unsupported` in M03: a `ProcessRevision` has no place for decisions, objective or constraints, and adding one is a schema migration outside M03.

## Alternatives considered

- **Reduced space** (the gray box's inputs are the decisions, its outputs the objective and constraints, each evaluation a nested simulation solve with implicit gradients). Rejected for M03: [A06] names the bridge that exposes residuals and the sparse Jacobian; a nested solve turns every solver failure into an NLP evaluation error; and an outputs-form gray box over decisions is what M05's trust-region adapter needs, so building it here would pre-empt M05's design. M03's verification (D3 V5) already uses the reduced-space derivatives, so nothing is lost.
- **A hand-transpiled Pyomo model of SYN-001.** Rejected: plan L271 and [A06] forbid a second hand-authored model.
- **CasADi's `nlpsol` with its bundled Ipopt.** Rejected: ADR 0006 D2.4 (the METIS 4.0 use restriction).
- **cyipopt directly, without PyNumero.** Not adopted: it would avoid ASL but departs from [A06]'s named bridge; it is the natural content of a later ADR if the audit fails only on ASL.
- **A finite-difference or Gauss–Newton Hessian.** Rejected: the former fabricates a derivative class the capability declares absent; the latter does not apply to general equality constraints.
- **Trust Ipopt's termination and Ipopt's state.** Rejected: blueprint §10 separates physical feasibility from optimizer termination; V1–V5 make that separation executable.
- **Bound every flow at zero.** Rejected: at the liquid heater four flows sit on the bound with gradients dependent on the equality rows (LICQ fails), which degrades the interior-point method for no physical gain.
- **Flip `validate(task="optimization")` now.** Rejected: there is no revision-level formulation for it to validate; R-129's watch-for ("a new operation returning it without an optimizer behind it") applies.
- **A SciPy fallback optimizer when the audit fails.** Not adopted as a default (N2): it is a scope and value judgment for Frank, and it would need its own ADR.

## Consequences

- C1. W24's M03 part depends on WO-6's audit verdict; if it fails, M03 delivers everything else and reports A35–A40 `BLOCKED`.
- C2. The default install, the default gate and every registered identity are unchanged; the `nlp` tests are deselected (not skipped) in the default gate and run by `scripts/m03_nlp_check.sh` in the audited environment.
- C3. Optimization results are only ever local, first-order, and for the regime of the start; the report says so in fields, not prose.
- C4. M05 can reuse the formulation, the verification (V1–V6) and the report type; it cannot reuse a cyipopt success as trust-region evidence (plan L271).

## Migration

None. The extra and the schema are new.

## Acceptance evidence

Specification assertions A31–A34, A41 and A47 `tested` in the default environment; A35–A40 `tested` in the audited environment (or `BLOCKED` with the audit as evidence); the design-lane review of WO-7 and WO-8; Frank's answer to N1 recorded before the extra is declared.

## Amendment 1 (design lane, 2026-10-08)

After the build of WO-7 and before WO-8 (specification §16). No decision is reversed.

- **D3, status precedence.** When one start's claimed solution is refuted (`NOT_VERIFIED`) and another start reports infeasibility (`INFEASIBLE_REPORTED`), the report is `NOT_VERIFIED`. The refutation is the more specific evidence. Ipopt's infeasibility verdict is local and heuristic, and it must not mask "the optimizer's answer is wrong". Every non-verified start is listed in `reasons`, under every status. The classification and the aggregation are one pure function in default-gate code (A47), and WO-8's adapter computes no status of its own. Rejected: `INFEASIBLE_REPORTED` first. A heuristic statement about the problem would then hide a refuted claim about a point. Rejected: requiring Ipopt success for `KKT_POINT_VERIFIED`. D3 makes the re-solved simulation the truth, so Ipopt's status is neither sufficient nor necessary.
- **D3, V2.** V2 compares an optimizer's state with the re-solved simulation; without such a state it is `not_evaluated`, and the candidate is not `passed`. A32 judges the reference optimum on V1 and V3–V5 accordingly.
- **D6, readiness.** `SIMULATION_NOT_READY` covers every way a start fails to be a qualified root: the flowsheet does not build; the decision values are refused before a solve (including a pressure specification moved alone, which SYN-001's single pressure field cannot represent); the start does not converge or certify; or Q3 cannot be evaluated because the start's sensitivity is refused at request level. The start record's `outcome`, `certificate_status` and `alias_residuals` determine which. Rejected: one code per sub-condition, because no consumer acts on them differently.

