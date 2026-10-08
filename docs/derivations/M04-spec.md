# M04 specification — the C1 reactor surrogate, Default split-conformal reporting, the registered sample plan, promotion and rollback

**Status:** design-lane authority for package M04 (plan v1.2 §4.4; gate W23; requirements A07, D12).
**Date:** 2026-10-08. **Author:** design lane (`specifier`). **Brief:** `docs/briefs/M04-specification.md`.
**Decisions:** ADR 0036 (statistical semantics), ADR 0037 (the surrogate in a flowsheet; amends ADRs 0019, 0035);
register R-240…R-249.
**Machine-readable expectations:** `benchmarks/m04/reference_values.json` and the registered plan
`benchmarks/m04/plan-it1.json`, both from `docs/derivations/scripts/m04_reference.py` (`--check` re-derives every
claim this document makes about its own numbers and requires both files byte-identical; 5269 claims at this commit).
**Built on:** M01 (`main`: the boundary, ADR 0027, DX-01), M02 (`wp/M02`: ADRs 0033–0035, the records, the coupling,
the replacement check), M03 (`wp/M03`: ADR 0031's vocabulary, R-184's seeded-data convention).

## 1. Authority and scope

This document fixes, for the C1 reactor and for every later consumer of its surrogate (M05, M07):

- the surrogate's inputs, outputs, representation, derivative and fit (§3);
- the hard and empirical domain tests (§3.6);
- the registered reference distribution (§4) and the registered sample plan of iteration 1 — seeds, sampler, counts,
  cost — fixed **before** the parent model runs (§5);
- Default split-conformal reporting: the score, the finite-sample rule, the coverage test and their qualifications
  (§6);
- the promotion criteria and the three verdicts (§7);
- how a surrogate enters a flowsheet, is promoted and is rolled back through M02's replacement machinery (§8);
- the end-to-end verification on synthetic parents with exactly known answers (§9);
- the `SurrogateManifest` and `ModelEvidence` records and the `surrogate_study` job operation (§10);
- the numbered assertions (§11), the build lane's work orders (§13) and the open questions with defaults (§14).

Where this document and an ADR it cites disagree, the ADR wins and this document is amended. M02's ADRs 0033–0035
are Proposed on an unmerged branch; ADR 0037 amends 0035 additively and is void if 0035 is withdrawn.

## 2. What M04 establishes (summary)

1. **A native surrogate unit.** `c1.reactor_surrogate` is M02's extent-fixed embedding (ADR 0034 D1) with the pinned
   coupling parameters (X̂, ΔT̂) replaced by a frozen quadratic f̃ of the scaled inlet: the same nine rows, analytic
   derivatives, solved on the plain `revision_eo` route without experiments. Element conservation is exact by
   construction; species nonnegativity is a hard admissibility test, never a projection.
2. **One registered reference distribution** P_ref: uniform on a 7-coordinate box around the C1 nominal inlet, inside
   both the parent's hard domain and its data domain.
3. **One registered plan per iteration.** Iteration 1: 144 training, 118 calibration and 300 test draws i.i.d. from
   P_ref by SplitMix64, and 5 gradient centres with 14 stencil experiments each — **632 cold experiments, about 95 min
   of one thread at 9 s each**. The probability that a correctly working pipeline passes the coverage test is 0.9035
   (distribution-free).
4. **Default split-conformal, joint over (X, ΔT).** Score s = max(|e_X|/w_X, |e_ΔT|/w_ΔT) with predeclared
   scales equal to the width limits w_X = 0.0025 and w_ΔT = 1.5 K; q̂ = the k-th smallest of n calibration scores,
   k = ⌈(n+1)(1 − α)⌉ in integer arithmetic; a failed draw scores +∞.
5. **Promotion is a test, not a reading.** PROMOTABLE iff the band is finite and q̂ ≤ 1 (the band lies within the width
   limits), the one-sided 95 % Clopper–Pearson lower bound on the frozen band's coverage from the 300 independent
   test draws is ≥ 0.90 (equivalently ≥ 279 hits), every prediction in the reference box is admissible, and the
   surrogate's gradient agrees with the parent's central difference within 25 % at all five gradient centres. Too
   little evidence is INSUFFICIENT_EVIDENCE, never a pass.
6. **Promotion and rollback are checked commits** (ADR 0035) with one new facet, `surrogate_evidence`, and one narrow
   exception in `derivatives` for a rollback to the surrogate's own parent.

## 3. The surrogate (derivation)

### 3.1 Inputs and scaling

The parent's map (M01 spec §8.3) is homogeneous of degree one in (n_in, N_tubes), so the conversion and the
temperature rise depend on the intensive inlet and the per-tube flow only. The surrogate's inputs are the seven
coordinates

| k | u_k | definition from the inlet (n₁…n₅ = H₂, N₂, NH₃, Ar, CH₄; T; P; N_tubes) | box [lo, hi] | centre c_k | half-width h_k |
| --- | --- | --- | --- | --- | --- |
| 1 | T (K) | T_in | [653.15, 693.15] | 673.15 | 20 |
| 2 | P (Pa) | P_in | [9.0e6, 1.0e7] | 9.5e6 | 5.0e5 |
| 3 | r | n_H₂ / n_N₂ | [2.5, 3.0] | 2.75 | 0.25 |
| 4 | y_NH₃ | n_NH₃ / n_tot | [0.02, 0.04] | 0.03 | 0.01 |
| 5 | y_Ar | n_Ar / n_tot | [0.01, 0.03] | 0.02 | 0.01 (binary64 0.009999999999999998) |
| 6 | y_CH₄ | n_CH₄ / n_tot | [0.01, 0.04] | 0.025 | 0.015 |
| 7 | F (mol/s) | n_tot / N_tubes | [0.0057, 0.0086] | 0.00715 | 0.00145 |

n_tot = (((n₁ + n₂) + n₃) + n₄) + n₅. The box bounds are the decimal literals shown, parsed to binary64; the centre and
half-width are the binary64 results of `(lo + hi) * 0.5` and `(hi - lo) * 0.5` (`reference_values.json` →
`constants.box`). The scaled input is z_k = (u_k − c_k)/h_k, so the box is [−1, 1]⁷. No other transform (no log, no
whitening) is applied; the transform is frozen with the predictor.

*Why these coordinates.* They are a bijection with the inlet at fixed N_tubes, they are the coordinates of the parent's
own hard and data domains (T, P, H₂/N₂, inerts, per-tube flow), and no direction of the inlet is silently held fixed:
the two inerts are separate inputs because their split varies in a loop with a purge and a dissolving separator.

### 3.2 Outputs and the conserved-coordinate representation

The outputs are M02's coupling coordinates (ADR 0034 D1–D2): the N₂ conversion X = ξ / n_N₂,in and the temperature
rise ΔT = T_out − T_in. With β_X, β_T ∈ ℝ³⁶ the frozen coefficients and φ the basis of §3.4,

  X̃(z) = β_Xᵀ φ(z),  ΔT̃(z) = β_Tᵀ φ(z).

The unit's rows are M02's embedded rows (design note §4.1) with the pinned parameters replaced:

- `C1RX-mole.<i>` (5): n_in,i + ν_i ξ − n_out,i = 0, ν = (−3, −1, 2, 0, 0);
- `C1RX-extent`: R_ξ = ξ − X̃(z(s)) n_N₂,in = 0 (kind `molar_flow`);
- `C1RX-temperature`: R_T = T_out − T_in − ΔT̃(z(s)) = 0 (kind `temperature`);
- `C1RX-pressure`: P_in − P_out = 0; `C1RX-duty`: Q + Ḣ_in − Ḣ_out = 0 by `pr-c1-v1`.

**Conservation is exact by construction.** n_out − n_in = ν ξ for every value of X̃, and the element matrix E
(rows Ar, C, H, N) satisfies E ν = 0 (M01 spec §8.9, claim RX-01); inerts pass unchanged. No fitted quantity can break
an element balance; the surrogate can only be wrong about *how far* the reaction goes and how hot the outlet is.

**Admissibility (hard, refused, never projected).** n_out ≥ 0 componentwise iff X̃ ∈ [−y_NH₃/(2 y_N₂), min(1, r/3)];
with M02's coupling bounds (ADR 0034 D2) the admissible output set is

  A(s) = { X̃ ∈ [0, min(0.95, r/3)] } × { ΔT̃ ∈ [−50, 250] K }.

These are exactly the values the parent-backed coupling could realise (its w is bounded to the same box), and r/3 is
the H₂ limit (r ∈ [1, 4] in the hard domain, so r/3 can be as low as 1/3 < 0.95 — a test that checks only [0, 0.95]
is wrong). A prediction outside A(s) is refused, not clipped: clipping would be a fabricated output with a kink in its
derivative, and a smooth saturation would change the representation for a limitation nobody has measured (plan L273:
complexity only for a measured limitation).

### 3.3 Derivatives (closed form)

