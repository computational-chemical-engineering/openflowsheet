# Brief — M05 design: the trust-region integration spike and the fixed-topology refinement loop

**To:** `architect`. **From:** the session (build lane), 2026-10-08. **Branch for the note:** `wp/M05`, from `main`.
M03, M04 and M02 are not merged; read them with `git show wp/M0x:<path>`.

**Plan row (v1.2 §4.4, L267, binding):** *M05 — M03, M04: distinct trust-region integration spike and
fixed-topology refinement loop.* *Acceptance:* ExternalFunction/glass-box composition with source maps;
parent-model checks at candidate optima; true-model call accounting; constraints and limitations retained.
- Lane: Design / Build (NUM/MOD). Gate **W24** (M05's half): "Fixed-topology optimization, eligible trust-region
  example and parent-model checks".
- Requirements:
  - **A06**: "Gray-box NLP and trust-region compositions tested separately". M03 built the gray-box NLP half.
  - **D13**: "Tested framework path, assumptions, finite-budget truth checks". Blueprint §1 D13: "Use a tested
    trust-region framework for eligible smooth gray-box problems. State theorem assumptions and finite-budget
    limitations. Do not promise convergence for arbitrary CFD, switches, or discrete synthesis."
- M05 is on the critical path; M07, the reference journey, follows (R-153).

## 1. The question

Write M05's design note, with work orders and decidable gates, plus the ADR(s) any interface, dependency or semantics
change needs. It must answer three things:
- **(a) The trust-region spike.** How the documented Pyomo trust-region framework is composed with OpenFlowsheet
  models, and on which eligible smooth gray-box example. If the framework cannot consume the intended mixed model, the
  note documents the failing composition and an ADR-backed, tested alternative.
- **(b) The fixed-topology refinement loop on C1.** The decision variables and constraints; how the reactor enters
  (the parent through M02's coupling, M04's surrogate, or both); the parent-model checks at candidates; refinement
  iterations; true-model call accounting.
- **(c) What W24's M05 half may claim, and what it may not.**

## 2. Why the architect

This is solver architecture and composition: a third-party optimizer framework, a compiled glass-box projection
with source maps, and an expensive, out-of-process, derivative-free black box, all within budgets. The plan and
blueprint say plainly that it may not compose, and that the fallback needs an ADR. A wrong choice costs the
v0.2 journey (M07).

## 3. Normative text (verbatim)

- **Plan L271:** "The Pyomo general NLP adapter and trust-region adapter are separate deliverables. A cyipopt success
  does not complete M05. Compile any needed Pyomo glass-box projection from canonical equations; do not maintain a
  second hand-authored reactor/flowsheet. If the chosen framework cannot consume the intended mixed model, document
  the failing composition and implement an ADR-backed tested alternative before claiming that gate."
- **Plan L593 (v0.2 scope):** "a tested trust-region adapter for one eligible smooth gray-box example, with
  assumptions and costs reported".
- **Blueprint §10:**
  - **L437:** "For eligible expensive smooth gray-box models, default to a tested trust-region framework through the
    Pyomo bridge before writing a new optimizer. The documented framework imposes differentiability assumptions and
    uses consistency corrections; arbitrary surrogate retraining does not preserve its convergence theory."
  - **L441:** "The documented Pyomo trust-region framework instead identifies black-box calls through **Pyomo
    `ExternalFunction`** and builds local surrogate subproblems; it is not automatically compatible with an opaque
    `ExternalGreyBoxModel`. Its separate adapter must expose expensive-model inputs/outputs and a framework-supported
    glass-box structure, generated from the canonical model where needed, with source maps and equivalence tests. This
    is a compiled projection, not a separately authored physical model. Demonstrate that exact composition in the
    v0.2 spike. If unsupported, use an explicit ADR and a tested alternative framework; do not claim trust-region
    guarantees merely because the generic cyipopt bridge solves an NLP."
  - **L443:** "The adapter must expose truth-model evaluation, reliable gradients or an explicitly qualified
    alternative, local model construction, trust-region/filter state, rejected steps, and cost. Pin the implementation
    and its assumptions. Finite-budget noisy experiments, phase switches, discrete topology changes, and unsupported
    derivative regimes receive empirical outcomes without an inherited stationarity guarantee."
  - **§9.3, L423:** "Begin with sensitivities and direct discrepancy checks. For constraints close to active, require
    parent-model evaluation or a justified error bound with engineering margin. Cheap screening may rank candidates;
    final decisions must state which models and uncertainties were actually checked."
  - **§9.3, L427:** "Freeze the surrogate during a solve/optimization subproblem. Refine in a new study iteration,
    rerun validation, promote a new version, and re-solve. Stop on predefined decision tolerances and evidence, or
    budget exhaustion. Budget exhaustion is not decision stability."

## 4. Current state (recon facts, 2026-10-08)

**The Pyomo trust-region framework is present in the audited M03 NLP environment.**
- **Location.** Pyomo 6.10.1 `pyomo/contrib/trustregion/`, in the env at
  `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/m03-ipopt/nlp`,
  built by `scripts/build-m03-ipopt-env.sh` on `wp/M03`.
- **Entry points.**
  - `TRF.py:591` `@SolverFactory.register('trustregion')` `class TrustRegionSolver`, citing Eason 2016/2018, Yoshio
    2020 and Biegler.
  - `solve(self, model, degrees_of_freedom_variables, ext_fcn_surrogate_map_rule=None, **kwds)` (:632).
  - The driver `trust_region_method(model, decision_variables, ext_fcn_surrogate_map_rule, config)` (:39). Its basis
    function b(w) defaults to 0.
  - Filter (default) and funnel strategies.
- **Black boxes and the subproblem solver.**
  - `interface.py:94` `TRFInterface` clones the model, replaces each `ExternalFunction` with a holder variable
    (`EFReplacement`, `replaceExternalFunctionsWithVariables` :156), and solves subproblems with
    `SolverFactory(config.solver)`, default `'ipopt'`. That is the **ASL `ipopt` executable**, not cyipopt.
  - Pyomo core `ExternalFunction(function=…, gradient=…, hessian=…, fgh=…)` with a Python callback becomes
    `PythonCallbackFunction` and needs no ASL library.
  - The contrib's tests skip without an `ipopt` executable.
- **Audit gap.** The env contains `bin/ipopt`. The audit inventory `benchmarks/m03/ipopt-inventory-x86_64.json`
  (`wp/M03`) lists `libipopt.so.3.14.20` and the cyipopt wrapper, but **not** `bin/ipopt`. Using the executable needs an
  [A10] audit extension.

**M03's gray-box NLP bridge, built on `wp/M03`; its ADRs 0031 and 0032 are pending Frank's licence answer N1.**
- `studies/nlp/greybox.py`: `FullSpaceGreyBox(ExternalGreyBoxModel)` over the parametric twin. Its Jacobian is the
  twin's exact [F_x F_p] (ADR 0032 D1).
- Hessian: absent; L-BFGS configured; an exact Hessian is refused (D2, R-187).
- `verify_candidate` checks V1–V6 on the re-solved certified simulation; `classify_starts` applies the status
  precedence KKT_POINT_VERIFIED > NOT_VERIFIED > INFEASIBLE_REPORTED > SOLVER_FAILED (R-212).
- `optimization_readiness` has 8 reason codes, and `optimize()` returns a typed UNSUPPORTED (R-191).
- Review note F6: the Jacobian is two CasADi calls, so property callbacks run twice. "Cache the twin per (spec,
  parameter subset) when M05 needs the speed."
