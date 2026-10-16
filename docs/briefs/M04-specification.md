# Brief — M04 specification: the reactor surrogate, Default split-conformal reporting, promotion and rollback

**To:** `specifier` (design lane). **From:** the session (build lane), 2026-10-08. **Branch:** `wp/M04`.

**Plan row (v1.2 §4.4, binding):**
- *M04 — M02: surrogate training, conserved-output representation, hard/empirical domain tests, independent
  calibration/test draws and Default split-conformal reporting.*
- *Acceptance:* frozen splits/transforms; finite-sample rule; coverage/error/gradient/domain metrics; insufficient-data
  outcome; promotion and rollback.
- Lane: Design / Build (MOD/NUM). Gate **W23**: "Surrogate conservation/domain/derivative/default UQ and promotion".
- Requirements:
  - **A07**: "Registered reference distribution, frozen predictor and independent splits".
  - **D12**: "Independent calibration/test and qualified coverage/error evidence".
- M05 (trust region) depends on M03 and M04. M07 (the reference journey) depends on M05. M04 is on the critical
  path (R-153).

## 1. The question

Write M04's authority documents — the derivation, the ADR(s) and the test specification, with numbered falsifiable
assertions and machine-readable reference values — so that the build lane can implement:
- (a) a surrogate of the C1 reactor that predicts a conserved-coordinate representation;
- (b) the hard and empirical domain tests;
- (c) the registered design of experiments: the reference distribution, the training, calibration and test sample
  counts, the seed, and the insufficient-evidence outcome;
- (d) Default split-conformal reporting, with its finite-sample rule and its qualifications;
- (e) surrogate promotion and rollback through M02's replacement machinery;
- (f) the `SurrogateManifest` and `ModelEvidence` records.

A `verdict` agent must later be able to judge W23 from the evidence alone.

## 2. Why the design lane

What "coverage" means, which reference distribution it is marginal over, the finite-sample rule, the domain criteria,
and what a promoted surrogate may claim are all statistical semantics that every later package inherits. M05's
trust-region framework and M07's journey consume the surrogate, and the blueprint is explicit that a careless reading
over-claims: coverage is not pointwise, not at optimizer-selected points, and not robust to shift. Registering the
sample counts before the parent model runs is itself a design-lane act (plan L273).

## 3. Normative text, verbatim (read the sources too)

- **Plan L273, "M04 starting implementation":** "use a small smooth quadratic response surface in scaled reactor
  inputs, preferably predicting reaction extents or another conserved-coordinate representation. Fit with a
  numerically stable least-squares method and validate independently before increasing model complexity. Record the
  training domain and enforce nonnegative species/extent constraints where applicable; a differentiable fit is not
  automatically a physically valid model. Define scalar or explicitly joint conformal scores, calibrate only after
  predictor/transform selection, and retain interval-width limits alongside coverage. Register training,
  calibration, and test sample counts before running the parent model, based on the approved experiment budget and
  the statistical criterion in v3.1. If the budget is insufficient, return insufficient evidence; do not reuse
  training points as calibration data. More complex surrogates are introduced only to resolve a measured error or
  derivative limitation."