The rows are polynomials in z composed with the input map, so residual and Jacobian describe the same function at
every state where the input map is defined (n_N₂ > 0, n_tot > 0). With g^X = ∇_z X̃ and g^T = ∇_z ΔT̃,

  ∂φ_m/∂z_k: 1 for the linear term z_k; z_j δ_ik + z_i δ_jk for the term z_i z_j (2 z_k when i = j = k);

  ∂u/∂s (rows u₁…u₇, columns n₁…n₅, T, P):
  ∂T/∂T = 1; ∂P/∂P = 1; ∂r/∂n_H₂ = 1/n_N₂; ∂r/∂n_N₂ = −n_H₂/n_N₂²;
  ∂y_j/∂n_i = (δ_ij − y_j)/n_tot for j ∈ {NH₃, Ar, CH₄}; ∂F/∂n_i = 1/N_tubes;

  ∂X̃/∂s_c = Σ_k (g^X_k / h_k) ∂u_k/∂s_c, likewise ∂ΔT̃/∂s_c;

  ∂R_ξ/∂s_c = −n_N₂ ∂X̃/∂s_c − X̃ δ_{c,N₂};  ∂R_ξ/∂ξ = 1;  ∂R_ξ/∂T_out = 0;
  ∂R_T/∂s_c = −∂ΔT̃/∂s_c − δ_{c,T};  ∂R_T/∂T_out = 1;  ∂R_T/∂ξ = 0.

The other seven rows are M02's and unchanged. The generator checks this chain rule against mpmath differentiation of
the composed rows at 50 digits (agreement 2 × 10⁻⁵¹ at J1–J3).

### 3.4 Basis and fit

φ(z) = [1, z₁, …, z₇, z₁², z₁z₂, …, z₁z₇, z₂², z₂z₃, …, z₇²]: the constant, the linear terms in coordinate order, then
z_i z_j for i ≤ j in lexicographic order — 36 terms (`constants.basis_order`). The predictor class is the full
quadratic, unregularized, fixed in advance; nothing about it is selected from data.

The fit uses the training draws whose experiments returned `ok`, in plan order. Φ is the N_ok × 36 matrix of φ(z)
rows, y the vector of X (or ΔT) values; β minimizes ‖Φβ − y‖₂ by Householder QR (`numpy.linalg.qr`, mode `reduced`,
then a triangular solve); X and ΔT share Φ. **Identifiability** (M03's τ_id, ADR 0031 D6): the fit is refused as
`training_unidentifiable` when N_ok < 36 or σ_min(Φ)/σ_max(Φ) < τ_id = 10⁻⁸. On the registered synthetic training set
the ratio is 0.12305 (κ = 8.1), so roundoff in the coefficients is at the 10⁻¹⁵ level.

### 3.5 Registered Jacobian states

The fixture surrogate of these states has the smooth synthetic case's coefficients (§9) rounded once to binary64
(`reference_values.json` → `fixture_coefficients`); the inlets are binary64 values (`jacobian_states[*].inlet`).

| State | Inlet | Why it is in the list |
| --- | --- | --- |
| J1 | nominal per tube (F₀ × y_nom, 673.15 K, 10⁷ Pa), N_tubes = 1 | The nominal point. z_T vanishes there to roundoff (the box is centred on 673.15 K), so every term carrying z_T is invisible at J1 — J2 exists for that reason. z_P = 1 exactly (the box's upper P bound). |
| J2 | u = (661.7, 9.37e6, 2.61, 0.0273, 0.0188, 0.0321, 0.00653) per tube, scaled to N_tubes = 1000 | Every z_k non-zero and pairwise distinct, so a permuted coordinate, a dropped cross term or a missing 1/N_tubes changes the Jacobian; all 14 inlet entries non-zero. |
| J3 | u = (703.15, 9.5e6, 2.75, 0.03, 0.02, 0.025, 0.00715), N_tubes = 1 | Outside the reference box in T only (z_T = 1.5): the residual still evaluates, the domain status is `outside_reference_domain` with scaled excess 0.5, and the hard domain admits it. |
| J4 | J1 with T_in = 780 K | Outside the parent's hard domain: refused at the causal evaluation and at the certificate check (§3.6). |
| J5 | J1 with n_N₂ = 0 | Input map undefined (r = n_H₂/0): `surrogate_input_undefined`. |
| J6 | all flows zero | Dormant inlet: ξ = 0 and T_out = T_in exactly (§3.7). |

No inlet Jacobian entry at J1–J3 cancels by more than a factor 4.45 (Σ|terms|/|entry|, generator), so binary64
evaluation is accurate to about 10⁻¹³ relative per entry.

### 3.6 Domain: hard and empirical

**Hard (refused).** The surrogate inherits its parent's hard domain verbatim (the variant's `boundary.hard_domain`:
T 573.15–773.15 K, P 5–15 MPa, H₂/N₂ ∈ [1, 4], inerts ≤ 0.2, and for the real variant the per-tube flow
[0.5, 2] × F₀). Outside it, and wherever the prediction leaves A(s) (§3.2), the unit refuses with the same status
class the parent uses (`out_of_domain`) and the reasons `surrogate_outside_hard_domain(<unit>:<bound>)` or
`surrogate_output_inadmissible(<unit>:<X|dT>)`. The refusal happens where hard domains are judged for a native unit:
the causal evaluation (traversal, initializer) and the certificate's `bounds_and_domain` check
`SURROGATE-DOMAIN:<unit>` at the converged state. The residual and Jacobian themselves stay defined (polynomials) so
that Newton may pass through an inadmissible iterate on its way to an admissible root, exactly as a pinned-parameter
row may; what is never issued is a certified solution at an inadmissible state.

**Empirical (flagged, not refused).** The empirical domain is the support of P_ref: z ∈ [−1, 1]⁷. Its scaled distance
is the excess e(z) = max(0, ‖z‖_∞ − 1). Inside (e = 0) the coverage evidence of §6 applies marginally; outside
(e > 0) **no coverage claim applies** and the run carries the limitation `surrogate_outside_reference_domain` with the
excess and the offending coordinates. The criterion is documented, scaled and cheap, and it is exactly the region the
statistical evidence was drawn from.

*Rejected criteria.* Convex-hull membership of the training draws (blueprint §9.2: it does not establish accuracy in a
sparse high-dimensional interior; here, with 144 points in 7 dimensions, most of the box lies outside the hull, so
the hull would disagree with the support of the very distribution the coverage is marginal over: fewer than 30 of
the 300 registered test draws lie in the hull of the 144 training draws — generator-asserted; 22 at this commit).
Nearest-neighbour density (a global quadratic's accuracy is not governed by local sample density; the i.i.d. test
draws measure accuracy over the whole interior directly). Leverage φᵀ(ΦᵀΦ)⁻¹φ (it measures how a least-squares
prediction amplifies *noise* in the data; the parent is deterministic, so the surrogate's error is model-form bias,
which leverage does not measure, and a pointwise flag would compete with the marginal claim without adding one).

### 3.7 Zero flow and undefined inputs

A dormant inlet (all flows zero; ADR 0001's zero-flow semantics, the dormancy form of T05b §7.6 as M02's embedded unit
uses it) gives ξ = 0 and T_out = T_in exactly — M02's ZERO_FLOW convention F = (X̂, 0) with the surrogate not
evaluated. An inlet with n_tot > 0 and n_N₂ = 0 has no defined r; the residual evaluation returns the unit's typed
failure `out_of_domain` / `surrogate_input_undefined(<unit>)` (it is also outside the hard domain, H₂/N₂ ∈ [1, 4]).

## 4. The registered reference distribution

**P_ref = the uniform distribution on the box of §3.1**, a product of seven independent uniforms in the u-coordinates.
It is registered by the id `m04-c1-box7-v1`, the bounds above, and the sampler of §5.1.

*Why this region.* It is process-relevant: it is centred on the C1 nominal reactor inlet (M01 spec §8.4) and spans
the variations a recycle loop imposes on the inlet — ±20 K in the preheat (the dossier's design decision, §9 of the
dossier), ±20 % in per-tube flow, the loop pressure, the makeup ratio and the NH₃ and inert levels a separator and
purge leave. It lies inside the parent's **data domain** (T 643.15–733.15 K, P ≤ 10 MPa, H₂/N₂ ≤ 3; asserted for every
draw), so the parent never flags a registered draw `extrapolated`, and inside the real variant's hard domain
including its flow bound. T_in ∈ [653.15, 693.15] K is exactly the interval over which M01 measured the start strategy
accepted at the design grid (M01.A41: 653.15, 673.15, 693.15 K). The box deliberately does **not** reach the
inlet temperatures below 653 K where M01 §10.4 places a possible interior optimum: that region lies partly outside the
kinetics' data domain, and claims there are M05's parent-model checks, not this surrogate's coverage.

