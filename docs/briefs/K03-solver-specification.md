# Specification brief — K03: scales, the tear Newton, globalization and phase attempts

**To:** `fable-specifier`
**From:** Opus 5, 2026-09-21
**Branch:** `wp/K03` (nothing implemented yet; K02 merged at `ab330ef`)
**Gate:** `PATH=.venv/bin:$PATH ./scripts/check.sh` — green, **1019 tests**

---

## 1. The question

**How does K03 solve SYN-001, exactly?** Plan §4.2 gives K03 "physical scales before
initialization; damped Newton on analytic and flash recycle residuals; bounded line search and
phase attempts", with acceptance evidence "solve traces, invalid-trial rejection, small-step
stagnation, known root, bad budget, phase-change restart, bound handling". The blueprint fixes the
shape of all of that and none of the numbers. This specification must fix the numbers, the
policies, and the five interface field sets, so that implementation is transcription.

**The single highest-leverage sub-question is §4 below**, on which residual the Newton actually
runs. Everything else is downstream of it.

## 2. Why this needs Fable

Four of the decisions are scientific-numerical policy with no test that would catch a bad choice
until much later: the scaling construction, the globalization rule, the phase-attempt contract,
and the treatment of a structurally rank-deficient system. CLAUDE.md puts "scaling and
globalization policy" and "phase-attempt controller design" in Fable's lane, and plan §4.2's
*Model* column for K03 is **Fable / Opus**. Requirements D01, D03, D06, D09 and A01 all land here.

## 3. What K02 delivered, and its four findings

K02 is complete, `tested`, reviewed. It gives K03 two routes to the same flowsheet.

**(a) A sequential-modular traversal.** `Syn001Flowsheet.traverse(recycle) -> Traversal` runs
feed → mixer → heater → flash → splitter causally and returns
`recycle_residual = G(t) − t` on three component flows. Measured at Fable's 20-digit converged
recycle: worst `|R(t*)|` = **3.6e-15 mol/s** over all five registered variants. It does **not**
solve; no iteration is performed anywhere in K02.

**(b) An equation-oriented `ProblemSpec`.** `Syn001Flowsheet.spec()` assembles **47 variables and
49 rows** with 9 property blocks, compiles on CasADi, and its residual vanishes at the 20-digit
answer to 5.5e-12 worst. Variables are seven streams × (3 flows, T, P), plus the heater's lifted
outlet split (`S3.vap.i`, `S3.liq.i`, `S3.V`, `S3.L`), plus two duties and two flash phase totals.

**Four findings K02 measured and deliberately did not work around. Each is a K03 policy question.**

1. **The registered tear initializer is outside the v0.0 mixer's domain.** Derivation §9 registers
   `recycle_i = r F_i`, and plan §3.2 fixes that stream at the flash temperature. At r = 0.5 that
   is an **equimolar stream at 360 K**, above its 347.44 K bubble point (`sum_zK_fresh` = 1.3837).
   The v0.0 mixer refuses a two-phase inlet, correctly. **A damped Newton started at the
   registered initializer fails on its first residual evaluation.** The K02 reviewer's suggestion
   was to register `t⁰ = G(0)` — the recycle from a zero-tear pass, `= (1−r) t*`, in-domain for
   every r — and to note that the tear map is affine along that ray so an off-ray start is also
   needed. **That is an amendment to your derivation §9 and is yours to make or reject.**

2. **The declared rows over-determine the pressure network by two.** Seven pressure variables carry
   nine declared pressure rows: `FEED-P` fixes one, `MIX-pressure` equates both inlets to the
   outlet, `HEAT-pressure` propagates through a declared zero drop, `FLASH-P` specifies both
   outlets **and its own inlet**, and `SPLIT-P` copies to both outlets. Every row is in a P01
   manifest, so K02 assembled them all. **A square Newton cannot run on 49 rows and 47 variables.**
   K03 needs a registered policy: structural elimination of provably redundant rows, a
   least-squares step, or something else — and blueprint §7.7 is explicit that "regularized
   least-squares steps are numerical recovery, not permission to discard equations".

