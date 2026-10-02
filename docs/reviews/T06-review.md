# T06 review — the F6 flash fix (ADR 0017), the Newton terminal refinement (ADR 0018), F4's sequential restart (ADR 0015), the verifier changes, unit-conversion-v2 (ADR 0016) and the ensemble harness, against `docs/derivations/T06-corpus-spec.md` (Amendments 1–4)

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-26. Plan §1.3 requires a design-lane
review: T06 touches a provider, the Newton core, phase logic, certificates and replay identity.
**Brief:** `docs/briefs/T06-review.md`.
**Reviewed at:** `wp/T06` = `1fdc717`. I reviewed the build lane's changes to `src/`, `benchmarks/t06/`,
`scripts/` and `tests/` in `63364f8..HEAD`. I read the design lane's documents in that range but did not
review them.
**Run here:**
- `tests/test_t06_w18_refinement.py`, `tests/test_t06_w18_policy.py`, `tests/test_t06_w13_f6.py` and
  `tests/test_t06_f4_restart.py` give 36 passed.
- The W1a/W1b/W12 unit tests give 183 passed. The W2/W3/W14/W19/W20 verifier tests give 48 passed.
- I did not run the full gate or a re-scoring. I ran one plan-level probe (P1) and two function-level
  probes (P2, P3); §8 lists them.

**Environment:** x86-64 Linux 6.12.86, the repository's `.venv`. I read run 2's x86-64 record
(`scratchpad/scoring/run2_x86.json`). I did not have the aarch64 record.
**Scope:** the `verdict` agent is ruling on the gate and the reference comparison
(`docs/briefs/T06-verdicts.md`). This review does not duplicate that work.

---

## 1. Verdict

**Ready to merge once M1 is closed.** M1 is a contradiction between ADR 0018's normative sentence and
the code. Under the direction I recommend, closing it means amending the ADR text and adding one test;
no `src/` change is needed.

The rest holds up, by reading and on the tests:
- the F6 provider fix;
- the Newton refinement, apart from M1;
- F4's restart;
- the ensemble's classification and gate;
- the verifier changes;
- unit-conversion-v2 with the component-order mapping.

The four tests weakened after measurement are all legitimate in substance (§5). Two of them need a
design-lane text change, because the build lane may not lower or relax a registered number: A50's
"exact" and A92's floor.

---

## 2. Must-fix

### M1 — ADR 0018's "the refinement never changes an outcome" is false under the property budget (needs a decision on which side moves; I recommend the text)

**Where.**
- `src/process_runtime/numerics/newton.py:309–323`: a refinement that ends in any failure is
  abandoned, and the attempt returns `x_k` `CONVERGED`.
- The region then runs the converged closure (`ops.converged`). Its kernel calls are refused, and
  `src/process_runtime/orchestrator/region.py:2113` turns that into `BUDGET_EXHAUSTED`.
- Independently, `src/process_runtime/orchestrator/executor.py:921–925` overrides any region result
  with `BUDGET_EXHAUSTED(property_calls)` whenever the meter refused a call.
- The newton.py module docstring (line 30) and ADR 0018 D4 both claim "never changes the outcome",
  and D4 names "a property-budget exhaustion" among the cases that return `x_k`.

**Measured (P1).** THM-09 start 1 from the published starts, policy `T06-revision-v2` and the same
policy with `eo_core = "newton"`. The two runs differ only in the core.

| policy | `max_property_calls` | outcome | property calls | closing message |
| --- | --- | --- | --- | --- |
| newton | 10 000 | `CONVERGED` | 365 | — |
| newton_refined | 10 000 | `CONVERGED` | 386 | `terminal_refinement(accepted: chord 1.84e-05 at S3.T): chord 10.02 at S3.T` |
| newton | **365** | `CONVERGED` | 365 | — |
| newton_refined | **365** | **`BUDGET_EXHAUSTED`** | 365 | `terminal_refinement(abandoned: EVALUATION_ERROR): chord 10.02 at S3.T` |

With the same start and the same cap, `newton` converges and `newton_refined` reports
`BUDGET_EXHAUSTED`. The closing message also misnames the cause as `EVALUATION_ERROR`, because the
compiled residual turns the refusal into an `error` evaluation before Newton sees it.

**Why the tests pass.** A88 (e)'s "budget" test
(`tests/test_t06_w18_refinement.py:267`) models the refusal as a `JacobianUnavailableError` at the
Newton layer. That layer does not decide the plan's outcome, so the test pins the wrong layer.

