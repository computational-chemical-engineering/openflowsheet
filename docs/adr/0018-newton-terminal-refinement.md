# ADR 0018 — A row-converged Newton iterate is refined once when its own first-order error exceeds the kind tolerance (`globalization.eo_core = "newton_refined"`)

**Status:** Accepted 2026-09-27 — T06's manifest `evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json` is `tested` (100 checks: 96 pass, 4 not_applicable with reasons; A29/A30 judged on scoring run 2, run 1's FAIL carried), after the design-lane review `docs/reviews/T06-review.md` and verdicts `docs/reviews/T06-verdicts.md`. Frank approved its enum widening (2026-09-26) and kept `newton_refined` as T07's default knowing D4′ (2026-09-27). Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Amended:** 2026-09-27, Amendment 1 (the closing round: D4′ and D5′ make D4's outcome claim exact under the property budget, review M1; Frank's approvals recorded). The section is at the end; D4 and D5 carry markers.
**Date:** 2026-09-26
**Author:** design lane (`specifier`), T06 scoring-round ruling; brief `docs/briefs/T06-scoring-round.md` (its §3 holds the ruling list). The `architect` was not consulted: the rule is one bounded termination step, prototyped and measured below; its seams are build-lane work under design-lane review.
**Normative text:** D1–D7 below, D4 and D5 as amended by D4′ and D5′ (Amendment 1); T06 spec §6.6 (A4, A5), §7.1 (A4), A86–A91, A96.
**Amends (additively):** ADR 0010 D1 (a third value of `globalization.eo_core`); K03 §5.2 (what `CONVERGED` returns under that value only). **Reverses:** nothing registered. ADR 0013's rejected alternative "a solver-side polish to roundoff after `CONVERGED`" stays rejected for its purpose (D7).
**Affected requirements:** V20 (verified success at the registered root), D14 (unchanged: the certificate's promise), D20 and blueprint §8.3 R0 (a new policy value; registered policies unchanged).
**Affected packages:** T06 (the revision path's policy `T06-revision-v2`); K03 (`numerics/newton.py`, `numerics/linear.py`); T02/T05b (`orchestrator/region.py` passes the rule); T07 (whether the application default selects it — Frank's).
**Blueprint authority:** §7.3 ("An already valid root need not take a small additional step to qualify" — qualification is unchanged here: the step is taken after it, never to obtain it, and never changes the attempt's outcome — D4′), §7.7 (a fallback states its trigger, count, cost and outcome).

## Context

T06's scoring run 1 (`docs/T06_DECISIONS.md`, 2026-09-26) failed its gate on four THM-09 `F-OTHER-ROOT`s (starts 1, 2, 5, 10). Each is the registered root stopped at the row tolerance: only `S3.T`/`S4.T` and the split move; `ΔT = −1.005e-5, −3.447e-5, −1.010e-5, −1.429e-5 K` against S3's `1e-5 K`. THM-09's U-PHF is pure B at `T_sat = 360 K`; its equilibrium row is `v_B L − K_B l_B V = V·L·(1 − K_B)` with `V·L = 0.066586` at the root, and K04 §5.2's tolerance `τ_eq = 9.3e-8 (mol/s)²` then admits `|T − T_sat| ≤ τ_eq/(V·L·∂lnK_B/∂T) = 5.0167e-5 K`, **5.02 × S3's allowance** (twin `closed_form.amendment_4.thm09_row_window`, generator-checked; the twin reproduces start 1's measured row `1.863e-8 = 0.2003 τ_eq` from the closed form). Whether a start is `SUCCESS` or `F-OTHER-ROOT` is where Newton's last iterate lands inside that window (starts 6 and 19 succeeded at 0.37 and 0.97 of the allowance).

This is not THM-09's alone. S3's allowance is T02 §6.4's `10 τ_kind`, argued from "the quadratic convergence that overshoots `τ` by orders" at registered starts; K04 F3 had already recorded that a state converged *to tolerance rather than to roundoff* carries `b` = 145–476 × `τ̂_min`, and that `VERIFIED` promises residual accuracy only. Run 1's successes sit up to 0.70 of their allowance (NET-10 start 4), 0.30 (THM-07), 0.14 (STR-01, NET-10), 0.12 (THM-10). The criterion S3 registers — the certified state within `10 τ_kind` of the root — is a solution-accuracy requirement no registered policy promises.

*Measured (this ruling, `wp/T06` at `f01ed8d`, prototype in the scratchpad, not committed):* the exact Newton correction at a row-converged iterate predicts S3's distance to first order — THM-09's `|δT|/τ_T` = 10.05, 34.47, 10.10, 14.29 at the four starts, exactly 10 × their S3 ratios — and one more Newton step removes it (S3 ratios after: 1.84e-6, 2.17e-5, 1.86e-6, 3.72e-6; `b` 5.3e-13…6.3e-12).

## Decision

- **D1. The value and its scope.** `globalization.eo_core` gains `newton_refined`: the damped Newton core of K03 §5 with D2–D5 added at a `CONVERGED` exit. It applies to every Newton attempt an EO region runs on the target declaration under that value — the region's attempts and ADR 0015's restart. It does **not** apply to the tear path (K03's tear Newton does not read `eo_core`), to edge 3's homotopy corrector at any `λ`, or to the PTC core. `newton` is unchanged and stays the default; every registered policy keeps it.
- **D2. The trigger.** At a `CONVERGED` exit at iteration `k ≥ 1` (never at `k = 0`: a state passed in qualifies as it is, blueprint §7.3), compute the **chord correction** `c = −S_x Ĵ_{k−1}⁻¹ F̂(x_k)` with the factorization of the attempt's last Jacobian — no new Jacobian, no new factorization, no residual evaluation. For every free column `j` whose declared quantity kind has a registered acceptance rule, `ρ_j = |c_j| / τ_kind(j)`, with `τ_kind` the `a + r·s` of that kind — the rule the region already applies to rows (ADR 0001 D6; `orchestrator/region.py`'s `KIND_TOLERANCE`, built from the same constants as the verifier's): flow 3.1e-8 mol/s, temperature 1e-6 K, pressure 1e-2 Pa, heat rate 1.01e-3 W. No new constant; like the row test, it does not read the policy document's `residual_tolerances` (empty in T06's policies; the region never reads it for rows either). The rule **fires** iff `max_j ρ_j > 1`, and never if `k` equals the iteration budget. The threshold is S3's allowance divided by 10 (9.90 for heat rate; twin claim `A4.refinement_threshold_leaves_a_margin_of_at_least_9.9_below_every_allowance`), ADR 0007 D2.4's margin of ten, which absorbs the chord's own error (measured ≤ 1 % on THM-09's 20 starts; a factor ≤ 3.1 at T05b B34a's near-singular states, which D4 catches).
- **D3. The refinement.** When it fires, the attempt takes **one** more iteration of K03 §5's loop from `x_k`, unchanged: a fresh Jacobian and factorization, the bound-aware step, the same line search, the same trial screen and the same attempt observer. At most one refinement per attempt.
- **D4. What is returned.** The refined iterate `x_{k+1}` is returned `CONVERGED` iff its step was accepted, every row passes at it, and its chord correction (with `x_k`'s factorization) has `max_j ρ_j ≤ 1`. Otherwise `x_k` is returned `CONVERGED`. **The refinement never changes an attempt's outcome** (**amended 2026-09-27, D4′:** this is the *attempt's* outcome. The refinement's calls are metered, so a property-budget refusal makes the *step* `BUDGET_EXHAUSTED(property_calls)`, and the region's closure judges the returned state. A solve's outcome can differ from `newton`'s; read D4′): a rejected or phase-changing trial, `α_max = 0`, an invalid trial, the observer closing the attempt, a property-budget exhaustion or any typed evaluation failure during it abandons it and returns `x_k`. *Measured:* on T05b's B34a sweep, 6 of 8 refinements did not contract (4.65 → 3.62; 1.42e4 → 7.1e3; 1.47e4 → 7.4e3 — linear convergence at a double root) and were reverted; 2 contracted (7.51 → 6.5e-5) and were kept; its registered tally did not move.
- **D5. Records.** No new event kind, outcome, field or enum value beyond D1's. The refinement's iteration is recorded as any iteration is (`jacobian`, `linear_solve`, `trial`, `step_accepted`). The attempt's closing event carries the chord solve's `LinearRecord` in its existing `linear` field whenever D2 ran (ADR 0004 D2/D3: every solve carries its record), and, when the rule fired, a `message` `terminal_refinement(<accepted|reverted|abandoned>: <reason>): chord <ρ_max!r> at <column>` (`<reason>` defined by D5′, Amendment 1); its `iteration` and `state_sha256` are the returned state's. The attempt context's and the certificate's `core` stay `newton`. Where the rule does not fire, the trace's R0 projection and the final state are those of `newton` bit for bit.
- **D6. The policy that selects it.** `T06-revision-v2` = `T06-revision-v1` with exactly one change, `globalization.eo_core = "newton_refined"`. It replaces `T06-revision-v1` wherever T06 registered v1 (spec §6.6 (A4)); v1 stays defined as run 1's policy. The tear path (`SYN-001-K03`) and NET-05 (`T04-W12`) keep their policies (run 1's S3 ratios there ≤ 0.072).
- **D7. What the certificate says, and what this is not.** Unchanged. `VERIFIED` promises residual accuracy and discloses `b` (K04 F3's default stands; no solution tolerance is registered); ADR 0013 D1 still judges the fresh-flash categories at the verifier's own projection, because the verifier must judge any supplied or replayed state. This ADR does not make the verifier depend on the solver's refinement. It is not ADR 0013's rejected "polish to roundoff": that was unconditional, on every solve, as a remedy for a verifier defect, and could not reach NP-G's resolution floor; this is one step, only when the solver's own estimate exceeds the kind tolerance, selected by a policy value, as a remedy for the solver's accuracy.

## Alternatives considered

- **Widening S3 to the row-tolerance window, or to the certificate's `b`, or adding "the registered root within `b`" to §7.2's explanations.** Rejected: chosen after four starts failed, each is the canonical post-hoc relaxation (CLAUDE.md "a failed gate stays failed"; spec §7.3). Registering solution tolerances is K04 F3's alternative, a requirement change that is Frank's.
- **The same rule under every existing policy (no enum value).** Rejected: a silent change of registered policies' meaning (K03's rule that a second behaviour is a new value a reader can see). *Measured with the guard:* it moves four registered tests (K04-F9 X04 ×2 and X25, T04 A11 — the A02 family's states converged to tolerance, which is exactly what K04-F9 registers) though it leaves K05's identity document byte-identical (`e4892e75…`, no firing in its runs).
- **The exact correction (a fresh Jacobian) at every exit.** Rejected: one Jacobian and one factorization at every converged attempt move the R0 solver counters of every solve that selects the value, for an estimate the chord gives within 1 % where it matters; D4 covers the chord's failures.
- **Re-forming or re-scaling the equilibrium row for small `V·L`** (dividing by `V L`, `ln K = 0` for one flowing component, a state-dependent `s_i`). Rejected: it changes the compiled equations of every lifted split (T05/T05b certificates and the `t05b` key), a state-dependent `s_i` contradicts K04 §5.1 ("never from an iterate") and moves `check_policy_sha256`, and it addresses only the small-`V·L` mechanism — NET-10's 0.70 is a coupled multicomponent case with `rcond₁` 4.3e-4.
- **Tighter solver row tolerances than the verifier's.** Rejected: an unprincipled factor that moves every registered trace and still leaves the error `‖Ĵ⁻¹‖`-dependent.
- **The orchestrator adopting the verifier's projection `x̃` as its answer.** Rejected: the certificate would then judge a state the verifier produced.
- **Skipping the refinement where a pivot screen flags a near-singular factorization.** Rejected in favour of D4: a threshold on a pivot ratio is a new constant; D4 decides by what the step achieved.

## Consequences

- C1. `numerics/newton.py`: the D2–D4 hook at the convergence test, enabled by the caller; `numerics/linear.py`: the factorization the step used is kept for one back-solve (no new factorization); `orchestrator/region.py`: enables the hook and supplies `τ_kind` per free column (from `KIND_TOLERANCE` by the column's declared kind) under `newton_refined` only. `orchestrator/trace.py` and `schemas/solve-policy.schema.json`: the enum value. `docs/interfaces-frozen.md` §2 gains a note like ADR 0015's.
- C2. Every registered policy, trace, certificate and identity key is unchanged by construction (no registered policy selects the value); the build lane proves it (T06 spec A87).
- C3. T06's revision path, its A02 registrations and the `t06` key's policy ids move to `T06-revision-v2` — a recorded, reasoned change (spec §10 (A4)); the full registered gate is re-run (plan §6.5).
- C4. Handed on: whether T07's application default selects `newton_refined` (recommended: yes, as ADR 0015's restart became the default — Frank's); whether the homotopy corrector's `λ = 1` endpoint should refine (T06 spec Q21). **(Amendment 1) The first is decided: yes** (Frank, 2026-09-26; kept 2026-09-27 with M1 known).

## Migration

None for stored artifacts: a policy document without the value is unchanged; a replay under `newton_refined` by an implementation without it is refused by the schema, as ADR 0015's value is.

## Acceptance evidence

T06 spec A86–A91 in `evidence/T06/<commit>/manifest.json`; the twin's `--check` (347 claims) with the Amendment 4 claims; run 2 of the scoring ensemble under `T06-revision-v2` on both machine classes. Register entry R-085. **(Amendment 1)** Also T06 spec A96, and A90 met on run 2r's records (spec A98).

---

## Amendment 1 — 2026-09-27 (the closing round: review M1; Frank's approvals)

**Author:** design lane (`specifier`); brief `docs/briefs/T06-closing-round.md` (its §2 holds the ruling list). **Source:** the design-lane review, `docs/reviews/T06-review.md` M1 (`bc9ef84`). **Spec:** T06 Amendment 5 (§6.6 (A5), §15 (A5), A88 (A5), A96). **Register:** R-085 amended.

**What was wrong.** D4's sentence was read, and written, as a statement about solves. It is true of the *attempt*: the Newton core returns `x_k`, `CONVERGED`, whatever ended the refinement. It is not true of the step. When the property meter refuses a call inside the refinement, the compiled residual reports an `error` evaluation, the core abandons the refinement and returns `x_k`, and then:

- the region's converged closure (`ops.converged`) needs provider calls that are refused (`orchestrator/region.py`, `BudgetExhaustedError` → `BUDGET_EXHAUSTED`);
- the executor marks the step `BUDGET_EXHAUSTED(property_calls)` whenever the meter refused any call (`orchestrator/executor.py`).

*Measured* (spec A96; `ref-x86-64`, `66861d5`): THM-09 start 1 converges under `newton` in 365 property calls. Under `newton_refined` it converges in 386 calls uncapped; at caps 365, 366, 375 and 385 (both ends of the range and two points inside it) it ends `BUDGET_EXHAUSTED`, and its converged attempt closes `terminal_refinement(abandoned: EVALUATION_ERROR): chord 10.02370482213442 at S3.T`; at 386 it converges again. **The code is the honest side.** Once the refinement has spent the budget, the closure at `x_k` cannot be evaluated, so `CONVERGED` could not be certified in any case, and the refinement's calls are real calls (K03 §11.2).

### D4′ (amends D4's outcome sentence)

**The refinement never changes an attempt's outcome.** The attempt returns `x_{k+1}` or `x_k`, `CONVERGED`, as D4 says. **The refinement spends the solve's property budget like any iteration.** A property-budget refusal during the refinement, in the region's converged closure after it, or at any later call of the same solve, is that step's `BUDGET_EXHAUSTED(property_calls)`, as it is for any refused call. A solve's outcome can therefore differ from `newton`'s in two ways only:

- **(i) Under a property budget,** it can end `BUDGET_EXHAUSTED(property_calls)` where `newton` would have finished. Measured: A96. The change is never toward success: a refused call cannot make a success.
- **(ii) When the region's converged closure proposes a phase conversion** (T03 §4.8's restart gate after `ops.converged`), the next attempt opens from the state the attempt returned, which is the refined one if the refinement was kept. The later path then starts from the more accurate state, and nothing bounds how it differs. The closure also judges the refined state rather than `x_k`. This has not been observed: in run 2 on `ref-x86-64`, every fired refinement was the last iteration of its start's final attempt (the verdicts' §2.4). Spec A90 (A5) lists any other.

Where the refinement's calls reach no property budget, and the closure accepts the refined state exactly when it would have accepted `x_k`, the solve's outcome is `newton`'s. The T06 harness's wall ceiling (spec §7.5) counts the refinement's time too.

### D5′ (the `<reason>` of D5's message)

`<reason>` is the word of the event that ended the refinement, as the Newton core sees it:

- `accepted`: the kept state's own chord, `chord <ρ!r> at <column>`;
- `reverted`: the reason D4's test failed (`chord <ρ!r> at <column>`, `chord <linear failure>`, `rows unconverged`);
- `abandoned`: the outcome the core would have returned, with its budget when it has one (`EVALUATION_ERROR`, `LINE_SEARCH_FAILED`, `PHASE_UPDATE_REQUIRED`, `BUDGET_EXHAUSTED(newton_iterations)`, …).

**A property-budget refusal reaches the core as a typed evaluation failure,** so its word is `abandoned: EVALUATION_ERROR`. The cause is recorded where it is decided, on the step:

- outcome `BUDGET_EXHAUSTED` with budget `property_calls`;
- the plan's message, the meter's own (`the property-call budget of <n> is spent; the call to … was refused rather than made`);
- `counters.property_calls = max_property_calls` (T06 A93).

The message is not changed. T06's report classifies an `abandoned` refinement in the last attempt of a start that ended `BUDGET_EXHAUSTED(property_calls)` as *abandoned (budget)* (spec A90 (A5)).

### Frank's decisions, recorded

- **The enum widening:** approved 2026-09-26, 21:23 (question tool; `bc45345`), before the widening commit (`9e5a7d2`, 22:10) and before run 2 (22:39).
- **`newton_refined` as T07's application default:** approved 2026-09-26 (`bc45345`), and kept on 2026-09-27 after M1 was reported to him (`66861d5`). C4's first hand-on is closed.
- **For information, not asked:** D4′ (ii) was identified by this amendment, after Frank's answer of 2026-09-27. It does not change the case for the default — it is the refined state's own path, not observed in run 2 — and run 2r's records will show whether it ever occurs (spec A90 (A5)).

### Alternatives rejected (Amendment 1)

- **Reserving property calls for the closure, or skipping the refinement below some remaining budget.** Either needs a new constant, and D4's own reasoning (decide by what the step achieved, not by a threshold) forbids that.
- **Leaving the refinement unmetered, so that D4's original sentence holds.** Its calls are real provider calls (K03 §11.2), and a budget that ignores some calls is not the registered budget.
- **Carrying a typed budget word into the refinement's message** (`abandoned: BUDGET_EXHAUSTED(property_calls)`). The refusal crosses the compiled residual, a CasADi callback, as an evaluation error. Carrying its type through would change the residual path for a message that lies outside R0, and the step already records the cause exactly.

### Consequences (Amendment 1)

- **C5.** `numerics/newton.py`'s module docstring: its sentence "It never changes the outcome (D4)." is replaced, by the build lane, with exactly: "It never changes the attempt's outcome (D4). Its calls are metered like any iteration's, so under a property budget the solve can end `BUDGET_EXHAUSTED(property_calls)` where `newton` would converge (ADR 0018 D4′, T06 A96)." No code line changes.
- **C6.** T06 spec: A88 (e)'s budget case is re-worded as a Newton-layer evaluation failure; A96 is the plan-level evidence; A90 is met on run 2r (A98), whose records list any fired refinement outside a start's final attempt.
- **C7.** T07 inherits D4′ with the default. Q28 of the T06 spec (event messages stay outside R0) keeps D5's floats harmless.

### Acceptance evidence (Amendment 1)

T06 spec A96 passing on `ref-x86-64` and on both CI architectures; A88 (e) re-worded; the docstring sentence equal to C5's; A90 met on run 2r's records.