- R-253's watch-for: before study or optimization records become replay-comparable (M05), the fixture comparison rules
  move into `run/compare` under an ADR 0025 amendment.
- ADR 0031 C3: sensitivities on revision-built (EO-path) flowsheets, PH-type splits, zero-flow splits and the kinetic
  CSTR are refused until a later ADR.

**M04's surrogate, spec on `wp/M04`, build running.**
- **The unit.** `c1.reactor_surrogate` is M02's embedded unit with (X̂, ΔT̂) replaced by a frozen quadratic in 7 scaled
  inputs: T_in, P_in, H₂/N₂, y_NH₃, y_Ar, y_CH₄, per-tube flow. It sits inside the box `m04-c1-box7-v1`:
  - T 653.15–693.15 K, P 9–10 MPa;
  - H₂/N₂ 2.5–3.0, y_NH₃ 0.02–0.04, y_Ar 0.01–0.03, y_CH₄ 0.01–0.04;
  - F 0.0057–0.0086 mol/s.
- **Derivatives and solve route.** Its derivative is analytic. It solves on `revision_eo`, with no experiments.
- **Promotion** is an integer-exact split-conformal verdict (ADR 0036). Promotion and rollback are checked commits
  (ADR 0037).
- **ADR 0037 D7:** "M04 delivers the unit, its evidence, promotion and rollback. Whether and how a trust region uses
  the surrogate, and every parent-model check at a candidate (`targeted_check`), are M05's."
