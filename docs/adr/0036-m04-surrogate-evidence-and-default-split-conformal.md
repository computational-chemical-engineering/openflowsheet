# ADR 0036 — M04: a registered uniform reference box, a plan registered before the parent runs, joint split-conformal with width limits as scales, and promotion decided by an integer coverage test

**Status:** Proposed, 2026-10-08. Accepted when M04's evidence manifest is `tested` for M04.A01–A24 and A34 of the
specification and the design-lane review of WO-2, WO-3 and WO-5 has closed its must-fix items.
**Author:** design lane (`specifier`), M04; brief `docs/briefs/M04-specification.md`.
**Normative text:** `docs/derivations/M04-spec.md` §3.4, §3.6, §4–§7, §11; expectations
`benchmarks/m04/reference_values.json` and the registered plan `benchmarks/m04/plan-it1.json` from
`docs/derivations/scripts/m04_reference.py`.
**Amends:** nothing. **Reverses:** nothing.
**Affected requirements:** A07 (registered reference distribution, frozen predictor, independent splits), D12
(independent calibration/test, qualified coverage/error evidence), W23; blueprint §9.1–§9.3.
**Affected packages:** M04; M05 and M07 (inherit the claim and its qualifications); any later surrogate (the
vocabulary of D5–D6).
**Register:** R-241 (inputs/outputs), R-242 (D1), R-243 (D4), R-244 (D3), R-245 (D2), R-246 (D5), R-247 (D7),
R-249 (D2 iterations).

## Context

Blueprint §9.2 makes split-conformal the Default for surrogate prediction error and lists what must hold for the claim
to mean anything: a registered, process-relevant reference distribution; predictor, transforms and score frozen before
calibration; disjoint calibration and test sets drawn i.i.d.; the finite-sample rule recorded; a joint construction
or a "marginal" label for several outputs; a predeclared sample-size plan, a confidence bound against a declared
minimum, width limits, and INSUFFICIENT_EVIDENCE when samples are too few. Plan L273 adds: register the counts before
running the parent, never reuse training points for calibration. Nothing in the repository yet fixes any of these, and
every later package inherits whatever M04 fixes.

## Decision

**D1. The reference distribution.** P_ref `m04-c1-box7-v1` is the uniform distribution on the box (T 653.15–693.15 K,
P 9–10 MPa, H₂/N₂ 2.5–3.0, y_NH₃ 0.02–0.04, y_Ar 0.01–0.03, y_CH₄ 0.01–0.04, per-tube flow 0.0057–0.0086 mol/s), inside
the parent's data and hard domains (spec §4). The coverage claim is marginal over it and over nothing else.

**D2. The plan is registered before the parent runs.** Seeds 20261008·1000 + 10i + j, SplitMix64, U = (w >> 11)·2⁻⁵³,
binary64 arithmetic in a registered order; iteration 1 draws 144 training, 118 calibration, 300 test and 5 gradient
centres (632 cold experiments). The plan is refused before any experiment when its cache misses exceed the approved
budget; it is never truncated or stopped early. A further iteration draws fresh calibration, test and gradient sets
and trains on all earlier P_ref records; it is automatic only after a failure whose sole reason is the coverage test,
at most three iterations, with the family-wise false-pass bound reported.

**D3. Failures stay in the denominator.** A draw whose experiment fails deterministically is excluded from the fit and
scores +∞ in calibration and test (never covered); a draw without a deterministic result makes the plan incomplete
(INSUFFICIENT_EVIDENCE) until a resumed job completes it.

**D4. One joint score, scaled by the width limits, and the integer finite-sample rule.**
s = max(|e_X|/0.0025, |e_ΔT|/1.5 K); k = ⌈(n+1)·19/20⌉ in integers; q̂ the k-th smallest score; no band when k > n
(INSUFFICIENT_EVIDENCE) or q̂ = +∞ (NOT_PROMOTABLE). The width criterion is q̂ ≤ 1.

