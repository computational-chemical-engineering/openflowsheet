# X07a ruling D1: the a36 application tests assert verdicts that LAPACK roundoff decides

**Status:** design-lane ruling (`specifier`), 2026-11-21, on the brief `X07a-D1-a36-ruling.md` (codehealth briefs) at
`d99117c5` (branch `wp/X07a`). Section 5.1 binds the X07a work order that edits `tests/test_m04_iterations.py`.
Section 5.2 is the M04 spec text to apply as a docs-only commit (M04 Amendment 4). **No ADR changes.**

## 1. Authority and scope

Read for this ruling, narrowly: M04 spec §3.4, §5.5, §6.1 to §6.4, §7.1 to §7.3, §9.1, §9.2, §11 (A16), §18 A1.2,
A1.3, A1.8 (A36), §20 A3.3; ADR 0036 D4, D5 and Amendment 1 D8; `studies/surrogate/conformal.py:1-80, 227-274`;
`studies/surrogate/iterations.py:1-17, 78-112`; `studies/surrogate/manifest.py:512-530`;
`tests/test_m04_iterations.py:1-130, 186-300, 329-368`; `tests/test_m04_study_job.py:1-12, 50-66`;
`tests/test_m04_wo9_synthetic_loop.py:1-14, 171-180`; `tests/m02_variant_support.py:18-40`;
`benchmarks/m04/reference_values.json` (`pipeline.smooth_full`); `docs/X07a_DECISIONS.md` WO18;
`docs/X07a-platform-ruling.md` R2.2.

Consistency with frozen text: no interface, schema, fixture, plan, registry, generator claim or reference value
changes. ADR 0036 is applied as written (D8), not changed.

## 2. Facts this ruling rests on

- **F-1 (WO18, measured).** `standin-x025-v1` is a constant response: X within 1 ulp of 0.25, ΔT = 0 exactly. Every
  score is fit roundoff, quantised at ulp(0.25)/w_X = 2.2204 × 10⁻¹⁴ (1.1102 × 10⁻¹⁴ below 0.25). Linux it2: n 118,
  k 114, q̂ 2.2204 × 10⁻¹³, m 300, H 286, h_min 279, 35 test scores equal to q̂, max score 11 quanta (2.44 × 10⁻¹³).
  Linux it1: q̂ 1.5543 × 10⁻¹³, H 285.
- **F-2 (WO18, measured).** Same observations, fit roundoff only (training rows permuted before the QR, 200 seeds):
  it2 H 275 to 300, NOT_PROMOTABLE 3/200; it1 H 273 to 299, 7/200. `np.linalg.lstsq` on Linux: it1 H 277
  (NOT_PROMOTABLE). macOS (Accelerate) failed it2 once and passed on rerun. Unperturbed controls are repeatable.
- **F-3 (spec).** §9.1 registers the stand-in *because* its residuals vanish, and says "no statistical outcome is
  asserted (the order statistic of roundoff-level scores is not a closed form)"; §9.2's stand-in row: verdict
  "not asserted".
- **F-4 (ADR 0036 D8, spec A1.3).** The verdict, H and the reason lists are R0 only conditionally: promised identical
  across platforms given the same records only when no decision they depend on is *near threshold*, a gap below
  10⁻⁸ in score units; otherwise a difference "is a recorded observation, not a mismatch".
- **F-5 (spec A1.8).** M04.A36's last clause: "`it2` for the smooth parent after A17's PROMOTABLE `it1` is
  `invalid_request` / `iteration_not_permitted`". A17 is registered in `reference_values.json`
  (`pipeline.smooth_full.result`: PROMOTABLE, k 114, H 283, q̂ 0.022440174316072229875) with generator-asserted
  margins: nearest test score to q̂ 6.85 × 10⁻⁴, neighbouring order statistics 3.52 × 10⁻³ apart.
- **F-6 (code).** The smooth parent is reachable through the application in tests by M02's registry patch plus the
  patched `InProcessBackend` (`tests/test_m04_wo9_synthetic_loop.py:171-180`); everything else is the production
  path. `tests/test_m04_study_job.py:7`'s "not reachable from a request" predates that pattern.
- **F-7 (code).** Promotion after a study reads the stored manifest: `derived_verdict` re-derives the verdict from
  stored scores by exact comparisons (`manifest.py:512-530`), used by the checker and the replacement check (A3.1).