- **Blueprint** (`docs/blueprint-v3.1.md`):
  - L38 D12: "Separate model discrepancy, numerical error, predictive uncertainty, and domain membership.
    Split-conformal is the Default reporting baseline with independent calibration/test draws from a registered
    reference distribution; alternatives require an ADR. Coverage qualifications remain mandatory."
  - L405–407 §9.1:
    - failed experiments stay in the dataset with failure labels and get no fabricated outputs;
    - DOE, training, calibration and test splits, transforms, seeds and parent lineage are immutable artifacts;
    - surrogates preserve conservation via extents or reduced coordinates;
    - a corrective projection is explicit and its derivative is accounted for.
  - L409–411 §9.2: hard admissibility comes from physics and the parent model. Empirical domain tests work in scaled
    coordinates (distances, density, documented criteria). "Convex-hull membership alone does not establish accuracy
    in a sparsely sampled high-dimensional interior."
  - L413 [A07]: split-conformal coverage is marginal under exchangeability; it is not pointwise, not
    optimizer-selected, and not robust to arbitrary shift.
  - L415:
    - freeze the predictor, transforms and score before calibration;
    - draw disjoint calibration and test sets i.i.d. from a registered process-relevant reference distribution;
    - adaptive DOE samples are not automatically exchangeable, and grids or Latin hypercubes are not labelled i.i.d.;
    - fresh random draws are the reporting baseline, and targeted optimum checks are labelled separately;
    - do not tune on the final test set;
    - if calibration is unaffordable, the outcome is INSUFFICIENT_EVIDENCE.
  - L417: for scalar scores and n calibration points, record the finite-sample quantile rule (ceiling correction and
    insufficient-sample behaviour). Multi-output claims need a joint construction or must be labelled marginal.
  - L419 promotion:
    - a predeclared sample-size plan, a confidence interval or test, width/error limits, and an independent
      evaluation set;
    - for an optional initial 95 % profile, report a one-sided 95 % bound against a separately declared minimum
      (default 90 %);
    - too few samples give INSUFFICIENT_EVIDENCE, not a pass.
  - L421–427 §9.3: the surrogate is frozen during a solve or subproblem. Refinement is a new study iteration:
    re-validate, promote, re-solve.
  - Appendix A:
    - **SurrogateManifest:** "Parent model, input/output mapping, splits, transforms, error/gradient metrics, domain,
      calibration assumptions, promotion result".
    - **ModelEvidence:** "Parent/data hashes, numerical convergence, experimental/reference comparisons, uncertainty
      and validation scope".
  - L592, v0.2 acceptance: "Coverage at adaptively chosen optima is not implied." L638 risk: surrogate error can
    change active constraints or the design ranking, so require parent-model checks.

## 4. Current state

The records and code you build on are on unmerged branches. Read them with `git show wp/M02:<path>` and
`git show wp/M03:<path>`; M01 is on `main`.

- **Parent model: M01's reactor boundary** (`src/openflowsheet/models/c1/boundary.py` on main; `docs/derivations/M01-spec.md` §8):
  - Outlet representation: the extent ξ, from a least-squares projection with inerts exact; n_out = n_in + νξ with
    ν = (−3, −1, 2, 0, 0) for (H₂, N₂, NH₃, Ar, CH₄); T_out; P_out = P_in; Q = Ḣ_out − Ḣ_in.
  - Hard domain (L68–71), refused: T 573.15–773.15 K, P 5–15 MPa, H₂/N₂ ∈ [1, 4], inerts ≤ 0.2. M02 adds a
    per-tube flow bound of [0.5, 2] × 0.007146961299302104 mol/s on the real variant (R-232).
  - Data domain (L74–76), flagged `extrapolated` rather than refused: T 643.15–733.15 K, P 5–10 MPa, H₂/N₂ ∈ [1.5, 3].
  - Nominal inlet: y = (0.70, 0.235, 0.03, 0.015, 0.02), T 673.15 K, P 10⁷ Pa.
  - The design-grid discretization estimate, DX-01, comes with every result: NH₃ high by 1.02–1.38 %, ξ by 1.44–1.94 %,
    T_out low by 1.24–1.67 K. It is an estimate, not a bound.
  - The reactor is noise-free within one machine fingerprint (bitwise), and agrees across fingerprints within
    ε_eval = 1e-6 relative.
  - About 9 s per cold experiment; 0 s on a cache hit.
- **The training data: M02's experiment records** (`wp/M02:schemas/experiment.schema.json`; ADR 0033):
  - request, result and attempt records. A result is written once, and only for deterministic outcomes.
  - The experiment identity is exact and process-level: a one-ulp change is a new experiment.
  - Failed or refused experiments carry no outlet values.
  - Stand-in records carry `identity.synthetic = true` and certify nothing about the reactor (R-199).
  - M02 provides one experiment per job (the `experiment` operation). **Batch sampling is explicitly M04's**
    (M02 design D12, R-229).
