# Fable brief — T02: recycle convergence, EO regions, and cross-unit specifications

**To:** `fable-specifier`
**From:** the Opus session
**Date:** 2026-09-24
**Deliverables:** `docs/derivations/T02-recycle-spec.md`, `benchmarks/t02/reference_values.yaml`
with a generator under `docs/derivations/scripts/` (the T01 pattern: `--check`, `--emit`, no
`process_runtime` import), and — **only if you rule that the frozen `SolvePlan` must change** —
`docs/adr/0009-<name>.md` (0009 is the next free ADR number)
**Plan row:** §4.2 T02 — "acyclic execution, safeguarded Anderson recycle, coupled sparse EO
blocks, cross-unit specification promotion"
**Acceptance (plan):** "Analytic/high-gain loops; acceleration restart; EO vs tear agreement;
duty-to-downstream-T spec; no nested SM controls"
**Package-specific (plan §4.2):** "the duty-to-downstream-temperature specification must produce a
SolvePlan whose EO region lists the heater, every intervening unit, and the specification
equation, and must fail with a capability error — not a nested loop — if any unit in the region
lacks EO derivatives."

---

## 1. The question

**How does a flowsheet get solved when it is more than one tear — which parts run causally, which
recycles are converged by substitution with acceleration, which regions are solved
equation-oriented, and what does the plan that records all of this look like?**

Seven things I need decided.

1. **The execution plan.** T01 now produces, for any closed declaration, the block-triangular
   form, the process loops and a chosen tear per loop. What is the rule that turns that into an
   ordered plan of *acyclic unit evaluations*, *tear loops* and *EO regions*? And how is it
   recorded: `SolvePlan` is frozen (plan §2.2) and K03-shaped — `tear_variable_ids`,
   `inner_row_ids`, one tear, `additionalProperties: false`. Extend it by ADR, or introduce a new
   type that holds per-region `SolvePlan`s? Your call; either way the frozen-schema rule means it
   is an ADR if it touches `SolvePlan`.
2. **The recycle solver's policy.** Blueprint §7.2: "Start with damped substitution and safeguarded
   Anderson acceleration. Record depth, regularization, restart, and coefficient safeguards …
   Detect oscillation, stagnation, and invalid states; merge a troublesome recycle into an EO
   block when supported." I need every one of those as a registered policy: depth `m`, the
   regularization of the least-squares problem, the damping, the acceptance test and its merit,
   the restart triggers, the coefficient bound, how an invalid trial state is handled (K03's rule
   is "shortened, not clipped and not retried" — does it carry over?), the oscillation and
   stagnation detectors, and the rule for giving up on substitution and merging the loop into an
   EO block.
3. **Anderson versus K03's Newton on the tear.** K03 already solves SYN-001's tear with damped
   Newton on `R(t)`, using the exact tear derivative from a Schur complement of the 44 × 44 inner
   EO block. That is not substitution. When is a tear loop converged by Anderson and when by
   Newton on the tear? What decides — derivative availability (every SYN-001 unit has exact EO
   derivatives), a policy, a measured contraction estimate?
4. **Registered analytic recycles.** SYN-001 is a weak test of an accelerator (§3.1–§3.2). I need
   closed-form cases for: high gain; oscillation (negative eigenvalue); substitution diverging
   (`ρ > 1`) but Anderson or Newton recovering; a non-normal map where restart matters; a nested
   loop / multi-edge feedback set (T01 hands these to T02, §3.5). With *what can be asserted*:
   Anderson's iterates are an algorithm's output, not a closed form, so tell me which statements
   are falsifiable — for a linear map, Anderson with depth `m ≥ n` and no damping is equivalent to
   GMRES and terminates in at most `n + 1` iterations in exact arithmetic; is that the kind of
   assertion you want registered, and with what floating-point allowance?
5. **EO versus tear agreement.** The plan's acceptance line. What is solved EO — the whole retained
   47 × 47 SYN-001 system in one Newton, presumably — what is compared against K03's tear
   solution, and to what tolerance under ADR 0007's declared numerical policy?