- **Spec §8.5:** M05 decides whether the trust region uses the surrogate "as the reduced model, as a warm start for the
  coupling's w, or not at all". M05 also owns `targeted_check` and refinement beyond §5.5.
- **Spec §7.4.** The surrogate may not claim coverage at a flowsheet's solved operating point or at an optimizer's
  candidate; that needs a parent evaluation labelled `targeted_check`.
- **M04 N6 default, pending Frank:** if the real surrogate is NOT_PROMOTABLE, M05 proceeds with the parent.

**M02's coupled reactor, on `wp/M02`, WO-7/8 running.**
- **ADR 0034 D1–D4.** The compiled reactor unit pins X̂ and ΔT̂; extent and offset rows are analytic.
  - Route `revision_coupled`: an outer Broyden on w = (X̂, ΔT̂), one experiment per iteration at the inner solution's
    exact reactor inlet, at most 15 iterations.
  - Converged iff |ξ_E − X̂ n_N₂| ≤ 1e-5 n_tot and |ΔT err| ≤ 1e-2 K.
  - **No sensitivity through the inner problem** (`external_map_unavailable`).
- **The reactor is an out-of-process child per experiment** (ADR 0033). It costs **25–45 s** per cold evaluation; the
  group's KPI certificate takes 12–35 s of that and stays (R-250).
- **Cost and parallelism.** A coupled solve takes about 2–6 min. Distinct-key experiments may run concurrently
  without changing a bit, with no more workers than physical cores (R-250).
- **Identity and caching.** Experiment identity is exact and process-level (D4). The cache serves deterministic
  outcomes only. Each result carries `cache_hit` and each attempt is one execution, which is the basis of true-model
  call accounting.
- **Model exceptions.** `model_exception` is a deterministic, cached refusal; the coupling backtracks on it (R-251).
- **The C1 loop case `C1-LOOP-M02-v1`** (design note §8.1):
  - makeup 1.0 mol/s at 300 K and 10⁷ Pa;
  - mixer → `c1.tp_heater` to 673.15 K → reactor with N_tubes = 1000 → `c1.tp_flash` at 253.15 K;
  - purge 0.02; zero ΔP.

  Its JSON is not built yet.

**C1 decision candidates, as the documents state them.**
- ADR 0022 D6 and the dossier §9: "the reactor inlet temperature … a kinetic reactor has an interior optimum …; the
  alternative is the purge fraction."
- The separator temperature and the recycle ratio are not declared decisions.
- R-169: M05 must treat `extrapolated` results as a constraint or a stated limit.

**Dependencies.**
- The project env is numpy, scipy and casadi only. Pyomo and cyipopt live only in the audited env, behind the `nlp`
  extra, pending N1.
- R-003 rejected Pyomo as the *compile backend*. A Pyomo glass-box projection compiled from the canonical model is a
  derived view, and must not become a second backend.
- The property provider `pr-c1-v1` is numpy code, not Pyomo-expressible algebra.

## 5. Constraints and invariants

- Identities do not move (SYN-001, K05, T06, M01's registered values, M02's experiment identity). Everything is
  additive.
- No second hand-authored model. Any Pyomo structure is compiled from the canonical model, with source maps and
  equivalence tests (plan L271).
- No CasADi `nlpsol` and no METIS-closure object (ADR 0006 D1.5). Any new binary, such as the `ipopt` executable, needs
  an [A10] audit extension.
- Optimizer termination is not feasibility, and local stationarity is not optimality. Candidates are judged on the
  re-solved certified simulation (R-188). True domain restrictions, never penalties (R-189).
- The surrogate is frozen within a subproblem; refinement is a new study iteration (§9.3).
- The default gate never runs the reactor or Ipopt. Those are opt-in, with committed records checked by default.
- True-model calls are expensive: 25–45 s each, parallel across distinct keys. Every budget is stated in cold
  experiments and in wall time.

## 6. Already decided — do not reopen