- **F-8 (code).** `coverage_failed` (`tests/test_m04_iterations.py:87-113`) sets the first 30 finite test scores to
  0.5. Whatever the roundoff, H after it is at most 270 < 279 (at most 300 finite scores, and at least
  30 − (300 − H_before) of the moved ones were hits), and q̂ ≤ 10⁻¹⁰ < 0.5. Its output is roundoff-independent.

## 3. Findings on the governing text

- **G-1. The tests contradict the spec, not the other way round.** `tests/test_m04_iterations.py:344` (it1
  PROMOTABLE), `:345` (its consequence, the it2 refusal), `:366` (it2 PROMOTABLE) and `:367` (its consequence, the it3
  refusal) assert stand-in outcomes that F-3 registers as not asserted and that F-4 does not promise across
  platforms: every stand-in score is within 2.5 × 10⁻¹³ of q̂, so every coverage comparison is near threshold. The
  brief's `:342` is `:344` at `d99117c5`.
- **G-2. The application half of A36 was run on the wrong parent.** F-5 names the smooth parent; the test used the
  stand-in because of F-6's outdated docstring.
- **G-3. §6.2 has an erratum.** "the deterministic parent gives ties with probability zero" is false for a parent the
  predictor reproduces to roundoff (F-1: 35 ties at q̂). The guarantee it qualifies still holds (section 4, R2).
- **G-4. X07a's platform ruling R2.2 does not apply.** It is none of P1 (replay mode), P2 (bitwise) or P3
  (policy-bounded). The defect is the same on every platform: Linux flips the verdict under a row permutation or
  `lstsq` (F-2). No `X07a-L` row is warranted.

## 4. Rulings

### R1. Option A, refined: no test asserts a near-threshold outcome

The A36 guard mechanics that need a given verdict take it from A17, the parent with a registered, margin-protected
verdict, or from a constructed manifest. They never take it from the stand-in. The stand-in keeps the
verdict-independent admission path and asserts the vanishing itself (D1.5). Section 5.1 gives the exact edits.

*Why it is not removing a case to pass a gate.* The four removed assertions never held as stated: each was a
roundoff-decided coin with a measured flip rate of 1.5 to 3.5 % on Linux alone (F-2). What replaces them is
deterministic on every platform. The PROMOTABLE refusal runs through the application on A17, A36's own text, and
no longer by luck. The it3 guard stays covered at library level by
`test_a36_it3_needs_both_earlier_iterations_and_their_chain` (`:235-257`, constructed coverage-only manifests from a
real smooth it2). D1.5 is new and can fail.

*Alternatives within A, rejected.* (A-inject) Building a PROMOTABLE stand-in it1 by moving its test scores below q̂
and registering it. It is deterministic, but it replaces a registered verdict with a constructed one where A36
names a registered one, and it drops the job-written-manifest-to-guard path. (A-branch) Reading the stand-in
verdict and asserting whatever the guard should do with it. The path taken would still be roundoff-chosen, so
the refusal branch is not guaranteed to run on any platform. (A-register) Registering the smooth it2 outcome in the
generator so that `:366-367` could be kept on the smooth parent. That costs a generator extension and a spec
amendment for one assertion that the library level already covers.

### R2. Option B rejected: an exact fit is not a defect of the method

1. **Validity survives ties.** On one platform, with the predictor frozen, s(x) is a deterministic function of the
   draw. The roundoff of the binary64 evaluation is part of that function, so calibration and test scores are
   i.i.d.
   (a) *Conformal bound.* Let S₍ₖ₎ be the k-th smallest of all n + 1 scores. Then s_{n+1} > s₍ₖ₎ (the k-th smallest
   of the first n) implies s_{n+1} > S₍ₖ₎. At most n + 1 − k scores exceed S₍ₖ₎, so by exchangeability
   P(s_{n+1} > q̂) ≤ (n + 1 − k)/(n + 1). Ties only lower the count.
   (b) *Coverage test.* Write s = F⁻¹(U) with U uniform and F⁻¹ the generalised inverse; F may have atoms, and a
   failure has mass at +∞. F⁻¹ is non-decreasing, so q̂ = F⁻¹(U₍ₖ₎) and C = F(q̂) ≥ U₍ₖ₎ ~ Beta(k, n + 1 − k).
   P(H < h_min | C) is non-increasing in C. So the false-failure probability of a correct pipeline is at most the
   continuous value at the same failure rate. With no failures, as on the stand-in, that value is
   P(BetaBin(300; 114, 5) < 279) = 0.096467 = 1 − 0.903533, the registered `finite_sample.registered_plan.power_no_failures`
   (§6.4).
   The stand-in's 3/200 and 7/200 in F-2 are consistent with that bound. They are not a test of it, because they
   vary roundoff, not draws.