- **The surrogate seam** (`wp/M02` ADR 0034 D1–D2):
  - The compiled reactor unit pins X̂ (conversion) and ΔT̂ (temperature rise) as parameters `U.coupling.X` and
    `U.coupling.dT`.
  - An outer Broyden iteration matches them to one experiment per iteration. It converges at
    |ξ_E − X̂ n_N₂| ≤ 1e-5 n_tot and |ΔT error| ≤ 1e-2 K.
  - The bounds are X̂ ∈ [0, 0.95] and ΔT̂ ∈ [−50, 250] K.
  - No sensitivity passes through the inner problem (D4).
  - A surrogate of (X, ΔT) as a function of the inlet is the natural replacement for the experiment in that loop.
  - Decide what M04 delivers there and what M05 does.
- **Promotion** (`wp/M02` ADR 0035):
  - Replacement is a checked commit against nine facets: resolvable, ports, components, conserved_quantities,
    reference_states, boundary_condition, degrees_of_freedom, derivatives, validity.
  - Invalidation works by operation.
  - Experiment records are never invalidated; rollback reuses them through the cache.
  - **There is no surrogate-specific facet.**
- **Reusable from M03** (`wp/M03:src/openflowsheet/studies/`):
  - `identifiability()`, an SVD rank test with τ_id 1e-8 (`estimation.py:546`);
  - the ESTIMATOR-settings-in-report pattern;
  - the "failed point is a result" and point-budget pattern (`sweep.py`);
  - the refusal and qualification vocabulary (ADR 0031 C2 names M04 as an inheritor);
  - the `study` schema.
  - M03's seeded data convention (R-184): SplitMix64, seed 20261008, erfinv at 60 digits in the generator; results
    stored as JSON and read, never regenerated. It is numerical verification, not validation.
- **Model identity:**
  - `MODEL_BUILDERS` (`application/revision_binding.py:1103`, 13 entries; M02 adds `c1.reactor` and
    `c1.reactor_standin`).
  - The frozen `ModelManifest` schema: `additionalProperties: false`; `execution_class` ∈ native_equation,
    explicit_reduced, experiment_provider.
  - M02's variant registry (`adapters/variants.py`).
- **Dependencies:** numpy 2.2.4 and scipy 1.15.3 only. There is no statistics library. G20's static audit
  (`tests/test_t07_global_state.py`) forbids legacy `np.random` calls, `import random` and `@cache` in `src`.
  Registered RNG precedents are R-069 (a scoped global seed for onenormest) and R-184.
- **Nothing exists for M04:** no code, schema, ADR, register entry on uncertainty or statistics, approved experiment
  budget, or registered reference distribution.

## 5. Constraints and invariants

- **Identities do not move.** That covers SYN-001, K05, the T06 corpus, M01's registered values and M02's
  experiment identity. Everything is additive.
- **Frozen interfaces and schemas change only by ADR.** `SurrogateManifest` and `ModelEvidence` are on plan §2.2's
  list; add them as schemas once used. M03's `schemas/registry.json` (R-213) is the schema list.
- **No new runtime dependency without an ADR.** numpy and scipy suffice for a quadratic least-squares fit and
  split-conformal.
- **Exact caches key on exact inputs.** A surrogate's evaluation is a native compiled function, so its residual and
  Jacobian describe the same function.
- **No placeholder success.** Insufficient budget gives INSUFFICIENT_EVIDENCE. A failed experiment stays in the
  dataset with its label and never gets fabricated outputs.
- **Numerical verification, empirical validation and optimality evidence stay distinct.** The surrogate's coverage is
  evidence about its error *relative to the parent model at design-grid resolution*. It says nothing about the real
  reactor (the parent has its own discretization bias, DX-01) and nothing about plant data.