**Consequence for T06.** None for the scoring. The effect can only turn a success into `F-BUDGET`,
never the reverse. In run 2 on x86-64, all three `F-BUDGET` starts ran out in a
`LINE_SEARCH_FAILED` or `PHASE_UPDATE_REQUIRED` attempt, not in a refinement. I could not check the
aarch64 run's fourth `F-BUDGET`.

**Consequence beyond T06.** The claim is the ground on which `newton_refined` was approved as T07's
application default.

**The minimal correction.** The code's behaviour is the honest one. Once the refinement has spent the
remaining budget, the closure at `x_k` cannot be evaluated, so `CONVERGED` could not be certified in
any case. The refinement's calls are real calls (K03 §11.2).

Recommended:
- Amend ADR 0018 D4 and the newton.py docstring: "a property-budget refusal during the refinement, or
  in the closure after it, is the step's `BUDGET_EXHAUSTED(property_calls)`. The refinement spends
  budget like any iteration."
- Replace A88 (e)'s budget test with a plan-level one: P1's two capped runs, asserting both outcomes.

Rejected: reserving budget for the closure, or skipping the refinement below some remaining budget.
Either needs a new constant, and D4's own reasoning forbids that.

*Falsifiable test:* P1 as a test. `newton` capped at its own total gives `CONVERGED`;
`newton_refined` at the same cap gives `BUDGET_EXHAUSTED`, with the refusal recorded.

---

## 3. Should-fix

### S1 — Judged at `x_final`, §8.8's saturation closure is stricter than the rows and escalates to `FAILED` with `false_success_detected` (needs a decision; keep it for T06)

**Where.** `verify/checks.py:666` (`closure_check`), `verify/table.py:1119`,
`verify/certificate.py:1150`.

**The mechanism.**
- When ADR 0013 D1's projection is refused (regularity not `NO_RANK_LOSS_DETECTED`, a domain exit, or
  the projection's rows not passing), the closure is judged at `x_final`.
- There the equilibrium rows bound `|y − Kx|` only by `τ_eq/(V·L)`, so the closure can reach many
  `τ_T` at a state that is correct to the rows.

**Measured (P2, function level).** A feed `(1,1,1)` at 1 bar just above its bubble point, split with
the provider's exact answer. The vapour is then perturbed so that the worst equilibrium row sits at
0.5 `τ_eq` (4.65e-8, which passes).

| `V·L` | closure | in `τ_T` |
| --- | --- | --- |
| 3.7e-2 | 4.0e-5 K | 40 |
| 3.7e-3 | 4.0e-4 K | 401 |
| 3.7e-4 | 4.0e-3 K | 4 010 |

Before W19 the same certificate was `UNVERIFIED`. It is now `FAILED` with
`false_success_detected` — a claim that the state is wrong, where the evidence shows only that the
label is not demonstrated at the rows' precision. THM-09 itself has `V·L = 0.067`, and ADR 0018
computes its row window as 50 `τ_T`. It escapes only because its projection runs.

**What is not affected.** Run 2's three catches are real:
- THM-09/3 and THM-09/18 are 5.08 K off in `S4.T`, and their energy and split checks fail too.
- NET-11/16 is the registered false label, judged at `x̃`.

T05b B34 (a)'s four moved states are in this regime: a vanishing phase, a refused projection, and
machine-dependent values. So A92 registered the behaviour on purpose.

**Recommendation.** No change for T06: the behaviour only makes the gate harder to pass. Register a
T07/K04 question: a closure failure judged at `x_final` whose value is within the row-implied bound
`τ_eq/(V·L·∂lnK/∂T)` should be `UNVERIFIED(label_not_demonstrated)`, not `FAILED`.

*Falsifiable test:* P2's state at `V·L = 3.7e-4` with the projection refused. Today it is `FAILED`
with `false_success_detected`; under the recommended rule it would be `UNVERIFIED`.

### S2 — A50: `certificate_sha256` is committed but checked nowhere, and it went stale at W19 unnoticed; the spec's "exact" needs an erratum

**Where.** `tests/test_t06_w8_references.py:94–138`.

The floats-to-roundoff change itself is sound (§5). The problem is the skipped field:
- `benchmarks/t06/references/results/ours-*.json` still carries `certificate_sha256`, which no test
  compares on any machine.
- `docs/T06_DECISIONS.md` (W18 entry) records that REF-03/04/05 and PC-2 carried stale hashes from W19
  onwards, and no test noticed.

**Correction**, either of:
- replace the field with a digest of the certificate's machine-independent content (verdict, check
  ids and results, limitations — the R0 projection that `run/identity.py:94` already builds) and
  compare that exactly; or
- drop the field from the committed record.

In both cases the `specifier` amends A50's tolerance column from "exact" to "non-floats exact; floats
to 1e-12 relative (ADR 0007)".