2. **Recorded verdicts are portable.** Promotion reads stored manifests and re-derives the verdict from stored
   floats (F-7), so it is the same on every platform. Only a re-run of the study can differ, and only when a decision
   is near threshold. F-4 already declares that difference an observation. A1.3 also scopes it: records from another
   environment are another study.
3. **Reachability.** `surrogate_study` admits registered parents with registered plans. As shipped, the only parent
   the quadratic reproduces to roundoff is the synthetic stand-in, which carries Q0 ("certifies nothing"). A parent
   outside the quadratic class leaves model-form residuals. The smooth synthetic parent, a mild exponential, already
   has a training RMS of 1.2 × 10⁻⁵ in X, about 5 × 10⁻³ score units or 2 × 10¹¹ quanta.
4. **B's variants are worse than the disease.** (B1) "Scores below a floor ε count as hits" is a band of half-width
   max(q̂, ε). It is valid, because a wider band covers more. But it rewrites §6.2 and §6.4 after the registered
   iterations ran under them (N2: the rule is frozen before calibration). It needs a new member or a changed meaning
   of `q_hat` (a schema change), and it moves the threshold to ε rather than removing it. (B2) A `degenerate_scores`
   reason refuses the best possible surrogate. As IE it is false, because the evidence is complete. As NP it is
   false too, because the surrogate is exact, and it would also block §5.5's iteration rule.

**Answer to the brief:** B is not a production defect. An exactly fitting surrogate gets a statistically valid
verdict whose re-run on other arithmetic may differ, exactly as D8 says. One residual weakness is that the
near-threshold status is computable from stored members but not reported. It is parked as OQ-2, default no change.

### R3. Option C rejected

A test that fails 1.5 to 3.5 % of the time on Linux under a pure roundoff change is flaky on every platform, not
limited on one (G-4). Declaring the macOS leg limited would leave a coin flip in the merge condition (CI green on
every leg). It would also record as a platform property what is a test asserting an unpromised quantity (rule 6:
the defective document is amended, not worked around). The macOS first-attempt failure at `a90be473` (job
136781135134) is recorded in the X07a manifest as a D8 observation, not as a limitation.

### R4. ADR and register

- **No ADR amendment.** ADR 0036 D4 and D5 make no continuity claim. D8 already makes near-threshold verdicts
  conditional. This ruling applies D8. §6.2's sentence is a justification erratum, not a change of semantics.
- **Register:** one new entry at the next free R-number on `main` when X07a merges. "M04/X07a: no test asserts an
  outcome that ADR 0036 D8 does not promise (a near-threshold verdict); A36's application half runs on A17; §6.2's
  ties erratum. Rejected: a score floor or `degenerate_scores` reason (B), a macOS platform row (C). Evidence:
  `docs/X07a-a36-ruling.md`, WO18."

## 5. Exact changes

### 5.1 `tests/test_m04_iterations.py` (binding)

1. **`:341-346`** becomes `test_a36_it2_after_a17s_promotable_it1_through_the_application`, on the smooth parent:
   - Add a function-scoped fixture that registers `SMOOTH` with `register_variants(monkeypatch)` and sets
     `runner_module.InProcessBackend = parents.backend_for()`, as in `test_m04_wo9_synthetic_loop.py:171-180`. The
     patch must be in place before `LocalApplication.create`: give this test its own application fixture that
     depends on the patch fixture. Test 2 keeps the unpatched `app`.
   - Body: D1.1, D1.2, D1.3 (section 6) with `body(SMOOTH, plan_id=...)`.
2. **`:365-367`** are deleted (the comment, the it2 verdict, the it3 submission). D1.5 is added after `:364`.
   `:349-364` are unchanged (D1.4).
3. **Docstring `:18-20`** becomes: "Through the application. On the smooth parent (registered for the test as in
   `test_m04_wo9_synthetic_loop`): `it2` before any `it1`, and after A17's PROMOTABLE `it1`, is `invalid_request` /
   `iteration_not_permitted`. On the stand-in: after a registered coverage-only `it1`, `it2` is admitted and its
   manifest names that predecessor. No verdict of a stand-in study is asserted: its scores are roundoff, so every
   coverage decision is near threshold (spec §9.1, ADR 0036 D8; `docs/X07a-a36-ruling.md`)."