- **M03's gray-box bridge** (ADR 0032): full space over the twin, L-BFGS, the V1–V6 verifier, and the status
  precedence. M05 is the *separate* trust-region bridge (A06).
- **M02's coupling and records** (ADRs 0033–0035, R-220…R-252).
- **M04's surrogate, its evidence, promotion and rollback** (ADRs 0036, 0037).
- **C1 and its pin**, the boundary (ADR 0027), and the domains.
- **The release sequence:** `0.2.0a1` after M02 `tested`, with its gate being specified on `wp/V02-alpha-gate`.

## 7. Genuinely open — decide these

1. **The eligible example for the spike.**
   - Does the Pyomo TRF compose with our models at all? Through an `ExternalFunction` wrapping what: the reactor
     experiment (X, ΔT)(inlet), the surrogate, or a unit on SYN-001?
   - Which glass-box part is compiled to Pyomo, and how: a code generator from `ProblemSpec`/canonical rows, or Pyomo
     `ExternalFunction`s for property calls?
   - Does a property provider's numpy code fit TRF's assumptions at all?
   - Possibly a small, smooth, honestly eligible example demonstrates the composition, and the C1 loop uses something
     else. Decide, and justify against D13's "eligible smooth gray-box".
2. **The fallback,** if TRF cannot consume the mixed model: an ADR-backed alternative (for example a
   trust-region/filter loop of our own over M03's adapter, M04's surrogate and parent checks), with what it may and may
   not claim.
3. **The C1 refinement loop.**
   - Decisions: reactor inlet T, purge fraction, others?
   - The objective, which the documents do not register; propose one with its justification.
   - Constraints, including the domains and `extrapolated` as a constraint.
   - How the reactor enters: the surrogate via `revision_eo` with M03-style sensitivities (but ADR 0031 C3), or the
     parent via `revision_coupled` (no sensitivities).
   - Parent checks at candidates (`targeted_check`), and the refinement iterations, interfacing with M04's further
     iterations.
   - Stopping on decision tolerances, not on the budget.
4. **True-model call accounting:** cold vs cached, per candidate and per iteration, and its records.
5. **What the TRF's Ipopt subproblem options must be** relative to ADR 0032 D2 (L-BFGS) and the `nlp` extra; and the
   `ipopt` executable's audit extension.
6. **Records and schemas.** M03's `optimization-report` and `study` schemas extended, or new ones. Replay class (R3 for
   experiment-backed). R-253's watch-for (move comparison rules into `run/compare`, ADR 0025 amendment) if M05 records
   become replay-comparable.
7. **Dependency on Frank's answers:** N1 (the `nlp` extra; without it M05's Pyomo route is BLOCKED) and M04 N6. What
   M05 delivers in each branch of those answers.

## 8. Already tried, measured or rejected

- **Pyomo/PyNumero as the compile backend** was rejected (R-003); only a derived projection is allowed.
- **CasADi's bundled Ipopt** is forbidden (ADR 0006 D1.5).
- **The reactor's cost:** 25–45 s per evaluation, not 9 s (R-250). The certificate is not removable.
- **No sensitivity through the coupled inner problem** (ADR 0034 D4). EO-path sensitivities are refused (ADR 0031 C3).

## 9. Verification

- The gate `./scripts/check.sh`, about 7700 tests.
- Opt-in `nlp` and `pymrm` gates, with committed records checked by default.
- W24, judged by a `verdict` agent from your gate table.
- One `reviewer` pass on the build.

## 10. Deliverable

On `wp/M05`, from main:
- `docs/design/M05-trust-region.md`, with these sections: decisions at a glance; the spike and its example; the
  composition and source maps; the fallback; the C1 refinement loop; accounting; records; work orders in dependency
  order, marked Opus or bounded, each with its acceptance; gates G1…Gn, each decidable from a recorded number; risks;
  and what M05 does not establish.
- ADR(s): **0038 onward** (0028 and 0029 are free but reserved: 0028 is the alpha gate's).
- Register entries: **R-260 onward**.
- A "Needs Frank" section, each item with its default.

Write no production code. A throwaway probe in the audited env, to establish whether TRF composes with a Python
`ExternalFunction` and with what subproblem solver, is allowed and encouraged. Record it as a probe.

## 11. Out of scope

Topology synthesis; Bayesian or multi-fidelity experiment design; M07's journey report; changes to M02, M03 or M04
semantics (raise conflicts as questions instead).