*Falsifiable test:* edit one committed record's certificate hash. Today the suite stays green; after
the fix it fails.

### S3 — A92's floor is a measured minimum's leading digits, on states the same branch shows to be machine-sensitive

**Where.** `tests/test_t05b_candidate_answers.py:249–252, 281`.

**The facts.**
- The floor is 9.4e-4 K, 1 % below the reference host's minimum of 9.494e-4 K.
- On the same commit, a sibling state moved by 30 % between machines (23.78 K → 16.16 K on both CI
  runners).
- A pin derived from the minimum will fail on some machine or be lowered again.

**What the assertion is for.** It says the closure fails by far more than `τ_T` — "not a
near-threshold call".

**Correction.** The `specifier` registers a principled floor in A92, for example `≥ 100 τ_T = 1e-4 K`,
and the test asserts that.

*Falsifiable test:* a state whose closure is 5e-4 K fails today's test and passes the registered rule.
That is the point: the rule states what is being claimed.

### S4 — W2's alias shift `s_j = 997·(j+1)` Pa makes every larger flowsheet `UNVERIFIED`, systematically (T07-facing; needs a decision)

**Where.** `verify/certificate.py:811, 835–859`.

**The mechanism.** `j` is the column's position in `variable_ids`, not among the pressures. Against
the domain `[5e4, 2e5]` Pa, the shift fits neither up nor down once:
- `j ≥ 75` at mid-domain;
- `j ≥ 100` at 1 bar;
- `j ≥ 150` at any pressure.

So from roughly 20 streams onwards, every certificate with an eliminated pressure alias is
`UNVERIFIED(pressure_shift_outside_domain)`. The result is typed, as §8.2 requires, and no T06 case
reaches it.

**Correction.** Use the pressure column's ordinal among pressures, or a smaller base. The shifted
state only feeds `eliminate_alias_rows`' spread test (`orchestrator/rank.py:229`), so no registered
certificate byte moves. It amends K03 §7.2, which makes it the design lane's call.

*Falsifiable test:* a revision with 25 streams at 1 bar and one alias. Today it is `UNVERIFIED` with
`pressure_shift_outside_domain`; after the change it is certified.

### S5 — An integer outside the double range crashes every reader with an untyped `OverflowError`

**Where.**
- `application/validation.py:536` (DIM-01, new in T06);
- `application/binding.py:572`;
- `models/revision_flowsheet.py:380` (`_number`);
- `read_parameter`'s `convert`.

**The failure.** `10**400` as a specification or parameter value raises `OverflowError` on all six
paths (P3). ADR 0016 V0/V4 say such a value is refused with reason `value`. The binding crash
predates T06, but DIM-01 repeats it, and `validate` reaches it because it checks only for missing
keys first.

**Correction.** Catch `OverflowError` at `float(raw)` and map it to the existing
`*_value_unsupported` / `parameter_quantity_invalid` codes.

*Falsifiable test:* P3's six calls return typed refusals.

---

## 4. Notes (no change required, or a small one)

**N1 — F6 (ADR 0017) is sound** (`thermo/syn001.py:230–233, 379`).
- *When the branch fires.* Only after both binary64 classification tests have put the feed in the
  two-phase region, and only when the bracket's two values share a sign.
- *Direction.* `f` decreases in β, so both negative means β < 0, which is `LIQUID`; both positive means
  `VAPOR`. That is the right way round.
- *Iteration count.* Only this branch returns 0 iterations, and `flash` keys on exactly that.
- *Unchanged paths.* A bracketed feed runs the old iteration bit for bit, and the exhaustion message is
  now true.
- *Residual edges, none reachable in SYN-001's domain.*
  - `f_low·f_high` could underflow to `+0.0` for values below about 1e-162. The feed would then go to
    bisection rather than be classified. This is unreachable: `|f(1)|` is O(1) whenever `f(0)` is at
    roundoff.
  - The opposite disagreement (`fl(Σ zK) ≤ 1`, `f(0) > 0`) stays `LIQUID`, as the ADR's rejected
    alternative intends. The saturation band's own test uses `f(0)`'s sign
    (`models/syn001/saturation_band.py:223`), so the two can disagree in that ulp. This predates T06.
- *A78.* I accepted its two-step proof as recorded. I did not re-run it.

**N2 — The refinement otherwise matches D2–D5.**
- The chord uses the kept factorization. The refined state is kept iff its step was accepted, its rows
  pass and its chord is ≤ 1. At most one refinement is taken, never at `k = 0` or at the budget. The
  core stays `newton`. The refinement is not passed to the homotopy or PTC cores
  (`orchestrator/region.py:2072`).