4. `tests/test_m04_study_job.py:7-8`: "are not reachable from a request (they are not registered)" becomes "are
   reachable from a request only through the test-only registry patch (`test_m04_wo9_synthetic_loop`,
   `test_m04_iterations`)".

Audit (grep of every test naming the stand-in): A16 (`test_m04_study_job.py:101-140`) asserts no verdict. Both A28
tests (`test_m04_wo8_replacement.py:177-185`, `test_m04_wo9_synthetic_loop.py:464-474`) echo the recorded verdict
without asserting a value. They comply, and nothing else changes.

### 5.2 M04 spec, Amendment 4 (docs-only; verbatim text to append as §21)

> **## 21. Amendment 4 (2026-11-21): stand-in verdicts are not asserted anywhere (X07a ruling D1)**
>
> *Erratum, §6.2.* Replace "with equality for continuous scores; the deterministic parent gives ties with
> probability zero." by: "with equality for continuous scores. Ties do not weaken it, and the coverage C = F(q̂)
> stochastically dominates Beta(k, n + 1 − k), so §6.4's false-failure probability stays at most its continuous value
> (0.096467 with no failures, one minus the registered `power_no_failures`). A parent
> the predictor reproduces to roundoff gives ties: the stand-in's scores are quantised at 2.22 × 10⁻¹⁴, and 35 of
> its it2 test scores equal q̂ (X07a WO18)."
>
> *§9.1, the stand-in.* Its outcomes are not asserted on any plan or route, library or application. That covers H,
> L, the verdict, the reason lists and anything that follows from them, such as an iteration's admission after it.
> Every stand-in score is within 10⁻⁸ of q̂, so every coverage decision is near threshold (ADR 0036 D8). X07a WO18
> measured both verdicts from one set of observations. What is asserted is the vanishing: q̂ ≤ 10⁻¹⁰, every
> finite test score ≤ 10⁻¹⁰, no IE reason, and no NP reason other than `coverage_bound_below_minimum`. A test that
> needs a given verdict takes it from A17 or from a constructed manifest.
>
> *M04.A36, last sentence.* "`it2` for the smooth parent after A17's PROMOTABLE `it1` is `invalid_request` /
> `iteration_not_permitted` through the application (the smooth parent registered for the test, as A47). With the
> stand-in through the application, `it2` after a registered coverage-only `it1` is admitted and lists that
> predecessor; its verdict is not asserted."

### 5.3 What does not move

`reference_values.json`, `m04_reference.py` and its claims, every plan, schema, fixture and registry, the verdict
function, `iterations.py`, the F0 corpus, and every library-level A36 test (`:163-300`).

### 5.4 What the changes do to existing evidence

- The historical junit and recall records naming the old test (`evidence/{M07,REL040,S13}/*/rc/step13/m04-tests.junit.xml`,
  `evidence/S16/ef915499…/recall-run{3,4}.json`) stay records of their commits. Those passes were real. They were
  never validation of a verdict (§9.1 already said so), and nothing is re-taken.
- M04's A36 status is unchanged. Its library half is untouched, and its application half now matches A36's text.
- The X07a manifest records three things: the test change, the WO18 macOS observation as a D8 observation (R3), and
  CI on every leg at the change's commit.

## 6. Assertions (cited by the tests as `X07a-D1.<n>`)

