# Brief — M03 specification: sweeps, implicit sensitivities, a small estimation, and the general NLP adapter

**To:** `specifier` (design lane). **From:** the session (build lane), 2026-10-08. **Branch:** `wp/M03` from `main`.
**Plan row (v1.2 §4.4, binding):** *M03 — T08: sweeps, implicit sensitivities and small parameter-estimation example;
general NLP gray-box/cyipopt adapter. Acceptance: sensitivity/adjoint checks on regular roots; singular-state
refusal; identifiable vs unidentifiable fit; optimizer with verified constraints and Hessian policy.* Lane: Design /
Build. Gate fed: **W24** (part: "fixed-topology optimization …"; M05 supplies the trust-region half). Requirement
ids: **A06** (two distinct bridges — M03 owns the general NLP one), **D16** (task-specific readiness: M03 owns the
optimization closure), D13 only as far as M05 inherits from M03.

## 1. The question

Write M03's authority documents — derivation(s), ADR(s) and a test specification with numbered falsifiable
assertions and machine-readable reference values — so that the build lane can implement (a) parameter sensitivities
of a converged regular root from Fₓ xₚ = −Fₚ, and the adjoint form, with branch and conditioning qualifications and a
typed refusal at singular or unqualified states; (b) sweeps as a study over declared parameters; (c) one small
parameter-estimation example with one identifiable and one unidentifiable fit, recorded with observation covariance,
bounds and identifiability evidence; and (d) the general NLP gray-box adapter (cyipopt through PyNumero
`ExternalGreyBoxModel`, blueprint §10 A06) with verified constraints and an explicit Hessian policy — and so that a
verdict can later judge M03's part of W24 from the evidence alone.

## 2. Why it needs the design lane