3. **The lifted equilibrium admits the classical trivial solutions.** `v_i L − K_i l_i V` is
   satisfied identically by every `v_i = 0` and by every `l_i = 0`. Measured at the once-through
   variant's genuinely two-phase heater outlet: the all-liquid split leaves **thirteen of the
   heater's fourteen rows at exactly 0.0**, and a solver free to choose `Q` closes the fourteenth
   at a duty **8237.85 W** below the true one — a complete spurious solution with every residual
   satisfied. No residual can exclude it. Blueprint §6.3 names the remedy in the abstract ("final
   phase admissibility check"); K03 must make it concrete.

4. **The registered recycle is saturated and double precision disagrees with the reference about
   which side it is on.** `sum_i z_i K_i` = **1.0000000000000002**, so the provider classifies the
   stream `TWO_PHASE` with β = 1.3e-17 while the 20-digit reference registers `LIQUID`. Both are
   right at their own precision. K02's units admit a stream as a single phase on an *intensive*
   criterion — the enthalpy gap divided by `dH/dT`, against the registered 1e-6 K — because a
   label check rejects the nominal variant. **K03's phase-attempt controller meets the same
   boundary, where the decision is about which active set to try and that remedy does not
   transfer.**

## 4. The open question I most need decided: which residual does Newton run on?

Plan §4.2's package constraint says, verbatim:

> **K03:** the tear Newton needs dR/dt through the unit chain. Use the assembled sparse Jacobian
> of the reduced tear residual from the selected backend as the primary path; a finite-difference
> tear Jacobian is retained only as a test oracle.

Three readings are open and they lead to very different implementations.

- **(A) Reduce the EO system to the tear.** Solve the 47-variable system for the non-tear
  variables at fixed `t`, and obtain `dR/dt` by block elimination on the assembled Jacobian
  (implicit function theorem). Literal reading of "reduced tear residual". Needs an inner solve
  per outer iteration, and needs finding 2 resolved first.
- **(B) Solve the full EO system directly**, 47 variables at once, with the tear being a
  structural label only. The assembled sparse Jacobian is then used as-is, which is what it is
  for. But G00 says "one numerical tear" and the plan says "tear Newton", so this may not be what
  the plan means.
- **(C) Keep K02's procedural traversal as `G(t)` and get `dR/dt` some other way.** The traversal
  contains an inner bracketed mixer solve and a Rachford–Rice flash, so the backend cannot
  differentiate it symbolically; this is the finite-difference route the plan demotes to a test
  oracle, unless the implicit-function derivative through each unit is supplied.

**My reading, offered so you can correct it rather than guess at it:** (A) is what the sentence
says, (B) is what the assembled Jacobian is actually good for, and the two coincide in exact
arithmetic. I lean (B) with the tear retained as the *initialization* and *diagnostic* structure —
but I am not confident, and G00's "one numerical tear" may be a hard requirement.

## 5. What is already fixed and must not be reopened

- **Scales come from registered physical nominals**, never from an iterate that may be zero
  (ADR 0001 D3.5). Registered: tear component flows **3 mol/s**, temperature **100 K**, pressure
  **1e5 Pa**, duty **1e5 W** (derivation §9). Scales precede initialization acceptance and are
  **frozen within an attempt**; a refresh starts a recorded segment (D06, blueprint §7.3).
- **The scaling algebra** is blueprint §7.3's: `x = x_ref + S_x x̂`, `F̂ = S_F⁻¹ F`,
  `Ĵ = S_F⁻¹ J S_x`. Verification tolerances stay independent of numerical scaling.
- **The linear solve is SciPy SuperLU** through `splu`, with explicit options and recorded linear
  residuals (D03, blueprint §3.1, ADR 0003 D2). No CasADi `Linsol` or `nlpsol` plugin on any
  default path — that is a distribution constraint as well as a numerical one (ADR 0006 D2).
- **The phase set belongs to the local nonlinear attempt and is frozen within it** [A01]: every
  accepted iterate, trial point, residual call, Jacobian call and derivative perturbation in one
  attempt uses one phase signature. A trial that cannot be evaluated in the fixed formulation
  returns a typed domain or `PHASE_UPDATE_REQUIRED` outcome; only the bounded outer controller
  changes the set, and every change closes an attempt and opens a new one.
- **Registered tolerances** (ADR 0001 D6, SYN-001 only): component balance `1e-9 + 1e-8 × 3` mol/s;
  energy `1e-5 + 1e-8 × 1e5` W (= **1.01e-3 W**); T `1e-6` K; P `1e-2` Pa; composition `1e-10`.
  The acceptance rule is blueprint §8.1's `|e_i| ≤ a_i + r_i s_i`, reporting all three.
- **Registered budgets** (`benchmarks/registry.yaml`): 10000 property calls, 50 iterations per
  attempt, 5 attempts. `SYN-001-capped-budget` caps property calls at **20** and must terminate
  with a typed `BUDGET_EXHAUSTED` and **no certificate**.
- **Small steps with large residuals are stagnation, not convergence**; an already valid root need
  not take an additional small step to qualify (blueprint §7.3).
- **Do not call failure to converge `PHYSICALLY_INFEASIBLE`** without independent evidence
  (blueprint §7.7).
- **No time at the evaluation boundary** (ADR 0008 D1). A homotopy parameter and a pseudo-time
  step are orchestration state, not `EvaluationContext` fields.
- **`NUM-02-linear-recycle`** is registered and analytic: `t = f + r t`, `t = f/(1−r)`, giving
  (2,2,2) at r = 0.5 and (20,20,20) at r = 0.95, with no thermodynamics. It exists to isolate
  tear-solver behaviour from the flash.

## 6. Already tried, with measured evidence

- **K02's traversal is correct and is not the bottleneck.** `R(t*)` is 3.6e-15 mol/s at every
  registered variant, and the tear map is *exactly affine along the ray through its fixed point*:
  `R(s t*) = (1 − r)(1 − s) t*`, measured to **1.1e-14** relative over four variants and eight
  scale factors from s = 0 to s = 4, and derived (adding saturated liquid of the flash's own
  composition to a two-phase mixture at the same T and P adds nothing that can vaporize). **A
  consequence worth your attention: plain successive substitution on this tear contracts by
  exactly `(1 − r)` along that ray, so the r-variants do not stress the tear solver the way three
  distinct cases would.** `benchmarks/registry.yaml` already records that the r-variants are one
  recycle case, not three.
- **The EO rows are correct**: the assembled residual vanishes at the 20-digit answer to 5.5e-12
  worst over all five variants, and the compiled and backend-free float routes agree **exactly**.
- **The heater/flash Jacobian is exact and declared-sparse**, with the block chain rule exercised;
  K01 measured 1 value call and 1 Jacobian call per block per assembly.

## 7. What the specification must contain

A document at **`docs/derivations/K03-solver-spec.md`** with numbered, falsifiable assertions in
the style of `docs/derivations/P02-composition-spec.md`, fixing:

1. **The verdict on §4** — which residual Newton runs on, and how `dR/dt` is obtained, with the
   reasoning and what the choice forecloses.
2. **Scale construction**: the exact `S_x` and `S_F` for the SYN-001 system, entry by entry, from
   the registered nominals; the refresh policy; and what happens to a row or column the nominals
   do not name.
3. **The merit function, the damping rule and the line search**: the acceptance criterion, the
   step-length sequence, the minimum step, and the stagnation test that distinguishes a small step
   with a small residual from a small step with a large one.
4. **The rank policy for finding 2**, consistent with blueprint §7.7's prohibition on discarding
   equations as a convenience.
5. **The trivial-root policy for finding 3**: the concrete admissibility test on a converged
   answer, and where it runs.
6. **The phase-attempt contract**: which phase sets exist for SYN-001, the initial choice, the
   `PHASE_UPDATE_REQUIRED` trigger, the restart bound, cycle detection and deterministic
   tie-breaking, and how it handles finding 4's saturated boundary.
7. **Initialization**: the order of blueprint §7.4's sources for this fixture, the accepted
   initializer for the tear given finding 1, and the projection-logging rule.
8. **Termination and outcomes**: the typed outcome vocabulary K03 returns, mapped onto blueprint
   §8.2's minimum taxonomy, and the budget accounting.
9. **The five interface field sets** — `SolvePolicy`, `SolvePlan`, `SolveEvent`, `AttemptContext`,
   `Checkpoint` metadata — as field lists with types and a sentence each on why the field exists.
   These join the plan §2.1 freeze, so a field omitted now costs an ADR later. `AttemptContext`
   must make [A01]'s frozen phase set structural rather than conventional.
10. **The registered test states and expected outcomes** for each of plan §4.2's seven acceptance
    items, so the tests are transcription and not invention.
11. **What the specification does not establish.**

And **`docs/adr/0004-superlu-options.md`**, which plan §4.1 pre-allocates and which is unwritten:
the explicit `scipy.sparse.linalg.splu` options (`permc_spec`, `diag_pivot_thresh`, `relax`,
`panel_size`, `options`), the recorded linear-residual check and its threshold, and the reason for
each choice. ADR 0009 is the next free number for anything else; 0004 is reserved for this.

## 8. Out of scope

- **K04's certificate and regularity screen.** K03 must leave the final unregularized target
  Jacobian and the traces available; judging them is K04's, and blueprint [A08] already fixes the
  recipe.
- Pseudo-transient continuation (T04), general homotopy beyond what SYN-001 needs (T02),
  multi-start and root-completeness studies (T03), rank diagnostics breadth (T06).
- Re-deciding the backend (ADR 0003), the canonicalization (ADR 0002), or any unit model (K02).
- Implementation. Write no production code; the document is what Opus implements against.

## 9. A caution from K02, since the same trap is present here

K02's Fable review found a defect that had survived a 65-mutation sweep: an equilibrium row that
was **never evaluated at a state where it could fail**, because every reference state made it
identically zero. The solver has the same shape of hazard — a globalization rule is only exercised
by a step that needs damping, and a stagnation test only by a run that stagnates. Where you fix a
policy, please also **name the state that makes it bite**, so the tests cannot be satisfied by a
fixture that never exercises it.
