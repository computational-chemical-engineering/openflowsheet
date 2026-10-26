# S10-C — the absent component's roundoff lift: K03's release at every step

**Package:** S10-C (design lane, `architect`; brief `docs/briefs/S10C-absent-component-ruling.md`), 2026-10-26.
**Amends:** `docs/derivations/K03-solver-spec.md` §5.3 (the release paragraph of 2026-09-25), register R-064, and the
witnesses of T06 A93 and T07's record-k leg (§4.7).
**Register:** R-782. **ADR:** none. No frozen interface (plan §2.1, §2.2) and no accepted ADR changes. R-064 was itself a
§5.3 amendment without an ADR, and this note widens it under the condition R-064's "Watch for" set: it brings its own
inertness proof.
**Closes:** S10-C design §7 Q4 for C-MW (CI run 40275276182: aarch64 fails A40–A42 on C-MW).

---

## 1. Problem and scope

C-MW is a methanol–water column on the three-component `wilson-ig-v1` record set. Ethanol is absent from every inlet.
At Stage A's start, 60 free columns (every stage's `l` and `v` of C2H5OH, and the product draws) sit at exactly `+0.0`,
and their exact Newton step is zero at every iterate. K03 §5.3 (R-064) discards the factorization's roundoff on such a
set only when the roundoff would block (`α_max = 0`). When the 60 roundoff entries of a step happen to be all `≥ 0`,
nothing blocks, the step is taken, and the set is lifted to about 1e-15 mol/s. After that its rows are no longer
exactly zero, so R-064 can never release it again. Roundoff-sized flows then cap every later `α_max` until one of them
lands on zero and blocks: `BOUND_BLOCKED` on `COL.stage.1.r.C2H5OH` on aarch64 at iteration 4, ending in
`homotopy_stalled(BOUND_BLOCKED)`. The sign pattern of BLAS roundoff decides whether the lift happens. On x86-64, 160 of
320 solves perturbed by 1–4 ulp fail the same way (`docs/S10C_DECISIONS.md`, "S10-C diag"). C-MW passes on x86-64 by
luck, not by margin.

The same defect is present beyond C-MW (measured, §4.6). Every `F-BUDGET` in T06's recorded ensembles on x86-64 is this
lift: the solve converges in 245–424 property calls once the lift is removed, where with it the solve exhausted 10 000.

**In scope.** The bound-aware step of K03's Newton core (`numerics/newton.py`, `_bound_aware_step`). The change applies
R-064's release at every iteration where it changes the step, with the same exactness conditions. Also in scope: the
rulings on the registered records that move (§4.7).

**Out of scope.**
- T04's PTC core. Its pseudo-steps and polish keep §5.3's first paragraph (R-064 amendment).
- The Anderson accelerator's bound handling.
- The linear solve and its records (ADR 0004).
- Case registration: C-MW and C-EW stay as registered.
- Equilibrium forms and S11.
- Any tolerance or budget constant.
- Cross-platform *bitwise* identity of the answers. Only the outcome and the registered tolerances are claimed to be
  platform-independent, as they are today between CI and local x86-64.

## 2. Constraints and invariants

- **Exact path.** The rule contains no tolerance. `x_i == lo_i`, `F_r == 0.0`, `J_{r,c} != 0.0` and `d_i != 0.0` are
  exact floating-point comparisons, and the squareness count is exact.
