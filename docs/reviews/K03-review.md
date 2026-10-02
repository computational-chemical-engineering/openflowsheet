# K03 review — the nonlinear solver, against `docs/derivations/K03-solver-spec.md`

**Reviewer:** Fable 5.1 (`fable-reviewer`), 2026-09-21
**Brief:** `docs/briefs/K03-implementation-review.md`
**Reviewed:** branch `wp/K03` at `ee81c6b` (current with `main` at `40ae9df`); evidence manifest
`evidence/K03/19764e1afba6e95cda84780019bba789c7a60085/manifest.json`
**Gate, re-run by the reviewer:** `PATH=.venv/bin:$PATH ./scripts/check.sh` — 1166 passed in 7.95 s, exit 0.
**What else was run:** five short probe scripts against the nominal variant and constructed controller
problems (scratchpad only; nothing committed). Every number below marked *measured* is from those runs;
every claim about a line of code was read in the file named.

Register entries consulted before recommending anything they cover: R-010, R-011, R-012, R-014, R-015,
ADR 0004. Nothing below asks for a registered decision to be reopened.

---

## 1. Verdict

**The implementation matches the specification with the listed must-fixes.**

The solve path itself — `R(t)`, the Schur-complement derivative and its three-way check, the structural
elimination, the Newton core on the registered states, the attempt restart on OFF-B — computes what §2–§9
say it computes, and the §7.2 sign override was correct (verified algebraically, §4 O6). The must-fixes are
not in the arithmetic. They are: one safeguard the specification, the module docstring and the manifest all
say is in place and is not (M1); one §9.3 predicate that is a tautology (M2); one result field that reports
a point the solver never accepted (M3); and two places where the evidence claims more than the code records
(M4, M5). Each is small to repair and each is verifiable by a measurement given with it.

The evidence establishes G00 as claimed. It establishes G01's "damped Newton" half more weakly than the
manifest reads (§6): the damping code runs and is consistent, but no registered assertion pins a damped step
that leads to a root, and one registered assertion (A02) has no test at all.

---

## 2. Must-fix findings

### M1 — The eliminated rows are not in the inner-consistency check

**Where.** `src/process_runtime/orchestrator/tear.py:174` builds `inner_rows` from
`elimination.retained_rows` only; `tear.py:328` iterates `self.partition.inner_rows` in
`check_inner_consistency`.

**What the specification says.** §3.1: the inner rows φ are "every other row: 46, of which 44 are retained
and 2 eliminated". §3.4: η is the max over inner rows φ. §7.3: the eliminated rows "are evaluated at every
accepted iterate as part of the §3.4 consistency check (they are inner rows)". The `rank.py` module docstring
(line 24) and the manifest's `K03.plan.rank_policy` description ("Eliminated is not discarded: the rows stay
assembled and are evaluated in the consistency check") repeat the claim.

**Measured.** `tear.partition.inner_rows` has 44 entries; `U-FLASH:FLASH-P:inlet` and
`U-SPLIT:SPLIT-P:recycle` are in neither `inner_rows` nor `tear_rows`. They are evaluated by
`_raw_rows` (all 49 rows come back) and then never read.

**Why it matters.** The certificate is computed once, at plan time, from the Jacobian pattern at one state
(`tear.py:155–173`; qualification is by *numerical* nonzeros, `rank.py:168`). The per-iterate evaluation of
the eliminated rows is the only thing that would catch a row that qualified at that state but is not
actually affine — and it is the safeguard the documents say exists. Today the solver trusts the certificate
unconditionally after plan construction.

