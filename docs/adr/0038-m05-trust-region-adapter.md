# ADR 0038 — M05: the trust-region adapter is Pyomo 6.10.1's TRF over a projection compiled from the canonical `ProblemSpec`, with Python-callback ExternalFunctions and the audited Ipopt executable for its subproblems

**Status:** Proposed, 2026-10-09. It is accepted when M05's evidence manifest is `tested` for the design note's gates
G1–G4, G7, G12 and G13, and the design-lane review of WO-2–WO-4 has closed its must-fix items.
**Author:** design lane (`architect`), M05.
**Normative text:** `docs/design/M05-trust-region.md` §4 (probe), §5.1, §6 (binding) and §9.1–§9.3.
**Register:** R-260 to R-266, R-271.
**Amends:** nothing. It adds the schema `trust-region-study-v1` (together with ADR 0039) to plan §2.2's list, and the
module `studies/trust_region/` to the backend-import guard's allow-list for `pyomo` only.
**Affected requirements:** A06 (M05's half), D13, W24 (M05's half); blueprint §10 L437, L441 and L443.
**Affected packages:** M05; M07 (consumes it); M03 (shares the audited environment, no change).

## Context

Blueprint §10 asks for the documented Pyomo trust-region framework for eligible expensive smooth gray-box models:
- the black box is identified through `ExternalFunction`;
- the glass box is "generated from the canonical model where needed, with source maps and equivalence tests";
- the adapter exposes truth evaluations, gradients or a qualified alternative, local models, trust-region and filter
  state, rejected steps and cost;
- the implementation and its assumptions are pinned.

Plan L271 forbids a second hand-authored model and requires an ADR-backed alternative if the framework cannot consume
the intended mixed model.

**The canonical model.** A `ProblemSpec` (`compile/spec.py`) is backend-free:
- its rows are builders over an `Algebra` (`exp`, `log`, `sqrt`) plus operator overloading;
- property calls are opaque `PropertyBlock`s with `values` and declared-sparse `jacobian`.

The C1 property provider `pr-c1-v1` is numpy code with analytic first derivatives (ADR 0026 D6). The C1 reactor is an
out-of-process, derivative-free experiment costing 25–45 s (R-250). In the coupled route it enters as two pinned
coordinates (X̂, ΔT̂) (ADR 0034 D1).

**The probe** (2026-10-09, audited M03 environment, design note §4) found:
- TRF composes with Python-callback EFs: wrapped in a `PropertyBlock`-style holder, Pyomo's example reproduces
  bitwise;
- TRF needs a gradient callback for every EF;
- it clones the model, which deep-copies callback state unless the owner preserves identity;
- it aborts on an exception and silently accepts NaN;
- it cannot use PyNumero cyipopt for its subproblems, because it passes `keepfiles`;
- its subproblem solver is the ASL `ipopt` executable. That executable loads three objects M03's inventory lacks:
  `bin/ipopt`, `libipoptamplinterface.so.3.14.20` and `libgomp.so.1`.

## Decision

**D1. Framework and pin.** The trust-region adapter is `pyomo.contrib.trustregion` from Pyomo 6.10.1 (Eason & Biegler
2016/2018; Yoshio & Biegler 2020), used unmodified. It is pinned by the version string and by the sha256 of
`TRF.py`, `interface.py`, `filter.py`, `funnel.py` and `util.py`, recorded by the audit extension (D4). Any mismatch
makes readiness `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)`. A Pyomo upgrade is a new ADR.

**D2. The glass box is a projection, not a backend.**
- `studies/trust_region/projection.py` calls each `EquationSpec.build` with a `PyomoAlgebra`, which implements exactly
  the `Algebra` protocol with `pyomo.environ`'s functions, and with Pyomo variables as symbols.
- Decisions are pinned inputs (ADR 0031 D1), promoted to scaled variables d ∈ [−1, 1] with the symbol c + h·d.
- Each property-block output becomes one Python-callback `ExternalFunction` behind an explicit output variable
  y == s·EF(inputs). The outputs of a block share one holder.
- Construction order and the source map `projection-source-map-v1` are as in design note §6.1–§6.2.
- `PyomoAlgebra` implements no `CompiledProblem` and no route can select it, so R-003 stands. A guard test (G13)
  enforces this.
- Refusals: `PARAMETER_NOT_DIFFERENTIABLE` (ADR 0031's meaning), `PROJECTION_NONSMOOTH`, `PROJECTION_STRUCTURE`,
  `PROJECTION_DOF`.
- Equivalence against the CasADi compiled problem: residuals ≤ 1e-12 scaled; x-Jacobian ≤ 1e-10; decision columns
  ≤ 1e-7 against an FD oracle (G4).

**D3. The expensive model enters full-space.**
- An external unit's pinned (X̂, ΔT̂) become variables with bounds [0, 0.95] and [−50, 250] K.
- Each is linked by `w == s·EF(inlet)` to one of two EFs on the unit's seven inlet variables (n_H₂, n_N₂, n_NH₃, n_Ar,
  n_CH₄, T, P).