- **R-064's invariants stand unchanged.**
  - `Z₀` requires the bound at the attempt's opening *and* at the iterate. A component that reached its bound during
    the attempt (T02 §6.3.3's disappearance) is never released.
  - A set is released only if its closed rows number exactly its columns. `Z*` is the union of the released sets.
  - `BOUND_BLOCKED`'s `blocked_by` is computed from the original direction.
  - No record is added. T04 callers pass `opening=`.
- **The step taken is the exact Newton step.** Zeroing `d` on `Z*` replaces roundoff with the exact value of the linear
  system's solution there. It never changes the exact step.
- **Bit identity.** Every registered solve in which the rule does not act (§4.4) stays bitwise unchanged, records and
  digests included. The solves in which it acts are named before implementation (§4.6). Each one is re-checked against
  its registered criteria, never re-tuned (§4.7).
- **Platform.** The fix must not depend on BLAS kernel, thread count or architecture. The evidence includes an aarch64
  run.

## 3. Decision

**(a): apply R-064's release at every iteration at which it changes the step.** That means wherever some component of
the largest released set `Z*` has a nonzero direction entry, with R-064's exactness conditions unchanged. Where
`α_max = 0`, R-064's existing paragraph applies verbatim.

This is the remedy and not a relaxation. R-064's proof that the exact step on `Z*` is zero (§4.2) never uses
`α_max = 0`. That condition only limited *where* roundoff was discarded. Discarding it at every step makes the iteration
the exact Newton iteration on `Z*` at every step, and that makes `Z*` an invariant set (§4.3): an absent component stays
at exactly `+0.0` on every machine for as long as its rows stay exactly closed. It is the smallest change that removes
the dependence on the sign of roundoff. As R-064 already found, the defect is arithmetic, not physics.

### Rejected alternatives

| Alternative | Why rejected |
| --- | --- |
| (b) A structural zero for a component absent from every inlet (pinned flows, rows dropped; column- or case-scoped form) | It changes the rows, variables and records of every attempt where it applies, which is why R-064 rejected the general form. It needs an ADR, and a definition of "absent from every inlet" that survives recycles. It also leaves the exposure in place wherever the structure is not a column: the T06 `THM-*` and `STA-02` revisions, NP-* and SC-*. More structure for a narrower fix. |
| (c) Register C-MW/C-EW on a two-component record set | Hides the exposure instead of removing it. It also removes S10-C's only registered evidence on absent-component handling (A41's absent flows, R-780). The T06 `F-BUDGET`s would remain. |
| (d) Keep `homotopy_stalled(BOUND_BLOCKED)` as a limitation | Against Frank's directive (fewest limitations, robustness first). A40–A42 would become platform-dependent, a class R-627 does not cover. x86-64 itself passes only by roundoff sign (160/320 perturbed solves fail), so a BLAS or libm update could flip it. |
| (e) Eliminate `Z*` from the linear solve (factor `J` on the complement) | Exact by construction. But it changes the factorization, the complement's direction (by roundoff) and ADR 0004's linear record in **every** attempt with a nonempty `Z*`, including every `α_max = 0` release today (NP-2, NP-G, SC-2, C-EW's first three steps). At the iterate level it gains nothing over assigning the exact zero. The result is a far larger identity blast radius and a change to a recorded interface. |
| (f) Compute `Z*` once at the attempt's opening and hold `d_{Z*} = 0` | Not provable at later iterates. Closure depends on `F(x)` and `J(x)` at the current iterate: a row closed at the opening because a coupling variable was zero there can open later. The proof covers per-step recomputation, which is cheap (§4.5). |
| (g) A roundoff threshold on inward or outward directions | A tolerance on the exact path. Rejected by R-064 and by the brief. |

## 4. Design

### 4.1 The rule (normative; replaces nothing, extends K03 §5.3)

After the linear solve at iteration `k`, let `d` be the unscaled direction and `ŝ` the scaled step kept for the record:

```
(α, L) := alpha(x, d, lo)                                    # §5.3 first paragraph, unchanged
if α == 0:
    R-064 as amended 2026-09-25 — unchanged, bit for bit
else:
    C := { i : lo_i finite, x_i == lo_i, opening_i == lo_i, d_i != 0 }   # one vectorized mask
    if C == ∅:                       return (d, α, L, released=())       # today's path
    Z* := released_set(x, opening, lo, F(x), J(x))           # the existing `_released`, unchanged
    if Z* ∩ supp(d) == ∅:            return (d, α, L, released=())       # today's path
    d' := d;  d'[Z*] := 0.0          # solve_newton zeroes ŝ[Z*], as it already does for released sets
    (α', L') := alpha(x, d', lo)     # equals (α, L), proved in §4.2; recomputed anyway
    return (d', α', L', released=Z*)
```

The line search then uses `d'` for every halving, as it already uses the released direction at `α_max = 0`. The landing
rule applies to `L'` at the first trial. Nothing else in `solve_newton` changes. `C` uses `d_i != 0` rather than
`> 0` so that the rule reads the same for any finite bound. For `lo_i = 0`, an entry `d_i < 0` in `C` forces `α = 0`
and never reaches this branch.

### 4.2 The step is still the exact Newton step, at any `α_max`

`J` has just been factorized, so it is nonsingular. Let `Z ⊆ Z₀` be released: the rows `R(Z)` with `F_r(x) == 0.0` and
every nonzero `J_{r,c}(x)` in a column of `Z` number `|Z|`. Row `r ∈ R(Z)` of `J d = −F` reads
`Σ_{c∈Z} J_{r,c} d_c = −F_r = 0`. The rows `R(Z)` of a nonsingular `J` are independent and have support in `Z`, so the
`|Z| × |Z|` block `J_{R(Z),Z}` has full rank and the exact solution has `d_Z = 0`. Nothing here involves `α_max`. The
argument concerns the evaluated `F` and `J`: an exactly-zero Jacobian entry, structural or not, closes a row exactly,
because the linear system being solved is the evaluated one.

**`α` and `L` are unchanged in the `α > 0` branch.** A component enters `α`'s minimum or `L` only if `d_i < 0` and
`x_i + d_i < lo_i`. For `i ∈ Z* ⊆ Z₀` we have `x_i == lo_i`, so such an `i` would give the ratio
`(lo_i − x_i)/d_i = 0`, and then `α = 0`. In the `α > 0` branch, therefore, no component of `Z*` is in the minimum or
in `L`, and zeroing `d` on `Z*` leaves both unchanged. The rule's only effect there is on the trial coordinates of `Z*`:
each `x_i + α d_i` with `d_i > 0` (roundoff) becomes exactly `lo_i`. One hypothetical exception is a finite `lo_i ≠ 0`
where `lo_i + d_i` rounds to `lo_i`; then `d_i < 0` can reach this branch, but by monotone rounding the trial
coordinate is `lo_i` with or without the rule.

### 4.3 `Z*` becomes invariant

Under the rule, a released component's trial coordinate is `lo_i` at every step where it is in `Z*`. Suppose its rows
are exactly zero whenever the set sits exactly at its bound. That holds for an absent component's balances and
equilibrium rows, whose terms are products with exactly-zero flows. Then `Z*` at the next iterate contains the
component again, and it stays at `+0.0` for the whole attempt on every machine. This is the property C-MW lacked.

The invariance is a consequence, not an assumption. The rule recomputes `Z*` at every step from `F(x)` and `J(x)`. A
component whose rows open (a reaction or a recycle starts producing it) leaves `Z*` and moves with its exact nonzero
step. R-064's rejection of "freeze every exactly-zero flow" is respected.

### 4.4 Inertness theorem

Consider a registered solve run on the pre-change code on a given machine. Call iteration `k` of an attempt **acting**
when `α_max(d_k) > 0` and `Z*(x_k) ∩ supp(d_k) ≠ ∅`. For `lo = 0` this is equivalent to: some released component has a
strictly positive direction entry, which is the event that lifts it.

**Theorem.** If no iteration of any attempt of a solve is acting, the solve under the amended rule is bitwise identical
to the pre-change solve on the same machine: every iterate, trial, record, outcome and digest.

*Proof.* By induction on iterations. With identical `x_k`, the residual, Jacobian, factorization, `d_k` and `ŝ_k` are
identical: same code, same inputs. If `α = 0`, the branch is unchanged code. If `α > 0` and `k` is not acting, then
either `C = ∅` or `Z* ∩ supp(d_k) = ∅`, and the amended function returns exactly the pre-change tuple `(d, α, L, ())`.
The trial, its evaluation and the acceptance test are then unchanged, so `x_{k+1}` is identical. ∎

The first acting iteration of a solve is the same with or without the change, because everything before it is
identical. So **the solves whose trajectories move are exactly the solves with an acting iteration on the pre-change
code.** A record or digest that does not capture the affected trial may still compare equal. The measured cases are the
NUM-03 ensemble, the SC-3 tests and the identity scripts' own runs (§4.6). The identity gate therefore checks
*moved ⊆ acting*, at the granularity of tests, records and digests.

### 4.5 Implementation shape and cost

- One function changes: `_bound_aware_step` in `src/openflowsheet/numerics/newton.py`, as in §4.1. `_released`,
  `_bound_aware_alpha`, `_trial_point` and `solve_newton` are unchanged; the caller already zeroes `ŝ` on whatever
  `released` it is handed. The docstrings of `_bound_aware_step` and the module header (line 23) cite R-782.
- **Order matters for identity.**
  - Compute `(α, L)` first.
  - When `α == 0`, take the R-064 branch exactly as today. Do not restructure it.
  - Evaluate `C` only in the `α > 0` branch.
  - Call `_released` only when `C ≠ ∅`.
  - Return the pre-change tuple, with `released = ()`, whenever `Z* ∩ supp(d) = ∅`.
- **Cost.** Every iteration of every solve pays one vectorized mask over `n`: four comparisons and an `any`. `_released`
  runs only at iterations with `C ≠ ∅`. It costs one CSR conversion of `J` and one pass over the rows. Over the whole
  test suite it is called 384 times, in 20 tests, and never on a SYN-001 path (§4.6). The common path allocates
  nothing.
- **No record, no new field.** `SolveEvent`, `LinearRecord` and `SolvePolicy` are unchanged. `step_inf` is computed from
  the zeroed `ŝ`, as it already is for releases at `α_max = 0`.

*Erratum 2026-10-26 (design lane, `reviewer`; `docs/reviews/S10C-r782-review.md` F1, F6; register R-783).* Two cost
statements above are corrected; the rule and the evidence are unchanged.
- **"The common path allocates nothing."** It allocates about six `n`-length boolean temporaries per iteration for the
  mask. That is negligible (G-R6: −1.2 %).
- **"It costs one CSR conversion of `J` and one pass over the rows."** `_released` also runs a recursive maximum
  matching (Kuhn) and a fixed-point propagation. Both are superlinear in `|Z₀|`.
  - Measured on a closed block shaped like a column: 0.4 ms at `|Z₀| = 60`, 213 ms at 4 000 and 1.5 s at 10 000.
  - A single absent component over 1 000 stages raises `RecursionError`.
  - This is R-064's code; R-782 runs it at every iteration with `C ≠ ∅` instead of only at `α_max = 0`.
  - No registered case exceeds `|Z₀| = 60`.
  - The remedy is an iterative matching with a worklist propagation, inert because `Z*` is unique (review F1).

### 4.6 Measured before the decision (scratch, on `f1a0a058`, local x86-64; not committed code)

A scratch copy of the tree carried §4.1 plus an observation log. In mode `detect` it returned the pre-change tuple and
logged the acting iterations; in mode `apply` it applied the rule.

- **C-MW, one solve per OpenBLAS kernel.**

  | Kernel | Pre-change | Amended |
  | --- | --- | --- |
  | default (Haswell) | `CONVERGED` in 9 | `CONVERGED` in 9 |
  | Prescott | `HOMOTOPY_STALLED` (worst 1.26e5 on B) | `CONVERGED` in 9 |
  | Sandybridge | `HOMOTOPY_STALLED` (worst 1.26e5 on B) | `CONVERGED` in 9 |
  | Nehalem | `CONVERGED`, only after a first attempt ended `BOUND_BLOCKED` at iteration 8 | `CONVERGED` in 9 |

  Under the amended rule, all four take a full step (`α = 1`) after the four opening halvings, and the worst A41 ratio
  is 1.2941e-7 to 1.2946e-7. At every acting iteration `|Z*| = 60`, and no component of `Z₀` with a nonzero direction
  was left outside `Z*`.
- **C-MW, the 320-solve ulp-perturbation campaign.** The perturbations are `x⁰` (±1 and ±1…4 ulp), the profile, the
  sweep T, the sweep K, the Newton step entries and libm `exp`/`log`, 40 seeds each.
  - Pre-change: 160 `HOMOTOPY_STALLED`, 55 rescued by edge 3, 105 converge directly.
  - Amended: **320/320 `CONVERGED`, every first Newton solve in 9 iterations, worst A41 ratio 1.2949e-7.** This matches
    the build lane's name-based causal check, now with `Z*` found by the rule itself.
- **Answers.** The 60 absent flows are exactly `+0.0` in both cases. Before the change they were up to 2.41e-18 mol/s in
  C-MW and 3.84e-22 mol/s in C-EW: the lift, and the source of R-780's measured 1.26e-18 and 2.18e-22. C-EW has one
  acting iteration, its last step. It converges in 4 either way, and its worst A41 ratio (2.1396e-8) is unchanged in
  every printed digit.
- **Whole suite** (408 test files, one pytest process per file).
  - The pre-change acting set **D**, by test, is 12 tests:
    - `test_s10c_columns.py`: A35 (M1 on C-MW); A40–A45 on C-MW and C-EW; A44 on C-MW and C-EW.
    - `test_t05b_contract.py`: B08/B10 [SC-3].
    - `test_t06_f4_edge3.py`: G3 [SC-3].
    - `test_t06_w20_counters.py`: A93 [THM-08-3, THM-08-12, THM-09-4].
    - `test_t07_interrupt.py`: `test_interrupt_at_every_record` and `test_interrupt_at_record_k[THM-09-4]`.
  - Detect mode: 13186 passed, 13 failed. Apply mode: 13182 passed, 17 failed.
  - The 13 shared failures are artifacts of the scratch set-up and occur in both modes. `test_m07_journey` A21 refuses
    a dirty tree. `test_t01_structural` fails when its file runs alone (test order).
  - The 4 extra failures are all in D: A93 ×3, where the starts now `CONVERGED` instead of `BUDGET_EXHAUSTED`, and T07
    record-k [THM-09-4], where the trace length pin of 154 is now 94.
  - Every other test in D passes. **No test outside D moved.**
- **Identity scripts (apply mode).** `S10C-IDENTITY PASS n=858 changed=[]`, and
  `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`, which is its registered pass line.
- **T06 ensemble, all 880 starts** (`starts-nominal-v1`, `holdout1`), run in both modes and compared by record with wall
  times excluded:

  | File | Starts moved | `F-BUDGET` → `SUCCESS` | `SUCCESS` → `SUCCESS` (bits only) | Any → failure |
  | --- | --- | --- | --- | --- |
  | nominal | 13 | 3: THM-08/03, THM-08/12, THM-09/04 | 10: STA-02/01, /03, /14; THM-07/13; THM-08/14, /17; THM-09/11, /14, /15, /16 | 0 |
  | holdout | 13 | 2: THM-09/24, /35 | 11: NUM-03/26; STA-02/22, /23, /27, /30, /36, /38; THM-07/34; THM-08/28, /37, /38 | 0 |

  Uncapped, the three nominal `F-BUDGET` starts now converge in 245, 279 and 424 property calls. With the lift they
  exhausted 10 000.
- **PTC-R1 (T08), all 882 runs (441 starts × 2 arms):** no acting iteration, nothing moved.

*Amended 2026-10-26 (§8.1–§8.2, R-784).* The CI dispatch adds the aarch64 and CI x86-64 results, including THM-09/03 on
ci-aarch64 (`F-BUDGET` → `F-FALSE-SUCCESS-CAUGHT`), which this local table could not show.

### 4.7 Registered records that move, and the rulings

These rulings are part of R-782. None of them edits a budget constant, a tolerance, a recorded run or a case.

1. **S10-C's C-MW and C-EW (A35, A40–A45).** The bits move and the assertions pass at their registered tolerances. The
   absent flows are now exactly `+0.0`. R-780's decision is unchanged, since exact zeros remain *not required*; only its
   measured figures are superseded.
2. **SC-3 (T05b B08/B10, T06 F4 G3).** The bits move, the tests pass, and no fixture pins them. No action.
3. **T06 A93, which loses its witnesses.** A93 tests that a revision-path solve's recorded `property_calls` equals what
   its meter charged, and equals `max_property_calls` exactly at `BUDGET_EXHAUSTED(property_calls)`. Its witnesses were
   run 1's three `F-BUDGET` starts, and since R-782 they converge.
   **Ruling:** the same three starts are re-run under `T06-revision-v2` with a *test-local* policy,
   `dataclasses.replace(entry.policy, max_property_calls=100)`. Each must end `BUDGET_EXHAUSTED` with
   `counters.property_calls == counters.requested_evaluations == 100` and no crash. The test asserts the local cap is
   100, in place of 10 000.
   Measured: all three hit exactly 100. 100 is 2.45× below the smallest converged cost (245), which leaves margin for
   cross-platform trajectory differences.
   A second test records R-782's effect: the same three starts, uncapped, are classified `SUCCESS` by
   `ensemble.classify`.
   The registry's `T06-revision-v2` stays at 10 000. This is a test witness, not a budget edit (R-087 "Watch for").
   A93's row in T06's spec gets an amendment note citing R-782.
4. **T07 G5 record-k leg (`test_t07_interrupt.py`).** THM-09 start 4 now converges in 94 records, where before it ended
   in a budget refusal after 154.
   **Ruling:**
   - `RUNS` is unchanged. The THM-09 length pin becomes the amended measurement on ref-x86-64 (94). Every `k ∈ K` still
     interrupts inside the run, since 89 < 94.
   - The "Measured at the base" comment gains an R-782 line, giving the new records / plan events / outcome and keeping
     the old line as history.
   - `test_interrupt_at_every_record` keeps the uncapped THM-09 start 4. To keep the budget refusal covered, it adds
     every record of THM-09 start 4 under the same test-local cap (`max_property_calls = 100`), each run plus one past
     the end. `prepare()` takes an optional policy override for this.
   - If CI aarch64 measures a length other than 94, the pin becomes a map keyed by `ensemble.machine_class()` holding
     both measured values. Record it in the decisions file; this is not a design question.
5. **T06 recorded ensemble runs** (run 1, run 2, run 2r, holdout1, on every class). They are records and are neither
   re-scored nor edited (R-087 and its 2026-09-27 amendment). A later dispatched A98 comparison of run 2r against run 2
   will report class discrepancies exactly at the starts listed in §4.6, for example `S` going from 434 to 437 on
   ref-x86-64. **These are R-782's declared consequence, not a regression.** Run 2's gate verdict stands, and any new
   run is a further record. R-782 is a correctness remedy to the solver, the route R-087 names ("remedies change the
   solver"). It is not a cost remedy, so R-087's result-inertness clause for cost remedies does not apply.
   *Amended 2026-10-26 (§8.1, R-784):* THM-09/03 on ci-aarch64, `F-BUDGET` → `F-FALSE-SUCCESS-CAUGHT`, is one of these
   declared consequences, and item 4's machine-class map applies to every class, not only aarch64 (§8.2).

## 5. Work orders (build lane, `opus-engineer`; dependency order)

Each WO is one commit on `wp/S10C`, with a message naming S10-C and R-782. Decisions and run lines go to
`docs/S10C_DECISIONS.md` under a new heading, "R-782 (absent-component release)".

| WO | Content | Acceptance |
| --- | --- | --- |
| **WO-R1** detector (inert tooling, before any solver change) | `scripts/s10c_release_detector.py` is a pytest plugin module, run as `pytest -p s10c_release_detector …` with `scripts` on `sys.path`. At configure time it wraps `openflowsheet.numerics.newton._bound_aware_step` **observation-only**: it returns the wrapped function's result unchanged. For each call with `α > 0` it evaluates §4.4's acting predicate using the module's own `_bound_aware_alpha` and `_released`. It writes one JSON line per acting iteration (`PYTEST_CURRENT_TEST`, `n`, `\|Z*\|`, `\|Z* ∩ supp(d)\|`, `max d` there) to a directory named by an environment variable, and a session-finish hook prints one line: `DETECTOR acting_tests=<N> acting_iterations=<M> released_calls=<K>`. Run it over the whole suite on this commit and record D. Also run the T06 ensemble (`scripts/t06_ensemble.py run`, nominal and holdout, run ids `r782-pre` and `holdout1`) on this commit, outputs kept outside the repository. | The suite's pass/fail set under the spy equals the plain suite's. On the workstation, D equals §4.6's 12 tests. If it does not, stop and report: the predicate is evaluated on the pre-change trajectory. |
| **WO-R2** the rule and its moved witnesses (one commit, so that a revert takes both) | Step 1: §4.1 in `_bound_aware_step`, with its docstrings, and the new tests in `tests/test_k03_r782_release.py` (G-R1). Existing B33c i–v unchanged. Run G-R4 on this working tree: exactly the four tests that §4.7 items 3–4 name fail. Step 2: §4.7 items 3 and 4, that is, the A93 capped witnesses plus the uncapped `SUCCESS` test, and the T07 re-pin plus the capped every-record leg. The A93 amendment note in the T06 spec is already committed with this note. | G-R1, G-R2, G-R4 (at step 1), G-R5 and G-R6 locally; full suite passes at step 2; ruff and mypy clean. |
| **WO-R3** aarch64 and ensemble evidence | Cherry-pick WO-R2 onto the scratch branch `wp/S10C-diag`, then make **one** CI dispatch with `s10c_diag=true` and `ensemble=true`. Then push `wp/S10C` and let CI run. Keep the artifacts under `evidence/S10c/<commit>/artifacts/` (ignored), referenced by SHA-256. Do not commit them as T06 run files. Re-run the T06 ensemble locally at WO-R2 and compare with WO-R1's run (G-R7). | G-R3, G-R7. |
| **WO-R4** manifest | Regenerate the S10-C evidence manifest at the final head with its generator. A40–A42 now carry the aarch64 run, and G1 is re-run. Run the T08 harvest only if the generator's `--check` requires it. | Manifest `tested`; `reviewed` not set. |
| **Review** | One focused `reviewer` pass on WO-R1 and WO-R2 against this note: a numerics change in the Newton core. | Verdict recorded. Merge per CLAUDE.md: full gate, CI green on both architectures. |

*Amended 2026-10-26:* WO-R5 (F2) and WO-R6 (F1) come before WO-R4; the order from WO-R4 on is §8.5's.

## 6. Verification gates

| Gate | Invariant | Measured how | Pass criterion | Configurations |
| --- | --- | --- | --- | --- |
| **G-R1** unit | §4.1–§4.2 at the function level | `_bound_aware_step` on hand-built `x`, `d`, `F`, `J`, with two or three variables and `lo = 0` | (i) `a` at `+0.0` at the opening and the iterate, row `F = 2a` closed, `d_a = +1e-30`, and `b = 1` with `d_b = −0.5`: the result has `d_a == 0.0` and `released == (0,)`, and `α` and the landing equal the unmodified direction's. (ii) As (i) but with the closed row's `F = 1e-300`, not exactly zero: nothing is released and `d_a` is kept. (iii) `a` positive at the opening, zero at the iterate, `d_a > 0`: not released. (iv) Two columns and one closed row (underdetermined): not released. (v) `d_a == 0.0` already: the returned direction equals the input and `released == ()`. B33c i–v pass unchanged. | local |
| **G-R2** C-MW robustness | The outcome does not depend on roundoff sign | The perturbation harness (`scratchpad/harness`, 320 solves) and `OPENBLAS_CORETYPE` ∈ {Haswell (default), Prescott, Sandybridge, Nehalem} | 320/320 and 4/4 `CONVERGED`. The first Newton solve takes 9 iterations in every case. Worst A41 ratio ≤ 1e-6 (measured 1.2949e-7). The 60 absent flows are exactly `+0.0` at the answer, in C-MW and in C-EW. | local x86-64 |
| **G-R3** aarch64 | The same, on the failing platform | The dispatch's `s10c-diag` job, then CI on `wp/S10C` | aarch64: C-MW `CONVERGED`, A40–A42 pass, absent flows `+0.0`. CI green on x86-64, aarch64 and default-install. | CI |
| **G-R4** identity | §4.4: nothing outside D moves | The full suite at WO-R2 step 1. `scripts/s10c_identity.py` and `scripts/s08_identity.py`, with base trees as registered. The T02–T07, T05b and K05 identity keys through their tests. | Every test outside D passes unchanged. The only failures at WO-R2 step 1 are the four that §4.7 items 3–4 name. `S10C-IDENTITY PASS n=858 changed=[]`, and S08's registered pass line. | local x86-64 |
| **G-R5** moved records | The solves in D still meet their registered criteria | The assertions as registered, and §4.7's amended witnesses | All pass at registered tolerances. A93 capped: exactly 100 and 100 on all three starts; uncapped: `SUCCESS`. T07: every `k` and every record interrupt correctly, uncapped and capped. No tolerance, case, budget constant or recorded run is edited. | local and CI |
| **G-R6** cost | Negligible overhead | G9's SYN-001 S02/S08 timings (S10-C design G9) before and after WO-R2, on the same machine, 3 repetitions | Median change ≤ +2 % | local |
| **G-R7** ensemble | No start regresses, on either class | The T06 ensemble, nominal and holdout, before (WO-R1) and after (WO-R2) locally, and the dispatch on both classes against the same-class committed run 2r and holdout1 records | Locally, the moved starts and class transitions equal §4.6's table. On every class, no start that is `SUCCESS` in the committed same-class record becomes non-`SUCCESS`, and every class change is failure → `SUCCESS`. Any other change stops for the design lane. *Amended 2026-10-26: the CI criterion is §8.2's.* | local, CI x86-64, CI aarch64 |

## 7. Risks and open questions

| # | Question | Needs | Default (work proceeds on it) |
| --- | --- | --- | --- |
| Q1 | Does T04's PTC core (pseudo-steps, polish) have the same lift exposure? R-064 kept PTC out because the proof does not transfer to `J + D/Δt` as it stands. | A fact: a detector on PTC's step. PTC-R1 measured nothing acting in the Newton arm; PTC was not instrumented. | Out of scope; PTC unchanged. R-782 lists it under "Watch for". A PTC failure on an absent component goes to the design lane and is not tuned. |
| Q2 | Could a solve in D have converged *because* of the lift, and now fail? | A fact: G-R5 and G-R7 | None did, across the suite and 880 ensemble starts locally. If one does on CI, stop and escalate with its trace. Never restore the lift. |
| Q3 | Registered campaigns not re-run here (V17/W27 tasks, release-candidate distributions) | A fact, workstation-only | The next release-candidate run covers them. R-782 is cited as the solver change between candidates. |
| Q4 | Should the one CI dispatch include the T06 ensemble (2 × 440 starts on each class, up to 180 min per runner), or only the `s10c_diag` job? | Frank's preference (CI minutes) | Include it. It is R-087's "re-run on both machine classes" for a solver remedy, and the only aarch64 evidence that no ensemble start regresses. |
| Q5 | Land this K03 change inside S10-C, as R-064 landed inside T05b, or as a separate K03 package? | Frank's preference (scope) | Inside S10-C on `wp/S10C`, with its own reviewer pass, following R-064's precedent and the directive to fix rather than register a limitation. |
| Q6 | The T07 length pin on aarch64 | A fact: G-R3 | §4.7 item 4's machine-class map if the values differ. |

## 8. Amendment 1 (2026-10-26, design lane `architect`): after the CI evidence

**Brief:** `docs/briefs/S10C-r782-ci-ruling.md`. **Register:** R-784 (§8.1–§8.2), R-785 (§8.3), R-786 (§8.4).
**Evidence:**
- Dispatch run 40295256025 on `wp/S10C-diag2`, commit `4a4677c4`, which is `1bc65b86` plus the gated diag job.
- Local runs on exported trees of `f9122cc7` (pre-change, with the WO-R1 detector) and `03ef9e2e` (R-782).
- Scripts: `docs/derivations/scripts/s10c_r782_gr7.py` (class comparisons) and `s10c_r782_one_start.py` (one start
  under the detector).

This section is normative where it says so. It edits no recorded run, tolerance, budget constant or case.

The CI artifacts used are kept outside the repository. WO-R4 files them under `evidence/S10c/<commit>/artifacts/`.

| Artifact | SHA-256 |
| --- | --- |
| `ensemble-ubuntu-latest/run2r-ci-x86-64.json` | `01e012583bb93365a32347e161085c3bc4476dcdd6ad5181b9c2f3b237b290e0` |
| `ensemble-ubuntu-24.04-arm/run2r-ci-aarch64.json` | `654c0804006ee6fd35df7b2ca36cef644dffea40fb56a6836b32197eee3019db` |
| `ensemble-ubuntu-latest/holdout1-ci-x86-64.json` | `79c1e9c73591d1857c6c670374ae3b114f69628658858cb1181aa8255490d7c8` |
| `ensemble-ubuntu-24.04-arm/holdout1-ci-aarch64.json` | `79c12f0aa4f45d7217e743513f35bd75f275b42f3c32b0a9fa69ce6f6ef0ae83` |

### 8.1 THM-09/03 on ci-aarch64: what changed, and the ruling

**The records.**

| Record | Class | Attempts closed | Property calls | Worst ratio |
| --- | --- | --- | --- | --- |
| ref-x86-64 runs 1, 2, 2r; ci-x86-64 runs 2, 2r (committed, pre-change) | `F-FALSE-SUCCESS-CAUGHT` | `PHASE_UPDATE_REQUIRED`, `CONVERGED` | 311 | 507999.99999999837 on `S4.T` |
| ci-aarch64 runs 2, 2r (committed, pre-change; bitwise equal) | `F-BUDGET` | `PHASE_UPDATE_REQUIRED`, `BOUND_BLOCKED`, `EVALUATION_ERROR` | 10 000 | none |
| R-782 dispatch, ci-x86-64 and ci-aarch64 | `F-FALSE-SUCCESS-CAUGHT` | `PHASE_UPDATE_REQUIRED`, `CONVERGED` | 311 | 507999.99999999837 on `S4.T` |
| Local ref-x86-64, 12 OpenBLAS kernels (default, Prescott, Core2, Penryn, Dunnington, Nehalem, Sandybridge, Haswell, Zen, Barcelona, Bulldozer, Atom), pre-change and R-782 trees | `F-FALSE-SUCCESS-CAUGHT` | `PHASE_UPDATE_REQUIRED`, `CONVERGED` | 311 | 507999.99999999837 on `S4.T` |

On the local runs the detector counted 0 acting iterations and 0 `_released` calls, on both trees and under all 12
kernels.

**What the solver returned, and why the verifier caught it.**
- Under R-782 on aarch64 the solve ends `CONVERGED` after 5 iterations in 2 attempts.
- The certificate's verdict is `FAILED`, with `false_success_detected`.
- Its `not_passed` list is `energy_balance.U-PHF`, `energy_balance.envelope`, `independent_split.U-PHF.S2.B`,
  `independent_split.U-PHF.S2.total` and `phase_admissibility.U-PHF.S2.closure`. There is no rank loss
  (`rcond_1` = 1.41e-3).
- This is THM-09's trivial `V → 0` root. T06's verdict (`docs/reviews/T06-verdicts.md`) records it on x86-64 as "failing
  on energy balance and independent split", and `docs/reviews/T06-review.md` gives it as 5.08 K off in `S4.T`.
- The event sequence (36 events), the iterations and the certificate's check list equal those of every x86-64 record
  from run 2 on.

**R-782 is what changed its path on aarch64.** The argument is a chain; no detector ran on aarch64 (§8.6 Q-B).
1. On x86-64 the start never acts. In every record and under every local kernel, no on-bound component has a nonzero
   direction entry at any iterate (`_released` is never called). The x86-64 outcome is therefore the pre-change code's
   exact-Newton outcome, the same with or without R-782.
2. The committed aarch64 trajectory leaves the x86-64 one at attempt 0's second iteration. That iteration takes a step
   with no line-search halvings, where x86-64 takes seven. The trajectory then runs `PHASE_UPDATE_REQUIRED` →
   `BOUND_BLOCKED` → `EVALUATION_ERROR` → budget, which is the lift's pattern of §1 and of the three x86-64 `F-BUDGET`
   starts. T06's verdict §2.4 describes it in those words.
3. Under R-782 the aarch64 trajectory equals the x86-64 one in its event sequence, iterations and counters, and in its
   worst ratio to every printed digit. Only the state's bits differ (`full_state_sha256` `e60162a3…` against x86-64's
   `916137aa…` / `eae0daa4…`).
4. Over the interval `6018ebcc` → `4a4677c4` on aarch64, 423 of 440 nominal and 429 of 440 holdout final states are
   bitwise unchanged. Every start that moved is in a family where R-782 acts: STA-02, THM-07, THM-08, THM-09. By §4.4,
   a start that moves had an acting iteration on the pre-change code on the same machine.
5. No x86-64 kernel reproduces aarch64's roundoff on this start. The difference comes from aarch64's own arithmetic, not
   from which BLAS kernel is chosen, so the local detector cannot see it.

**It is not a regression in substance.**
- Both classes are failures. S is unchanged by this start on both classes: it moves 434 → 437 only through the three
  `F-BUDGET` → `SUCCESS`.
- No unverified answer is delivered as verified. The certificate rejects the state, and the start now fails in 311
  property calls instead of 10 000.
- The new class is the start's exact-Newton outcome, which x86-64 reaches on every record and kernel without the rule
  acting. R-782 replaced aarch64's roundoff by the exact zero of §4.2. The old `F-BUDGET` was the roundoff artifact, not
  a better outcome.
- It removes a registered platform dependence. T06's verdict names two per-start outcomes that differ between the
  architectures (`T06-verdicts.md` §2.3(d) and §5 item 4): THM-09/03's class, and the rescue status of STA-02/0, /2 and
  /17. Under R-782 both agree across architectures (§8.2).
- The trivial root belongs to THM-09's starts and the phase logic, and the certificate catches it by design. The only
  thing that kept aarch64 off it was roundoff seeding an on-bound component, which R-783's "Watch for" (self-coupled
  absent set) excludes: a seed must come from the initializer.