Plan §1.3: derivations, sensitivities, regularity/certificate policy and adversarial verifier tests are design-led.
What counts as a "regular root" for sensitivity (as opposed to K04's square-simulation [A08] screen, which blueprint
§8.1 forbids applying to decision variables), when a sensitivity is refused, what identifiability means operationally,
and what an optimizer result may claim (local stationarity ≠ optimality; termination ≠ feasibility) are semantics
every later package (M04 surrogates' gradient checks, M05 trust region, M07 journey) inherits.

## 3. Current state (read these; the digest is curated for you)

- **Recon digest:** `docs/briefs/M03-recon-digest.md` (≈38 KB, excerpts with `file:line`). Its §0 bottom line, §2
  tensions, §3 code, §4 dependencies and §9 "not found" are the core. Summary:
  - No M03 code exists: no dF/dp, adjoint, sweep, `Study`, `ExperimentRequest`, `OptimizationReport`, estimation,
    identifiability or NLP adapter. Those type names appear only in plan/interfaces-frozen/schemas README.
  - K01 `CasadiCompiledProblem` (`compile/casadi_backend.py:302`) gives an exact sparse Jacobian, JVP and VJP
    (582–600) **with respect to variables only**; parameters are baked in as float constants (`spec.parameters`,
    L327; identified by `constants_sha256`). `Capabilities` (`compile/compiled.py:61`) has jacobian/jvp/vjp/hessian;
    Hessian is `"absent"` and raises (602–614).
  - The only sensitivity code is K03's exact Schur-complement dR/dt for SYN-001's 3-variable tear
    (`orchestrator/tear.py:318`, R-010) — blueprint §5.1's implicit-function formula specialised to the tear.
  - Specification rows are promoted as v − p (`application/binding.py:204–214`); T04's typed homotopy re-binds pinned
    inputs (`orchestrator/homotopy.py:74–128`, R-030) — the nearest precedent for "a parameter".
  - K04 regularity screen `verify/regularity.py:156` on the 47×47 target Jacobian, `RegularityStatus`
    (`verify/__init__.py:42`).
  - `validate(task="optimization")` returns typed `unsupported`; `READY_FOR_OPTIMIZATION` is never returned (R-129).
  - SYN-001 candidate parameters (`cases/SYN-001-nominal.yaml`): split fraction r = 0.5, flash T 360 K, heater outlet
    T 350 K, feed 300 K / 100 kPa, fresh feed 1.0 mol/s per component; `kinetic_cstr` Damköhler and coolant
    parameters; `conversion_reactor` conversion and ν.
- **Normative text:** blueprint §10 (`docs/blueprint-v3.1.md` L429–447) — read whole; §5.1 (L173–175), §5.2
  (L179–181), §6.3 (L224), §8.1 (L374). Plan §4.4 rows, L271 (the two-adapter rule), A06 L321, D16 L311, W24 L353.
  `docs/requirements.yaml` D16 (L330–352), A06 (L502–506), W24 (L739–742), M03 (L955–960).
- **Conventions you must respect:** ADR 0001 (state, units, signs), ADR 0003 (CasADi backend; D5.4 "M03's Hessian
  policy is written against the negotiated capability"; Q3 below; T5 trigger), ADR 0004 (SuperLU explicit options;
  one factorization per iteration), ADR 0006 (distribution; D1.5, D2.4 below), ADR 0007 (reproducibility/certificate),
  ADR 0010 (globalization/homotopy), ADR 0013 (verifier's fresh flash), ADR 0019/0020 (application contract, frozen;
  M06's Amendment 3 is approved and lands in parallel — stay additive and do not collide with it).

## 4. Constraints and invariants

- **Existing identities do not move.** SYN-001's structural hash, the K05 identity document, every registered T06
  corpus value: bit for bit. Parameter derivatives must be **additive** (e.g. a separately compiled Fₚ function or an
  optional capability), never a change to the existing compiled residual/Jacobian or its hash. If your design needs an
  identity move, say so explicitly — it needs Frank.
- Frozen interfaces (plan §2.1, `docs/interfaces-frozen.md` §1: `CompiledProblem` is frozen) and schemas (§2.2) change
  only by ADR; prefer additive widening (an optional capability with explicit `absent`).
- Residual, Jacobian and Fₚ describe the same function at the same state; exact caches key on exact canonical inputs.
- No placeholder success: unsupported sensitivity/optimization requests return explicit typed refusals; a penalty is
  not constraint satisfaction; optimizer termination is not feasibility; local stationarity is not optimality.
- Correctness fixtures need an analytic or independent expectation (mpmath closed forms, as K01/K03 did).
- **Distribution (ADR 0006 D1.5, D2.4; ADR 0003 Q3):** M03 must NOT use CasADi's bundled `nlpsol:ipopt` (it is
  loadable in `.venv` but sits in the METIS-4.0 closure; no default path may load it). Ipopt must come from a
  separately distributed package (cyipopt, as the plan names) **whose own [A10] audit is run first** — a build-lane
  task. cyipopt and Pyomo/PyNumero are not in `requirements.lock`, `pyproject.toml` or `.venv`; any addition is an
  optional extra, never a default dependency, and the default install must not require GPL components (blueprint
  §15). State, as a gate in your spec, what the audit must find for the adapter to be usable, and what M03 delivers
  if no audited Ipopt distribution is acceptable (a typed unsupported result and the evidence why).
- Performance: SYN-001 Newton is milliseconds; a full sensitivity matrix must reuse the converged factorization
  (ADR 0004: one factorization), not refactorize per parameter.

## 5. Already decided — do not reopen

- Backend CasADi 3.8.0 (R-003, ADR 0003); Pyomo was rejected **as the compile backend** — the A06 bridge is a separate
  numerical adapter over `CompiledProblem`, not a second hand-written model (plan L271, blueprint §10).
- K03's dR/dt construction (R-010); finite differences are test oracles only, never the production derivative.
- Regularity screen semantics (R-016, R-084) for square simulation; blueprint §8.1: optimization must not reuse that
  square rank test on decision variables.
- `validate(task="optimization")` typed unsupported until an optimizer exists behind it (R-129) — M03 decides when
  that flips and what evidence flips it.
- Order R-153: M03 runs alongside M01/M06; M02 → M04 is the critical path. The trust-region adapter (Pyomo
  `ExternalFunction` route) is **M05's**, not yours; do not design it beyond what M03's interfaces must leave room for.
- Frank approved ADR 0019 Amendment 3 (M06) on 2026-10-08.

## 6. Genuinely open — decide these

1. How parameters are declared and differentiated: which pinned inputs are "parameters" for a study; how Fₚ is
   produced (separate CasADi function keyed by the same structural identity? capability field?), and the identity of a
   sensitivity result.
2. "Regular root" for sensitivity: the qualification (conditioning estimate from the existing factorization, branch /
   phase-regime stability, active bounds, saturation band of ADR 0012) and the typed refusal vocabulary.
3. Forward vs adjoint: when each is used; the consistency identity the tests check (e.g. λᵀ(Fₓ xₚ) = −λᵀFₚ, adjoint vs
   forward on the same output functional to a registered tolerance); the finite-difference oracle and its step policy.
4. Sweep semantics: warm-start chaining vs independent solves, failure retention (a failed point is a result, not a
   gap), and what a sweep may claim.
5. The estimation example: which flowsheet (SYN-001 is the natural host; justify), synthetic data generation with a
   registered seed and noise model (self-generated data is fine for a *numerical* verification of estimation, but say
   so: it is not empirical validation), the identifiable fit and the unidentifiable one (and the operational test —
   e.g. rank/singular values of the scaled sensitivity matrix, profile or covariance), what is reported.
6. NLP adapter: reduced vs full space for M03's example; the Hessian policy (the capability is `absent`; blueprint A06:
   "explicitly configure a supported approximation" — e.g. Ipopt limited-memory quasi-Newton, recorded as such);
   scaling; KKT/termination recording; multistart evidence; "verified constraints" — the independent post-solve check
   at the optimum (reuse K04's verifier on the converged flowsheet?). And the readiness flip for D16/R-129.
7. The [A10] acceptance criterion for an Ipopt distribution (what licence/METIS/notice findings are acceptable, which
   linear solver), and the fallback if none passes.
8. Schemas: `Study`, `ExperimentRequest/Result`, `OptimizationReport` are planned names (plan L106) — specify what
   M03 needs, minimal and additive; the schema `$id` move (R-149, deferred) may ride on the first schema change if
   cheap; M01 and M06 may also touch schemas — coordinate by staying additive.

## 7. Already tried and rejected (measured)

- P02 matched spikes: Pyomo/PyNumero/ASL route ~2.5× slower per Newton iteration at the boundary and harder to
  install (R-003) — as a *compile backend*. That finding does not by itself bar the A06 bridge; say how the bridge's
  cost is bounded.
- CasADi bundled Ipopt: available, rejected on distribution grounds (ADR 0006 D1.5) — not a technical failure.

## 8. How the answer will be verified

The gate `./scripts/check.sh` (ruff, ruff format, mypy strict, pytest; ~6880 tests on main, green). Derivative test
patterns to reuse: `tests/test_k03_tear.py` (152 FD of the traversal, 165 oracle refusal, 180 affine-ray identity),
`tests/test_k01_compiler.py` (241 fourth-order FD, 254 transpose, 267 Hessian absent), singular refusal
`tests/test_k04_regularity.py` (152, 338), `tests/test_k03_linear.py:128`. A `verdict` agent will later judge W24's
M03 part against your assertions, so every assertion must be decidable from a recorded number.

## 9. Deliverable

On `wp/M03`: `docs/derivations/M03-*.md` (derivation + test specification with numbered assertions, tolerances and
their justification), ADR(s) under `docs/adr/` (next free number — check the directory on main **and** note that
`wp/M06` holds 0030 and M01 is choosing numbers concurrently starting at 0026; take 0031 onward to avoid
collisions), decision-register entries (take **R-180 onward**: M01 holds R-154…R-169, M06 holds R-170…R-175),
machine-readable reference values (JSON under `benchmarks/m03/`, generated by a committed mpmath/independent
generator), and a "Work orders" section: the build-lane steps in dependency order, each with its acceptance
assertions, marked bounded/Opus, including the [A10] Ipopt audit as its own work order. A "Needs Frank" section for
anything that is genuinely his (e.g. accepting an Ipopt distribution's licence terms), each with your default.

## 10. Out of scope

The trust-region framework and Pyomo `ExternalFunction` composition (M05); surrogates and conformal UQ (M04); the
reactor and its boundary (M01/M02); topology synthesis; TEA/LCA; Bayesian/multi-fidelity experiment design; any
change to the K03 solver's numerics or the K04 verifier's semantics.
