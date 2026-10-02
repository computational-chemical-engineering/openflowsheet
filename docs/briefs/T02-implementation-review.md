# Fable brief — T02 implementation review

**To:** `fable-reviewer`
**From:** the Opus session (Opus 5.5)
**Date:** 2026-09-24
**Design notes under review:** `docs/derivations/T02-recycle-spec.md` (yours, amended 2026-09-24)
and `docs/adr/0009-execution-plan-and-recycle-trace.md` (Proposed)
**Commit range:** `fe0a4de..HEAD` on branch `wp/T02` (T02 commits from `f24c658`)
**Evidence:** `evidence/T02/<commit>/manifest.json` — MANIFEST_PENDING
**Deliverable:** `docs/reviews/T02-review.md`, and a ruling on §5 Q1 recorded as an amendment of
ADR 0009 D3 (and ADR 0007 D2.2's rows) if you change the policy

---

## 1. What was built

| Module | Specification |
| --- | --- |
| `numerics/anderson.py` | §5 safeguarded Anderson; `acceleration`/`restart` events (§5.8) |
| `orchestrator/execution.py` | §3 `ExecutionPlan`, §4.2 solver choice, NEST-1's tear set, §7.1 `specification_regions`, §7.4 `plan_or_refusal`/`PlanRefusal` |
| `orchestrator/region.py` | §6 the EO region solve and the lifted phase policy (your 2026-09-24 amendment of §6.3.3) |
| `orchestrator/merge.py` | §4.4 the merge edge for a bare recycle (`converge_with_merge`) |
| `orchestrator/executor.py` | runs an `ExecutionPlan` on one trace (A33), SYN-001's merge edge |
| `orchestrator/trace.py`, `attempts.py` | ADR 0009 D2–D4 fields; `best_x` carried from the Anderson core |
| `application/binding.py`, `validation.py` | §7 A02 binding (freed/promoted), R-022 extension |
| `verify/failure.py` | D6 `provide_derivatives`; `refusal_bundle`; merge observation |
| `orchestrator/budget.py` | `PropertyMeter` (region property-call metering) |
| `scripts/t02_identity.py` | A02/A34 cross-platform identity (R0 + R1/R2 floats) |

Five A02 revisions and six registry entries (three in the denominator, two liquid-guess expected
failures handed to T03, CAP-1).

## 2. What I ran, and what it produced

Gate green at **1515** (1411 before T02). `t02_reference.py --check` 114. CI run 35979824190: the
`check` job green on both runners, the `identity` job **red** (§5 Q1).

Measured against your registered values (every one within its stated tolerance unless noted):
A07 every linear variant terminates at iteration 4 and reproduces the 40-digit twin; A08 the
nonlinear variants within `[ref, ref+2]`; A09–A20 the registered closures, restarts, drop counts
and trajectories; A21 two attempts (vapour leaves through a *component*, per your amendment), A22
one attempt at each variant, A23 iteration 0 with zero Jacobians, A24 the projection recorded;
A25 the plan equals `ref.syn001.plans["SYN-001-A02-*"]`; A28–A29 360/365/355 K in 3/4/3
iterations, one attempt; A30 `inadmissible(S3, all_liquid, 2.4959938386229013)` at
`S3.T` within 1e-5 K of 389.438 243 827 2; A31 `STAGNATION → kernel_disagrees` at
439.999 999 7 K then 280.000 02 K; A27 CAP-1 refused with zero calls; A14 the merge lands on `S1`;
A15/A17 one Newton iteration; A16 `exactly_singular`.

## 3. Your rulings of 2026-09-24, applied

§6.3.3 any lifted variable (A21 passes with the counts unchanged); D6 `provide_derivatives` in the
schema, `OUTCOME_ACTIONS` so `EVALUATION_ERROR` in the same class keeps `report_defect`; the
projection as `initializer_candidate projected(…)` + `initializer_accepted`.

## 4. Decisions I took that you should check

1. **R-022 extension** (`6645df5`, isolated): structural under-specification *alone* validates
   `DRAFT`, not T01 §12.3's `INVALID`; `STR-02` stays `FAIL`. A26(b) is the first registered
   revision to reach it through `validate()`.
2. **R-023**: the A02 start value is a `role: free` specification, not a new `initial_guess`
   field (the ProcessRevision schema is frozen).
3. **K04 fix** (`8d533eb`, isolated): the bundle's verdict-word guard matched `FAILED` inside
   `INITIALIZATION_FAILED`, `LINEAR_SOLVE_FAILED`, `LINE_SEARCH_FAILED` — those bundles could not be
   built at all. The three codes are removed before the scan; a test pins the exemption to exactly
   the vocabulary's codes containing a verdict word. Touches K04 A20.
4. **The executor absorbs inner traces.** Each step's K03/region solve records to a scratch trace;
   its events are copied into the plan's trace with fresh sequence numbers and counters offset by
   what the plan had spent, except the inner `plan_built` and `solve_closed`, whose outcome goes on
   `region_closed`. One trace, one `plan_built` (with `step_count`, carried as a nullable field —
   D3 says `plan_built` "carries" it), one `solve_closed`. K03's solver is unchanged.
5. **Region checkpoint label**: `candidate_root` only when the region *kept* the attempt; an
   attempt that converged on an inadmissible branch is `partial` (A30).
6. **`PropertyMeter`** (`76b245d`): a pass-through counting provider installed by the binding,
   because the region's property blocks capture the provider at declaration time. An unmetered
   flowsheet is refused by `execute_plan` rather than reported as zero. **No budget is enforced
   inside a region** — only metered.
7. The executor's `evaluate` step for the feed computes nothing (a boundary; outlet specified).
8. `best_x` is an additive optional field on `NewtonResult`/`SolveResult` (the merge start), `None`
   under Newton.

## 5. Questions that need your ruling

**Q1 — A34 fails, and I have not relaxed it.** R0 is equal across x86-64/aarch64 (every plan, every
recycle decision). `gamma_inf` is not, under ADR 0007 D2 (1e-9 relative, floor 1e-12):

| Case, event | `kappa_2` | `gamma_inf` x86-64 | aarch64 | relative | `kappa_2 · ε` |
| --- | --- | --- | --- | --- | --- |
| REC-03 γ=0.1, 6 | 9.67e3 | 0.017849421154344 | 0.017849420965506 | 1.06e-8 | 2.1e-12 |
| REC-05 γ=0.1, 8 | 6.12e3 | 0.030830101165351 | 0.030830101363735 | 6.4e-9 | 1.4e-12 |

The difference is four decades above the least squares' own roundoff, so it is not the solve; the
late columns are differences of nearly converged residuals and carry the iterates' last-bit
difference, relative to their own small size. Options I can see: a floor relative to the step's
data accuracy; `gamma_inf` compared only on events whose residual is above some multiple of the
tolerance; `gamma_inf` reclassified as a measurement that is recorded but not compared. The choice
is yours.

**Q2 — `kappa_2`'s floor.** The comparator applies a floor as `abs_tol`, so a floor of 1.0 on a
quantity that is ≥ 1 by definition accepts any difference below 1 (8% at κ≈12). Is that what D3's
"a condition number below one is not a measurement" meant?

**Q3 — region budgets.** Metered, not enforced (§4 item 6). Enforce in T02, or leave to T03?

**Q4 — measured deviations from the spec's wording**, asserted as measured: A26(a)'s
over-specified-unit list names `U-FLASH` (the promoted row's unit); `U-HEAT` is named through
`SPEC-heater-outlet-T` among the candidates. A29 355 K converges in 3 iterations (you measured 4;
bound ≤ 6).

## 6. Where I am least sure

- The merge on SYN-001 (`executor._converge`): reconstruct from `best_x` by one traversal, then the
  region with the kernel's phase set — exercised only by a forced budget of one iteration.
- The executor's counter arithmetic across absorbed traces.
- `specification_regions`' membership rule (paths either direction ∪ the loops touching them) on
  anything but SYN-001.

## 7. Not worth your time

Formatting, schema JSON layout, the manufactured-map reproduction (exact against your twin), the
registry prose.
