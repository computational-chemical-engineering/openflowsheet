# T02 review — the execution plan, the safeguarded Anderson recycle, the EO region and the cross-unit specification, against `docs/derivations/T02-recycle-spec.md` and ADR 0009

**Reviewer:** Fable 5.1 (`fable-reviewer`), 2026-09-24. Plan §1.3: Fable reviews every Opus package
that touches residuals, derivatives, phase logic, scaling, certificates or replay identity; this one
touches all six.
**Brief:** `docs/briefs/T02-implementation-review.md`.
**Reviewed at:** `wp/T02` = `0b71214`; commit range `fe0a4de..0b71214`; the seven T02 test files
green here (98 passed, 4.7 s); the brief reports the gate green at 1515 and `t02_reference.py
--check` at 114. The evidence manifest was not available at review time (MANIFEST_PENDING).
**Environment here:** x86-64 Linux 6.12.86, the repository's `.venv`. The CI pair's identity
artefacts (run 35979824190, both runners) were downloaded and are the basis of §5.
**Measured:** every finding marked *measured* was produced by a probe against the code at this
commit, run in this session; the probes are described inline so they can be re-run. Nothing below is
inferred from reading alone where it could be run.
**The specification is mine.** Where a finding turns on the specification's own wording it is
numbered against the specification, and the amendment is made in this commit.

---

## 1. Verdict