**A specification inconsistency this exposes, which the fix must resolve.** §7.2 tolerates a constant
mismatch up to `a_P = 1e-2 Pa`, which is `1e-7` scaled; §3.4's `η_inner = 1e-10` is `1e-5 Pa`. Including the
eliminated rows in η literally, as §3.4 is written, would make any flowsheet with a tolerated nonzero `m_e`
end `INNER_SOLVE_INCONSISTENT`. (Every registered SYN-001 case has `m_e = 0` exactly, so the five variants
are unaffected either way.) The consistent reading is the certificate's own identity: at every Jacobian
evaluation check `|F_e(x) − m_e| / S_e ≤ η_inner` for each eliminated row `e` — which, with the retained
rows already at η, is the identity `F_e − Σ σ_k F_k = m_e` verified at the iterate rather than assumed
from the plan.

**Minimal correction.** In `check_inner_consistency`, iterate over every non-tear row; for a row in
`elimination.eliminated_ids` compare `abs(values[name] − m_e)`; report it under `worst_row` like any other.
Add one sentence to §3.4 stating the eliminated rows enter η through their certificate identity.

**Confirm by.** `set(tear.partition.inner_rows) | elimination.eliminated_ids == set(spec.equation_ids) −
set(tear_rows)` (46 rows); the five variants' η unchanged at ~2e-16 (both `F_e` are zero to rounding there).

### M2 — `stalled_at_the_wall` is a tautology; §9.3's second trigger is not implemented

**Where.** `src/process_runtime/orchestrator/attempts.py:198–205`:

```python
return self.iterations_with_wall[-1] >= self.iterations_with_wall[-1] - window
```

`a >= a − window` is true for every `window ≥ 0`; the closing iteration is never passed in, so no value of
`stagnation_window` can change the answer.

**Measured.** `_PhaseWall(policy, sig)` with `iterations_with_wall = [0]`:
`stalled_at_the_wall("LINE_SEARCH_FAILED")` → `True`; `stalled_at_the_wall("STAGNATION")` → `True`.

**What the specification says.** §9.3, second bullet: the attempt ends `PHASE_UPDATE_REQUIRED` when a line
search fails or stagnation fires "**and at least one `phase_update_required` rejection occurred in the last
`stagnation_window` iterations**".