6. **A02: the cross-unit specification.** The region rule (blueprint: "the specification
   equation, free adjusted variable, all intervening dependencies, and any connected recycle SCC
   needed for closure; upstream boundary values can remain fixed from the sequential solve"),
   the degree-of-freedom validation after promotion, and the capability failure when a unit in the
   region lacks EO derivatives. §3.3 has a candidate case inside SYN-001 with an independent
   expectation; confirm it or give me a better one.
7. **The registered assertions**, A-numbered with tolerances, exact vs toleranced, and for each
   where its expectation comes from.

## 2. Why this needs Fable

Every item above is numerical policy or a scientific claim that others are judged against:
globalization and acceleration safeguards (blueprint §7.2, your lane by CLAUDE.md), which solver
a region gets, a schema change to a frozen type, and benchmark registration. The failure mode is
specific and I measured the reason for it: **SYN-001 cannot distinguish a good recycle
accelerator from a bad one** (§3.1–§3.2), so a solver written and tested only against it would
pass its gate while being untested on everything blueprint §13.2's recycle row lists.

## 3. What exists now, measured today

All numbers measured on `main` at `fe0a4de`, gate green at 1411.

### 3.1 SYN-001's recycle map is gentle

Spectrum of `∂G/∂t` at the converged tear, from K03's exact tear derivative (`R = G − t`):

| Case | r | T_flash | ρ(∂G/∂t) | eigenvalues | plain substitution to 1e-10 |
| --- | --- | --- | --- | --- | --- |
| nominal | 0.50 | 360 | **0.500** | 0, 0.353, 0.5 | 34 iterations |
| once-through | 0.00 | 360 | 0 | 0, 0, 0 | no loop |
| high-recycle | 0.95 | 360 | **0.950** | 0, 0.912, 0.95 | 449 iterations |
| all-liquid-310K | 0.50 | 310 | 0.500 | 0.5, 0.5, 0.5 | 34 iterations |
| all-vapor-420K | 0.50 | 420 | 0 | 0, 0, 0 | no loop (dormant recycle) |

`ρ = r` exactly wherever the loop is live. The spectrum is real and non-negative: **there is no
oscillation anywhere in SYN-001**, and the only "high gain" case is 0.95.

### 3.2 K03's Newton converges in one step, for a structural reason

At every live variant K03 takes one Newton step (2 residual calls, 1 Jacobian, 2 linear solves;
154 / 151 / 96 property calls). Measured reason: `R(t)` is linear to `1e-14` relative along the
ray through `t*` — `|R(s·t*) − J(t*)(s−1)t*| / |R| = 1.4e-15` at `s = 0.5` and `2.5e-16` at `s = 2`
— and K03's initializer starts *on* that ray (`t0 = 0.5 t*` nominal, `0.05 t*` high recycle).
Off the ray the map is genuinely nonlinear: `|J(t0) − J(t*)| / |J(t*)| = 2.8e-2` (nominal), `0.21`
(high recycle), `0` (all-liquid, where it is linear everywhere).

So SYN-001 exercises almost none of an accelerator's nonlinear behaviour, and K03's one-step
convergence is a property of the initializer as much as of the solver.

### 3.3 A02 is expressible inside SYN-001, with an independent expectation

In SYN-001 the flash is isothermal, so a heater-duty specification cannot target a downstream
*temperature* directly: the rows reading `S3.T` are the heater's own and `FLASH-duty`, and nothing
else. But the cross-unit shape is there. **Free the heater outlet temperature (drop
`HEAT-T`) and specify the flash duty (`SPEC:SPEC-flash-duty` over `U-FLASH.Q`).** Measured through
T01:

- the declaration is `STRUCTURALLY_CLOSED`, counts `{47, 49, 47, 2}`;
- the BTF moves `S3.T` into the heater's lifted-split block, which grows from 8 to 9 rows by
  taking `FLASH-duty` — the heater and the downstream energy balance solved together, which is
  A02's EO region; the specification row is its own singleton upstream of it;
- the tear is still `S6`, the signature still `(U-FLASH,)`.

And it has an answer that does not come from the solver being tested. Solving K03 at a sweep of
heater temperatures:

| T_heater (K) | Q_heater (W) | Q_flash (W) | sum |
| --- | --- | --- | --- |
| 340 | 8 721.618138 | 47 616.451308 | 56 338.069446 |
| 350 | 13 360.809069 | 42 977.260378 | 56 338.069447 |
| 355 | 31 656.963378 | 24 681.106069 | 56 338.069447 |
| 360 | 56 338.069447 | **0.000000** | 56 338.069447 |
| 365 | 82 449.679507 | −26 111.610060 | 56 338.069447 |

`Q_heater + Q_flash` is invariant (the overall energy balance from feed to flash products at
360 K), and `Q_flash = 0` exactly at `T_heater = T_flash = 360 K`. So `Q_flash = 0` has a
closed-form answer; a non-zero `Q_flash` puts `S3.T` inside the two-phase band, where the duty
curve is steep (factor 2.4 between 350 and 355 K) and the heater's phase regime is inside the EO
block — which touches the attempt signature (T03 owns the general rule; K03 §9 is interim).

This is a *duty-to-downstream-duty* specification. The plan's wording says "downstream-T". A
literal downstream temperature needs an adiabatic unit downstream of the heater, which SYN-001
does not have (T05 adds a PH flash and a valve). Rule on whether the SYN-001 case discharges the
plan's A02 test, or whether T02 must register a new small flowsheet.

### 3.4 What exists in code

| Path | What it is |
| --- | --- |
| `numerics/newton.py` | Damped Newton with bound-aware line search, K03 §5; generic `Problem`, tested on `NUM-02-linear-recycle` (`R = f + r t − t`, `f = (1,1,1)`, a scalar gain, no oscillation) |
| `numerics/linear.py` | ADR 0004's single SuperLU call with recorded evidence |
| `orchestrator/tear.py` | `Syn001TearProblem`: `R(t)`, the Schur-complement tear derivative, `solve_tear` — **SYN-001-specific**, three-variable tear read by K03, now derivable from T01 |
| `orchestrator/attempts.py` | K03's phase-attempt controller; `SIGNATURE_UNITS = ("U-FLASH",)` hard-coded, derived by T01 |
| `models/syn001/flowsheet.py` | `traverse(recycle)`: the causal sequential-modular pass, unit by unit, giving `G(t)` |
| `graph/` (T01) | Declaration trace, DM, certificates, BTF, process loops, tear rule, attempt-signature rule; `multi_edge_feedback_set` reported `unsupported` |
| `application/binding.py` | Binds registered SYN-001 revisions only; `Unbound` with three kinds (R-022) |
| ModelManifest `derivatives` | Per-model derivative declaration, `method: unavailable` is an honest answer — the hook for A02's capability failure |

There is **no** substitution solver, no Anderson, no general execution order, no EO solve of a
region other than K03's inner block, and no plan type that holds more than one tear.

### 3.5 Inherited from T01 (`docs/reviews/T01-review.md` §6)

- A loop no single edge breaks is `multi_edge_feedback_set` and is T02's to sequence.
- The structural report is in every run bundle; T02's plan should cite its BTF and tear rather
  than recompute them.
- Every declared specification value must reach the declaration (M2); the recorder mechanism in
  `binding.py` discovers which parameter a pinned row reads.
- Matching and block lookups are quadratic — fine at a few hundred variables; measure before a
  large flowsheet.

## 4. What I propose, for you to confirm or overturn

**4.1 Plan shape.** A new `ExecutionPlan` holding an ordered list of steps — `evaluate(unit)`,
`converge(loop, method, SolvePlan)`, `solve_eo(region, SolvePlan)` — each carrying a K03-shaped
`SolvePlan` for its region, so `SolvePlan` itself is untouched and no ADR is needed. The cost is a
new schema (additive, which plan §2.1 allows).

**4.2 Solver choice for a loop.** Newton on the tear when every unit in the loop declares exact EO
derivatives (as K03 does now); Anderson on the substitution map when any does not; merge into EO
when Anderson fails its safeguards and derivatives exist. My worry: that makes Anderson reachable
only by a unit without derivatives, and every SYN-001 unit has them — so the registered analytic
cases would be the only thing exercising it.

**4.3 Anderson defaults**, as a starting point only: depth 5, Tikhonov regularization scaled to
the difference matrix's largest singular value, restart when the difference matrix's condition
estimate exceeds a threshold or the scaled residual grows, coefficient bound on `|α|`, damping 1.

**4.4 A02 case.** §3.3's SYN-001 variant, with `Q_flash = 0` (closed form: `T_heater = 360 K`,
`Q_heater = 56 338.069447 W`) and one non-zero value inside the two-phase band.