- Engineer reading (ii), "rejected trial" read as a failed line search: agreed. D3 says "the same line
  search", and D4's three conditions on the returned iterate are what protect the outcome. Observer
  notifications made during the refinement do not reach `decide` for a converged attempt
  (`orchestrator/phase_contract.py:475–478`).
- Engineer reading (iii), a chord back-solve failure returns the iterate as `newton` would: agreed. The
  non-empty closing message on that path is outside R0, because `run/identity.py:78–86` projects no
  message.
- D5's message carries `ρ!r` floats. That is consistent with R-029 only while event messages stay out
  of R0. T07 should keep it that way or drop the floats.

**N3 — F4's restart (ADR 0015) matches design note §5.2–§5.5** (`orchestrator/executor.py:764–850`,
`orchestrator/revision.py` `restart_start`).
- P5 is decided on integers and ids.
- `passes_used ≤ 2` does reproduce `traversal-G0-v1`'s start: same code, same passes, and a rejected
  pass 2 fails both.
- The restart is metered with what the plan has left. The initializer's own calls fall outside that
  window, by T05 §2.2's rule.
- Rescued starts are honest successes of the solver *with its registered fallback*: certified at the
  restart's root, provenance `traversal-G0-pass8-v1`. On acyclic cases they do not depend on the
  perturbation, and the report says so.

**N4 — The ensemble gate implements no explanation route** (`benchmarks/t06/ensemble.py:803`). Every
`F-OTHER-ROOT` fails the gate. That is stricter than §7.3 and moot at run 2's zero. A genuine second
root would fail the gate where the spec might pass it, so if one appears, the gate needs the design
lane's explanation, not a code change.

**N5 — `platform.machine() == "x86_64"` stands in for `ref-x86-64`** (`tests/test_t06_w13_f6.py:32`).
This branch's own evidence (A50, B34 (a)) shows the CI x86-64 runner is not numerically the reference
machine. A75's control passes there today, but it would be better keyed to a recorded host
fingerprint.

**N6 — Verifier, small items.** The verifier is sound otherwise, and R-016 holds: `verify/saturation.py`
imports no `models/`, and both paths give the closure a fresh `Syn001Provider()`.
- W14's refusal cannot fire on the production path, because one `assemble_target` call builds both
  identities. It is defence in depth, as A82 says.
- W3's save/seed/restore of numpy's global generator is not thread-safe. This matters for T07's
  HTTP/MCP bindings if they verify in threads.
- The tear path's closure reads the constant `TEMPERATURE_TOLERANCE`, not the policy's value. That is
  the registered legacy set.
- The engineer's `closure_nonpositive_phase` cannot occur at solver states or at `x̃`.

**N7 — Units, small items.** Units are otherwise exact and uniform: every reader goes through one
conversion function; the constants are exact fractions; the tests would fail under the identity
mapping or under SI-valued fixtures.
- `convert_input_value` rejects an `np.float64`, because its `repr` is `np.float64(…)`. No reader
  passes one today. Fix: `Fraction(repr(float(v)))`.
- `-0.0` in a converted unit becomes `+0.0`, while `-0.0 Pa` stays `-0.0`, so D7's "twin bit for bit"
  depends on downstream normalization, which I did not trace.
- A `molar_flow` declaration written in `kg/s` is converted, not refused. ADR 0016's table registers
  exactly this.

**N8 — X26's exact-zero bounds.** `SOLUTION_ERROR_BOUNDS` is 0.0 for SC-2, DZ-1, DZ-2 and DZ-4…DZ-9.
These are now held only below 1e-12. An exact zero there is platform-independent, so they could stay
pinned `== 0.0` (`tests/test_k04f9_t05b.py:486`).

---

## 5. Tests weakened after measurement (brief item 6), against "no relaxed checks"