**The numerics are faithful.** The Anderson core (`numerics/anderson.py`) is the registered policy
of §5 in the twin's order of operations — depth `min(5, k, n)`, the condition filter and coefficient
bound as repeated column drops with the refused value recorded, no merit test, growth counted as
stagnation, the oscillation response confined to plain steps, K03's exact landing — and the A07–A20
agreement with the 40-digit twin is two derivations meeting, not a fixture matching itself. The
lifted EO phase policy of §6.3 as amended (`orchestrator/region.py`) implements what the two
measurements demanded and nothing more: the landing hook fires only on an *accepted* full step
(`newton.py:477`), the watch is consulted after the accepted step and before the next convergence
test, so a landing that is also a root closes `PHASE_UPDATE_REQUIRED` and never `CONVERGED` on a
two-phase signature; appearance is admitted only at closure; the cycle rule is K03's. A21–A24 and
A28–A31 pin the closed forms (P01's 20-digit state, the energy invariant, the branch roots) and not
the solver's own output. The merge edge on the manufactured maps (A14–A17, A32) is as specified.

**It is not done.** Two paths return a wrong result silently, both reachable from a revision
document or a policy value, both invisible to the gate because the registered cases do not reach
them, and both have the same mechanism underneath: the executor does not run the plan it records.

1. A cross-unit specification whose adjusted variable and target share an owner — free the heater's
   outlet temperature, specify the *heater's* duty — validates `READY_FOR_SIMULATION`, is planned as
   a plain tear, and reports **`CONVERGED` with the heater at its 358 K guess and
   `U-HEAT.Q = 46 381 W` against a specified 40 000 W** (M1). A placeholder success path, the thing
   `CLAUDE.md` forbids first.
2. `SolvePolicy.recycle.tear_streams` — the alternate-tearing override the specification registers
   (A18) — changes the recorded `tear_streams` and nothing else: the `SolvePlan` keeps the original
   tear variables, the override is not checked to be a set of cycle edges (`("S1",)` is accepted), and
   the executor tears `S6` regardless, so the R0 plan document is inconsistent with itself and with
   what ran (M2). A18's alternate tear is tested on a hand-built map only.
3. The `converge` step hands the flowsheet to K03's `solve_tear`, which builds *its own* `SolvePlan`
   from the flowsheet's own compiled problem; the `ExecutionPlan`'s per-step `SolvePlan` — the R0
   artefact ADR 0009 D1 exists for — is never consumed, and no check says the two describe the same
   problem (M3). This is why M1 and M2 are silent.

The failed gate A34 is a policy failure, not an implementation one, and the brief was right not to
relax it. §5 rules it: `kappa_2` and `gamma_inf` are least-squares quantities of *residual
differences*, whose cross-platform agreement scales as `ε/‖f̂_k‖` and cannot be described by a
constant floor; they are compared relatively inside a registered comparability window and recorded
outside it, and the `kappa_2` floor of 1.0 is withdrawn as a category error (M4, Q1, Q2).

The decisions in brief §4 were sound with one exception each way: the R-022 extension and the K04
fix are accepted as made (N3, N4); the `PropertyMeter` is right but a region still runs without the
K03 §11.2 budget the specification says applies unchanged (S4, Q3); and the `eo` override skips the
capability rule the specification applies to every region (S1). The measured deviations of brief
Q4 are accepted and the specification's wording is amended (N5).

What I did not examine: `t02_reference.py` (my own twin) beyond `--check`; the registry prose and
the A02 revision YAMLs beyond their `role: free` and promotion entries; the schema JSON layout;
the K03 fixture regeneration; `.github/workflows/ci.yml`; `k05_structural_identity.py` beyond
what `test_t02_identity.py` asserts; `docs/progress.md`.

---

## 2. Must-fix findings

### M1 — A unit-local freed/promoted pair is planned as a plain tear and reports `CONVERGED` at the guess

**Where.** `src/process_runtime/orchestrator/execution.py:428-429`:

```python
if adjusted_owner == target_owner:
    return ()  # unit-local: that unit's evaluator serves it (blueprint [A02])
```

and `src/process_runtime/orchestrator/executor.py:258`, where the `converge` step runs
`solve_tear(flowsheet, ...)` on the flowsheet the binding built — with the freed coordinate *pinned
at its guess* (`binding.py`, "the pre-solve's flowsheet") and the flowsheet's own `HEAT-T` row, not
the declaration's rows with `HEAT-T` removed and the promotion row added.

**Measured.** `SYN-001-A02-360.yaml` with `SPEC-flash-duty` retargeted to `heater / duty.Q`,
value 40 000 W (`role: free` on `S3.T` at 358 K kept):

```
validate:  READY_FOR_SIMULATION   (no check fails; 47 x 47, closed)
binding:   freed {U-HEAT:HEAT-T: S3.T}   promoted {SPEC:SPEC-heater-duty: U-HEAT.Q}
plan:      [evaluate, converge]   region_count 0
run:       CONVERGED   S3.T = 358.0   U-HEAT.Q = 46381.246 W   (specified 40000.0)
```

The specification is unmet by 6 381 W and nothing in the result, the trace or the plan says so.
The closed form of §7.6 puts the answer near 356.8 K (`Q_heater` 31 657 W at 355 K, 46 381 W at
358 K).

**Why.** Blueprint [A02]'s "the unit's evaluator serves it" presumes a unit with a local solver for
the freed outlet. No v0.1 unit has one — the SYN-001 heater's evaluator takes `T` and reports `Q` —
and the manifests do not declare such a capability, so the shortcut has no premise to stand on. The
`return ()` then lets the loop be torn *around* a unit whose specified outlet is free, which is
exactly the situation §7.1 says cannot be traversed.

**Correction.** In `specification_regions`, a pair with one owner is a region too: that unit and
every loop containing it (the same rule with `between = ∅`). Keep the unit-local shortcut only
behind a manifest declaration that the unit's evaluator solves the freed outlet for the target —
which no v0.1 unit makes — so the branch is unreachable until a unit earns it. §7.1 is amended in
this commit to say so. The register's R-023 gains the sentence: a `role: free` specification is
always served by a region in v0.1. And M3's guard, so that a step whose rows are not the
declaration's cannot run.

**Test that catches it.** The probe above, asserting either a `solve_eo` step whose result has
`U-HEAT.Q` within `1e-2 W` of 40 000 and `S3.T` in `(355, 358)` K, or a typed refusal naming the
unit — and never `CONVERGED` with `|U-HEAT.Q − Q_spec| > 1e-2 W`.

### M2 — `recycle.tear_streams` changes the record, not the plan; it is not validated; the executor ignores it

**Where.** `src/process_runtime/orchestrator/execution.py:631-632`:

```python
if policy.recycle.tear_streams is not None:
    tear_streams = tuple(policy.recycle.tear_streams)
```

`tear_variables` and `tear_rows` were fixed above it from T01's chosen stream (or the iterated set)
and are not recomputed; nothing checks that the named streams are cycle edges of the loop or that
removing them leaves the loop acyclic (§3.3: "may name any set that leaves the loop acyclic").

**Measured.** SYN-001 nominal, `recycle.tear_streams = ("S3",)` and then `("S1",)` (the feed
stream, not a cycle edge):

```
override=None:     tear_streams=('S6',)  solve_plan.tear_variable_ids=('S6.n.A','S6.n.B','S6.n.C')
override=('S3',):  tear_streams=('S3',)  solve_plan.tear_variable_ids=('S6.n.A','S6.n.B','S6.n.C')
override=('S1',):  tear_streams=('S1',)  solve_plan.tear_variable_ids=('S6.n.A','S6.n.B','S6.n.C')
executor, all three: CONVERGED, K03 plan tear ids ('S6.n.A','S6.n.B','S6.n.C')
```

The `ExecutionPlan` — R0, in the identity job, in every bundle — says the loop was torn at `S3`
(or at a stream that is not in the loop) while its own `SolvePlan` and the run say `S6`.

**Correction.** Resolve the override *through* the candidates: every named stream must be a
candidate of the loop (else a typed refusal naming the stream); the named set must leave the loop's
units acyclic under `_components` (else `UnsupportedRankStructureError`, the same code the
non-square region uses); then `tear_variables`/`tear_rows` come from the named candidates exactly as
the iterated path derives them. And M3, so that what runs is what was planned.

**Test that catches it.** SYN-001 with `tear_streams = ("S3",)`: the `SolvePlan`'s
`tear_variable_ids` are `S3`'s state columns and the executed K03 plan's are the same; with
`("S1",)`: a typed refusal. NEST-1 with `("s1", "s5")` through `build_execution_plan` (a declaration
for NEST-1 is needed; today only `iterated_tear_set` is exercised): tear ids `(s1.x, s5.x)`.

### M3 — The executor does not execute the step's `SolvePlan`, and nothing checks that what ran is what was planned

**Where.** `src/process_runtime/orchestrator/executor.py:258` (`solve_tear(flowsheet,
policy=step_policy)`) and `:316-318` (the pre-solve). `solve_tear` constructs `Syn001TearProblem`
and K03's `build_plan` from the flowsheet, records its own `plan_built` — which `_absorb` then
drops (`executor.py:92-93`) — and solves the flowsheet's compiled problem. The step's
`solve_plan` (tear ids, inner ids, eliminated rows, scales, bounds, signature units) is never read.
The `spec` argument of `execute_plan` reaches the region path (`_region` compiles it) and not the
tear path.

**Consequence.** ADR 0009 D1's plan is a record of intent with no enforcement; M1 and M2 are the two
cases where intent and execution already differ. K05 will replay the recorded plan against a run
that did not use it.

**Correction (minimum).** After `solve_tear`, compare `result.plan` with the step's `solve_plan` on
`tear_variable_ids`, `tear_row_ids`, `inner_variable_ids`, `inner_row_ids`, eliminated row ids,
`signature_units`, `model_version`, `constants_sha256`, and the tear problem's row set with
`spec.equation_ids`; on any difference end the step with a typed outcome
(`UNSUPPORTED_RANK_STRUCTURE` with a message naming the first differing field, or a new
`PLAN_MISMATCH` if Fable is asked for one — I would use the existing code) and never run. The
proper fix — `solve_tear` accepting a `SolvePlan` and a `ProblemSpec` — is a K03 interface change
and can wait for the package that first needs a second flowsheet; the guard cannot.

**Test that catches it.** M1's and M2's probes fail the guard; the five registered variants and
the A02 pre-solves pass it.

### M4 — A34: `kappa_2` and `gamma_inf` under a constant floor (Q1, Q2)

**Where.** ADR 0009 D3 (last paragraph), ADR 0007 D2.2 (the two T02 rows),
`benchmarks/k04/reference_values.yaml` `numerical_policy.floors` (`kappa_2: 1.0`,
`gamma_inf: 1e-12`), `scripts/t02_identity.py:159-160` (the float document carries the two
values and nothing to scope them by), `src/process_runtime/run/compare.py:307-311` (the floor is
`abs_tol`, exactly D2.1's formula).

**Measured** (the CI pair's `t02-floats.json`, every accelerated event of every registered recycle
case, annotated with the scaled residual `‖f̂_k‖∞` at that event from a local run of the identical
R0 trajectory; `τ̂ = 1.03e-8`):

| Regime | Events | Worst `|Δκ₂|/κ₂` | Worst `|Δγ∞|/γ∞` |
| --- | --- | --- | --- |
| `‖f̂_k‖∞ ≥ 1e-4` | 26 of 44 | 3.3e-13 (REC-02 γ=0.1, ev 5, κ = 2.7e4) | 3.3e-13 |
| `1e-5 ≤ ‖f̂_k‖∞ < 1e-4` | 6 | 1.8e-11 | 3.2e-10 (REC-03 γ=0.1, ev 5) |
| `‖f̂_k‖∞ < 1e-5` | 12 | 2.15e-9 (REC-03 γ=0.1, ev 6, ‖f̂‖ = 5.5e-8) | 1.06e-8 (same event); 6.4e-9 (REC-05 γ=0.1, ev 8, ‖f̂‖ = 1.7e-6) |

On every event `|Δγ∞|/γ∞ ≤ 50 · ε / ‖f̂_k‖∞` (the factor is 2.6, 50, 41, 0.4, 32 on the five events
above 1e-10), and the same bound holds for `κ₂`. That is the signature of *data* error, not solve
error: the columns of the least squares are differences of residuals, whose absolute cross-platform
error is `O(ε · ‖x̂‖ ‖Ĵ‖)` regardless of how small the residual has become, so their relative error
is that over `‖f̂_k‖`. `κ₂ ε` — the floor's argument — describes the rounding of the *solve*, four
decades below what was measured, exactly as the brief said. A constant floor is the wrong kind of
object for this quantity. The `kappa_2` floor of 1.0 is also a category error: `κ₂ ≥ 1` by
definition, so "below 1 is not a measurement" is vacuous, and what the floor did in the CI run was
accept `|Δκ₂| = 2.1e-5` at κ = 9.7e3 (2.15e-9 relative) as agreement.

**Ruling** (the amendment is in ADR 0009 D3 and ADR 0007 D2.2 in this commit; the register's
R-026 records it). `kappa_2` and `gamma_inf` are R1/R2 with a **comparability window**: compared
under D2.1's relative rule with **no absolute floor** on `acceleration` events whose scaled
residual `‖f̂_k‖∞ = residual_inf_unscaled / S ≥ 1e-4`; **recorded and shape-checked, not
value-compared** below it — the treatment `UNREPRODUCIBLE_COUNTS` already receive, with the same
kind of measured justification. The window is two decades above the worst in-window deviation
(3.3e-13 against 1e-9, D2.4's margin of ten, squared) and four decades above `τ̂`; it is the regime
in which §5.9 already registers trajectories (`1e-6` was considered and rejected: REC-05 γ=0.1's
event 8 sits at 1.7e-6 and deviates 6.4e-9). The *decisions* the two feed (`depth_used`, the drop
counts) stay R0 and are promised, in D2.4's sense, only when not near threshold: `κ₂ ∉ [1e7, 1e9]`
and `‖γ‖∞ ∉ [1e3, 1e5]` on every accelerated event, asserted per platform (A19's clause,
generalized to every registered case; the registered maxima are 2.7e4 and 125). This is an ordinary
addition under D2.3 — D2.1's formula for every compared float is unchanged; what is added is the
scope of comparison for two paths, on D2.4's principle — and not a new policy id.

**Rejected:** a floor proportional to `κ₂ ε` (wrong physics, measured four decades short); a
residual-scaled relative tolerance `1e-9 · max(1, 1e-4/‖f̂‖)` (fits every measured point with
margin ≥ 9 but is a new comparison rule, hence a policy id, for two intermediate quantities);
"recorded, never compared" (loses a real check where the data are good, and needs a new float class
in D2.2 anyway).

**Mechanism (Opus).** `scripts/t02_identity.py` writes `residual_inf_scaled` beside `kappa_2` and
`gamma_inf` on each accelerated event; the comparison applies the window on the *committed*
document's residual (the `SELF_FLOORED` precedent, a sibling-keyed rule: compared iff sibling
≥ threshold), so the side of the window is decided once; `REGISTERED_FLOOR` for the two paths is
0 with the window registered beside it in `numerical_policy` (`k04_reference.py`, the YAML, ADR
0007's table); `test_t02_identity.py` asserts the window and the decision-margin per event. A34's
text is amended accordingly. The gate stays failed until this lands. **This amendment itself turns
one local test red** — `test_a34_adr_0007_d2_2_carries_both_rows` pins the withdrawn floors
(`"| 1.0"`, `"| 1e-12"` in the D2.2 table) — and `test_a34_the_two_floors_are_registered_where_the_policy_lives`
stays green only because the K04 policy YAML still carries the old floors. Both are the mechanism's
to rewrite with the window; neither is to be restored. The register's R-026 records the ruling.

---

## 3. Should-fix

### S1 — `method: eo` promotes a loop to a region without §7.4's capability rule

`execution.py:613-615` builds `region_step(loop_region, …)` with no `capable[unit]` check; the check
at `:544-550` runs over `specifications` only. *Measured:* the nominal flowsheet with the heater's
`residuals` derivative `unavailable` and `recycle.method = eo` builds `[evaluate, solve_eo]`. §7.4:
"if any unit of a region is not EO-capable, the plan is not built". Correction: the same
`CapabilityUnavailableError` for every `solve_eo` step, promoted loops included (the specification
rows are empty; the message's "for the plan" branch already exists for it). Test: the probe, expecting
`PlanRefusal` with `CAPABILITY_UNAVAILABLE` naming `U-HEAT`.

### S2 — The merge edge is decided in two places

`orchestrator/merge.py:converge_with_merge` (used by the manufactured-map tests) and
`executor._converge` (`executor.py:270-302`, used by every flowsheet run) each implement §4.4's
trigger test, the `unsupported` message (`f'...; merge_into_eo: unsupported({unit}, "derivatives:
{declared}")'`, duplicated verbatim), and the `taken` result shape. `MERGE_TRIGGERS` is shared; the
rest is not. Correction: one function that takes a recycle result and the step's `region_on_merge`/
`merge_unsupported` and returns the decision and message; both callers use it. Also
`ConvergeResult.attempts` returns 1 or 2 regardless of the phase contract's attempt count — under
the attempt controller it is wrong; take it from the recycle result.

### S3 — `execution_plan_r0` strips the declared scales and bounds ADR 0009 D1 calls R0

`run/identity.py:37-56` removes every float, so `column_scales`, `row_scales` and the bound values
leave the compared document (`bounds: {name: [null]}` after the tuple is stripped of its `0.0`).
D1: "R0 entire (ids, integers, orderings, declared scales and bounds)". The scales are policy
constants (3.0 mol/s, 10 K, …), not measurements; compare them exactly as their shortest decimal
strings, as `beta_substitution` already is (`t02_identity.py:154-157`). Test: a plan whose
`column_scales["S6.n.A"]` is changed to 3.1 must differ in the R0 projection.

### S4 — A region runs with no property-call budget (Q3)

Brief §4 item 6. §5.7: "K03's property-call budget and attempt budget apply unchanged"; K03 §11.2's
guard refuses the call that would exceed the cap. The region path meters (`PropertyMeter`) and
enforces nothing; A31's attempts run 13 and 9 Newton iterations to the provider's domain edges
with every property block evaluated per residual and per Jacobian, and nothing bounds that.
Ruling: enforce in T02. Mechanism: `PropertyMeter` takes an optional cap (or wraps a
`BudgetedProvider`); `_region` catches `BudgetExhaustedError` and closes the step
`BUDGET_EXHAUSTED` with `budget = property_calls`, as `solve_tear` does (`tear.py:527`). Test: A02-360
with `max_property_calls = 50` ends `BUDGET_EXHAUSTED` with `counters.property_calls == 50` exactly.

### S5 — The kernel's refusal is an untyped crash on the region path

`region.py:219-220`: `raise ValueError(f"the kernel could not split …")` — in the projection at
`x⁰`, in §6.3.4(a)'s restart and in §6.3.4(b)'s verdict. Through the executor the A02 pre-solve
shields it (an out-of-domain guess fails there first, typed), but `solve_region` is a public
function and a supplied state outside `[280, 440] K` produces a Python exception where the vocabulary
has `EVALUATION_ERROR`. Correction: return `closed("EVALUATION_ERROR", …)` naming the stream and
the provider's status. Test: `solve_region` from the nominal `x(t*)` with `S3.T = 450`.

### S6 — `BOUND_BLOCKED` is attributed to "the first watched variable at zero"

`region.py:556-560`. The Newton core knows which components block (`_bound_aware_alpha`'s
`crossing` with `x == lower`) and reports none of them; the region guesses. Today the guess cannot
be wrong — a watched variable starts positive and reaches zero only through an accepted landing,
which `landed` already caught — but a rule that guesses is one measurement away from being wrong (the
lesson of §15 finding 10). Correction: `_bound_aware_alpha` returns the blocking indices;
`NewtonResult` (or the `BOUND_BLOCKED` message, structured) carries them; the region attributes only
a watched blocker and otherwise leaves the closure to §6.3.4(b).

### S7 — The pre-solve is absorbed inside the region step with attempt indices restarting

`executor.py:316-319`. The `solve_eo` step's bracket contains the pre-solve's
`attempt_opened(0)…attempt_closed(0)` (tear signature) followed by the region's
`attempt_opened(0)…` (lifted signature): two attempt 0s in one step, one trace. K03's pairing rule
passes; K05's replay will not know which attempt 0 to replay. Correction: offset the absorbed
attempt indices as counters are offset, or record the pre-solve as the initializer it is
(`initializer_candidate` / `initializer_accepted` around it, its inner events carrying
`attempt = -1` is not in the schema — so offsetting is the minimal form). Test: attempt indices are
strictly increasing within a step.

### S8 — Two solve results for one converged step

`_converge` returns `iterations = recycle + region` and `detail = region_result` after a merge,
discarding the recycle's `SolveResult` (its attempts, its checkpoint, its contexts) from the step;
the bundle for a failed merged step then describes the region only. Keep both (the `ConvergeResult`
shape in `merge.py` has the slot) — S2's single function returns it.

---

## 4. Notes (no change required, or a wording amendment made here)

- **N1 — the Anderson core against the twin.** Order of operations verified by reading against
  §5.2–§5.7 and by A07–A20's exact counts; the restart clears the history so the restart iterate's
  step is plain (§5.6 "iterate kept"); the coefficient bound's refused value is recorded on the drop
  (A17). The oscillation detector tests the previous iterate's dominant component against
  `tolerance_hat[dominant]` only — "both above the scaled tolerance" holds because an unconverged
  iterate's largest component exceeds *some* row's tolerance, not necessarily its own; with per-kind
  tolerances on a mixed-kind tear (none registered) the flip test could fire on a component within
  its own tolerance. Harmless (it damps plain steps only); noted for T05.
- **N2 — `beta_substitution` on an Anderson step.** The event records `rules.beta` (the mixing, 1)
  rather than the damping "in force" (0.5 after the flag), so that A20's "stays 1 on Anderson steps"
  holds. §5.8's wording "in force" is amended to "applied to this step" in this commit; the
  implementation is the intended one.
- **N3 — the K04 verdict-word fix (`8d533eb`).** Correct and narrowly pinned: the three codes are
  removed before the scan, the words stay forbidden in prose, and the test enumerates the vocabulary's
  codes containing a verdict word. K04 A20's meaning is preserved.
- **N4 — the R-022 extension (`6645df5`).** Accepted: `failed == {"STR-02"}` is the right
  narrowness (any second failure stays `INVALID`), and blueprint §4.3's words carry it. The register
  entry is adequate.
- **N5 — brief Q4.** A26(a): T01's over-determined part is a set of rows and the canonical matching
  decides which of `HEAT-T` and the promotion row is unmatched; naming `U-FLASH` with `U-HEAT`
  reached through `SPEC-heater-outlet-T` among the candidates is a correct reading of the same
  structural fact. A26 is amended to "naming the over-specified unit among `U-HEAT`/`U-FLASH`, with
  both rows among the candidates". A29's "measured 4" was a prototype figure; 3 is within the bound
  and needs no change.
- **N6 — the executor's counter arithmetic (brief §6).** Verified by reading: `_offset` adds the
  plan's spent counters to every absorbed event; the absorbed `solve_closed`'s counters set the new
  total; the region's `property_calls` are the meter's delta from the step's start, offset the same
  way. Correct. The gap is S7, not the counters.
- **N7 — the decision margin that makes the R0 drop decisions a promise.** From the CI table: the
  largest accepted `κ₂` is 2.69e4 (REC-02 γ=0.1, event 5), the largest `‖γ‖∞` 125 (REC-05 γ=0, event
  3) — three and two decades inside `condition_max` and `coefficient_max`. No registered case is
  near threshold in D2.4's sense; A19's clause should say so for every case (M4's mechanism).
- **N8 — single-loop assumptions.** `report.tear.inner_rows`/`inner_variables` are read as if one
  loop existed (`execution.py:634-637`), every consistent certificate is eliminated in every loop's
  `SolvePlan` (`:662-664`), and the iterated tear set's `tear_rows` are "the producer's rows touching
  a torn variable" (`:625-630`), which over-collects on a producer whose balance row touches the torn
  stream. §12 says no registered flowsheet has two loops; the day one does, these three lines are
  the ones to revisit, and `Candidate` should carry its tear rows from T01.
- **N9 — the `evaluate` step.** Any unit but the feed raises `ValueError` (`executor.py:208-212`),
  a Python exception, not the "typed refusal" the module note promises; v0.1's honest limit, but it
  should be `UNSUPPORTED_RANK_STRUCTURE`-shaped, not a traceback. `role: free` without a `value` is
  silently not freed (`binding.py`, `entry.get("value") is not None`), so it surfaces as
  over-specification rather than §7.5's `INITIALIZATION_FAILED` naming the variable — typed, wrong
  object.
- **N10 — performance.** `compile_problem(spec)` runs once per region step and once per merge
  (`executor.py:380`), and `Syn001TearProblem(flowsheet)` is built again for the merge's
  reconstruction (`:288`), on top of `solve_tear`'s own — three to four compiles per plan run where
  one would do (T01 review S9's shape). `_reach` is `O(|units| · |connections|)` per call, called
  four times per specification; `specification_regions` is called once. Nothing here matters at
  47 variables; measure before the first large flowsheet.
- **N11 — verification quality, beyond M1–M3.** A33's `well_formed` hard-codes `depth_used ≤ min(5,
  3)` (SYN-001's `n`); the A02 identity document is the same twice on one machine (good); the A27
  refusal is asserted through `plan_or_refusal` with the bundle validated against the schema (good);
  A21 admits any of the four lifted vapour variables, as amended. The tests pin what they claim
  except where M2 (A18 off-plan) and S3 (A02's R0 minus scales) say.

---

## 5. Rulings on brief §5

- **Q1 (A34, `gamma_inf`)** — M4: comparability window at `‖f̂_k‖∞ ≥ 1e-4`, relative rule with no
  floor inside it, recorded outside it; the drop decisions R0 with D2.4's margin asserted. Amended in
  ADR 0009 D3 and ADR 0007 D2.2; register R-026. Not relaxed: the two failing events are *outside* the
  regime in which the quantity is a measurement, and the regime is stated with the measurement that
  defines it.
- **Q2 (`kappa_2` floor 1.0)** — withdrawn as a category error (M4). Inside the window `κ₂` agrees
  to 3.3e-13 relative; the floor was hiding a 2.15e-9 disagreement outside it.
- **Q3 (region budgets)** — enforce in T02 (S4). K03 §11.2 applies unchanged by §5.7's own words,
  the mechanism exists, and the liquid-guess cases show a region attempt running to the domain edge.
- **Q4 (measured deviations)** — accepted; A26's wording amended, A29 unchanged (N5).

Brief §4's decisions: 1 (R-022 extension) accepted, N4; 2 (R-023) accepted with M1's sentence
added; 3 (K04 fix) accepted, N3; 4 (absorbed traces) accepted with S7; 5 (checkpoint label) correct;
6 (`PropertyMeter`) correct as far as it goes, S4; 7 (feed step) accepted, N9; 8 (`best_x`) correct.

---

## 6. FOR FRANK

Nothing in this review needs a decision of Frank's. The A34 ruling is a Fable amendment under ADR
0007 D2.3 (an ordinary addition, same policy id); if Frank would rather see it as a `v2` policy id,
that is a one-line change to the amendment and nothing else moves. The spec's F1/F2 defaults
(`docs/T02_STATE.md`) stand.

---

## 7. What T03 inherits

1. **The lifted phase policy is sound as far as T02 takes it** (§6.3.1–5); T03's two additions
   (§6.3.6) are unchanged, and S6's blocker attribution should land before T03 builds on
   `BOUND_BLOCKED`.
2. **A region without a property budget (S4)** would be T03's controller's problem if T02 leaves it.
3. **The identity comparison's window (M4)** applies to any float T03 records from a least squares or
   a difference of residuals: register the window with the float, not a floor.
4. **The executor must run the plan it records (M3)** before T03 adds an attempt controller that
   reopens steps.