- The EF values are M02's coupling coordinates (ξ_E/n_N₂,in, T_E − T_in), computed by M02's own projection function.
- TRF thereby solves the coupling and the optimization together. The reactor is evaluated only at inlets: one
  experiment per trial point, and n_in = 7 per gradient.

**D4. Subproblem solver.**
- TRF's `solver` is the alias `openflowsheet_trsp_ipopt`: a subclass of Pyomo's `IPOPT` shell plugin with the
  executable `<sys.prefix>/bin/ipopt` pinned by sha256 and the options `M05-trsp-ipopt-v1` (design note §6.7).
- The options set the exact Hessian (from the ASL; the subproblem is pure algebra), `bound_relax_factor = 0`,
  `honor_original_bounds = yes`, `acceptable_iter = 0`, `mu_strategy = monotone`, MUMPS, and user scaling.
- ADR 0032 D2 (L-BFGS for M03's twin, which has no Hessian) is not in conflict: here the Hessian exists.
- **[A10] audit extension:** a workload `trf-trsp-executable` inventories the executable's loaded objects with M03's
  tooling into `benchmarks/m05/trsp-inventory-x86_64.json`, with the verdict in `docs/m05-trsp-audit.md`. M03's
  criteria apply unchanged (G1). No new package enters the environment.
- **Contingency** (only if G1 fails): the alias `openflowsheet_trsp_cyipopt`, which drops `keepfiles` and `tee` and
  solves through the already-audited PyNumero cyipopt. It must reproduce TR-E1 within 1e-8, and it is recorded as a
  configuration the framework did not itself test.

**D5. The ExternalFunction contract.** Each black box has one `EFHolder`, which:
- returns itself from `__deepcopy__`, so TRF's clone shares it;
- memoizes on exact binary64 input tuples;
- never returns a non-finite value (`TruthRefused("non_finite_output")`);
- raises `TruthRefused(status, reason)` for every refusal — property `DomainError`, any experiment status other than
  `ok`, an infeasible FD side, and the budget;
- enforces the run and study caps before every cold request;
- appends every request to the truth ledger (ADR 0039 D6).

TRF has no evaluation-failure path, so a refusal ends the run as `TRF_TRUTH_REFUSED`; retries are the study's (ADR 0039
D3).

**D6. Truth adapters and gradients.**
- `ParentExperimentTruth` (M02 `ExperimentRunner`, one runner per study, so ADR 0034 D5's frozen identity spans the
  study).
- `SurrogateTruth` (M04 `QuadraticSurrogate`, analytic `inlet_sensitivity`).
- A test-only `SyntheticTruth`.

A derivative-free truth gets the finite-difference policy `M05-fd-v1`:
- forward differences in the inlet coordinates, h_j = 2⁻¹⁴·max(|w_j|, f_j), applied as an exact difference;
- the inward side at a hard-domain bound;
- the seven points run concurrently on min(7, physical cores − 1) workers;
- a once-per-study gradient-quality check (η against η/4, ≤ 1e-3 scaled; at most two ×4 escalations).

FD gradients are optimizer internals and are never reported as sensitivities. ADR 0031 C3 is untouched.

**D7. Basis functions** (`M05-basis-v1`):
- property EFs get the affine Taylor model at w₀. It leaves every r_k unchanged and fixes TRF's first subproblem,
  which under the default b = 0 would see zero enthalpies and ln φ;
- the reactor EF gets the promoted M04 quadratic, compiled through `PyomoAlgebra` on the clone's arguments, or else the
  constant d(w₀).

The basis is frozen for the run and the study (blueprint L427, L437).

**D8. Configuration and state exposure.**
- **Configuration.** `M05-trf-config-v1` (design note §6.7) is passed to `solve()`, never to the factory constructor.
  It sets trust radius 0.25, minimum 1e-4, maximum 1.0, 30 iterations, feasibility termination 1e-5, step-size
  termination 0.5·min_j(δ_j/h_j), and Pyomo's defaults otherwise. EF outputs are scaled by powers of two from their
  start values, so θ is relative.
- **State.** Trust-region and filter state and rejected steps are read from the `pyomo.contrib.trustregion` INFO
  records, parsed exactly, with the filter reconstructed from θ-type steps. The outcome comes from the captured EXIT
  lines, which must agree with the logged values. Outcomes: `TRF_CONVERGED`, `TRF_FEASIBLE_STALLED`,
  `TRF_MAX_ITERATIONS`, `TRF_SUBPROBLEM_FAILED`, `TRF_TRUTH_REFUSED(...)` and `TRF_ERROR(...)`.