## 5. Already decided, not open

- Blueprint §7.2 and [A02] as quoted above, including **no nested SM secant/control loops** in
  v0.1: a missing capability is a capability failure, never an invented loop.
- The frozen interfaces and schemas (plan §2.1/§2.2): a change to `SolvePlan` is an ADR.
- K03's specification in force: damped Newton, the attempt controller, ADR 0004's SuperLU options,
  the budgets, "a small step is never evidence of convergence".
- ADR 0007: R0 structure bit-identical across the registered pair; one numerical policy
  `K04-numerical-policy-v1` for R1/R2 comparisons.
- T01 as merged, R-018 through R-022 in `docs/decision-register.md`: the structural source is the
  declaration; the graph layer is given its names; closure after certified redundancy; a copy is
  a difference; an unanalysed revision is `DRAFT` unless its specifications contradict.
- Wegstein and Aitken are out unless measured benefit justifies them (blueprint §7.2).
- NET-07, the thermally coupled recycle, is T06's (plan §4.2), not T02's.

## 6. Already tried and rejected, with evidence

- **Treating SYN-001 as a recycle test.** §3.1–§3.2: real non-negative spectrum, `ρ = r`, and
  Newton converges in one step because the initializer starts on a ray along which the map is
  linear to `1e-14`. A solver tested only here is untested.
