# ADR 0039 — M05: the C1 fixed-topology study optimizes the reactor inlet temperature for liquid NH₃ product; candidates are judged by parent checks at the decision tolerance; every true-model call is accounted

**Status:** Proposed, 2026-10-09. It is accepted when M05's evidence manifest is `tested` for the design note's gates
G5–G12 (G11 opt-in) and the design-lane review of WO-5–WO-9 has closed its must-fix items.
**Author:** design lane (`architect`), M05.
**Normative text:** `docs/design/M05-trust-region.md` §5.2–§5.3, §7, §8 and §9 (binding), §11 (claims).
**Register:** R-267 to R-271, R-273.
**Amends:** nothing. It registers the study `c1-trf-study-v1`, the objective `c1-obj-nh3-liquid-v1`, the test-only
variant `m05-synthetic-interior-v1`, and the configurations `M05-parent-checks-v1` and `M05-budget-v1`.
**Affected requirements:** W24 (M05's half), D13 (finite-budget truth checks); blueprint §9.3 L423 and L427; R-169;
R-188; R-189.
**Affected packages:** M05; M07 (the before/after decision and the truth checks).

## Context

ADR 0022 D6 and the C1 dossier name the reactor inlet temperature as the v0.2 decision ("a kinetic reactor has an
interior optimum"), and the purge fraction as the alternative. No objective is registered.

R-169 flags `extrapolated` results; the bed leaves the kinetics' data domain at every registered state. M04's
surrogate may not claim coverage at a candidate, which needs a parent evaluation labelled `targeted_check` (M04 spec
§7.4). M02's coupled route converges to |ξ_E − X̂ n_N₂| ≤ 1e-5 n_tot and |ΔT err| ≤ 1e-2 K (ADR 0034 D3), and refuses
sensitivities. ADR 0031 C3 refuses EO-path sensitivities, so M03's V5 (an adjoint KKT check) is unavailable on C1.

## Decision

**D1. The study `c1-trf-study-v1`.**
- **Case.** `C1-LOOP-M02-v1`.
- **Decision.** The `c1.tp_heater` outlet-temperature specification T_in, in the box [643.15, 733.15] K (the inlet span
  of the kinetics' data domain). The purge fraction is fixed at 0.02.
- **Objective `c1-obj-nh3-liquid-v1`.** Maximize the NH₃ molar flow of `c1.tp_flash`'s liquid outlet (mol/s,
  scale 1).
- **Constraints**, generated from the bound variant's hard domain and from the admissibility set A(s) (M04 spec §3.2),
  with a margin of 1e-6 relative on expression constraints: T and P bounds; 1 ≤ H₂/N₂ ≤ 4 and inerts ≤ 0.2 in
  division-free form; per-tube flow ∈ [0.5, 2] F₀ for the real variant; X̂ ∈ [0, 0.95] and X̂ ≤ r/3; ΔT̂ ∈ [−50, 250] K;
  the provider domain on stream T and P; molar flows ≥ 0.
- **Stated limits, never constraints:** `extrapolated`, `surrogate_outside_reference_domain`, `synthetic` and
  `fd_gradient`.
- **Decision tolerance.** δ_T = 0.5 K.

**D2. The eligible example and the test truth.** TR-E2 is D1's formulation with:
- the box [653.15, 693.15] K;
- the reactor EF bound to `m05-synthetic-interior-v1`: test-only, in-process, `synthetic: true`, boundary block equal
  to the stand-in's, defined by X = 0.16·exp(a·z − z_T²) and ΔT = 80 K·exp(b·z) with a and b as in design note §5.2.
  It has an analytic gradient and no failure region.

The independent expectation T_ref comes from a tightly coupled reference in test support: Newton on w to 1e-12 scaled
through M02's inner solve at pinned w, then golden-section search to a bracket of 0.05 K.

TR-E2-FD repeats TR-E2 through the production FD path.

LOOP-S and LOOP-R exercise the loop on M04's synthetic smooth parent (with its PROMOTABLE prefix-plan manifest) and its
rough parent (NOT_PROMOTABLE), with the box [653.15, 693.15] K.

**D3. The refinement loop.**
- **S0.** A certified coupled solve at the nominal 673.15 K, which must pass P1.
- **A.** TRF on the promoted surrogate. Only if one is promoted for the bound parent; otherwise it is recorded as
  skipped, `surrogate_not_promoted`.
- **B.** Parent checks (D4).
- **C.** TRF on the parent through the EF, with the promoted-surrogate or constant basis, started from the best
  parent-checked state.
- Then B again. At most 3 study iterations. On a TRF abort: one retry from the same start at ¼ of the radius.
- **Stop** with `DECISION_STABLE` exactly when a candidate earns `PARENT_LOCAL_EVIDENCE`. Otherwise:
  - `NOT_STATIONARY_AT_DELTA` restarts from the best feasible poll point;
  - any other candidate status stops `FAILED(<status>)` and is escalated;
  - the iteration limit gives `ITERATION_LIMIT`, and the budget gives `BUDGET_EXHAUSTED`. Neither is ever called
    stable.
- **M05 does not retrain the surrogate.** Within a run, retraining voids TRF's theory (blueprint L437); between
  iterations, M04 owns training (its spec §5.5).

**D4. Parent checks `M05-parent-checks-v1`.** At each candidate, the revision document is edited in memory to the
candidate's binary64 decision, solved through its route without a commit, and labelled `targeted_check`.

| | Check | Pass iff |
| --- | --- | --- |
| P1 | Targeted check | `CONVERGED` and certificate `VERIFIED` |
| P2 | Gross agreement, TRF state against re-solve | J and states agree within 1e-3 (scaled); failure is a defect signal |
| P3 | Constraints on the certified state | every D1 constraint holds within 1e-9 × its scale |
| P4 | Regimes | every regime label equals S0's |
| P5 | Poll | for every feasible poll point at ±δ (only the inward one at a bound): J_j − J* ≤ e* + e_j |

**The noise floor.** e_i = 2(|∂J/∂X̂|·ΔX_i + |∂J/∂ΔT̂|·ΔT_i), where:
- ΔX_i and ΔT_i are solve i's *achieved* coupling residuals, from its certificate;
- the sensitivities come from central differences of M02's inner solve at the candidate's w (h_X = 1e-4,
  h_T = 1e-2 K; no reactor call).

**Reported, not judged:** the curvature, and the indifference half-width √(2(e* + max e_j)/|c|).

**Candidate statuses**, by precedence: `PARENT_CHECK_FAILED` (P1), `REGIME_CHANGED` (P4),
`PARENT_CONSTRAINT_VIOLATED` (P3), `PROJECTION_DISAGREES` (P2), `NOT_STATIONARY_AT_DELTA` (P5) and
`PARENT_LOCAL_EVIDENCE`; `NOT_CHECKED` when the budget runs out first. The claims are always
`global_optimality: false`; `stationarity` is `poll_at_delta` or `not_claimed`.

**D5. Budgets `M05-budget-v1`.**
- REAL: ≤ 400 cold parent experiments and ≤ 4 h per study; ≤ 250 cold and ≤ 30 iterations per TRF run.
- In-process configurations: ≤ 2000 evaluations and ≤ 1 h.
- Concurrency: ≤ min(7, physical cores − 1) FD workers, and two poll solves.

**D6. True-model call accounting.**
- **Ledger.** One `truth-ledger-v1` JSON-Lines entry per holder request: study iteration, stage, TRF run and
  iteration, purpose, truth, inlet hash and experiment key, served as cold, store hit or memo hit, executions, status,
  `extrapolated`, wall time.
- **Coupled checks.** One summary per coupled-check solve, taken from its `external-coupling.json`.
- **Totals** by stage, study iteration and candidate.
- **Identities, gated:**
  - every M02 store attempt of the study is attributed to exactly one ledger entry or check summary;
  - cold + store hit + memo hit = requests;
  - TRF 6.10.1's request structure per run: 1 start value, 1 PMP value, K trial values, and
    7·(1 + A − [final logged iteration accepted]) FD points (design note §8.3);
  - no cap is ever exceeded.

**D7. Records.**
- The schema `trust-region-study-v1` (design note §9.1): spec, environment pins, runs with iteration logs, the
  reconstructed filter, outcomes and assumptions blocks A1–A7, candidates with P1–P5, the poll and noise floor,
  accounting, status, claims and limitations, and artifacts by hash (source map, ledger, coupled runs).
- **Replay classes as M02's:** an in-process truth is re-evaluated; an out-of-process truth is R3, served from the
  record under ADR 0034 D6's rule. Same-machine replay must be bitwise; cross-architecture comparison is under
  `T08-numerical-policy-v2` with a test-level pre-pass.
- M05 adds no product-level study replay. R-253's move into `run/compare` (an ADR 0025 amendment) therefore falls to
  the first package that does.

**D8. Exposure.** The library `openflowsheet.studies.trust_region`, evidence scripts, registered configurations and
committed records under `benchmarks/m05/`. There is no job operation.

## Alternatives considered

- **(T_in, φ) jointly under the NH₃ objective.** Rejected: by the steady-state inert balance the purge loss of N₂ falls
  monotonically with φ, so φ runs to its bound — a degenerate decision. An economic objective that makes φ meaningful
  needs prices (Frank, N-F1).
- **`extrapolated` as a constraint.** Rejected: it is infeasible, because every registered state is extrapolated
  (R-169). The flag is counted and carried instead.
- **M04's box7 as a constraint on the real study.** Rejected: it is the surrogate's empirical domain, not the parent's
  hard domain, and blueprint R-189 allows only true restrictions. Outside it, stage A carries M04's limitation.
- **M03's V5 (an adjoint KKT check).** Rejected: refused on this path by ADR 0031 C3, and it would be a sensitivity
  claim.
- **A finite-difference KKT test as the verdict.** Rejected: with the coupling-tolerance noise, its tolerance cannot be
  set without unknown third derivatives. The poll makes the decision-relevant claim directly; the curvature is
  reported.
- **A fixed objective noise floor.** Rejected: computing it from the achieved residuals keeps the threshold small. The
  safe failure is an extra refinement, never a false stability.
- **Retraining the surrogate between study iterations.** Rejected: M04 owns training, and its splits must stay i.i.d.
- **Counting from the experiment store alone.** Rejected: it cannot attribute a call to a purpose, iteration or
  candidate.
- **Extending M03's `optimization-report`.** Rejected: its content is disjoint, and A06 keeps the bridges apart.

## Consequences

- M07 gets a before/after decision (T_in nominal against the candidate) with parent checks and costs.
- With a flat objective, the honest output is an indifference interval at the coupling's resolution.
- The poll needs one targeted check plus at most two coupled solves per candidate, plus four inner solves with no
  reactor call.
- The test-only variant ships nowhere.

## Migration

None.

## Acceptance evidence

Design note gates G5 (TR-E2), G6 (TR-E2-FD and the request identity), G7 (accounting), G8 and G9 (the loop and the
N6 branch), G10 (replay), G11 (REAL mechanics, opt-in) and G12 (default gate on the committed records).