- **One TRF run per process.** `stdout` capture is process-global.

**D9. Examples.**
- **TR-E1**, Eason–Biegler example 1 as a `ProblemSpec`, is the framework-equivalence oracle against Pyomo's native
  example (G3).
- **TR-E2**, the C1 formulation of ADR 0039 with the test-only C^∞ truth `m05-synthetic-interior-v1` (analytic
  gradient), is the eligible smooth gray-box example (G5). Its assumptions are stated item by item (design note §5.2,
  A1–A7). Pyomo 6.10.1 has no restoration phase: a subproblem failure aborts, and that is a stated limitation of the
  implementation.
- The real reactor is **qualified, not eligible** (smoothness assumed, gradient by FD). Its outcomes are empirical.

**D10. Distribution.**
- Pyomo and the executable live only in the audited `nlp` environment. Until N1 the default install answers
  `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)`, naming the audit (M03 D5's pattern).
- `trust_region_readiness` lists every failing reason.
- No other optimizer is substituted except through ADR 0040.

## Alternatives considered

- **Our own trust-region/filter loop over M03's adapter.** Rejected as the primary route: it is not "a tested
  framework" (D13), and the documented framework composes (probe). It is kept, in reduced space, as ADR 0040's
  conditional fallback.
- **M03's `ExternalGreyBoxModel` as TRF's black box.** Rejected: TRF identifies black boxes only through
  `ExternalFunction` (blueprint L441), and A06 keeps the bridges apart.
- **Grey-box blocks for the properties inside the TRF subproblem, via cyipopt.** Rejected:
  - TRF passes `keepfiles` (probe P8);
  - its DOF count and step rejection cannot see grey-box internals;
  - Ipopt would need L-BFGS for the whole subproblem.
- **Peng–Robinson written as Pyomo algebra.** Rejected: it is a second model of the provider, including its root
  selection (plan L271).
- **A text code generator emitting a Pyomo model file.** Rejected: a second artifact to keep in sync. The in-memory
  projection calls the same builders the CasADi backend calls.
- **The reactor through M02's coupled solve, as a reduced-space black box.** Rejected:
  - each evaluation is a 2–6 min solve carrying the coupling-tolerance noise;
  - a gradient needs n_d more such solves;
  - full space needs 1 + 7 experiments per accepted iteration and no outer loop.
- **TRF's default basis b = 0.** Rejected: its first subproblem would zero every property output.
- **Returning NaN, or a penalty value, on a refused evaluation.** Rejected: TRF accepts NaN silently (probe P7), and a
  penalty is forbidden (R-189).
- **A central-difference gradient.** Rejected: twice the cost; the gradient check measures forward accuracy instead of
  assuming it.

## Consequences

- One new optional subpackage, `studies/trust_region/`, and one new schema.
- One newly audited binary set (`bin/ipopt` and two libraries) in the existing environment.
- The default gate is unchanged in cost.
- Pinning internals (log text and EXIT prints) means a Pyomo upgrade fails G2 loudly rather than silently changing
  behaviour.
- The adapter is generic in the number of decisions and of external units. C1 uses one of each (ADR 0039).

## Migration

None. No identity, schema or registered value changes.

## Amendment 1 (2026-10-09): rulings on the build (design note §16)

- **D2.** Omitted rows are exactly the certified alias elimination's (R-274). Scales come from K03's
  `Scaling.from_spec` (R-275). The shape check `PROJECTION_IMPLICIT_EF_INPUT` uses a perfect matching with the
  decisions and the link-EF outputs fixed (R-278).
- **D5.** `run_trf` pre-flights every EF at x₀, and any refusal recorded in a run means no candidate (R-276; probe P13).
- **D7.** A basis is mandatory. The reactor EF without a promoted surrogate gets the affine Taylor basis at w₀, not
  the constant d(w₀). TRF's default b ≡ 0 is allowed only as TR-E1's explicit `zero_basis` (R-277; probe P14).
- **D8.** Exits are classified with θ re-checked from the returned model. `TRF_CONVERGED` needs at least one accepted
  TRSP step. The new outcomes are `TRF_EXIT_WITHOUT_STEP` and `TRF_STALLED_INCONSISTENT` (R-279; probe P14).

## Acceptance evidence

Design note gates G1 (audit), G2 (pin), G3 (TR-E1), G4 (equivalence), G7 (accounting mechanics), G12 (default gate)
and G13 (no second model, no backend). The probe is recorded in design note §4 as a probe, not as evidence.