- **A literal duty-to-downstream-temperature case in SYN-001.** Impossible as the flowsheet
  stands: the flash is isothermal, so no downstream temperature depends on the heater (§3.3).
- **Reading structure from the compiled Jacobian.** Register R-018; do not reintroduce it for the
  execution plan.

## 7. How the answer will be verified

The gate on both CI architectures; an evidence manifest generated by measurement, one check per
A-number; your reference generator with `--check`; the G05 identity job, into which the execution
plan's R0 projection should go (as T01's structural report did). Correctness fixtures need an
analytic or independent expectation — for T02 that means the closed-form analytic loops, K03's
tear solution as the independent comparison for EO, and §3.3's energy-balance invariant.

## 8. Deliverable

`docs/derivations/T02-recycle-spec.md` in the shape of your K03 and T01 specifications: numbered
sections; the execution-plan rule and its record; the recycle policy with every safeguard as a
registered value; the solver-choice rule; the A02 region rule, its DOF check and its capability
failure; the registered cases with closed forms; numbered falsifiable assertions with tolerances;
what the specification does not establish; open questions with defaults. Plus
`benchmarks/t02/reference_values.yaml` and its generator. Plus ADR 0009 only if `SolvePlan`
changes.

Rule on each of §4's four proposals by name, as you did for T01.

## 9. Escalate to Frank rather than choosing

If a point turns on something only Frank can settle — a scientific requirement that would have to
change (the plan's "downstream-T" wording may be one), scope, or a public promise — write it under
`FOR FRANK` with options and a recommended default, and continue.

## 10. Out of scope

T03's general phase-attempt controller and ADR 0005 (say what T02 needs from it and stop); PTC,
homotopy and SER (T04); new unit models (T05); NET-07 and reference comparisons (T06); jobs and
bindings (T07); the general revision compiler from manifests. Production code.