**Ruling (R-784).** Accepted.
- THM-09/03 on ci-aarch64, `F-BUDGET` → `F-FALSE-SUCCESS-CAUGHT`, is one of R-782's declared consequences (§4.7 item 5).
- The rule does not change.
- G-R7's criterion is amended (§8.2). Its clause "every class change is failure → `SUCCESS`" stopped every failure →
  failure change as a possible regression. What R-782 claims is narrower: no success is lost, and roundoff at an
  on-bound component no longer decides an outcome.

### 8.2 G-R7: the amended criterion and its result

**Amended CI pass criterion (normative; replaces G-R7's second and third sentences in §6).** On every machine class,
compared with the committed same-class record:
- (a) no start that is `SUCCESS` there becomes non-`SUCCESS`;
- (b) every class change is either failure → `SUCCESS`, or failure → failure where both of the following hold:
  - the new class equals the start's class in the same dispatch's R-782 run on every other machine class;
  - the new class equals the start's class in a committed record of a machine class on which R-782 left that start's
    class and property-call count unchanged;
- (c) any other change stops for the design lane.

The local half is unchanged: the moved starts and class transitions equal §4.6's table.

*Why (b) is the right line.* A failure → failure change that lands on the class other platforms reach without the rule
acting is R-782 removing a roundoff decision, which is the remedy's purpose. A change to a class that no platform reaches
would be a new failure mode, and it still stops.

**Result** (`s10c_r782_gr7.py classes`, against the committed `run2r-ci-*` and `holdout1-ci-*` files). The CI job stops
at `a98`, so it never ran the holdout half; that half is completed here from the `holdout1-ci-*.json` artifacts.

| Starts | Class | S | failure → `SUCCESS` | `SUCCESS` → failure | failure → failure | Final states moved in bits |
| --- | --- | --- | --- | --- | --- | --- |
| nominal | ci-x86-64 | 434 → 437 | THM-08/03, THM-08/12, THM-09/04 (`F-BUDGET`) | 0 | 0 | 187 |
| nominal | ci-aarch64 | 434 → 437 | THM-08/03, THM-08/12, THM-09/04 (`F-BUDGET`) | 0 | THM-09/03 `F-BUDGET` → `F-FALSE-SUCCESS-CAUGHT`; (b) holds: ci-x86-64 has that class with 311 calls before and after | 17 |
| holdout | ci-x86-64 | 436 → 439 | THM-09/24, THM-09/35 (`F-BUDGET`); THM-09/31 (`F-FALSE-SUCCESS-CAUGHT`) | 0 | 0 | 190 |
| holdout | ci-aarch64 | 436 → 439 | THM-09/24, THM-09/34 (`F-BUDGET`); THM-09/37 (`F-FALSE-SUCCESS-CAUGHT`) | 0 | 0 | 11 |

**G-R7 is met on both classes, nominal and holdout, under the amended criterion.**

**Across the two classes, same dispatch** (`s10c_r782_gr7.py cross`):

| | Before R-782 (committed) | After R-782 |
| --- | --- | --- |
| Class disagreements (880 starts) | 5: nominal THM-09/03; holdout THM-09/31, /34, /35, /37 | 0 |
| Rescue-status disagreements | 11 | 1: STA-01/22, which R-782 moves on neither class |
| S^first, nominal | 370 \| 367 | 379 \| 379 |

These facts are not R-782's, and they are not ruled here (§8.6):
- **The ci-x86-64 runner CPU changed.** The committed records ran on an AMD EPYC 7763, this dispatch on an AMD EPYC
  9V74. Most of the 187 and 190 bitwise moves on that class come from the change. A98's bit counts on ci-x86-64 no
  longer isolate R-782, and its classes moved only as the table shows.
- **Holdout THM-09/31 stays platform-dependent.**
  - On ref-x86-64 it is `F-FALSE-SUCCESS-CAUGHT` (241 calls), measured locally on both trees, with no acting iteration.
  - On ci-aarch64 it is `SUCCESS` (397 calls) before and after R-782, and on ci-x86-64 after (`F-FALSE-SUCCESS-CAUGHT`
    before). These records do not separate R-782's share of that change from the CPU's.
  - Here roundoff away from any on-bound component decides between the trivial root and the physical one. That is T06's
    phase-logic exposure, not the lift.
- **THM-09/04 cost.** It converges in 2855 property calls on both CI classes, against 424 locally. T07's length pin for
  it (§4.7 item 4) may therefore differ from 94 on ci-x86-64 as well as on ci-aarch64. The map holds every class's
  measured value; this is a clarification of item 4, not a design question.

### 8.3 F2: A41 asserts the absent flows exactly zero (R-785)

**Ruling: the reviewer's default, with one precision.** The assertion is IEEE equality `== 0.0`, which ignores the sign
of zero. It is the predicate that R-064 and R-782 themselves use (`x_i == lo_i`). A signed zero carries no physical
meaning, so asserting its sign would test arithmetic detail, not the invariant.

**Normative text.**
- **The test.** `tests/test_s10c_columns.py::test_a41_the_state_is_the_registered_root`, for both registered cases (C-MW
  and C-EW):
  - After the tolerance assertion, assert that every entry of `zeros` is `== 0.0`. `zeros` holds the absent component's
    liquid and vapour flow on each equilibrium stage, 60 per case.
  - On failure, the message lists each nonzero entry's variable name and value.
  - Both recorded properties stay.
  - In the docstring, "absent flows exactly 0.0 or not" becomes "absent flows exactly 0.0 (asserted, R-785)".
- **The spec.** In S10C-spec A41, the cell "absent flows ≤ that stage's flow tolerance" becomes "absent flows `== 0.0`
  exactly (R-785); the tolerance check also applies". OQ-2's default is superseded (S10C-spec §12, Amendment 2).
- **R-780.** For C-MW and C-EW, its "exact zeros are not required" is superseded. Every other part of R-780 stands.

**Why the assertion is safe on every platform.** By §4.3 the invariance follows from IEEE products with exact zeros and
from the rule's exact assignment. No BLAS result enters it. Measured:
- G-R2 locally: 320/320 perturbed solves and 4/4 kernels.
- The dispatch's s10c-diag final states on ci-x86-64 and ci-aarch64: in both C-MW and C-EW, 60 of 60 absent flows are
  exactly `+0.0`, and none is `−0.0`.

**What a failure means.** Something has reached a solve path where R-782 does not hold the set: T04's PTC, the Anderson
accelerator, an edge-3 restart whose initializer seeds the absent component, or a partial regression of the rule. It
goes to the design lane. It is never relaxed back to the tolerance check without a new register entry.

### 8.4 F1: `_released` without recursion, before the merge (R-786)

**Ruling.** The reviewer's remedy is accepted, but its timing changes. It lands on `wp/S10C` before WO-R4, as its own
commit, WO-R6.
- *Why before the merge.* F2 already forces a code commit, a full gate and CI on both architectures before the merge, and
  F1 can share that gate and that CI. After the merge it would need its own branch, gate and CI, and `main` would carry
  R-782's per-iteration call into a recursive, superlinear function in the meantime.
- *No reviewer pass.* The change is inert by construction, and G-R8's bit identity is the proof.
- *Fallback.* If WO-R6 fails G-R8, or is not ready when everything else is, revert its commit and merge without it. It
  then becomes the first commit of a follow-up branch, `wp/K03-released`, which must land before any case with
  `|Z₀| > 60` is registered.

**Design (normative).** The name, the signature
`_released(x, opening, lower, residual, jacobian) -> tuple[int, ...]`, the docstring's contract and the result all stay
the same. Only the algorithm changes. Let `m × n` be `jacobian`'s shape.

1. `on_bound = isfinite(lower) & (x == lower) & (opening == lower)`. If no entry is set, return `()`.
2. **Closed rows, vectorized.**
   - Take `rows = csr_matrix(jacobian)`, as today, with arrays `indptr`, `indices` and `data`.
   - Set `kept = data != 0.0` and `row_of = repeat(arange(m), diff(indptr))`.
   - Set `n_kept = bincount(row_of[kept], minlength=m)` and
     `n_in = bincount(row_of[kept & on_bound[indices]], minlength=m)`.
   - Then `closed = (asarray(residual, float64) == 0.0) & (n_kept > 0) & (n_in == n_kept)`.
   - If no row is closed, return `()`.

   This is today's per-row filter, entry by entry: `F_r == 0.0`, at least one nonzero entry, and every nonzero entry in
   a `Z₀` column.
3. **Compact incidence `B`.**
   - `z0 = flatnonzero(on_bound)` (ascending); `local[z0] = arange(len(z0))`; `crow[closed_rows] = arange(k)`.
   - `B` is the `k × len(z0)` CSR matrix built from the entries with `kept & closed[row_of]`, at
     `(crow[row_of], local[indices])`, with **data 1.0, never `J`'s values**. Duplicate entries therefore sum to a nonzero
     value, as today's per-entry loop counts them, and cannot cancel.
4. **Maximum matching.**
   - `match = scipy.sparse.csgraph.maximum_bipartite_matching(B, perm_type="column")`. This is an iterative
     Hopcroft–Karp in compiled code. `match[r]` is row `r`'s column, or −1.
   - `row_of_col[match[match >= 0]] = flatnonzero(match >= 0)`, and −1 elsewhere.
5. **`outside`, by a worklist.**
   - Start with `outside = (row_of_col < 0)` and push those columns onto a `collections.deque`.
   - Pop a column `u`. For each row `r` in column `u` of `B.tocsc()`, let `c = match[r]`. If `c >= 0` and
     `not outside[c]`, set `outside[c]` and push `c`.
   - Each column is pushed at most once.
6. **Released set and count.**
   - `released = ~outside`. If it is empty, return `()`.
   - `count` is the number of rows of `B` with no entry in an `outside` column (one `bincount` over `B`'s entries).
   - If `count != released.sum()`, return `()`.
7. Return `tuple(int(i) for i in z0[released])`, ascending, as Python ints.

**Why the result is identical (inertness).**
- Steps 1–3 select today's closed-row family by today's predicates.
- Today's Kuhn loop, one augmenting search per row from an empty matching, yields a maximum matching (Berge), and so
  does step 4.
- Today's fixed-point loop and step 5 compute the same set: the columns reachable from an unmatched column along
  alternating paths (a non-matching edge from column to row, then the matching edge from row to column). By the
  Gallai–Edmonds / Dulmage–Mendelsohn theorem, that set is exactly the set of columns left uncovered by *some* maximum
  matching. It does not depend on which maximum matching was found.
- `outside`, `released`, the count and the returned tuple are therefore identical for every input on which today's code
  returns. The new code also returns where today's raises `RecursionError`.
- `_bound_aware_step` then returns the identical tuple, so every solve is bitwise unchanged (the argument of §4.4).

**Cost.**
- Step 2 is `O(nnz J)`, vectorized.
- Step 4 is `O(nnz B · √|Z₀|)`, in compiled code.
- Step 5 is `O(nnz B)` in Python.
- There is no recursion, and the common path (`C = ∅`) does not call the function at all.

### 8.5 Work orders after WO-R3, and G-R8

This replaces §5's order from WO-R4 on. Each WO is one commit on `wp/S10C` whose message names S10-C and the register
entry. Run lines go to `docs/S10C_DECISIONS.md` under "R-782 (absent-component release)".

| WO | Content | Acceptance |
| --- | --- | --- |
| **WO-R5** F2 (test and spec) | §8.3: the A41 assertion and its docstring. The S10C-spec amendment is already committed with this note. | A41 passes locally on both cases. A scratch mutation that sets one absent flow to `1e-300` before the assertion makes it fail (not committed). |
| **WO-R6** F1 (inert K03) | §8.4 in `numerics/newton.py`, with the docstring citing R-786. New tests in `tests/test_k03_released.py`. | G-R8 |
| **WO-R4** manifest | As §5, plus three citations. G-R7 cites §8.2 (both halves, both classes, the amended criterion) and the artifact hashes above. G-R3 cites the s10c-diag artifacts. The manifest states that WO-R5 and WO-R6 are inert to every solve, so the dispatch evidence at `4a4677c4` holds for the merge head. | Manifest `tested`; `reviewed` not set |
| **Merge** | The full gate once, at the head after WO-R6 (after WO-R5 if WO-R6 is dropped). CI green on x86-64, aarch64 and default-install. **No new CI dispatch:** WO-R5 only changes a test, and WO-R6 is inert. | per CLAUDE.md |

**G-R8 (F1 inertness).** Measured locally (x86-64). Every item must pass.
1. **Brute-force oracle.**
   - 2 000 seeded instances with `|Z₀|` from 1 to 10. Each has `k ≤ |Z₀|` closed rows that carry a planted injective
     row → column assignment, plus random extra entries inside `Z₀` with probability 0.1, 0.3 or 0.6. Each also has open
     rows: a nonzero residual, or an entry outside `Z₀`. Some instances store explicit zeros.
   - The oracle enumerates every nonempty `Z ⊆ Z₀` and keeps those with `closed(Z) == |Z|`. `Z*` is their union.
   - The planted matching makes `closed(Z) ≤ |Z|`, so `Z*` is itself tight. Assert that.
   - Assert that `_released` returns `tuple(sorted(Z*))`, or `()` when no tight set exists.
2. **Old against new.**
   - Copy R-064's recursive implementation verbatim into the test module as `_released_r064`.
   - Run 2 000 seeded instances with `|Z₀|` up to 300. They include instances that violate Hall's condition (more
     closed rows than columns on some subset), stored zeros, duplicate entries, and residual entries equal to `−0.0`.
   - The two functions return identical tuples on every instance.
3. **Long chains.**
   - One absent component over 1 000 stages: `|Z₀| = 2 000`, a column-shaped closed block, with rows in stage order and
     reversed. It returns all 2 000 indices, with no `RecursionError`.
   - A 10 000-column block completes.
   - The times go to the decisions log and are not asserted. Expected: well under 0.1 s.
4. **Existing tests.** B33c i–v and G-R1 i–v pass unchanged, and so do the 12 tests of D.
5. **Identity scripts.** `S10C-IDENTITY PASS n=858 changed=[]`, and S08's registered pass line.

### 8.6 Open questions (each with the default work proceeds on)

| # | Question | Needs | Default |
| --- | --- | --- | --- |
| Q-A | F1 before the merge or after it | Frank's preference (scope) | Before the merge, as WO-R6, with §8.4's fallback. It shares F2's gate and CI. |
| Q-B | An aarch64 detector run on `f9122cc7` over THM-09/03 (and STA-02/00, /02, /17) to observe the acting iteration directly | A fact; costs one CI dispatch (Frank's preference: CI minutes) | No dispatch. The ruling holds whatever the cause (§8.1, "not a regression in substance"). If an aarch64 dispatch is made later for another reason, add the detector over these four starts. |
| Q-C | The ci-x86-64 runner CPU changed (EPYC 7763 → 9V74) | A fact for T06 and R-627, not for S10-C | Record it in the decisions log. No action in S10-C; the next T06 record on that class names the CPU. |
| Q-D | Holdout THM-09/31: which root wins (the trivial one or the physical one) depends on the platform, away from any on-bound component | A design question for phase logic (T02/T06) | Out of scope. Record it, and list it with T06's platform-dependence items for that owner. |