*Alternatives rejected.* The whole hard domain (most of it is outside the data domain, and a quadratic over 200 K of
an equilibrium-limited reactor is unlikely to meet any width limit worth stating); the whole data domain (still 90 K
and P down to 5 MPa: the same objection, at roughly twice the misfit risk); a Latin hypercube or a grid as the
"reference" (blueprint §9.2: not i.i.d.; they are allowed for training only, and training here is i.i.d. too, which is
simpler and lets a failed iteration's calibration and test draws join the next training set, §5.5).

## 5. The registered sample plan (iteration 1)

### 5.1 Sampler and requests

- Seeds: seed(i, split) = 20261008·1000 + 10·i + j with j = 1 training, 2 calibration, 3 test, 4 gradient; for
  iteration 1: 20261008011, …012, …013, …014.
- Words: SplitMix64 (R-184's generator; constants as `m03_reference.py`). Draw j of a split consumes words 7j … 7j+6
  in coordinate order.
- Uniform: U = (w >> 11) · 2⁻⁵³ ∈ [0, 1) — exact in binary64 (unlike R-184's (w >> 11) + ½, which needs 54 bits).
- Draw: u_k = lo_k + (hi_k − lo_k) · U in binary64, in that operation order.
- Gradient centres: the same formula on the inner box lo′ = c − 0.95 h, hi′ = c + 0.95 h (binary64, that order);
  stencil u ± (0.05 · h_k) e_k, plus before minus, coordinates in order.
- Request (N_tubes = 1): y_N₂ = (1 − y_NH₃ − y_Ar − y_CH₄)/(1 + r) (left to right), y_H₂ = r · y_N₂,
  n = (F·y_H₂, F·y_N₂, F·y_NH₃, F·y_Ar, F·y_CH₄), T = u₁, P = u₂.

Production code derives the plan from these constants; `benchmarks/m04/plan-it1.json` is the bitwise expectation
(M04.A02) and is never read by installed code (T08's no-walk-up rule). Experiment identity is exact (ADR 0033): one ulp
is a new experiment, which is why the arithmetic order is registered.

Generator-asserted plan invariants: every draw and every stencil point lies in the box, the hard domain (with the real
variant's flow bound) and the data domain; all 632 requests are distinct; every calibration or test draw is at least
0.2085 (∞-norm, scaled) from every training draw — no near-duplicate leakage (blueprint §9.1).

### 5.2 Counts, and why

| Split | Count | Experiments | Purpose |
| --- | --- | --- | --- |
| training | 144 (= 4p) | 144 | the fit; i.i.d. from P_ref, used for nothing else |
| calibration | 118 | 118 | q̂ (§6.2) |
| test | 300 | 300 | the coverage test and error metrics (§6.4) |
| gradient | 5 centres | 70 (5 × 2 × 7) | the gradient metric (§7.2) |
| **total** | | **632 cold experiments** | ≈ 5690 s ≈ **95 min** on one thread at M01's 9.0 s |

- **n = 118** gives k = ⌈0.95 × 119⌉ = 114 and k/(n+1) = 0.95798: the ceiling correction leaves the expected
  coverage slightly above nominal, which buys power. P(conditional coverage C < 0.90) = 0.00652 under
  exchangeability (C ~ Beta(114, 5) for continuous scores).
- **m = 300**: the coverage test passes iff H ≥ h_min(300) = 279 hits; P(pass) for any exchangeable pipeline is
  **0.9035** (beta-binomial, no failures). The false-pass probability at a true coverage of exactly 0.90 is
  0.0458 ≤ 0.05.
- **N = 144 = 4p**: the out-of-sample error inflation of least squares is about √(1 + p/N) = 1.12 against 1.15 at
  3p; the extra 36 experiments cost 5.4 min.
- Alternatives computed (`finite_sample.alternatives`): (99, 300) power 0.819; (118, 200) 0.824; (149, 400) 0.901 at
  131 more experiments; (199, 400) 0.890; (299, 400) 0.914 at 281 more. (118, 300) is the cheapest plan found with
  power above 0.90.

### 5.3 Failed experiments in each split

Every registered draw stays in its split with its label; none gets a fabricated output (blueprint §9.1).

| Outcome of a registered draw | Training | Calibration / test | Gradient stencil |
| --- | --- | --- | --- |
| `ok` | fitted | scored | used |
| deterministic failure (refused, not converged, not accepted; a result record exists) | excluded from Φ, listed with its label | **score +∞: counted in n or m, never covered** | the centre is `parent_failed` |
| no deterministic result (transient failures beyond M02's retries, a cancelled job) | — | — | — |

The last row makes the plan **incomplete**: the verdict is INSUFFICIENT_EVIDENCE (`plan_incomplete`) until a resumed
job completes it from the cache. A split is never shrunk to the draws that succeeded — that would narrow a denominator
(CLAUDE.md) and turn the coverage claim into one conditional on an event the reader cannot see.

*Why +∞ keeps the guarantee.* With an atom of mass f at +∞, U_(k) of the probability-integral transform still has the
Beta(k, n+1−k) law; q̂ is finite iff U_(k) < 1 − f, and then the band's coverage of the event "the parent returned a
result and it lies in the band" is C = U_(k). Failures therefore widen the band instead of eroding the claim, and
when they exceed n − k = 4 calibration draws there is no finite band (`band_not_finite`).

*What failures cost* (`finite_sample.registered_plan_with_failures`, exact under the same law): at a parent failure
rate of 1 % in the box the band is finite with probability 0.9931 and the plan passes the coverage test with
probability 0.8966; at 2 %, 0.9111 and 0.8146; at 5 %, 0.2919 and 0.1997. A parent that fails on more than a few
percent of the reference box cannot support a 95 % band there — a measured property of the parent, reported as
`band_not_finite`, not a defect of the plan.

### 5.4 Budget and the refusal before running

The approved budget is a number of **cold** experiments (cache hits cost nothing; ADR 0033's exact cache). At study
start the job computes every request key of the plan, counts the cache misses, and refuses with
INSUFFICIENT_EVIDENCE (`budget_below_plan`) — writing no experiment — when the misses exceed the budget. A plan is
never truncated to fit a budget, and a running plan is never stopped early on the strength of interim results.

### 5.5 Iterations

Iteration i ≥ 2 uses seeds seed(i, ·), draws fresh calibration (118), test (300) and gradient (5) sets, and trains on
every `ok` P_ref record of iterations < i (their training, calibration and test draws: i.i.d. from the same P_ref, so
the next training set is still a sample of it). Its plan file `plan-it<i>.json` is emitted by the generator and
committed before it runs. Rules:

- an iteration may follow automatically only when the previous verdict's only reason is
  `coverage_bound_below_minimum` (which happens by chance with probability ≈ 0.10 for a correct pipeline);
- any other NOT_PROMOTABLE reason is a measured limitation: the next iteration needs a design-lane amendment
  (a richer predictor class or another box — plan L273) and is not automatic;
- at most three iterations under this specification; every iteration's manifest is retained, and the promoted
  manifest lists its predecessors and reports the family-wise false-pass bound 0.05 × (number of iterations whose
  coverage test was evaluated).

## 6. Default split-conformal reporting

### 6.1 The score

  s(x) = max( |X(x) − X̃(x)| / w_X , |ΔT(x) − ΔT̃(x)| / w_ΔT ),  w_X = 0.0025, w_ΔT = 1.5 K;  s = +∞ for a failed draw.

The scales are the **declared width limits**, fixed before any data (blueprint L415: predictor, transforms and score
frozen before calibration). One joint score gives one q̂ and a rectangular band [X̃ ± q̂ w_X] × [ΔT̃ ± q̂ w_ΔT] whose
coverage is **joint** over the two outputs at one query; the width criterion is the single inequality q̂ ≤ 1.

*Why these limits.* They sit inside the parent's own registered discretization bias at the design grid (DX-01):
w_X / X_nom = 1.58 % against ξ's 1.44–1.94 % (X_nom = 0.158010 from M01's registered ξ), and 1.5 K against T_out's
1.24–1.67 K (both asserted by the generator). A surrogate band no wider than the error already accepted by using the
design grid at most doubles the model-form uncertainty a decision carries; a band wider than that would dominate it.

*Rejected:* per-output scalar scores (two marginal claims, which blueprint L417 requires to be labelled marginal, and
the flowsheet consumes both outputs together); scales from the training residuals (data-dependent, though legal, and
they decouple the score from the stated width limits); a Bonferroni pair (a joint claim from two scores at α/2 each,
strictly wider than the max-score rectangle for the same coverage).

### 6.2 The finite-sample rule

For n calibration scores (+∞ for failures) and α = 1/20 (a rational; nominal 1 − α = 0.95):

  k = ⌈(n + 1)(1 − α)⌉, computed in integers as k = −(−(n+1)·19 // 20);
  if k > n: **no band**, INSUFFICIENT_EVIDENCE (`calibration_too_small`) — this is n < n_min = 19;
  else q̂ = the k-th smallest score (an order statistic: one of the inputs, never interpolated);
  if q̂ = +∞: **no band**, NOT_PROMOTABLE (`band_not_finite`).

Guarantee (exchangeable scores, which i.i.d. draws from P_ref and a frozen predictor give): P(s_{n+1} ≤ q̂) ≥ k/(n+1)
≥ 1 − α, with equality for continuous scores; the deterministic parent gives ties with probability zero. Registered
values: k(18) = 19 > 18; k(19) = 19; k(39) = 38; k(99) = 95; **k(118) = 114** (the uncorrected ⌈0.95 n⌉ = 113 is
wrong); k(119) = 114; k(149) = 143; k(199) = 190.

### 6.3 What the band claims, and the qualifications that travel with it

The claim: **"with probability at least 0.95 over the calibration draws and a fresh draw x ~ P_ref, the parent
returns a result at x and both its outputs lie in the band at x."** The coverage test of §6.4 adds: "and this frozen
band's coverage of P_ref is at least L with 95 % confidence."

The mandatory qualifications (strings in every manifest and every surrogate-backed run's limitation, ADR 0036 D6):

- Q1 `marginal over P_ref m04-c1-box7-v1; not pointwise`;
- Q2 `not at optimizer-selected or adaptively chosen points` (a solved loop's reactor inlet is one);
- Q3 `no claim outside the reference box or under distribution shift`;
- Q4 `relative to the parent at its design grid; excludes the parent's discretization bias DX-01 and says nothing
  about the physical reactor`;
- Q5 `joint over (X, dT) at one query; no simultaneous claim over several queries or several surrogate units`;
- Q6 `nominal 0.95 (finite-sample k/(n+1) = <value>); one-sided 95 % lower bound <L> from <m> independent test draws;
  declared minimum 0.90`;
- Q7 `no empirical validation (no plant or literature data)`;
- Q0, first when the parent is synthetic: `SYNTHETIC: certifies nothing about the reactor` (R-199).

### 6.4 The coverage test on the independent test set

Given the frozen band, the m test scores give H = #{j : s_j ≤ q̂} (a failed draw is a miss). Conditional on training
and calibration, H ~ Binomial(m, C) with C the band's coverage of P_ref, so the one-sided 95 % Clopper–Pearson lower
bound

  L(H, m) = B⁻¹(0.05; H, m − H + 1) (L(0, m) = 0)

is a 95 % lower confidence bound on C. **The decision is made in integers:** pass iff H ≥ h_min(m), the smallest h
with P(Binomial(m, 0.90) ≥ h) ≤ 0.05 — equivalent to L ≥ 0.90 and immune to the last digits of a beta quantile.
h_min(300) = 279 (L(279, 300) = 0.900761, L(278, 300) = 0.896939). A test set smaller than m_min = 29 cannot pass even
with no misses (L(29, 29) = 0.901855, L(28, 28) = 0.898534): INSUFFICIENT_EVIDENCE (`test_too_small`).

An observed coverage below 0.95 is not evidence that the guarantee failed (blueprint L419); the test is against the
declared minimum 0.90, and its power for a correct pipeline is 0.9035 at the registered plan.

## 7. Promotion criteria and verdicts

### 7.1 Criteria

A study is **PROMOTABLE** iff all of:

1. the plan is complete and was within budget;
2. the fit is identifiable (§3.4);
3. n ≥ 19 and m ≥ 29;
4. the band is finite and **q̂ ≤ 1** (width limits);
5. **H ≥ h_min(m)** (coverage bound ≥ 0.90);
6. every calibration and test prediction is admissible (§3.2) — an inadmissible prediction inside the reference box is
   a defect of the predictor, not an extrapolation;
7. every gradient centre is complete and **max e ≤ ρ_g = 0.25** (§7.2);
8. no registered draw was flagged `extrapolated` by the parent (the box is inside the data domain, so a flag means
   the variant's data domain differs from the one registered here — a finding, and an amendment).

Error metrics are reported, not judged: per output the test set's max |e|, RMS |e| and empirical 95th percentile of
|e|, the training RMS, and the fraction of test draws with s ≤ 1.

### 7.2 The gradient metric

At each gradient centre and for each output o, D_o,k = (f_o(s⁺_k) − f_o(s⁻_k)) / (z_k(s⁺_k) − z_k(s⁻_k)) is the
parent's central difference in scaled coordinates (z recomputed from the stencil requests by the input map), and

  e_o = ‖∇_z f̃_o(z_c) − D_o‖₂ / max(‖D_o‖₂, w_o).

*Step and floors.* h_z = 0.05 (a stencil spans 5 % of a half-width). The parent's iteration noise is ≤ 1.6 × 10⁻⁸
relative (M01.A42), so the difference carries ≈ 1.6 × 10⁻⁸ |f| / (0.1) ≈ 2.6 × 10⁻⁸ in ∂X/∂z against gradients of
order 10⁻², i.e. ≈ 3 × 10⁻⁶ relative; the truncation error h²|f‴|/6 is unknown for the reactor and is 3.5 × 10⁻⁶
relative on the smooth synthetic parent (asserted < 10⁻³). Both are four orders below ρ_g.
*Why 0.25.* When ‖D‖ ≥ w_o, e ≤ 0.25 bounds the angle between the surrogate's and the parent's gradients by
asin 0.25 = 14.5° and their magnitudes within ±25 %: the surrogate's descent directions are the parent's. Below w_o
per unit z a gradient is under the band's resolution and is judged absolutely (this also keeps the stand-in's
constant map, D = 0, well defined).

The gradient centres are drawn i.i.d. from the inner box and are labelled **gradient-check evidence at 5 random
points**; they carry no probability statement.

### 7.3 Verdicts and their precedence

The verdict function (`reference_values.json` → `verdict_vectors`, V01–V16) evaluates, in this order, and records
**every** reason it finds:

| Reason | List | Condition |
| --- | --- | --- |
| `budget_below_plan` | IE | cold experiments needed > approved (refused before running; nothing else evaluated) |
| `plan_incomplete` | IE | a registered draw without a deterministic result |
| `training_unidentifiable` | IE | N_ok < 36 or σ_min/σ_max < 10⁻⁸ |
| `calibration_too_small` | IE | k > n |
| `band_not_finite` | NP | q̂ = +∞ |
| `test_too_small` | IE | m < 29 |
| `width_limit_exceeded` | NP | q̂ > 1 |
| `coverage_bound_below_minimum` | NP | H < h_min(m) (not evaluated when `test_too_small`) |
| `gradient_check_incomplete` | IE | a centre with a failed stencil experiment |
| `gradient_limit_exceeded` | NP | max e > 0.25 |
| `inadmissible_prediction` | NP | an inadmissible calibration or test prediction |
| `parent_extrapolated` | NP | a registered draw flagged `extrapolated` |

Verdict: **INSUFFICIENT_EVIDENCE** if the IE list is non-empty; else **NOT_PROMOTABLE** if the NP list is non-empty;
else **PROMOTABLE**. Both lists are recorded whatever the verdict (V13), and every metric that can be computed is
computed — a failed study is still a complete record.

### 7.4 What a promoted surrogate may claim, and what it may not

May: the band and its coverage statement of §6.3 with Q1–Q7, the error metrics on the test set, the gradient agreement
at five random points, exact element conservation, and the hard-domain and admissibility guards.
May not: coverage at a flowsheet's solved operating point or an optimizer's candidate (Q2 — that needs a parent
evaluation, labelled `targeted_check`, M05/M07); coverage outside the box; anything about the physical reactor or
plant data; simultaneous coverage over several units or queries; sensitivities of the flowsheet as the *reactor's*
sensitivities (they are the surrogate-backed flowsheet's; M03 C3 currently refuses EO-path sensitivities anyway).

## 8. The surrogate in a flowsheet; promotion and rollback (ADR 0037)

### 8.1 A native unit, not an experiment provider

`c1.reactor_surrogate` enters `MODEL_BUILDERS` with the rows of §3.2 and the instance configuration N_tubes (as
M02's embedded unit; the surrogate's input F = n_tot/N_tubes). Its ModelManifest: `execution_class`
`explicit_reduced`; `evaluation_cost_class` `cheap`; ports, components and accumulation declarations identical to
M02's embedded unit; `derivatives` = residuals w.r.t. free variables `analytic` and **outlet.state w.r.t.
inlet.state `analytic`**, with the note "derivative of the surrogate; agreement with the parent is the gradient
metric of its manifest"; validity = the parent's hard domain; limitations = Q0 (if synthetic) and Q1–Q7. A revision
bound to it solves on the existing `revision_eo` route: no outer coupling, no experiment, the surrogate frozen for the
solve because its coefficients are compile-time constants of an instance pinned by hash.

**Rejected: the surrogate as the experiment inside M02's coupling loop.** The coupled route refuses every sensitivity
(ADR 0034 D4), so the surrogate's one structural advantage — an analytic derivative — would be thrown away; an outer
Broyden iteration around an analytic map solves by fixed point what Newton solves directly; and the loop exists to
call the parent, which is what a truth check (M05/M07) does, not what a promoted surrogate is for.

### 8.2 Identity and resolution

For a surrogate instance, `model.id` = `c1.reactor_surrogate`, `model.version` = the surrogate id
(`m04q7-<parent variant id>-<plan id>`, e.g. `m04q7-standin-x025-v1-it1-prefix`), `model.artifact_ref` = the SHA-256
of the canonical SurrogateManifest. The binder resolves the manifest by hash from the project's artifact store (kind
`surrogate_manifest`, written by a completed `surrogate_study` job) through an injected resolver (R-237's pattern) and
refuses an unknown id, a mismatched hash or a manifest that fails its checker (A24) as `revision_unsupported`,
`surrogate_manifest_mismatch(<instance>)`.

### 8.3 The replacement check for a surrogate side (amends ADR 0035 D2)

The check runs when either side is variant-backed **or surrogate-backed**. For a surrogate side, the facets read the
manifest; `parent` is the manifest's `parent` block (model id, variant id, variant SHA-256, and a verbatim copy of the
variant's `boundary` block):

| Facet | For a surrogate side |
| --- | --- |
| `resolvable` | in `MODEL_BUILDERS`, manifest resolves by hash and passes its checker |
| `ports`, `components`, `conserved_quantities`, `degrees_of_freedom`, `reference_states` | as ADR 0035 (the declarations equal M02's embedded unit's) |
| `boundary_condition` | the manifest's `parent.boundary` is the side's variant boundary block; compared as ADR 0035 |
| `derivatives` | as ADR 0035, **except** old = surrogate S and new = S's parent exactly (id, variant id, SHA-256): the parent's `unavailable` outlet-w.r.t.-inlet derivative is not a loss; `pass`, detail `restores_parent_declaration` |
| `validity` | the manifest's hard domain (= the parent's) |
| **`surrogate_evidence`** (new) | `not_applicable` when neither side is a surrogate. New = surrogate S: `pass` iff S's verdict is PROMOTABLE (re-derived by the checker from the stored scores, not read from a field) **and** old is S's parent exactly or a surrogate with the same parent; details `verdict=<v>`, `parent_mismatch`. New = non-surrogate and old = surrogate S: `pass` iff new is S's parent exactly (rollback), else `fail` (`replace_via_parent`). |

`model-replacement.schema.json`'s facet enum gains `surrogate_evidence` (additive). `synthetic` stays reported, not
judged.

### 8.4 Failed promotion, rollback, invalidation

- **Failed promotion** (NOT_PROMOTABLE or INSUFFICIENT_EVIDENCE, or any failed facet): the transaction is `rejected`
  (`model_replacement_incompatible`), the head revision is unchanged, and the study's manifest, evidence and
  experiment records remain as immutable artifacts.
- **Rollback** is a checked commit back to the parent (the derivatives exception above) or to an earlier surrogate of
  the same parent. Experiment records are never invalidated (ADR 0035 D4), so a coupled solve after a rollback reuses
  every experiment the same revision content ran before.
- **Invalidation** is ADR 0035 D4's rule unchanged: promotion and rollback commits invalidate the `run-` jobs of the
  expected revision. A `surrogate_study` job is scoped to a variant, not a revision, and is **not** registered in
  `EVIDENCE_OPERATIONS`: its evidence is about the parent's map and survives every revision change.

### 8.5 The seam: what M04 delivers and what M05 does

M04 delivers the surrogate unit, its evidence, promotion and rollback, and the run limitations. M05 decides whether
and how its trust region uses it (as the reduced model, as a warm start for the coupling's w, or not at all), owns
every parent-model check at a candidate (`targeted_check`, labelled separately from the coverage evidence), and owns
refinement loops beyond §5.5's iterations.

### 8.6 What a surrogate-backed run reports (no schema change)

The certificate gains, per surrogate unit: the check `SURROGATE-DOMAIN:<unit>` (category `bounds_and_domain`, value =
the scaled excess e(z), tolerance null, `pass` iff hard-domain and admissible); the limitation
`{kind: "surrogate_model", unit, surrogate_id, manifest_sha256, band: {X: q̂ w_X, dT_K: q̂ w_ΔT}, coverage: {nominal,
finite_sample, lower_bound, minimum, test_draws}, qualifications: [Q0…Q7]}`; and, when e(z) > 0,
`{kind: "surrogate_outside_reference_domain", unit, scaled_excess, coordinates}`. The band is a constant offset for
split conformal with fixed scales, so it needs no per-point field. Limitations are open objects keyed by `kind`
(`solution-certificate.schema.json`), so nothing in a frozen schema changes.

## 9. Verification on synthetic parents

### 9.1 The parents

- **The stand-in** `standin-x025-v1` (M01 spec §8.13, shipped, synthetic): X ≡ 0.25, ΔT ≡ 0. Registered *because* its
  residuals vanish: the fit is exact (β_X = 0.25 e₀, β_T = 0), q̂ is at roundoff, and no statistical outcome is
  asserted (the order statistic of roundoff-level scores is not a closed form).
- **Two test-only in-process variants** (in `tests/support`, never shipped, `synthetic: true`, boundary block equal to
  the stand-in's), evaluating per tube with z from the tube's (F, y, T, P):

  X = 0.16 · exp(A · a·z), ΔT = 80 K · exp(A · b·z),
  a = (−0.06, 0.04, 0.03, −0.05, −0.01, −0.015, −0.08), b = (−0.10, 0.03, 0.02, −0.04, −0.01, −0.01, −0.04),

  returning raw outlet flows n_raw = n_tube + ν X n_N₂,tube and T_out = T + ΔT, and `NotAccepted("synthetic_failure_region")`
  iff z_T + z_F > 1.6. `m04-synthetic-smooth-v1` has A = 1, `m04-synthetic-rough-v1` A = 4. The failure threshold was
  chosen, before any score was computed, so that the full plan has failures in every split; no registered request lies
  within 0.0167 of it.

The smooth parent is not a quadratic, so residuals are non-zero (training RMS 1.20 × 10⁻⁵ in X, 4.40 × 10⁻³ K in ΔT)
and every statistic is non-trivial; it is exactly computable, so every statistic has a closed-form expectation.

### 9.2 Registered expectations (`reference_values.json` → `pipeline`)

| Case | Failures (train / cal / test) | N_ok | q̂ | H / m | L | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| smooth, full plan | 2 / 3 / 13 | 142 | 0.0224401743 | 283 / 300 | 0.916211 | **PROMOTABLE** |
| smooth, prefix plan | 1 / 1 / 0 | 71 | 0.0249160653 | 59 / 60 | 0.923360 | **PROMOTABLE** |
| rough, prefix plan | 1 / 1 / 0 | 71 | 1.6139880778 | 59 / 60 | 0.923360 | **NOT_PROMOTABLE** [`width_limit_exceeded`] |
| stand-in, prefix plan | 0 / 0 / 0 | 72 | 0 (roundoff) | — | — | not asserted |

Max gradient error: smooth full 0.00403, smooth prefix 0.00340, rough prefix 0.0721 (all below 0.25). Margins that
make the integer outcomes exact in binary64: smooth full — nearest test score to q̂ 6.85 × 10⁻⁴, neighbouring order
statistics 3.52 × 10⁻³ apart, q̂ 0.978 from the width limit; rough — 0.136, 0.093 and 0.614.

### 9.3 The prefix plan

The first 72 training, 39 calibration (k = 38) and 60 test draws and the first 2 gradient centres of iteration 1
(28 stencil experiments; 199 experiments in all) — an i.i.d. prefix is i.i.d. It keeps the default gate cheap for the
cases that do not need the full plan's power.

## 10. Records and the job operation

### 10.1 `SurrogateManifest` (`schemas/surrogate-manifest.schema.json`, `surrogate-manifest-v1`)

Blueprint App. A: "parent model, input/output mapping, splits, transforms, error/gradient metrics, domain, calibration
assumptions, promotion result". Members (all required; `additionalProperties: false` throughout):

- `schema_version`, `surrogate_id`, `model_id` (`c1.reactor_surrogate`), `synthetic` (= the parent's), `iteration`,
  `plan_id`, `predecessors` (manifest SHA-256s of earlier iterations, in order);
- `parent`: `{model_id, variant_id, variant_sha256, fingerprint_sha256s, boundary}` — `boundary` the variant's block
  verbatim; `fingerprint_sha256s` the distinct environment fingerprints of the records used;
- `input_map`: `{id: "c1-inlet-u7-v1", coordinates: [{name, unit, lo, hi, centre, half_width}] ×7}`;
- `output_map`: `{id: "extent-fixed-xdt-v1", outputs: ["X", "dT_K"], admissible: {X: [0, 0.95], X_le_r_over_3: true,
  dT_K: [-50, 250]}}`;
- `predictor`: `{basis: "full-quadratic-v1", terms: 36, coefficients: {X: [36], dT_K: [36]}, fit: {method:
  "householder-qr-v1", training_ok, singular_value_ratio, training_rms: {X, dT_K}}}`;
- `score`: `{id: "joint-max-scaled-abs-v1", scales: {X: 0.0025, dT_K: 1.5}}`;
- `reference_distribution`: `{id: "m04-c1-box7-v1", kind: "uniform_box", sampler: "splitmix64-u53-v1", seeds}`;
- `splits`: per split `{count, keys: [experiment_key] in plan order, keys_sha256, failed: [{index, status, code}]}`;
  the gradient split also `{centres: [{index, status, stencil_keys}]}`;
- `calibration`: `{alpha: "1/20", n, k, scores: [number | null], q_hat: number | null}`;
- `evaluation`: `{m, scores: [number | null], hits, lower_bound: number | null, h_min, c_min: 0.9, delta: 0.05,
  errors: {X: {max, rms, p95}, dT_K: {...}}, fraction_within_width}`;
- `gradient`: `{step_z: 0.05, rho_g: 0.25, centres: [{index, status, errors: {X, dT_K} | null}]}`;
- `domain`: `{empirical: "box", hard: <parent hard domain>, inadmissible_predictions, parent_extrapolated}`;
- `assumptions`: the fixed list — exchangeability from i.i.d. draws of P_ref, predictor/transform/score frozen before
  calibration, failures scored +∞, deterministic parent within one fingerprint;
- `qualifications`: Q0 (if synthetic) and Q1–Q7, with Q6's values filled;
- `promotion`: `{verdict, insufficient: [..], not_promotable: [..], familywise_false_pass_bound}`;
- `evidence_sha256`: the ModelEvidence document's hash.

No non-finite number is serialized: a failed draw's score and an infinite q̂ are `null`, the reason in `failed` or in
`promotion`. Rules a JSON Schema cannot express are a checker (A24) that the replacement check also runs.

### 10.2 `ModelEvidence` (`schemas/model-evidence.schema.json`, `model-evidence-v1`)

Blueprint App. A: "parent/data hashes, numerical convergence, experimental/reference comparisons, uncertainty and
validation scope". A scope record that points into the manifest rather than repeating it:

- `schema_version`, `subject` `{model_id, version, artifact_ref}` (the surrogate), `parent` `{model_id, variant_id,
  variant_sha256, synthetic}`;
- `data`: `[{split, count, keys_sha256}]` — equal to the manifest's (A23);
- `numerical`: `{parent_accuracy: <the variant's accuracy block: precision floor, path independence, discretization
  estimate>, fit: {training_ok, singular_value_ratio}}`;
- `comparisons`: `[{reference: "parent_model", quantity: "surrogate approximation error", split: "test", pointer:
  "/evaluation"}]`;
- `experimental_comparisons`: `[]` with the required `experimental_comparisons_reason`: "none: no plant or literature
  data (M04 scope)";
- `uncertainty`: `{method: "split-conformal-default-v1", claim: "joint, marginal over P_ref", nominal: 0.95,
  lower_bound, minimum: 0.9}`;
- `scope`: `{evidence_class: "synthetic_verification" | "model_approximation", establishes: [..], does_not_establish:
  [..]}` — the two lists are §7.4's.

### 10.3 The `surrogate_study` job operation (ADR 0019 Amendment 5, in ADR 0037)

Right `execute`. Request `{parent: {model_id, variant_id, variant_sha256}, plan_id: "it1" | "it1-prefix" | "it<i>",
budget: {max_cold_experiments}}`. `it1-prefix` (§9.3) is accepted only for a synthetic parent. For `it<i>`, i ≥ 2, the
training set is every `ok` P_ref record of `it1` … `it<i−1>` of the same parent (§5.5). It runs the plan's experiments through M02's runner one by one (cache first; M02 D12
left batch sampling to M04), then fits, calibrates, tests, checks gradients, writes the manifest and the evidence as
artifacts (kinds `surrogate_manifest`, `model_evidence`), and returns `{verdict, surrogate_id, manifest_sha256,
evidence_sha256, cold_experiments, cache_hits}`. A cancelled job keeps its experiment artifacts; resuming re-reads them
through the cache. Determinism: with every record cached, the manifest is bitwise reproducible (A32).

## 11. Assertions

Tolerances state their floor and why they sit above it and below the smallest error worth catching. "Registered" means
`reference_values.json` or `plan-it1.json`. Default gate = `./scripts/check.sh`; opt-in = recorded in the evidence
manifest with its command, never in the default gate.

**Plan and sampler (default gate)**

- **M04.A01** — SplitMix64's first three words for each iteration-1 seed equal `splitmix64_first_words` exactly
  (integers).
- **M04.A02** — The production sampler and request builder reproduce every `u` and every request (n, T, P) of
  `plan-it1.json` **bitwise** (562 draws, 5 centres, 70 stencils), and the 632 experiment keys are distinct. Exact:
  identity is exact (ADR 0033), so any difference is a different experiment.
- **M04.A03** — A plan any of whose requests leaves the box, the hard domain or the data domain is refused at study
  start (`plan_invalid`, nothing executed): checked with a copy of the plan with one T set to 700.0 K. The plan
  `it1-prefix` requested for a non-synthetic parent is refused (`plan_not_registered_for_parent`).

**Finite-sample rule and verdicts (default gate, pure functions)**

- **M04.A04** — k(n) equals `finite_sample.k` for every registered n, computed in integers; n_min = 19.
- **M04.A05** — q̂ on each verdict vector equals the registered value **exactly** (it is an element of the input), with
  `null` as +∞; a band is absent exactly where registered (V02, V04).
- **M04.A06** — L(h, m) matches `finite_sample.clopper_pearson` within 10⁻⁹ absolute (floor: `scipy.stats.beta.ppf`
  agrees with the 50-digit values to ≤ 10⁻¹⁵ on the registered table, measured; ceiling: no registered L lies within
  7 × 10⁻⁴ of 0.90, generator-asserted, and one hit moves L by ≥ 3 × 10⁻³); `finite_sample.h_min` (29 → 29, 60 → 59,
  300 → 279) and m_min = 29 exactly; the pass decision is H ≥ h_min(m).
- **M04.A07** — Every vector V01–V16 yields exactly the registered verdict and both registered reason lists in the
  registered order (all three verdicts and every reason of §7.3 are reached).
- **M04.A08** — A manifest's `calibration.k`, `evaluation.h_min`, n and m equal the plan's registered values (118,
  114, 300, 279 for `it1`; 39, 38, 60, 59 for `it1-prefix`) — no denominator is narrowed.

**The surrogate function (default gate)**

- **M04.A09** — φ(z*) at the registered z* equals `basis_at_zstar.phi` within 10⁻¹⁴ relative per entry (floor: two
  roundings of decimal z* ≈ 2 × 10⁻¹⁶; a permuted order changes entries by O(1)).
- **M04.A10** — On the smooth full training set the coefficients equal `pipeline.smooth_full.coefficients` within
  10⁻¹⁰ × ‖β_ref‖∞ per output, and the singular-value ratio within 10⁻⁸ relative. Floor: κ = 8.1 times binary64
  roundoff of the records (ΔT's ulp 1.1 × 10⁻¹³ K at 750 K) ≈ 10⁻¹⁴ relative. Ceiling: the smallest coefficient is
  1.3 × 10⁻⁶ of the largest and all coefficients differ pairwise by more than 10⁻⁸ of it (generator), so a dropped or
  permuted term fails by four orders.
- **M04.A11** — The prefix training set with every F set to the box centre (z₇ ≡ 0) is refused
  `training_unidentifiable` (σ ratio < 10⁻⁸; exactly rank-deficient by two columns).
- **M04.A12** — At J1–J3 with the fixture coefficients: the 14 inlet entries of R_ξ and R_T equal `jacobian_states`
  within 10⁻¹⁰ relative per entry; the ξ and T_out columns are exactly (1, 0) and (0, 1); the rows vanish at the
  registered causal outlet within 10⁻¹⁵ relative to (n_tot, T). Floor: cancellation ≤ 4.45 × ~250 terms × 1.1 × 10⁻¹⁶
  ≈ 10⁻¹³.
- **M04.A13** — Conservation: at J1–J3 and at every surrogate-backed solution of A26, |E(n_out − n_in)| ≤
  10⁻¹⁴ n_tot,in per element and the inert flows are bitwise equal in and out.
- **M04.A14** — Domain: J1, J2 `within_reference_domain` (excess 0); J3 `outside_reference_domain`, excess 0.5 within
  10⁻¹², offending coordinate `T`; J4 refused `surrogate_outside_hard_domain(<unit>:T)`; J5 refused
  `surrogate_input_undefined`; J6 ξ = 0 and T_out = T_in exactly.
- **M04.A15** — Admissibility (fixture manifests with constant predictors, every other coefficient 0): β_X[0] = −0.01
  refused `surrogate_output_inadmissible(<unit>:X)` at J1; β_X[0] = 0.96 likewise; β_X[0] = 0.5 at J1's flows with
  n_H₂ replaced by 1.2 n_N₂ (H₂/N₂ = 1.2 inside the hard domain, r/3 = 0.4 < 0.5) likewise — the H₂ bound, which a
  [0, 0.95]-only check misses — while β_X[0] = 0.5 at J1 itself is admitted; β_T[0] = 260 refused
  `(<unit>:dT)`.

**The study end to end (default gate, in-process parents)**

- **M04.A16** — Stand-in, prefix plan: no failures; β_X[0] = 0.25 within 10⁻¹⁴ and every other β_X within 10⁻¹⁴;
  β_T = 0 within 10⁻¹² K; q̂ ≤ 10⁻¹⁰; the manifest carries Q0 first and `evidence_class: synthetic_verification`.
  Floor 2.2 × 10⁻¹⁴ (one ulp of 0.25 over w_X); the smooth case's q̂ = 0.0224 shows the same quantity non-vanishing.
- **M04.A17** — Smooth, full plan: failed indices per split exactly as registered; N_ok = 142; coefficients per A10;
  q̂ within 10⁻¹⁰ absolute of 0.022440174316072; **H = 283 exactly**; L within 10⁻⁹ of 0.916211187; every gradient
  error within 10⁻⁸ absolute of its registered value; verdict PROMOTABLE with both reason lists empty. Floors: scores
  ≈ 10⁻¹³ (A10's record roundoff over w); gradient errors ≈ 10⁻¹²; the integer H is exact because no test score lies
  within 6.85 × 10⁻⁴ of q̂.
- **M04.A18** — Rough, prefix plan: q̂ within 10⁻⁹ relative of 1.6139880778; H = 59; verdict NOT_PROMOTABLE with
  `not_promotable == ["width_limit_exceeded"]`.
- **M04.A19** — Smooth, prefix plan: q̂ within 10⁻¹⁰ of 0.024916065269; H = 59 (= h_min(60): one miss allowed, one
  taken — the integer count is exact, the nearest test score being 3.2 × 10⁻³ from q̂); verdict PROMOTABLE. (This manifest is
  the promoted surrogate of A25–A29 and the source of the schema fixtures.)
- **M04.A20** — Budget: on a store without records, the smooth prefix study with `max_cold_experiments` = 198 (one
  below its 199 cache misses) ends INSUFFICIENT_EVIDENCE `["budget_below_plan"]` with zero attempts written; on A19's
  store (all 199 records cached), `max_cold_experiments` = 0 reproduces A19's manifest bitwise (A32's rule) with zero
  new attempts.
- **M04.A21** — Plan incomplete: a variant of the smooth test-only parent that returns `ExecutionFailure` (transient,
  M02 design note §5.1) for one designated stencil request, on every attempt, ends the prefix study
  INSUFFICIENT_EVIDENCE with `plan_incomplete` in the IE list and that request named; no run of an incomplete plan is
  ever PROMOTABLE.
- **M04.A22** — Every registered failure of A17 is in its split's `failed` list with status `not_converged` and code
  `reactor_not_accepted(synthetic_failure_region)`, a `null` score, and no outlet values in its experiment result; the
  manifest's n = 118 and m = 300.
- **M04.A23** — Split integrity: the key lists are pairwise disjoint, equal the plan's request keys in plan order, and
  their SHA-256s equal ModelEvidence's `data`; refitting from the listed training records reproduces the coefficients
  bitwise.
- **M04.A24** — The manifest checker accepts A17's manifest and rejects each single mutation: q̂ not the k-th
  smallest stored score; H ≠ #{score ≤ q̂}; a verdict inconsistent with the stored metrics; a missing qualification;
  a qualification with an unfilled `<…>` field; overlapping splits; n or m different from the plan's counts; a
  non-finite number.

**Promotion and rollback (default gate, the synthetic loop)** — a project whose C1 loop revision binds the reactor to
`m04-synthetic-smooth-v1` (as M02 G8 binds its test-only variant), solved once on the coupled route.

- **M04.A25** — Committing the A19 surrogate in place of its parent: `committed`; every facet `pass`, including
  `surrogate_evidence` and `derivatives`; `invalidations == ["run-<that job>"]`; the report's SHA-256 in the new
  revision's provenance.
- **M04.A26** — The surrogate-backed revision solves on `revision_eo` (not `revision_coupled`) with zero experiment
  attempts and a certificate; at the solution the rows of §3.2 hold to the solve's registered tolerance and A13 holds;
  the certificate carries `SURROGATE-DOMAIN:<unit>` and the `surrogate_model` limitation with band
  (q̂ w_X, q̂ w_ΔT) = (6.22902 × 10⁻⁵, 0.0373741 K) within 10⁻¹⁰ relative (`pipeline.smooth_prefix.band`) and Q0–Q7.
- **M04.A27** — Committing the A18 (rough) surrogate instead: `rejected`, `model_replacement_incompatible`,
  `surrogate_evidence` `fail` with detail `verdict=NOT_PROMOTABLE`; the head revision unchanged; `preview_change`
  returns the same report and commits nothing.
- **M04.A28** — Committing a surrogate of the stand-in in place of the synthetic parent: `surrogate_evidence` `fail`,
  detail `parent_mismatch` (whatever that surrogate's verdict).
- **M04.A29** — Rollback: committing the parent in place of the A25 surrogate: `committed`; `derivatives` `pass` with
  detail `restores_parent_declaration`; a coupled solve of the rolled-back revision writes **zero** new attempts (every
  experiment a cache hit).
- **M04.A30** — Committing the A17 (full-plan) surrogate in place of the A19 one: `committed`; `surrogate_evidence`
  `pass` (same parent).

**The real reactor (opt-in, after M02 WO-5; recorded, never in the default gate)**

- **M04.A31** — Iteration 1 on the real variant: every executed request is bitwise a request of `plan-it1.json`; the
  manifest and evidence validate and pass the checker; the verdict and every metric of §7 are recorded, whatever the
  verdict; `parent_extrapolated` is 0 or reported as a finding.
- **M04.A32** — Re-running the study with every record cached reproduces the manifest bitwise (job ids and timestamps
  are not members of it) with zero cold experiments.
- **M04.A33** — If A31 is PROMOTABLE: A25, A26 and A29 on `C1-LOOP-M02-v1` with `c1.reactor`, plus one parent
  evaluation at the surrogate-backed solution's reactor inlet recorded as `targeted_check` with |e_X|/w_X and
  |e_ΔT|/w_ΔT — reported, not judged (blueprint L415; Q2).

**Generator and schemas (default gate)**

- **M04.A34** — `python docs/derivations/scripts/m04_reference.py --check` exits 0 with every claim passing and both
  files byte-identical.
- **M04.A35** — `surrogate-manifest` and `model-evidence` are in `schemas/registry.json`; one valid fixture each,
  emitted from A19's run, and one invalid each (a required member removed); `model-replacement`'s facet enum contains
  `surrogate_evidence`.

## 12. Reference generator and files

`docs/derivations/scripts/m04_reference.py` imports nothing from `openflowsheet`; mpmath at 50 digits; the
least-squares expectations by normal equations at 50 digits (κ² ≈ 66, so ~48 correct digits); the Clopper–Pearson
bound by bisection on the regularized incomplete beta; the power by the beta-binomial sum. It emits
`benchmarks/m04/reference_values.json` (constants, sampler words, finite-sample numbers, verdict vectors, basis, fixture
coefficients, Jacobian states, the four pipeline cases, the claim list) and `benchmarks/m04/plan-it1.json`. It refuses
to emit when any claim fails. Runtime ≈ 26 s.

## 13. Work orders (build lane, in dependency order)

"Opus" = `opus-engineer`; "bounded" = a `sonnet-implementer` may take it from this document alone; **R** = design-lane
review before merge (it touches residuals, derivatives, promotion or the statistical semantics).

| WO | Lane | Content | Depends on | Acceptance |
| --- | --- | --- | --- | --- |
| WO-1 | bounded | `studies/surrogate/plan.py`: seeds, SplitMix64, U, the box and inner box, stencils, requests; the plan-invariant guard | — | A01–A03 |
| WO-2 | Opus, R | `studies/surrogate/conformal.py`: integer k, the order-statistic q̂ with +∞, h_min / m_min, Clopper–Pearson (SciPy), the verdict function and reason order | — | A04–A08 |
| WO-3 | Opus, R | `studies/surrogate/quadratic.py`: input map, basis, QR fit, identifiability, prediction, ∇_z, the chain rule to the inlet, admissibility, domain status | — | A09–A11 |
| WO-4 | Opus | Test-only parents in `tests/support` (smooth, rough) as in-process variants | M02 WO-4, WO-6 merged | used by A16–A23 |
| WO-5 | Opus, R | The `surrogate_study` job operation: plan keys, cache-miss budget refusal, sequential experiments through M02's runner, fit/calibrate/test/gradient, manifest + evidence + checker; ADR 0019 Amendment 5 surface | WO-1–WO-4 | A16–A24 |
| WO-6 | Opus | Schemas, registry, fixtures emitted from A19's run | WO-5 | A35 |
| WO-7 | Opus, R | The unit `c1.reactor_surrogate`: rows, analytic Jacobian, causal evaluate, dormancy, refusals, certificate check and limitations; binder resolution by hash (injected resolver) | WO-3, WO-5; M02 WO-7 (embedded unit) | A12–A15, A26 |
| WO-8 | Opus, R | Replacement check: the surrogate side, `surrogate_evidence`, the rollback exception, the schema enum | WO-7; M02 WO-11 | A25, A27–A30 |
| WO-9 | Opus | The synthetic-loop end-to-end tests | WO-8; M02 WO-8/9 | A25–A30 |
| WO-10 | bounded | A test running the generator's `--check` | — | A34 |
| WO-11 | Opus, opt-in | Iteration 1 on the real variant (≈ 95 min), its evidence; if PROMOTABLE, A33 | WO-5, WO-8; M02 WO-5 | A31–A33 |
| WO-12 | bounded | Evidence manifest `evidence/M04/<commit>/manifest.json` with the W23 table (§15), register pointers | all | — |

WO-1, WO-2, WO-3 and WO-10 need nothing from M02 and can start now.

## 14. Open questions, with defaults

- **N1 — the experiment budget** *(needs Frank: local machine time).* DECISION: approve 632 cold experiments
  (≈ 95 min on one thread) for iteration 1, and up to two further iterations of 488 each (≈ 73 min) under §5.5's
  rules — at most ≈ 4 h in all. Alternative: iteration 1 only, any further iteration by a new approval. Reversible by:
  lowering `max_cold_experiments` in the job request; a refused budget yields INSUFFICIENT_EVIDENCE, never a partial
  study.
- **N2 — the width limits** *(needs Frank's preference: what error is worth catching).* DECISION: w_X = 0.0025,
  w_ΔT = 1.5 K (inside DX-01's ranges). Alternative: tighter (1 %, 1 K) at a higher risk of `width_limit_exceeded`,
  or looser (3 %, 3 K) for a band that dominates the parent's bias. Reversible by: an amendment *before* iteration 1
  runs (the score is frozen before calibration; changing it afterwards is tuning on the test set).
- **N3 — the gradient criterion** *(needs Frank's preference).* DECISION: ρ_g = 0.25 at 5 centres. Alternative:
  report-only. Reversible by: an amendment before iteration 1 runs.
- **N4 — the reference box** *(needs a fact: the C1 loop's operating region, M05/M07).* DECISION: the box of §3.1.
  The fact that settles it: the reactor inlet of M02's `C1-LOOP-M02-v1` solved with the real reactor (M02 G12) and M07's
  decision range for T_in. If the loop's inlet lies outside the box, register a new box (and a new P_ref id) by
  amendment before iteration 1. Reversible by: amendment; nothing has run.
- **N5 — sequential versus concurrent experiments** *(needs a fact: whether M02's runner tolerates concurrent jobs on
  one variant).* DECISION: sequential (95 min). Alternative: k workers, ≈ 95/k min; results are unaffected (exact
  identity, deterministic parent). Reversible by: a runner option; no record changes.
- **N6 — the real verdict and the critical path** *(needs a fact: iteration 1's outcome).* DECISION: M04 is `tested`
  when A01–A35 hold, whatever A31's verdict; a NOT_PROMOTABLE real surrogate is recorded as a measured limitation and
  M05 proceeds with the parent (its trust region composes the reactor itself, ADR 0034). Alternative: hold M05 until a
  real surrogate is promoted. Reversible by: Frank's ruling.

## 15. The W23 gate table (for the `verdict` agent)

| W23 item | Evidence | Assertions |
| --- | --- | --- |
| Conservation | exact by construction; checked at fixtures and at surrogate-backed solutions | A13, A26 |
| Domain (hard, empirical, admissibility) | refusals and flags at registered states; per-draw domain records | A03, A14, A15, A31 |
| Derivative | the unit's Jacobian against closed forms; the gradient metric against the parent | A12, A17, A31 |
| Default UQ | the finite-sample rule, the verdict function, the full synthetic pipeline with closed-form expectations; the real iteration recorded | A04–A08, A16–A24, A31, A32 |
| Insufficient-data outcome | budget, incomplete plan, small n/m, unidentifiable fit | A07, A11, A20, A21 |
| Frozen splits/transforms | the registered plan reproduced bitwise; split integrity; determinism | A01, A02, A23, A32 |
| Promotion and rollback | checked commits with the new facet; rejection; lineage; rollback with cache reuse | A25–A30, A33 |

W23 is **met** on numerical verification when A01–A30, A34, A35 are `tested` in the default gate and A31–A32 are
recorded for the real variant; what the real surrogate may claim is then whatever its recorded verdict says. A
PROMOTABLE real verdict is not part of W23 (N6).

## 16. Decisions taken in this specification

- DECISION: surrogate as a native EO unit → `c1.reactor_surrogate`. Alternative: the experiment inside M02's coupling.
  Reversible by: ADR 0037 D1 superseded (R-240).
- DECISION: inputs → seven coordinates (T, P, r, y_NH₃, y_Ar, y_CH₄, F), affine scaling to the box. Alternative: five
  (one lumped inert, fixed P). Reversible by: a new input-map id (R-241).
- DECISION: outputs → (X, ΔT), M02's coupling coordinates; admissibility refused, never projected. Alternative: ξ in
  mol/s; clipping. Reversible by: a new output-map id (R-241).
- DECISION: P_ref → uniform on the box of §3.1. Alternative: the data domain. Reversible by: amendment before
  iteration 1 (R-242).
- DECISION: score → joint max with scales = width limits. Alternative: two scalar scores labelled marginal.
  Reversible by: amendment before iteration 1 (R-243).
- DECISION: failed draws → +∞ in calibration and test, excluded from training; no result → plan incomplete.
  Alternative: exclude failures and condition the claim on success. Reversible by: ADR (R-244).
- DECISION: plan → (144, 118, 300, 5 × 14), power 0.9035. Alternative: (149, 400), power 0.901 at +86 experiments.
  Reversible by: amendment before iteration 1 (R-245).
- DECISION: promotion → integer coverage test H ≥ h_min, q̂ ≤ 1, admissibility, gradient ≤ 0.25; verdict precedence
  IE > NP. Alternative: observed coverage ≥ 0.95. Reversible by: ADR (R-246).
- DECISION: empirical domain → the box, flagged with its scaled excess. Alternative: convex hull, NN density,
  leverage. Reversible by: a new criterion id (R-247).
- DECISION: replacement check → new facet `surrogate_evidence`, rollback exception in `derivatives`. Alternative: a
  separate `promote_surrogate` operation. Reversible by: ADR 0037 superseded (R-248).
- DECISION: iterations → fresh calibration/test, previous P_ref records join training, automatic only after a
  coverage-only failure, at most 3, family-wise bound reported. Alternative: re-test the same predictor on a new test
  set. Reversible by: ADR (R-249).

## 17. What M04 does not establish

- **Nothing about the physical reactor.** Every number is relative to the parent at num_z = 800, whose own bias
  (DX-01) is estimated, not bounded, and excluded from the band (Q4).
- **No pointwise or conditional accuracy.** The band covers 95 % of P_ref marginally; at a particular inlet — in
  particular a solved loop's or an optimizer's — it may not (Q1, Q2). Truth there is a parent evaluation.
- **No claim outside the box or under shift** (Q3); a loop driven outside it gets a limitation, not a band.
- **No simultaneous claim** over several surrogate units, several solves, or both outputs at several points (Q5).
- **No empirical validation** (Q7) and no optimality evidence.
- **The synthetic cases verify the pipeline, not the reactor surrogate.** A16–A30 are numerical verification on
  parents whose answers are exact; their PROMOTABLE verdicts say nothing about whether the real surrogate will be. They
  are never cited as validation of `c1.reactor_surrogate` on `c1.reactor`.
- **The gradient metric is five random points**, not a bound on the derivative error anywhere.
- **The power figure 0.9035** is the probability that a correct pipeline passes the coverage test; it is not the
  probability that the real surrogate is promoted (that also needs q̂ ≤ 1, which depends on the reactor).
- **No sensitivity of the flowsheet** is established by the surrogate's analytic derivative (M03 C3 refuses EO-path
  sensitivities; M05 decides their use).
- **Iteration 1 has not run.** The plan is registered; its outcome is unknown at this commit.