| test | change | judgement |
| --- | --- | --- |
| A50 (`tests/test_t06_w8_references.py:94`) | live solve vs committed record: floats to 1e-12 relative, non-floats exact, `certificate_sha256` skipped | **Legitimate in substance.** ADR 0007 makes cross-machine bitwise equality unattainable. The measured difference is 1.2e-15. The bound sits 1e6 inside every §9.4 tolerance, and the guard test proves it still bites. **Procedurally**, the spec row says "exact", so the `specifier` must ratify the change. The skipped hash is S2. |
| T05b B34 (a) (`tests/test_t05b_candidate_answers.py:282`) | the moved closure values (30.70 K, 23.78 K) are recorded, not asserted | **Legitimate.** A92 registers the verdict, `false_success_detected`, the closure as the only failing check, and a floor; it does not register the values. All of these are still asserted on every machine. The values are a false success lying along a singular null direction (T05b §17). A 7.6 K cross-machine landing difference is expected there and certifies nothing false. The now-unasserted constants should be moved to a comment or the measurements file. |
| A92's floor, 9.4e-4 vs the text's 9.5e-4 (`:252`) | lowered by 0.1e-4 | **Legitimate as a correction; flagged correctly.** "≥ 9.5e-4 K" is 9.494e-4 rounded *up*, so the text states a false bound. The engineer truncated the value and reported it, as the build lane must not lower a registered number. S3 asks for a principled floor instead of either number. |
| X26's roundoff split (T05b, `85d4c96`, `tests/test_k04f9_t05b.py:483`) | bounds pinned below 1e-12 are held `< 1e-12` instead of `rel = 1e-3` | **Legitimate.** These are regression values, not registered ones; the registered rule (`b ≤ 1e-7`) is unchanged; values at roundoff (a few ulps × `‖J⁻¹‖`) differ in their leading digits between platforms. The split still separates roundoff-set from truncation-set cases. See N8 for the exact zeros. |

No other test in the range was loosened. The remaining edits to closed-package tests are the four
A92 re-registrations, which add assertions, and the T05 W11 unit mutations, which ADR 0016 D9.1
re-points and re-registers.

---

## 6. The brief's "least sure" list

1. **F6 and A78:** sound (N1).
2. **The refinement:** sound except M1. Engineer readings (ii) and (iii): agreed (N2). Reading (i) is
   M1.
3. **F4's restart and the ensemble scoring:** sound (N3, N4).
   - The success rule, the classification order (`F-GEN` → `F-CRASH` → `F-TIME` → outcome → verdict
     → S3) and the rescue test follow §7.1–§7.2.
   - Clustering is reported only.
4. **The verifier:** sound. S1 and S4 need decisions; N6 holds the small items.
5. **Units and component order:** sound. S5 and N7.
6. **Weakened tests:** §5.

---

## 7. FOR FRANK

1. **ADR 0018's promise that the refinement "never changes an outcome" is not true under a property
   budget (M1).** You approved `newton_refined` as T07's default on that promise.
   - Measured: the same start under the same cap converges under `newton` and ends
     `BUDGET_EXHAUSTED` under `newton_refined`.
   - It does not touch the scoring. It can only turn a success into `F-BUDGET`, and it was not hit on
     x86-64.
   - My recommendation is to correct the ADR's sentence, not the code: the refinement spends budget
     like any Newton step. This does not change the case for T07's default.
2. **What run 2's PASS measures.**
   - Starts that succeeded on the first solve: 370 on x86-64, 367 on aarch64. Both are below 418.
   - The gate passes on the registered fallback (ADR 0015): 64 and 67 rescues. On the ten acyclic
     cases these do not depend on the perturbation.
   - This is by design and the report discloses it. The `verdict` agent is ruling on the gate itself.
3. **The certificate now calls some unverifiable two-phase labels "false success detected" (S1).**
   These are states with a vanishing phase and a refused projection. This is conservative for T06. For
   T07 there is a question of wording: `FAILED` asserts the state is wrong, where "not demonstrated"
   would be accurate. It is recommended as a T07 question, not a T06 change.

---

## 8. Probes (scratchpad `review_t06/`; `PATH=.venv/bin:$PATH PYTHONPATH=src:.`)

- **P1** `p1_budget.py THM-09 1` runs the published start through `execute_plan` with
  `user_start`, under `T06-revision-v2` and under that policy with `eo_core = "newton"`. Each is run
  uncapped and then capped at `newton`'s own property-call total. Output as in M1.
- **P2** `closure_probe.py` computes §8.8's closure at a perturbed two-phase split whose equilibrium
  rows pass at 0.5 `τ_eq`, for three values of `V·L`. Output as in S1.
- **P3** `units_probe.py`: `10**400` through DIM-01, both bindings and `read_parameter` (six paths),
  and `convert_input_value(np.float64(26.85), "degC")`.

---

## 9. Not examined

- the design lane's documents (the twin, the reference YAML and the ADR texts, except where quoted);
- the IDAES and DWSIM harness internals and the reference comparison (the `verdict` agent's);
- `verify/projection.py` beyond its preconditions, and `onenormest`'s accuracy beyond A2.4;
- the aarch64 run file;
- A78's proof, which I did not re-run;
- the regenerated schema fixtures;
- the generator's sampling law, and the starts file beyond reading its records;
- `check_quantity`'s signed-zero handling;
- the evidence manifest, per the brief.