| # | Route, parent | Assertion | Tolerance and why |
| --- | --- | --- | --- |
| D1.1 | app, smooth | `it2` before any `it1`: `invalid_request`, pointer `/body/plan_id`, reason `iteration_not_permitted`, message contains `it1 has no manifest` | exact (strings) |
| D1.2 | app, smooth | `it1` job `completed`; `promotion.verdict` PROMOTABLE, `insufficient` [] and `not_promotable` []; `calibration.k` 114, `evaluation.hits` 283; \|q̂ − 0.022440174316072229875\| ≤ 10⁻¹⁰. All values are read from `reference_values.json` → `pipeline.smooth_full.result`, not retyped | integers exact. They are D8-promised because the generator asserts every gap ≥ 6.85 × 10⁻⁴ ≫ 10⁻⁸. q̂: the measured binary64 deviation is 1.8 × 10⁻¹⁵ (spec §18, A17), 4.7 decades below 10⁻¹⁰. A wrong order statistic moves q̂ by ≥ 3.52 × 10⁻³, and a fit change of 10⁻⁵ in X (the smooth training RMS) moves scores by 4 × 10⁻³ |
| D1.3 | app, smooth | then `it2`: refused as D1.1 with message containing `it1 ended PROMOTABLE`; the job list has exactly 1 job | exact |
| D1.4 | app, stand-in | `:352-364` unchanged: admitted after `coverage_failed` it1, `completed`, id `m04q7-standin-x025-v1-it2`, (cold, cache) (1050, 0), predecessors [sha256], bound 0.1, `check_manifest` [] | exact. It is roundoff-independent by F-8, and the counts are plan-derived (562 + 488) |
| D1.5 | app, stand-in | the it2 manifest: `calibration.q_hat` ≤ 10⁻¹⁰, every non-null `evaluation.scores[i]` ≤ 10⁻¹⁰, `promotion.insufficient` [], set(`not_promotable`) ⊆ {`coverage_bound_below_minimum`}. The verdict and H are not asserted, and no it3 is submitted | 10⁻¹⁰ is A16's q̂ bound and A1.3's score floor. The measured maximum is 2.44 × 10⁻¹³ (11 quanta, F-1), so the margin is 2.6 decades. A 10⁻⁶ relative bias in X gives scores ≥ 10⁻⁴, and a stray coefficient error ≥ 2.5 × 10⁻¹³ in X exceeds the bound. The reason-list half fails if width, gradient, admissibility or extrapolation trips: each is decided far from its threshold on the stand-in: q̂ ≤ 10⁻¹⁰ against 1; e ≤ 10⁻¹⁰ against 0.25 when the coefficients meet A16's 10⁻¹⁴; admissibility margins 0.083 in X and 50 K |

D1.5 states the vanishing *because* it is why no verdict is asserted. D1.2 is the same quantity not vanishing
(q̂ = 0.0224, margin 6.85 × 10⁻⁴).

## 7. Acceptance for the work order

- `pytest tests/test_m04_iterations.py` passes locally. Record the D1.5 measured values in the WO entry: q̂, the max
  test score, the max gradient error and `domain.admissibility_margin`.
- Two scratch mutations, not committed, are reported in the WO entry. (i) A guard that admits after PROMOTABLE
  fails D1.3. (ii) Adding 10⁻¹² to the stand-in fit's β_X[0] fails D1.5.
- CI is green on every leg at the commit, first attempt. One green run does not prove the absence of roundoff
  dependence. The structural argument does: after the change, every asserted verdict is A17's, whose margins the
  generator asserts.
- The docs-only commit applies section 5.2. `python docs/derivations/scripts/m04_reference.py --check` is unchanged.

## 8. What this ruling does not establish

- That the stand-in's verdict is PROMOTABLE, or NOT_PROMOTABLE, on any platform. It is not a registered quantity.
- That macOS (Accelerate) runs the fit bitwise-repeatably on one machine. The failing attempt and its rerun may have
  run on different hardware. A3.3, A49 and W-2 govern that, and this ruling does not depend on it.
- Anything about the real reactor's surrogate. R2.3's reachability argument concerns the shipped parents only.
- Validation of the coverage test with ties against data. R2.1 is a proof. F-2's frequencies vary roundoff, not
  draws, and are only consistent with it.
- That a near-threshold flag is unnecessary for every future parent (OQ-2).

## 9. Open questions, each with a default

- **OQ-1 (needs a fact: the macOS and Windows values of D1.5).** Settled by the first CI run after the change. The
  default is that 10⁻¹⁰ holds, since A16's q̂ ≤ 10⁻¹⁰ already passes on every leg. If D1.5 fails on a leg, stop and
  return here. Do not widen the bound.
- **OQ-2 (needs the user's preference: a reported near-threshold flag).** It would mean a manifest member, a schema
  change and an ADR 0036 amendment. The default is no. Revisit when a non-synthetic parent's study has a
  decision within 10⁻⁸, which is computable from its stored manifest.
- **OQ-3 (needs a fact: the job path reproduces A17).** The default is yes, since A47 shows the job path reproduces
  A19. If D1.2 fails, that is a defect in the job path: stop and report. Do not re-register A17.