- **The test suite never runs the reactor.** Reactor-dependent work is opt-in; the committed records are what the
  default gate checks (M02's pattern).

## 6. Already decided — do not reopen

- **The reactor model and its boundary:** C1, the pin `6089593`, the boundary and domains (ADR 0027), M02's
  execution, records, cache, coupling and promotion design (ADRs 0033–0035, R-220…R-237).
- **Split-conformal is the Default** (blueprint D12/A07); an alternative needs an ADR.
- **The starting surrogate is a quadratic response surface** in scaled inputs, predicting extents or conserved
  coordinates (plan L273). Complexity is added only for a measured limitation.
- **Order** (R-153): M04 follows M02. M02 is still building, so the real-variant records do not exist yet. Your
  specification may register sample counts and a reference distribution now; the experiments run after M02's WO-5.

## 7. Genuinely open — decide these

1. **The surrogate's inputs and outputs.**
   - Which inlet coordinates are inputs: T, P, composition (which ratios), per-tube flow.
   - The scaling.
   - The outputs (X or ξ/n_N₂, ΔT, others?) as a conserved-coordinate representation, with nonnegativity and the
     extent bounds enforced.
   - Its derivative: analytic, from the quadratic.
   - How it enters the flowsheet: at the M02 coupling seam, or as its own native unit.
2. **The registered reference distribution:** a process-relevant distribution over the inputs within the hard domain,
   or the data domain, or a sub-box around the loop's operating region. Its seed and sampler.
3. **The sample plan.**
   - Training, calibration and test counts, from the approved experiment budget and the finite-sample rule. At about
     9 s per cold experiment, 100 experiments take about 15 min.
   - The training design (space-filling is allowed for training, but not labelled i.i.d.).
   - Disjoint i.i.d. calibration and test draws.
   - The INSUFFICIENT_EVIDENCE rule.
   - What happens to failed or refused experiments in each split: they count in the denominator? They are excluded,
     with the domain refusal reported?
4. **The conformal scores:** scalar per output, or joint (max of normalized errors). The quantile rule, with the
   ceiling correction. The interval-width limits.
5. **The promotion criteria.**
   - The one-sided 95 % bound against a declared minimum (default 90 %).
   - Error and gradient metrics: gradient checks against what? The parent has no sensitivities; finite differences on
     the parent are noise-limited at about 1.6e-8/h.
   - Domain metrics.
   - What a failed promotion leaves in place, and rollback.
6. **The empirical domain test:** a scaled distance or density criterion, documented, beyond the hard box and the
   convex hull.
7. **The schemas:** `SurrogateManifest` and `ModelEvidence`, minimal and additive. Whether a surrogate is a new model
   variant in M02's registry (`execution_class: explicit_reduced`?) and how ADR 0035's facets apply, including whether
   a surrogate-specific facet is needed.
8. **The synthetic stand-in:** whether M04's whole pipeline is first verified end to end on the stand-in. That would
   be numerical verification with a known answer, ξ = 0.25·n_N₂,in. The real reactor runs come after M02's WO-5.
9. **The budget.** The plan's "approved experiment budget" does not exist. Propose one, with its cost in machine time,
   as a "Needs Frank" item with a default. This is local compute; there is no money cost.

## 8. How the answer will be verified

- The gate `./scripts/check.sh`, about 7500 tests.
- Your assertions, with independent references: closed-form or mpmath checks of the quadratic fit and of the
  finite-sample quantile; a stand-in run whose truth is known exactly.
- W23, judged by a `verdict` agent from your gate table.
- One `reviewer` pass on the finished build.

## 9. Deliverable

On `wp/M04`:
- `docs/derivations/M04-spec.md`: the derivation plus the test specification, with numbered assertions, tolerances
  and their justification, and the registered sample plan.
- ADR(s): use **0036 onward**; 0026/0027 are M01's, 0030 M06's, 0031/0032 M03's, 0033–0035 M02's.
- Register entries: use **R-240 onward**.
- A generator for the reference values, independent of `openflowsheet`, with `--check`.
- A "Work orders" section listing the build-lane steps in dependency order, each with its acceptance assertions,
  marked bounded or Opus.
- A "Needs Frank" section, each item with its default.

## 10. Out of scope

- Trust-region optimization over the surrogate (M05).
- The M07 journey.
- Changing M02's execution or records design.
- Bayesian or multi-fidelity design of experiments.
- Validation against plant or literature data.
- Any change to the reactor or its pin.