**Failure scenario.** An attempt has a single overshoot at iteration 0 (a phase-rejected trial, halved,
accepted — §9.3's common case), then proceeds in-regime and stagnates or exhausts a line search at iteration
20. Per §9.3 the outcome is `STAGNATION`/`LINE_SEARCH_FAILED`. The implementation restarts, and it restarts
from iteration 0's largest-α rejected trial, because `best_point` is reset only when a *new* wall iteration
arrives (`attempts.py:176–181`), so the restart point can be arbitrarily stale. The new attempt then either
converges elsewhere, cycles (`ACTIVE_SET_CYCLING`), or exhausts attempts — any of which misreports what
happened. No registered case reaches this: OFF-B closes on the patience rule, which is correct.

**Minimal correction.** Give `stalled_at_the_wall` the closing iteration (`result.iterations` is the failing
iteration index for both outcomes) and return
`outcome in (...) and iterations_with_wall and closing − iterations_with_wall[-1] < window`
(choose `<` or `≤` and record it). Separately, §9.3's sentence "the restart point is the phase-change-rejected
trial with the largest α in the *last line search* of the closing attempt" cannot be satisfied when the
closing line search contains no phase rejection (which the second trigger explicitly allows); the code takes
the most recent line search that had one, which is the only sensible reading. Amend the sentence to say so.

**Confirm by.** A unit test on `_PhaseWall` with `iterations_with_wall = [0]`, window 5, closing iteration
20 → `False`; and with `[0, 18]`, closing 20 → `True`.

### M3 — `SolveResult.x` on `ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED` is a point the solver never accepted

**Where.** `attempts.py:340` assigns `x, opening = restart` (a *rejected* trial in the new regime); the
`_closed` calls at `attempts.py:243–256` and `346–358` then return that `x` with `residual_inf` and `merit`
taken from `last` — the closing attempt's *accepted* iterate. The two describe different points.

**Measured** (constructed controller, a residual whose signature flips persistently): outcome
`ACTIVE_SET_CYCLING`, `result.x = [-84.03]`, `result.residual_inf = 69.67`, residual evaluated at
`result.x` = 7926.4.

**Minimal correction.** Pass `last.x` (or the checkpoint's state) in both calls. `x` should be the same point
`residual_inf`, `merit` and `checkpoint.state_sha256` describe.

**Confirm by.** Any controller run ending in either outcome: `problem.residual(result.x)` must reproduce
`result.residual_inf`.

### M4 — The property-call budget is not enforced and its counters are never populated; the manifest is silent

**Where.** `SolvePolicy.max_property_calls` (`trace.py:326`) is read nowhere. `Counters.property_calls`,
`requested_evaluations`, `cache_hits` are never incremented (grep: no writer in `src/`); no guard exists at
the provider boundary; no typed `BudgetExhausted` exists.

**Measured.** After the full nominal solve, `result.counters` is
`property_calls=0, requested_evaluations=0, cache_hits=0, residual_calls=2, jacobian_calls=1,
factorizations=1`. §13.6 registers the same solve at ≥ 68 provider calls.

**What the specification says.** §11.2 (three budgets; "every `SolveEvent` carries the cumulative counters,
so a trace shows where a budget went"); §13.6 and A15 (`SYN-001-capped-budget`: `BUDGET_EXHAUSTED(property_calls)`
with `counters.property_calls == 20` exactly). The manifest's `limitations` name the initializer chain as
unimplemented and say nothing about this; `checks[]` has no entry for A15. Three counter fields that always
read zero and a policy field with no effect are, under CLAUDE.md's rule, placeholders.

**Minimal correction.** Preferred: implement it — K02's `ExactPropertyCache` keeps the counters; a guard at
the provider boundary that refuses the call exceeding the cap by raising a typed exception, converted by
`solve_with_attempts` to `BUDGET_EXHAUSTED(budget="property_calls")`; populate the three counters on every
event. Acceptable now: record `K03.A15` as `unsupported` in the manifest, add the budget to `limitations`,
and document the three counters as unpopulated in `Counters`' docstring. Note S7: the redundant traversals
will inflate the count until they are removed, so §13.6's "6 + 62" accounting must be re-measured.

**Confirm by.** `SYN-001-capped-budget` produces the registered outcome with `property_calls == 20`, zero
accepted iterations and no attempt opened.

### M5 — The inner-block solves factorize three times and leave no record on the trace

**Where.** `tear.py:313`: `[solve_linear(j_phi_u, j_phi_t[:, k])[0] for k in range(len(tear))]` — three
`splu` factorizations of the same 44×44 matrix, and the `LinearSolveRecord` of each is discarded (`[0]`).
`newton.py:274` counts only the 3×3 reduced-system factorization.

**Measured.** 3 `splu` calls per `tear.jacobian()`; no `linear_solve` event in any trace has `dimension 44`.

**What the normative text says.** Spec §3.4: "three SuperLU solves against one factorization". ADR 0004 D2:
"no path that skips the record"; D3.1: the residual, the `|U_ii|` extremes and `nnz` are recorded "per solve,
on the `SolveEvent`"; Consequences: "the three right-hand sides of the Schur complement share one
factorization within a Jacobian evaluation". The ADR states D1–D3 bind every production-path linear solve,
and this is the one the ADR was written for.

**Effect on the evidence.** Numerics: none — same matrix, deterministic factorization, identical solutions.
Evidence: the manifest's per-variant `factorizations: 1` counts a subset; `K03.linear.evidence`'s 44×44
numbers (`1.1e-16`, `7.13e-3`) come from `tests/test_k03_linear.py:201` factorizing the block itself, not
from any solve's trace; the 44×44 solve's residual threshold (D3.2) *is* enforced inside `solve_linear` on
each call, so the guard is live, but the record is thrown away.

**Minimal correction.** Let `solve_linear` accept an `(n, k)` right-hand side (`SuperLU.solve` does),
factorize once, return one record; have the Jacobian evaluator return `(matrix, evidence)` (or take the
trace) so the core can emit a `linear_solve` event for the inner block and count the factorization. The
same channel carries η for S1.

**Confirm by.** `splu` calls per `jacobian()` == 1; one `linear_solve` event with `dimension 44` per
`jacobian` event; the manifest's 44×44 numbers taken from those events.

---

## 3. Should-fix

**S1 — η is computed and dropped.** `newton.py:262–271` records the `jacobian` event without
`inner_consistency`; `tear.jacobian` computes η (`tear.py:279`) and does not return it. A24's first clause
("every `jacobian` event has `inner_consistency.eta ≤ 1e-10`") cannot be evaluated on any trace. The
manifest's `2.0e-16` is from `tests/test_k03_tear.py:196`, a direct call at `t*` — a state at which no
registered solve evaluates a Jacobian (they evaluate at `t⁰`). The check itself does run inside `jacobian()`
(`tests/test_k03_tear.py:365` proves it raises), so the solve is protected; the reported number is not the
solve's. Fix with M5's channel and report η from the registered solves' traces.

**S2 — A35 is not implemented.** `Checkpoint.full_state_sha256` and `jacobian_identity` have no writer
(`attempts.py:298–308` constructs without them). §6 and A35 say K03 records them for K04; the manifest does
not list this. Reconstruct `x(t)` once at the final accepted iterate and hash it; record the last
`_raw_jacobian`'s identity; or record `unsupported`.

**S3 — §8.2's admissibility check is not implemented** (A26/A27); `tp_state.py:271` says it is K03's; the
manifest is silent. On the tear path it cannot fire (§8.1), but it is the only solver-side guard on the
branch of the sink block (S3), which the signature deliberately does not freeze — see Q3. Implement the
three-row table on the reconstructed final state, or record `unsupported`.

**S4 — Make the certificate's linear half exact.** `rank.py:191–220` has every coefficient row in hand; add
the check `c_e == Σ σ_k c_k` (exact, over the pressure columns). *Measured:* it holds for both SYN-001 rows.
Today the two-probe spread is the only witness that the path's signs telescope, and it witnesses that along
one direction (`997·(index+1)`); a sign-error pattern with `Σ c_k (index_k + 1) = 0` would be invisible to
it. Contrived, but the exact check is free. Also state in the docstring that qualification reads numerical
nonzeros at one state (`rank.py:168`, at `G(0)`, where the recycle is dormant at `r = 0`), so a row whose
non-pressure coefficient vanishes there would qualify falsely — M1's per-iterate identity is the runtime
guard for exactly that.

**S5 — Registered assertions with no test, and a manifest that cannot show it.** No test mentions 365 K:
A20/A23 at `JAC-365K` and A21's "every entry ≥ 1e-2 at 365 K" are untested, and A21's exact zeros at 360 K
(design invariant 3, "no accidental zeros") are compared to the closed form at `1e-12`, not asserted `== 0.0`
beside nonzero neighbours. A02 (the Armijo inequality on *recorded* trace numbers) has no test —
`test_the_armijo_condition_is_the_registered_one` asserts the policy constant only. A03 (residual on
`step_accepted` recomputed by a traversal) I could not find. The manifest does not follow §15.1's
one-`checks[]`-entry-per-AID layout, which is why these are silent. Add an AID → test-node table (manifest or
ledger) with `unsupported` where there is none; then the gaps are visible instead of discovered by a reader.

**S6 — Register a seed where damping is necessary and sufficient.** See §6 for why. `arctan(x)` from
`x⁰ = 1.5` is the standard one: undamped Newton diverges (`x¹ = −1.69`), one Armijo halving lands at `−0.097`
and the iteration converges. Assert both an `armijo` rejection and `CONVERGED`. Also make
`test_an_armijo_rejection_is_not_a_phase_wall` say what its problem does: *measured*, the cubic
`x³ − 2x + 2` from 0 ends `LINE_SEARCH_FAILED` at iteration 6 with `x = 0.81639 = sqrt(2/3)`, the stationary
point of the merit function (`f·f' = 0`, `f = 0.911`), after 71 Armijo rejections. That is correct
line-search-Newton behaviour and a good "no infeasibility claim" case like NUM-05; the test currently asserts
only `attempts == 1` and passes on a failure it does not name.

**S7 — Redundant traversals before the first iteration.** *Measured* on the nominal solve: 9 traversals
where 3 are needed — 5 at `t⁰` (`_partition` → `reconstruct`; `build_plan` → `reconstruct` for
`jacobian_nnz`; `signature_of(start)`; `residual(start)`; `jacobian(start)` → `reconstruct`), 3 at the
dormant recycle (`initial_recycle()` called from `_partition`, `build_plan`, `solve_tear`), 1 at `t*`.
`build_plan` also differentiates the lifted system a second time. Free here; at scale every traversal is an
inner solve, and M4's counter will count them all. Keep the initial state and Jacobian from `_partition`;
let the opening signature come from the `residual()` evaluation the core makes anyway; cache the last
reconstruction by tear-vector hash. Spec §10.1 says "nothing is evaluated twice".

**S8 — An unregistered fourth regime.** `FLASH_REGIME` (`attempts.py:52–57`) maps
`("ZERO_FLOW", "ZERO_FLOW") → "ZERO_FLOW"`; §9.1 registers three regimes. Unreachable for SYN-001 (the fresh
feed is nonzero). Register it in §9.1 or remove it; R-012's "watch for" is silent widening of the signature.

**S9 — Plan-level outcomes are exceptions, not results (needs a decision).** `SCALE_UNAVAILABLE`,
`SPECIFICATION_CONFLICT` and `UNSUPPORTED_RANK_STRUCTURE` raise from `Syn001TearProblem.__init__`; an
initializer whose traversal fails raises a bare `ValueError` at `attempts.py:231` where §10/§11.1 say
`INITIALIZATION_FAILED`; none of them records `solve_closed`. Exceptions are not silence, so invariant 4
holds, but D01's typed-outcome channel is bypassed and a caller must know three exception types. I would
resolve it in K05's job layer (catch → `SolveResult` with the outcome and a `solve_closed` event) and say so
in the manifest now; if K03 is to own it, `solve_tear` should catch and return. Either way, record which.

---

## 4. Observations (no action required unless noted)

**O1 — The one state where the consistency check passes and the derivative could still be poor** (brief
§9.1). The Schur complement is the implicit-function derivative of the lifted system on the branch through
`x(t)`; η ≤ 1e-10 establishes the point is on *a* branch, non-singularity of `Ĵ_φu` establishes the branch is
locally unique, and the frozen flash regime plus the sequential solves' continuity establish the traversal
stays on it. That argument is airtight for SYN-001 (Q1 below). Its floating-point weak spot is not η but the
linear-solve check: `ρ_lin` is normalized by `‖Δ‖_∞`, and if the inner block has a near-singular *sink*
sub-block (the heater outlet's lifted split near its bubble point at 350 K — the S3 block's determinant is
`L³(1 − Σ x K)`), `‖Δ‖_∞` is dominated by huge sink components that do not reach `Ĵ_ρu`, and the normalized
residual says nothing about the accuracy of the components that do. The `|U_ii|` screen would show it and
would not act. Not reachable at any registered state (smallest S3 margin 0.038). Two defensible responses,
either of which I would take before T02: restrict the Schur complement to the sub-block reachable from the
tear rows (the sink block contributes nothing in exact arithmetic), or check the residual componentwise on
the rows that feed `Ĵ_ρu`.

**O2 — `None` matches any signature.** `newton.py:363`: `trial_evaluation.signature not in (None, signature)`.
A residual evaluator that omits its signature silently disables [A01] for a non-empty attempt signature.
Suggest: for a non-empty attempt signature, `None` is `EVALUATION_ERROR`.

**O3 — `should_close` ignores its `iteration` argument** (`attempts.py:190–196`); it is correct only because
it is called on every iteration. `phase_wall_patience = 0` fires immediately; `SolvePolicy` validates none
of its integers.

**O4 — `_bound_aware_alpha`** (`newton.py:472–477`): `np.isclose(…, rtol=0, atol=0)` is `==`; the `or` is
redundant. A trial that lands within an ulp *above* the bound is not snapped — consistent with §5.3's
"reaches"; fine.

**O5 — `LINE_SEARCH_FAILED` for an unevaluable initial point** (`newton.py:209–220`) is a misnomer, not an
infeasibility claim; on the tear path it is pre-empted by `attempts.py:229–231`. Fold into S9.

**O6 — The §7.2 override was right.** *Measured* from the assembled coefficient rows over `(S1…S7).P`: for
both eliminated rows the signed sum of the path rows' coefficient vectors equals the eliminated row's
exactly, with the signs `+FEED-P − MIX-pressure:0 + MIX-pressure:1 − FLASH-P:liquid` for the second. The
implementation's tuple order differs from the table's order (`test_k03_rank.py` compares as a dict); A30's
"exactly (ids, path rows, signs)" should say "as a set".

**O7 — `SPECIFICATION_CONFLICT`'s message says "there is no state satisfying both".** That is an
infeasibility claim, and it is the one place the vocabulary may make one: it carries an algebraic proof
(given affinity). Worth one sentence in the docstring so a later reader does not "fix" it into a hedge.

**O8 — `estimates.jacobian_nnz`** is the numerical nnz at `G(0)`'s state; the plan is meant to hold no
iterate. The compiler's structural pattern would be iterate-free.

---

## 5. The five questions of brief §1

**Q1 — Is `dR/dt` the derivative of `R`?** Yes, on the argument in O1, and I find no state for SYN-001 where
η ≤ 1e-10 holds and the derivative is of something else. The two provisos are: (a) the argument needs every
unit whose regime is *not* frozen to sit in a sink block of the inner system — true for SYN-001 (S3's lifted
split and `U-HEAT.Q` are sinks) and exactly what T01's rule must guarantee in general; (b) the floating-point
proviso of O1 near a saturated sink block. The brief's specific worry — "*an* inner solution rather than *the*
one the traversal used" — is answered by uniqueness: with `Ĵ_φu` nonsingular the branch through `x(t)` is
locally unique, and a state where two branches coalesce is exactly a singular `Ĵ_φu`, which the flash's
signature excludes and S3's sink status makes irrelevant. **No finding**, beyond M1 (the safeguard is
narrower than stated) and O1.

**Q2 — Is a two-probe certificate a certificate?** For the constant part, yes: given the rows are affine in
the pressure columns with the coefficients read at the plan state, the combination is identically constant
and two probes along a non-uniform shift witness that no pressure column survives the telescoping. For the
linear part it is a witness along one direction, not a certificate; the exact coefficient identity is
available for free and should be added (S4). For affinity itself no finite number of probes is a
certificate; that is a property of the declared row form, and the per-iterate check M1 restores is the
runtime guard. The 150 kPa conflict, the non-constant-mismatch refusal and the one-probe refusal are all
pinned by tests. **Finding: S4 (should-fix), plus M1.**

**Q3 — Is §9.1's flash-only signature the right principle?** Yes, and the reason survives T03: the frozen
set must cover every phase selection in a block that is upstream of or contains the tear rows in the
block-triangular form of the inner system, and no selection in a sink block — that is a statement about the
dependency graph, not about SYN-001. Freezing a sink's regime turns a discontinuity that `R` cannot see into
a wall the attempt must cross (R-012's measurement). What the principle relies on, and what should be said
next to it, is that a sink's branch is *someone's* responsibility: here it is §8.2's admissibility check and
K04's verification of the full state, because `U-HEAT.Q` is a certified quantity and the solver has
deliberately stopped watching the block that determines it. §8.2 is not implemented (S3). **Finding: none
against the principle; S3 for the guard it relies on.**

**Q4 — Do the evidence and the seeds establish G00 and G01?** G00 yes; G01 with limitations. Detailed in §6.

**Q5 — Does any of the 15 outcomes claim infeasibility by implication?** No. `STAGNATION` and
`LINE_SEARCH_FAILED` messages describe the search, not the problem (the cubic case of S6 is the test of this:
it stops at a merit stationary point and says only that no trial was accepted). `BOUND_BLOCKED` is a
statement about a direction. `SPECIFICATION_CONFLICT` does claim there is no solution, legitimately, with a
proof (O7). `LINE_SEARCH_FAILED` for an unevaluable initial point is misnamed (O5). **No finding.**

---

## 6. G00 and G01

**G00 — met.** Five variants from the registered initializer to the 20-digit recycle (worst 3.9e-14), the
products and duties, the overall balance, one tear, all named units. The limitation the brief states is
stated strongly enough and is correct: along the ray the map is affine and the variants exercise the
initializer, the exact derivative and the convergence test, not the globalization. M1–M5 do not change any
G00 number.

**G01 — met with limitations.** The callback half is K01's. The Newton half:

- What the seven seeds establish: the convergence test before any factorization (NUM-01), the typed singular
  failure (NUM-02 at r = 1), the scale transformation (A31), the exact bound landing and `BOUND_BLOCKED`
  (BND-01/02), the invalid-trial halving to `2⁻²⁰` (NUM-06), and stagnation without an infeasibility claim
  (NUM-05). OFF-A establishes a genuinely nonlinear two-step convergence on the real problem, at `α = 1`
  both times. OFF-B establishes the phase restart.
- What nothing establishes: that an **Armijo-rejected step followed by a shorter accepted one leads to a
  root**. On the real problem no registered start needs damping (OFF-A accepts `α = 1`; OFF-B's rejections
  are `invalid_trial` and `phase_update_required`). On the seeds, Armijo halvings occur in NUM-05 (*measured*
  56) and in the unregistered cubic (*measured* 71) and both end in typed failure, correctly; no test asserts
  the halvings in NUM-05, and the cubic's test asserts neither its halvings' effect nor its outcome. A02 —
  the assertion that the recorded acceptances and rejections obey the registered inequality — has no test.
- Therefore: the "damped" in "damped Newton" is exercised and its bookkeeping is consistent, but the
  registered evidence pins damping's failure modes and not its success mode. S6 (one seed, one assertion)
  and an A02 check on recorded traces close it. This is a coverage limitation, not a defect found: I read
  the line search (`newton.py:331–417`) and find it implements §5.3–§5.4 as written.

---

## 7. What this review does not establish

- Anything about the reference values: they are mine at 40 digits and I did not re-derive them here.
- Correctness of K01's differentiation or K02's unit models; I took the lifted rows and the traversal as
  given and checked only that the solver uses them as §3 says.
- The schemas, fixtures, generator and ledger (brief §10) — not examined beyond reading `trace.py`.
- Bit-reproducibility across runs or platforms; I ran the gate once.
- The finite-difference oracle at 365 K, which nobody has run (S5).
- Any behaviour at a saturated lifted stream (O1) — named by the specification as unestablished and still so.
- Performance at any size beyond 47 variables; S7 is a count, not a timing.
- Human numerical or process-modeling sign-off: `review.numerical` and `review.process_model` stay `pending`;
  this document does not set `reviewed` on anything.