**D5. Promotion is decided in integers and every reason is recorded.** Pass the coverage test iff the test hits
H ≥ h_min(m) (the Clopper–Pearson one-sided 95 % bound ≥ 0.90; h_min(300) = 279); m < 29 or n < 19 is
INSUFFICIENT_EVIDENCE. PROMOTABLE iff the plan is complete and within budget, the fit identifiable (τ_id = 10⁻⁸), the
band finite with q̂ ≤ 1, H ≥ h_min, every prediction in the box admissible, every gradient centre complete with
relative error ≤ 0.25 against the parent's central difference at h_z = 0.05, and no registered draw flagged
`extrapolated`. Verdict precedence INSUFFICIENT_EVIDENCE > NOT_PROMOTABLE > PROMOTABLE, with both reason lists always
recorded (spec §7.3's vocabulary).

**D6. The qualifications travel with the claim.** Q0 (synthetic parent) and Q1–Q7 of spec §6.3 — marginal, not at
selected points, not outside the box, relative to the parent at its design grid, joint at one query only, the nominal
and finite-sample levels with the lower bound, no empirical validation — are members of every manifest and every
surrogate-backed run's limitation.

**D7. Domains.** Hard: the parent's own hard domain plus the admissible output set (X ∈ [0, min(0.95, r/3)],
ΔT ∈ [−50, 250] K), refused and never projected. Empirical: the box, flagged with the scaled excess max(0, ‖z‖∞ − 1);
outside it no coverage claim applies.

## Alternatives considered

- **The data domain or the hard domain as P_ref.** Rejected: 90–200 K of an equilibrium-limited reactor for a
  quadratic, and pressures the loop does not visit; the misfit risk buys no decision M07 needs (spec §4).
- **Per-output scalar scores.** Rejected: two marginal claims for outputs the flowsheet consumes together (blueprint
  L417).
- **Scales from training residuals.** Rejected: decouples the score from the stated width limits for no gain.
- **Excluding failed draws and conditioning the claim on success.** Rejected: it narrows a denominator and hides the
  conditioning event; +∞ keeps the Beta(k, n+1−k) law of the band's coverage (spec §5.3).
- **Observed test coverage ≥ 0.95 as the promotion rule.** Rejected: blueprint L419 — an observed coverage below
  nominal is not evidence of failure, and a point estimate is no confidence bound.
- **Deciding the coverage test on a floating-point beta quantile.** Rejected: the integer h_min is exact and
  equivalent.
- **A Latin hypercube or a grid for training.** Not rejected by the blueprint, but i.i.d. training is simpler and lets a
  failed iteration's calibration and test records become the next training set.
- **Convex hull, nearest-neighbour density or leverage as the empirical domain.** Rejected (spec §3.6): the hull holds
  fewer than 30 of the 300 registered test draws; density and leverage measure noise amplification or local sampling,
  not the model-form bias of a deterministic parent.
- **Re-testing an unchanged predictor on a fresh test set after a failure.** Rejected: it is repeated selection on
  test sets; a new iteration changes the training set and draws a new calibration set as well.
- **A conformal alternative (CV+, jackknife+, conditional or Mondrian conformal).** Not adopted: blueprint D12 makes
  split-conformal the Default; an alternative needs its own ADR and evidence.

## Consequences

- C1. Iteration 1 costs 632 cold experiments (≈ 95 min, one thread, 9 s each); a correct pipeline passes the coverage
  test with probability 0.9035, distribution-free.
- C2. The real surrogate's verdict is unknown until it runs; NOT_PROMOTABLE for `width_limit_exceeded` is a measured
  limitation that needs a design-lane amendment (a richer predictor or another box), never a relaxed limit.
- C3. The score's scales and the width limits are one decision: changing either after calibration is tuning.

## Migration

None. No identity, fixture or registered value moves.

## Acceptance evidence

M04.A01–A24 and A34 `tested` in `evidence/M04/<commit>/manifest.json`; the generator's `--check` green; A31–A32
recorded for the real variant (opt-in); the design-lane review of WO-2, WO-3, WO-5.
