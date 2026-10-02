# T06 F4 — Recovery for a revision-built EO region: the sequential restart, edge 3's second action

**Package:** T06 (finding F4, spec Q1, register R-074), branch `wp/T06` at `792c594`. **Lane:** design (`architect`), 2026-09-26. **Brief:** `docs/briefs/T06-F4-recovery.md`.
**Governs:** ADR 0010 D1, D3 and D7 (amended additively by the ADR 0015 draft in Appendix A); T06 spec §3.2 (NET-02's row), §6.6 (the revision path's policy) and §10 (the `t06` key's NET-02 entry). The amendments are listed in §6; the build lane applies them in the commits §7 names.
**Status:** design. Items marked *measured* were measured on this host (`.venv`, Python 3.13.5) at `792c594` with the repository's own code. The measurements used scratch scripts and monkeypatches, which are not committed. NET-02 was built from spec §4.3 with `tests/t05b_support.revision`. That helper declares the feed after the units and orders the connections S1, S6, S2, S3, S5, S4, S7, so the build lane's file may differ in iteration counts but not in outcomes. Appendix C gives the recipe.

---

## 0. The decision in five lines, and the frozen-interface flag

1. **Edge 3 gets a second action, the sequential restart.** When a region solve on a revision-built flowsheet ends in one of edge 3's trigger outcomes and the region has no continuation parameter, one new region solve runs. It starts from a new registered initializer, **`traversal-G0-pass8-v1`**: the traversal continued for 8 passes from dormant tears. Its opening is a fresh opening, and it runs the policy's core under a fresh contract state.
2. **It is selected by a new policy value**, `globalization.eo_recovery = "homotopy_or_sequential_restart"`. The homotopy has precedence, and there is at most one recovery per region step, so `eo_recovery_max_count = 1` still holds. No registered policy carries the new value, so no registered result moves.
3. **Rejected:** (a) a continuation parameter for revision flowsheets, (b) PTC mass mappings for the T05 units, and (c) a bound-aware or projected Newton step. The reasons are in §4. For (c), the probe measured the projected step collapsing the recycle to zero, and it would also move registered K03 trajectories.
4. **Measured on NET-02:** `CONVERGED` and `VERIFIED` under both contracts, within T02 §6.4's allowances. On 20 independent perturbed starts, 20 of 20 are `VERIFIED` at the root: 9 without the edge and 11 through it.
5. **The T06 ensemble's revision path runs a new policy**, `T06-revision-v1`. It is `T05b-v2` with only `globalization.eo_recovery` changed. NET-02 under `T05b-v2` and `T05-W13` stays registered as `BOUND_BLOCKED`, as the edge-off control (T04's HOM-01/HOM-N precedent).

> **FROZEN-INTERFACE FLAG — for Frank (the build lane takes it to him).** There are two additive enum widenings and nothing else:
> - `schemas/solve-policy.schema.json`: `globalization.eo_recovery` goes from `["homotopy", "none"]` to `["homotopy", "none", "homotopy_or_sequential_restart"]`.
> - `schemas/solve-event.schema.json`: `eo_recovery_unsupported` goes from `["no_continuation_parameter", null]` to that list plus `"no_restart_initializer"`, `"restart_start_unchanged"` and `"restart_initializer_failed"`.
>
> The matching Python `Literal`s widen with them. No field is added or removed, no default changes, and every existing document stays valid and byte-identical. Fixtures regenerate identically. The precedent is ADR 0012's widening of `phase_contract`, which Frank approved on 2026-09-25.
>
> **Default while the answer is pending:** implement on `wp/T06` in one isolated commit (WO1) and do not merge T06 to `main` until it is approved. If Frank declines, revert WO1 and take §10's variant, which needs no schema change and keeps coarser records.

---

## 1. Problem and scope

**Problem.** NET-02 is a heater, a PH flash and a recycle at `r = 0.95`, built from a revision. From its registered initializer it ends `BOUND_BLOCKED` at iteration 1. Edge 3 records `unsupported(no_continuation_parameter)`, because a revision flowsheet's region never has a promoted specification row. `eo_core = "ptc"` would refuse `PTC_MAPPING_INVALID`. NET-02 is one of the 22 eligible ensemble cases, so it can cost up to 20 of the gate's 22 allowed failures.

**In scope:**
- a recovery path for a revision-built EO region that ends in an EO globalization failure (spec Q1);
- its trigger, preconditions, count, records and cost;
- the policy that selects it;
- NET-02's registration under that policy;
- the inertness proof;
- the work orders and gates.

**Out of scope:**
- PTC mass mappings and PTC qualification (ADR 0010 D5 stands);
- specification regions on revision flowsheets (T07);
- a restart for SYN-001's legacy flowsheet, which has its own tear path and registered policies;
- a second recovery after a stalled homotopy;
- Wegstein or any other accelerated tear iteration;
- the provider defect found on the way (§9 Q6), which is reported, not fixed here;
- the ensemble's scoring rules (T06 §7, unchanged).

---

## 2. What was measured, and what it says about the mechanism

| What (*measured*) | Result |
| --- | --- |
| NET-02, registered start (`traversal-G0-v1` = traversal pass 2), both contracts | `BOUND_BLOCKED` at iteration 1. The first accepted step has `α = 0.0018230797498657856`, and `S6.n.A` lands on `+0.0`. The direction at `x⁰` is `ΔS6 = (−95.8, −182.5, −257.3)` mol/s, `ΔS3.L = −568` mol/s and `ΔU-HEAT.Q = +1.17e6` W. The root needs `S6 = (6.644, 11.514, 15.826)`, which is **up** from `(0.175, 0.367, 0.632)`. |
| Scaled Jacobian at `x⁰` (47 × 47) | `σ_min = 1.66e-4`, `σ_max = 3.99`, `cond = 2.4e4`. The right singular vector of `σ_min` is the loop inventory: `S3.L` 0.509, `S5.N` 0.507, `S5.n.C` 0.244, `S3.liq.C` 0.235, `S6/S2/S3.n.C` 0.231, `S5.n.B` 0.172. Only the splitter's recycle rows are nonzero at `x⁰` (the torn closure). |
| One more traversal pass (pass 3) | `σ_min = 1.48e-3`, `cond = 2.8e3`, with the same mode. The Newton step along it is `+69` scaled, which has the right sign. `CONVERGED` in 6 iterations, at the root. |
| Starts after traversal passes `k = 3 … 28` | All `CONVERGED` at the root, in 3–6 iterations. Pass 29 of the sequence fails: `U-MIX`: `liquid enthalpy: Rachford-Rice did not reach 1e-14 in 200 iterations`. |
| A projected step (the blocked component's direction zeroed, then `α_max` recomputed; probe patch of `_bound_aware_step`) | `S6 → (0, 0, 0)` and `LINE_SEARCH_FAILED` after 5 iterations. One trial leaves the domain (`S2.T = 279.69 K`). |
| Seeding the traversal from the failed opening's torn stream `(n, T, P)` | 11 of 11 failing perturbed starts are refused at pass 1 by `U-MIX`'s equal-inlet-pressure rule, because the perturbed `S6.P` differs from the feed's. |
| 20 independent perturbed starts: T06 §6.2–§6.4's law with key prefix `F4-probe-v1`, **not** the gate's keys | Without the edge, 9 of 20 are `CONVERGED` at the root. The 11 failures are 10 `BOUND_BLOCKED` at iteration 1 and 1 `ACTIVE_SET_CYCLING`. With the restart (§5), 20 of 20 are `CONVERGED` and `VERIFIED` at the root; the 11 rescued starts each take 4 iterations in the restart. |
| NET-02 with the restart (probe patch of `executor._eo_recovery`), `T05b-v2` and `T05-W13` | `CONVERGED` and `VERIFIED` under both. Errors against `ref.closed_form.corpus_cases.SYN-001-T06-NET02`: `S4.T` 1.02e-9 K; `S6.n` 8.8e-10, 2.9e-9 and 5.4e-9 mol/s; `U-HEAT.Q` 1.6e-5 W. Items: item 0 ends `BOUND_BLOCKED` after 1 iteration; item 1 ends `CONVERGED` after 4. Solve plus verify takes 0.23 s. The restart start is 8 passes, 1 734 provider calls and 0.057 s; `traversal-G0-v1` itself makes 407 calls. |
| C2 and C3 (T05) from the restart start | C2: all 8 passes succeed; `CONVERGED` in 2 iterations; the largest difference from the registered path's state is 1.8e-12. C3: pass 4 fails in `U-MIX` with the same Rachford–Rice non-convergence, so passes used = 3; `CONVERGED` in 3 iterations; the largest difference is 3.2e-7 **W**, in `U-HX.Q`. C1 is acyclic, so its restart start is `traversal-G0-v1`. |

**Mechanism.** At the registered start, the region's linearization puts the recycle loop's inventory mode where its loop gain exceeds 1. The Jacobian is nearly singular in that mode, and the Newton step moves the inventory the wrong way by two orders of magnitude.

This comes from the heater. It is pinned at 358 K, close to the bubble point of the heavy recycle; at the root its vapour fraction β is only 0.015. Recycled heavy material suppresses the heater's vaporization, and that feeds back into more liquid. The bound is only where the wrong-signed step first becomes visible.

So a bound rule cannot fix the failure: the direction itself is wrong. A better start does fix it. One further sequential pass already puts the linearization on the right side, and every later pass up to the provider failure keeps it there.

---

## 3. Constraints and invariants

- **Target problem only (R-035).** The certificate judges the declaration the solve solved. The restart solves that same declaration with the same compiled instance. There is no λ, no modified problem and no re-binding. `verify_revision` is unchanged.
- **No registered result moves.** SYN-001, T02–T05b registered results, the identity keys `t02` … `t05b` and the structural hash `4ce030ca…` are all unchanged. Inertness holds by construction: the new code runs only under the new policy value, and no registered policy carries it (§5.8, gate G5).
- **Deterministic and recorded.** Every decision on the edge is an integer or structural decision, or a typed status of a unit evaluation, which is the same class as `traversal-G0-v1`'s own `INITIALIZATION_FAILED`. Every switch leaves an R0 record. Nothing is clipped, no tolerance moves, and no check is relaxed.
- **R-016.** The verifier shares nothing with the solver. The restart's state is never handed to the verifier; the verifier certifies `x_final` as before.
- **R-031's lesson is kept.** The restart never starts from the failed end state.
- **K03 unchanged.** §5.3, including R-064's structural-zero release, the Newton core and the phase contracts (v1 and v2) are all unchanged.
- **ADR 0010 D5 unchanged.** PTC stays experimental and is never selected automatically. `PTC_MAPPING_INVALID` is not a trigger.

---

## 4. The decision and the alternatives rejected

**Chosen: option (d), a sequential re-initialization as edge 3's second action.** Blueprint §7.4 orders initialization sources as user guesses, warm starts, local initializers, upstream propagation and physical nominals, "checking every candidate". Blueprint §7.7 authorizes "reinitialize" after an invalid trial and "try another globalization" after an EO globalization failure. When the solve from the first source fails, the restart moves to the next source, upstream propagation, carried far enough to leave the region where the registered two-pass start is wrong-signed.

It changes neither the equations nor the identity of the problem. It works for every recycle the traversal can tear, whether the loop is closed by a splitter, a separator, a flash or an exchanger. It adds one new initializer and one branch.

| Rejected | Why |
| --- | --- |
| **(a) A continuation parameter for revision flowsheets** | *Split-fraction continuation* (`r: 0 → r*`) covers only loops closed by a splitter. It misses C2's separator-top recycle, NET-03's flash-liquid loop and NET-06's thermal loop, which is not "fewest limitations". A *general tear-connection homotopy* has to cut the torn connection at λ < 1: a consumer-side copy of the torn stream, with rows that mix it with its guess. A λ-level would then no longer be a re-binding of pinned inputs with the target's `model_version`, which contradicts ADR 0010 D2 and ADR 0008 D1.2(ii)/D1.3, and it would need a new ADR on level identity. That is far more than NET-02 needs. The *global Newton homotopy* stays rejected (ADR 0010). R-030's rejected alternative "recycle-closure continuation" stays rejected; this note does not reverse it. |
| **(b) PTC mass mappings for the T05 units** | The mappings for seven unit models would be a derivation (specifier work; T05 spec §12.4 registered none). PTC is experimental and can never be selected automatically (ADR 0010 D5); reversing that needs T04 §8.4's qualification evidence. It would at best make PTC available under `eo_core = "ptc"`, and it is not an edge-3 action (R-031). |
| **(c) A bound-aware, projected or active-set Newton step in K03 §5.3** | *Measured*: the direction is wrong-signed in the inventory mode, so projecting out the blocked component drives the whole recycle to zero and ends `LINE_SEARCH_FAILED`. Changing §5.3 would also move registered K03, T02 and T03 trajectories and would need an inertness proof over every registered trace. |
| **More passes in the registered initializer itself** (make `traversal-G0-v1` longer) | It moves every registered revision trace (start, iterations, identity keys). It also does not help the ensemble, whose perturbed starts replace the initializer. |
| **Seeding the restart from the failed opening's torn values** | *Measured*: 11 of 11 are refused by the mixer's equal-pressure rule. Rescuing them would need a projection rule for the guess, which is more machinery for a start that has already failed. |
| **An adaptive pass count, e.g. passes until the tear update is below ε** | It adds a floating-point stopping decision, so the pass count would lose its R0 status. On NET-02 the tear update after 25 passes is still 0.24 mol/s (loop gain ≈ 0.95), so the loop is far from converged either way. A fixed 8 is enough (§2: every `k ≥ 3` converges) and costs 0.057 s. |
| **A ladder of restarts (passes 2, 4, 8, 16, each followed by EO)** | It means several recovery solves per step, which breaks `eo_recovery_max_count = 1` and complicates the records, for no measured need. Revisit only with a registered case that fails from `traversal-G0-pass8-v1` and converges from a longer sequence. |
| **Wegstein-accelerated passes** | Its extrapolation leaves the unit domains (negative flows, mixer admissibility) and would need its own bounding rules. Direct substitution is enough on the measured case. |
| **A separate edge 4 with its own policy field and records** | It adds a policy field, a new `opening_source` value and new event fields, which is more frozen surface. As edge 3's second action it reuses `eo_recovery`, `recovered_from`, `branch_provenance` continuity, `eo_recovery_start`, the trigger set and the count. |
| **Folding the restart into the existing value `eo_recovery = "homotopy"`** | That silently changes a registered value's meaning (ADR 0010 D1: "a later rule is a new value"). It would also move records for every revision region that ends in a trigger under a registered policy. |

---

## 5. The design

### 5.1 The policy value and what it means

`globalization.eo_recovery ∈ {"homotopy", "none", "homotopy_or_sequential_restart"}`. The default stays `"homotopy"` in `GlobalizationPolicy`.

- `"none"`: no recovery. Unchanged.
- `"homotopy"`: ADR 0010 D3 exactly. Unchanged, byte for byte, including `unsupported(no_continuation_parameter)`.
- `"homotopy_or_sequential_restart"`: edge 3's action is chosen by preconditions. It is the specification continuation when the region has a continuation parameter; otherwise it is the sequential restart when §5.2's preconditions hold; otherwise it records `unsupported(<reason>)` and the failed outcome stands. **At most one recovery region solve per region step per solve**, so `eo_recovery_max_count` stays the literal `1`. A homotopy that stalls is not followed by a restart: `HOMOTOPY_STALLED` is not a trigger.

### 5.2 Trigger and preconditions (in this order; the first that fails decides)

| # | Check | If it fails |
| --- | --- | --- |
| P0 | `policy.globalization.eo_recovery ∈ {homotopy, homotopy_or_sequential_restart}`, and the step's detail is a `RegionResult` | return the step unchanged, with nothing recorded (as today) |
| P1 | `eo_recovery_due(failed.outcome, failed.budget)`: the ADR 0010 D3 trigger set **unchanged** (`LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`, `BUDGET_EXHAUSTED(newton_iterations \| ptc_steps)`, `PTC_STALLED`, `ACTIVE_SET_CYCLING`, `ATTEMPTS_EXHAUSTED`) | as today |
| P2 | `continuation_parameter(...)` is not `None` | run the homotopy (today's code, unchanged) |
| P2′ | reached only when P2 found no parameter: `eo_recovery == "homotopy_or_sequential_restart"` | under `"homotopy"`: `unsupported(no_continuation_parameter)`, **today's return statement, unchanged** |
| P3 | `isinstance(flowsheet, RevisionFlowsheet)` | `unsupported(no_restart_initializer)` |
| P4 | `revision.restart_start(flowsheet, spec.variable_ids)` returns a `RestartStart` (§5.3) | it returned `InitialStateFailure`: record one `initializer_rejected` event with message `restart_initializer_failed: <failure.message>`, then `unsupported(restart_initializer_failed)` |
| P5 | not (`failed.branch_provenance[0]["initializer_source"] == "traversal-G0-v1"` and `restart.passes_used ≤ 2`) | `unsupported(restart_start_unchanged)`. With `passes_used ≤ 2` the restart start *is* `traversal-G0-v1`'s start: the same code on the same passes, so the opening would be the failed one. This is decided structurally, never by comparing floats. |
| — | action (§5.4) | — |

For each rejected pass in P4 (§5.3), one `initializer_rejected` event is recorded **before** P5 is decided, whatever P5 decides. The message is `restart_pass_rejected(<k>): <unit>: <code>`.

### 5.3 The restart initializer `traversal-G0-pass8-v1` (normative)

The constants are `RESTART_INITIALIZER_ID = "traversal-G0-pass8-v1"` and `RESTART_PASSES = 8`, in `orchestrator/revision.py`. A different pass count is a new initializer id, never a changed constant.

1. `p₁ = flowsheet.traverse({})`. If it fails, return `InitialStateFailure(p₁.failed_unit, p₁.code)`, exactly as `traversal_start`'s step does.
2. If `p₁.torn` is empty, the chosen pass is `p₁` and `passes_used = 1`. Go to step 5.
3. For `j = 2 … 8`: `p_j = flowsheet.traverse(p_{j−1}.computed_torn)`.
   - If `p_j` fails and `j = 2`: return `InitialStateFailure` (as `traversal_start`, including its prefix-torn check).
   - If `p_j` fails and `j ≥ 3`: stop, record the rejection `(j, p_j.failed_unit, p_j.status, p_j.code)`, and continue with `p_{j−1}`.
   - If `p_j` is `ok` but `p_j.torn ≠ p₁.torn`: raise `ValueError`. This is a defect, as in `traversal_start`.
4. The chosen pass is the last `ok` pass. `passes_used` is its index, between 2 and 8.
5. Reconstruct the start from the chosen pass with `_start_from_pass(flowsheet, variable_ids, chosen)`. That function is `traversal_start`'s steps 3–6, **extracted verbatim** (`orchestrator/revision.py` lines 144–220 at `792c594`): streams, owned variables, lifted splits (the PH closure's split, or the TP re-flash) and `band_routes`.
   - If the reconstruction refuses (`kernel_refused(<stream>)`) and `passes_used ≥ 3`: record that rejection with the same grammar, decrement `passes_used`, and reconstruct from the previous pass.
   - If it refuses at `passes_used = 2` (or 1): return `InitialStateFailure`.
6. Return `RestartStart(values, band_routes, passes_used, rejected)`.

The initializer makes no compiled residual or Jacobian call (T05 A27's clause). Like `traversal-G0-v1`, **its provider calls fall outside the region's metered window** (T05 §2.2's registered rule for initializers). Its cost is bounded by 8 traversals; for NET-02 that is 1 734 calls and 0.057 s. §9 Q7 records the alternative.

### 5.4 The action

`_region(region, restart.values, flowsheet, spec, policy, run, spent, following, RESTART_INITIALIZER_ID, band_routes=restart.band_routes, item0_opening_source="eo_recovery_start")` runs one ordinary region solve.

- It uses the policy's core and phase contract.
- §6.2's projection and pins run on the new start; this is a fresh initializer output, unlike the homotopy's already-projected item-0 opening.
- It starts from a fresh contract state (used signatures and attempt count), as the merge edge and the homotopy recovery do.
- Its attempt indices continue from `following`.
- Its property calls are metered with the plan's remaining allowance, exactly as in `_region` today.

Then, as for the homotopy recovery (the same `replace(...)` shape as `executor.py:698–719`):

- `branch_provenance = recovered_provenance(failed.branch_provenance, recovered.branch_provenance, first_initializer_source=RESTART_INITIALIZER_ID)`;
- `checkpoint = recovered.checkpoint or failed.checkpoint`;
- the step takes `outcome = recovered.outcome`, `iterations = step.iterations + recovered.iterations`, `message = recovered.message`, `detail = recovered`, `eo_recovery = "taken"` and `recovered_from = failed`.

**The outcome is the restart's.** The restart solve is never itself recovered.

### 5.5 Records (all existing fields except the flagged enum values)

| Record | Value on a restart |
| --- | --- |
| step `region_closed` event | `eo_recovery: "taken"`; or `"unsupported"` with `eo_recovery_unsupported` ∈ {`no_restart_initializer`, `restart_start_unchanged`, `restart_initializer_failed`} (new values), or `no_continuation_parameter` only under `"homotopy"` |
| `initializer_rejected` events (existing kind, recorded through the existing `_reject_initializer`) | one per truncated pass: `restart_pass_rejected(<k>): <unit>: <code>`; or one `restart_initializer_failed: <message>` (P4) |
| recovery's first `branch_provenance` item | `opening_source: "eo_recovery_start"` (existing value, read as "the recovery's opening"); `initializer_source: "traversal-G0-pass8-v1"` (a free string in the schema); `core` the policy's (`newton`); `continuation: null` |
| `AttemptContext` | `core` = the policy's core; `continuation: null` |
| `Checkpoint` | the recovery's; `continuation_lambda: null` |
| certificate | unchanged rules; `branch_provenance` carries both solves' items densely |
| `homotopy_step` events | none |

**R0 classes (ADR 0007).** R0: the new `eo_recovery` value, the three reasons, the initializer id, `passes_used` (it is implied by the rejection events), and the rejection messages' pass index and unit. As with `traversal-G0-v1`'s refusals, the decision that a pass failed is the unit's typed status, which is conditionally R0 under D2.4 like every outcome word.

### 5.6 Seams and signatures (additive; nothing frozen except §0's flag)

```python
# orchestrator/trace.py
class GlobalizationPolicy:
    eo_recovery: Literal["homotopy", "none", "homotopy_or_sequential_restart"] = "homotopy"
EoRecoveryUnsupported = Literal["no_continuation_parameter", "no_restart_initializer",
                                "restart_start_unchanged", "restart_initializer_failed"]
# SolveEvent.eo_recovery_unsupported, StepResult.eo_recovery_unsupported and
# executor._bracket(eo_recovery_unsupported=...) take EoRecoveryUnsupported | None.

# orchestrator/revision.py
RESTART_INITIALIZER_ID: Final = "traversal-G0-pass8-v1"
RESTART_PASSES: Final = 8

@dataclass(frozen=True)
class RestartStart:
    values: dict[str, float]                 # over variable_ids, in their order
    band_routes: tuple[str, ...]
    passes_used: int                         # 1 (nothing torn) or 2..RESTART_PASSES
    rejected: tuple[tuple[int, str, str, str], ...]   # (pass, unit, status, code), in order

def _start_from_pass(flowsheet, variable_ids, traversed) -> TraversalStart | InitialStateFailure
def restart_start(flowsheet: RevisionFlowsheet, variable_ids: Sequence[str]
                  ) -> RestartStart | InitialStateFailure
# traversal_start(...) becomes passes 1-2 + _start_from_pass(...), with output bit-identical (G5c).

# orchestrator/region.py — solve_region(...) gains a keyword-only argument:
item0_opening_source: Literal["initializer", "eo_recovery_start"] = "initializer"
# Used for item 0 iff recovery is None. The homotopy recovery keeps "eo_recovery_start" as today.

# orchestrator/executor.py — _region(...) passes item0_opening_source through (default unchanged);
# _eo_recovery(...) gains the P2' to P5 branch as a helper _sequential_restart(...).

# orchestrator/recovery.py
def recovered_provenance(failed, recovery, *, first_initializer_source: str | None = None)
# None: today's check (== failed item 0's source). Given: the recovery's first item must name it.
```

The T06 policy is defined **once**, in the T06 support module that both the tests and the ensemble runner import (the pattern of `POLICY_V2` in `tests/t05b_support.py`):

```python
T06_REVISION_POLICY = replace(POLICY_V2, policy_id="T06-revision-v1",
    globalization=replace(POLICY_V2.globalization, eo_recovery="homotopy_or_sequential_restart"))
```

### 5.7 Cost (blueprint §7.7's "estimated cost")

At most 8 traversal passes plus one region solve, whose own budget is `max_attempts × max_iterations_per_attempt` iterations and the plan's remaining property calls. On NET-02 the passes take 0.057 s and 1 734 unmetered provider calls, and the restart solve takes 4 iterations and 0.23 s including verification. That is well inside T06 §7.5's 60 s ceiling.

### 5.8 Why nothing registered moves (the inertness argument)

The only behavioural change is behind `eo_recovery == "homotopy_or_sequential_restart"`. Every registered policy has `"homotopy"` or `"none"`: `GlobalizationPolicy`'s default is unchanged, and no registered case, fixture or script sets the new value. Under `"homotopy"`, `_eo_recovery` executes today's statements in today's order.

Two refactors touch registered paths:
- `traversal_start`'s extraction into `_start_from_pass` is a pure move of code (proved in G5c);
- `solve_region`'s new keyword has a default equal to today's constant (proved in G5a).

`as_document()` of every registered policy is byte-identical, because the new value never appears. Schema fixtures regenerate byte-identically (R-015).

---

## 6. T06 registration consequences (applied by the build lane, reviewed by the design lane)

1. **Spec §6.6.** Change "the revision path under `T05b-v2`" to "the revision path under **`T06-revision-v1`** (`T05b-v2` with `globalization.eo_recovery = homotopy_or_sequential_restart`; this note, ADR 0015)". Record its canonical document hash in the campaign manifest. The tear path and NET-05 keep their registered policies, because the restart is unavailable on a legacy flowsheet. This amendment is made before any ensemble solve is seen, as §6.6 requires.
2. **NET-02 (spec §3.2, registry).** The expectation `verified_at_reference` is registered **under `T06-revision-v1`**: `CONVERGED` through edge 3's restart (item 0 `BOUND_BLOCKED`, item 1 `eo_recovery_start` / `traversal-G0-pass8-v1`), certificate `VERIFIED`, and the state within T02 §6.4's allowances of the twin root. The **control** under `T05b-v2` and `T05-W13` is registered as `BOUND_BLOCKED` with `unsupported(no_continuation_parameter)`, which is today's measured result. R-074 is closed by R-075 (Appendix B).
3. **Spec §10 (`t06` key).** The key keeps its definition and gains one entry, NET-02 under `T06-revision-v1`. NET-02's `T05b-v2` entry stays `BOUND_BLOCKED` and does not move. The ensemble definition in the key names each path's policy id.
4. **Spec §2 and M1 are unchanged.** M1's expected pilot (NET-02 `BOUND_BLOCKED` under both registered contracts) stays true.

---

## 7. Work orders (in dependency order; each is one commit naming T06)

| WO | What | Acceptance |
| --- | --- | --- |
| **WO1** *(flagged, isolated commit)* | Widen the two schema enums and the Python `Literal`s (§5.6, trace-level only); update the schema descriptions, `schemas/README.md` and `docs/interfaces-frozen.md` §2 (a T06 / ADR 0015 entry); add ADR 0015 as **Proposed** (Appendix A) and R-075 plus its index line (Appendix B) | Every committed schema fixture regenerates **byte-identically** with its generator; every fixture validates; `as_document()` of every registered policy is unchanged (hash list before and after); full gate green |
| **WO2** | `revision.py`: extract `_start_from_pass`; `traversal_start` calls it; no other change | G5c: `traversal_start`'s output (values dict and `band_routes`) is bit-identical, compared by SHA-256 over canonical JSON, for C1, C2, C3, C3X (its failure message), every T05b revision case and every T06 revision case available; full gate green |
| **WO3** | `revision.restart_start`, `RestartStart` and the constants (§5.3) | Unit tests. **C1** (acyclic): `passes_used = 1` and values equal `traversal_start`'s. **C2**: `passes_used = 8`, no rejection. **C3**: `passes_used = 3`, with one rejection `(4, "U-MIX", "not_converged", …)` (*measured*). **NET-02**: `passes_used = 8`. **C3X**: `InitialStateFailure` whose message equals `traversal_start`'s. A spy provider or problem shows no compiled residual or Jacobian call. |
| **WO4** | `solve_region(item0_opening_source=...)` and `_region`'s pass-through; `recovered_provenance(first_initializer_source=...)` | G5a: every registered region trace is unchanged (the event stream's R0 projection plus a hex dump of the provenance items, T04's `0b4ceb4` precedent); full gate green |
| **WO5** | `executor._eo_recovery`'s P0–P5 and `_sequential_restart` (§5.2, §5.4, §5.5) | G1, G2, G3, G4-legacy (§8) pass; G5a and G5b pass |
| **WO6** | `T06_REVISION_POLICY` in the T06 support module; NET-02's registry entries and spec amendments (§6) | A test asserts the policy differs from `POLICY_V2` in exactly `policy_id` and `globalization.eo_recovery` (the pattern of `test_t05b_review_s3._v2`); G1 runs on the committed `benchmarks/t06/cases/` NET-02 file |
| **WO7** | G6: the restart start converges for every registered cyclic revision case | A parametrized test over C2, C3, STA-02, NET-02, NET-03, NET-06, NET-09, NET-10, NET-11, REF cases with a tear, and T05b's cyclic cases. **A failure is a stop-and-report to the design lane.** Do not tune `RESTART_PASSES` against it. |
| **WO8** | G7: the independent-perturbation regression (prefix `F4-probe-v1`, **never** the gate's prefix) | NET-02 20 of 20 `VERIFIED` at the root under `T06-revision-v1`. The split between first-solve and restart successes is recorded, not gated (the probe measured 9 and 11); the committed file's ordering may shift it. |
| **WO9** | The full ensemble re-run (plan §6.5; T06 phase R) under the amended §6.6 | T06 §7.3's gate, with rescued starts reported per case (§9 Q3) |

---

## 8. Verification gates

| Gate | Invariant | Measured how | Tolerance and configurations |
| --- | --- | --- | --- |
| **G1** | NET-02 is solved and certified | `bind → plan_revision → execute_plan → verify_revision` under `T06-revision-v1`, and under a `T05-W13`-based twin with the new value (a contract-independence check) | `CONVERGED`; `VERIFIED` under `K04-check-policy-v1`; every registered coordinate within T02 §6.4's allowances (flows 3.1e-7 mol/s, T 1e-5 K, P 0.1 Pa, duty 1e-2 W). *Probe*: 5.4e-9, 1.0e-9 K and 1.6e-5 W. Records: `eo_recovery = taken`; items are `[initializer / traversal-G0-v1 / BOUND_BLOCKED, eo_recovery_start / traversal-G0-pass8-v1 / CONVERGED]`; no `homotopy_step`; no `initializer_rejected`. Iteration counts are recorded, not gated. |
| **G2** | Edge-off control unchanged | NET-02 under `T05b-v2` and `T05-W13` | `BOUND_BLOCKED` with `unsupported(no_continuation_parameter)`; trace byte-identical before and after WO1–WO5 |
| **G3** | P5 fires on an acyclic registered start | SC-1, SC-2 and SC-3 under `T05-W13` with the new value | Each case's outcome is its registered `T05-W13` outcome (T06 §2 measured `ACTIVE_SET_CYCLING` for all three). Where that outcome is a trigger, `unsupported(restart_start_unchanged)`; where it is not, nothing is recorded. The trace is otherwise identical to `T05-W13`'s except the policy record. |
| **G4-legacy** | P3 | T04's HOM-U (`test_a09_hom_u…`) with the new value | `unsupported(no_restart_initializer)`; the outcome `BUDGET_EXHAUSTED(newton_iterations)` stands |
| **G5a/b/c** | Inertness | (a) the full test suite; (b) `scripts/k05_structural_identity.py` keys `t02` … `t05b` and the structural hash `4ce030ca…`, plus every committed identity document; (c) WO2's bit-identity of `traversal_start` | Byte-identical, with no exceptions. A changed digit is a defect in the change. |
| **G6** | The restart initializer is sound on the registered corpus | WO7 | Every cyclic case is `CONVERGED` from `traversal-G0-pass8-v1`, and its state is within T02 §6.4's allowances of the registered root |
| **G7** | Rescue of perturbed starts (design evidence, not the gate) | WO8 | 20 of 20 |
| **G8** | T06's gate | WO9 | `S ≥ 418` of 440, with no unexplained `F-OTHER-ROOT` and no `F-CRASH`, on both machine classes (T06 §7.3, unchanged) |

---

## 9. Risks and open questions (each with a recommended default)

| # | Question | Kind | Default |
| --- | --- | --- | --- |
| Q1 | Approve §0's two additive enum widenings (a frozen-interface change)? | **Preference (Frank)** | Yes. Implement as the isolated WO1 and do not merge T06 until approved. If declined, revert WO1 and use §10. |
| Q2 | Should the product default policy (T07's application layer) enable `homotopy_or_sequential_restart`? | **Preference (Frank)** | Yes, following his robustness steer. In v0.1 it is enabled only in `T06-revision-v1`; flipping `GlobalizationPolicy`'s *Python default* would move registered policy documents, so it must not be done. |
| Q3 | Does a start rescued by re-initialization count as a success for V20's robustness gate? The rescued start's outcome is independent of the perturbation, so within a case rescued successes are perfectly correlated. | **Preference (Frank)** | Yes, per his standing directive that recorded fallbacks count. The T06 report shows, per case, successes from the first solve and successes through the restart, so Newton's own basin stays visible. The report says in words that a restart discards the start. |
| Q4 | Does `traversal-G0-pass8-v1` converge on every registered cyclic revision case (G6)? | **Fact** | Expected yes: C2, C3 and NET-02 are measured. If not, stop and report. Do not change the pass count on the build lane's initiative. |
| Q5 | Should `LINEAR_SOLVE_FAILED` also trigger the restart? A singular Jacobian at a degenerate perturbed start may be a start problem, not a rank problem. | **Fact** (the ensemble would show it) | No. Keep ADR 0010 D3's trigger set, following blueprint §7.7's rank row. Revisit only if the ensemble shows perturbed revision starts ending `LINEAR_SOLVE_FAILED` that the restart start solves. |
| Q6 | **New finding.** `Syn001Provider`'s Rachford–Rice iteration inside `U-MIX`'s liquid enthalpy fails to converge ("did not reach 1e-14 in 200 iterations") at states the traversal reaches: C3 at pass 4, NET-02 at pass 29. This is a typed `not_converged` on a mixer outlet close to its bubble point. It may also reject Newton trials in the ensemble through the compiled `H_*_liquid` blocks. | **Fact** (a provider defect needs its own diagnosis) | Record it as T06 finding F6, owned by the build lane with a design-lane review. It does not block F4, because §5.3's truncation absorbs it. Reproduction: C3's traversal from dormant tears, pass 4. |
| Q7 | Should the restart's traversal passes be metered against `max_property_calls`? | **Preference** (budget semantics) | No: unmetered, like `traversal-G0-v1` (T05 §2.2's registered rule for initializers), and bounded by 8 passes. The alternative, metering them, needs a budget-refusal branch inside the edge. |
| Q8 | Should the restart also run after a `HOMOTOPY_STALLED` homotopy on a region with a continuation parameter? | **Preference / scope** | No. The count stays 1, and there are no such regions on revision flowsheets in v0.1. It is a new decision if T07 adds specification regions. |
| Q9 | Should `RESTART_PASSES = 8` be a policy constant? | **Preference** | No. It is part of the initializer's id, so a change is a new id and nothing silently changes. |
| Risk | A flowsheet whose sequential map diverges (tear gain above 1) gains nothing from the restart: its passes wander and its failure stands, recorded. | — | This is accepted: the edge is recorded and bounded. Such a case would argue for (a) or for PTC later, with evidence. |

---

## 10. The variant if the schema widening is declined

In this variant **no schema changes.**

- The switch moves to `SolvePolicy.initializer_chain`. That is an existing free-string array, "the §10.1 source order by id" (K03 §12.1), which the solver does not read today.
- A policy whose chain is `("user_guess", "traversal-G0-v1", "traversal-G0-pass8-v1")` enables the restart; every registered policy has `()`.
- `eo_recovery` stays `"homotopy"`. The unsupported reasons collapse to the existing `no_continuation_parameter`, and the restart's rejections are recorded only as `initializer_rejected` events.
- Everything else in §5 is unchanged.

The cost is coarser records: a reader cannot tell, from `eo_recovery_unsupported` alone, "no parameter" from "the restart would reopen the same start". Edge 3's action set also then depends on a second field. That is why this is the fallback and not the choice.

---

## Appendix A — ADR 0015 (draft; status Proposed; the build lane commits it as the design lane's text)

**Title.** Recovery edge 3, second action: sequential re-initialization of a revision-built region.
**Date.** 2026-09-26. **Author.** Design lane (`architect`), T06 F4.
**Affected requirements.** D01 (recovery edges named by the policy), V20 (robustness), D20 and blueprint §8.3 R0 (new values classified).
**Affected packages.** T06 (the ensemble's revision policy, NET-02's registration), T02 (executor), T04 (edge 3's action set, which ADR 0010 D1, D3 and D7 extend additively), T05 (`revision.py`'s initializer), T07 (the application default, Q2).
**Blueprint authority.** §7.4 (initializer order, checking every candidate), §7.7 (EO globalization failure: another globalization; invalid trial: reinitialize; every fallback edge states a trigger, preconditions, a count, a cost, a checkpoint policy and an outcome).

**Context.** NET-02 ends `BOUND_BLOCKED` at iteration 1 from `traversal-G0-v1`, and edge 3 has no continuation parameter on a revision region. The measured cause is a wrong-signed Newton step in the recycle's inventory mode at the two-pass start (`cond Ĵ = 2.4e4`; `ΔS3.L = −568` mol/s, while the root's recycle `ΣS6` is 33 mol/s above the start's). One more sequential pass fixes the sign, and every start from 3 to 28 passes converges (design note §2).

**Decision.**
- **D1.** `globalization.eo_recovery` gains the value `homotopy_or_sequential_restart`, and the default stays `homotopy`. Under the new value, edge 3's action is the specification continuation if the region has a continuation parameter; else the sequential restart if the flowsheet is revision-built, its restart initializer builds, and the restart start is not the failed item 0's start by construction; else `unsupported(<reason>)`. The trigger set and `eo_recovery_max_count = 1` are unchanged.
- **D2.** The restart initializer `traversal-G0-pass8-v1` is the traversal from dormant tears continued to 8 passes. A failing pass `j ≥ 3` truncates the sequence to pass `j − 1` and is recorded. Passes 1–2 must succeed, as `traversal-G0-v1`'s do. Like every initializer, it is unmetered (T05 §2.2).
- **D3.** The action is one region solve from the restart start. It gets §6.2's projection, the policy's core and contract, and a fresh contract state. Its first item has `opening_source = eo_recovery_start` and `initializer_source = traversal-G0-pass8-v1`, and its items continue the failed solve's provenance densely. The outcome is the restart's, and the certificate judges the target declaration (R-035).
- **D4.** `solve-event`'s `eo_recovery_unsupported` gains `no_restart_initializer`, `restart_start_unchanged` and `restart_initializer_failed`. Each is R0.

**Rejected alternatives.**
- Split-fraction or tear-connection continuation: its coverage is limited, or its level identity contradicts ADR 0010 D2 and ADR 0008 D1.
- PTC mappings for T05 units: experimental, with derivations not done (D5 stands).
- A projected or bound-aware Newton step: measured to collapse the recycle, and it would move K03 trajectories.
- A longer registered initializer: it moves every registered trace.
- Seeding from the failed opening's torn values: measured to be refused by the mixer's pressure rule in 11 of 11 cases.
- An adaptive pass count: its decision is a float and it is unneeded.
- A restart ladder: more than one recovery per step.
- Folding the restart into `homotopy`: a silent change of a registered value's meaning.

**Consequences.**
- Two additive schema enum widenings, with fixtures regenerated identically. **This needs Frank's approval** (frozen interfaces).
- The T06 ensemble's revision path runs `T06-revision-v1`.
- NET-02 is registered `VERIFIED` under it, with `BOUND_BLOCKED` as the edge-off control.
- Every existing policy, trace and identity key is unchanged.

**Acceptance evidence.** The design note's G1–G7. T06's manifest lists them; G8 is T06's gate.

## Appendix B — register entry R-075 (draft)

**R-075 — A revision-built region that fails its EO globalization is re-initialized once, from the traversal continued to 8 passes (edge 3's second action).**
Date 2026-09-26. Decided by the design lane (`architect`, T06 F4); ADR 0015 (Proposed). Normative text: `docs/design/T06-F4-recovery.md` §5. Evidence: §2 (*measured* probes). Affects T06, T02, T04 and T05; T07 through Q2.

**Decision.** This is D1–D4 above. NET-02 is `VERIFIED` under `T06-revision-v1`, and R-074 is closed.

**Rejected alternatives, and why.** Those listed in ADR 0015.

**Watch for:**
- `RESTART_PASSES` changed without a new initializer id;
- the restart made the default of `GlobalizationPolicy` (it would move registered policy documents);
- the restart seeded from a failed state;
- the pass count tuned on the gate's own starts.

## Appendix C — how the probes were run (reproduction recipe; not committed)

1. **NET-02.** Build it with `tests/t05b_support.revision("NET02", …)`:
   - units C3's `U-MIX`, C1's `U-HEAT`, C1's `U-PHF` and C3's `U-SPLIT`, with `split_fraction = 0.95`;
   - `Source("S1", "U-MIX", "inlet", "liquid", (1, 1, 1), 300, 1e5)`;
   - links S6 `U-SPLIT.recycle → U-MIX.inlet` (L), S2 `U-MIX → U-HEAT` (L), S3 `U-HEAT → U-PHF` (VL) and S5 `U-PHF.liquid → U-SPLIT` (L);
   - products S4 `U-PHF.vapor` (V) and S7 `U-SPLIT.purge` (L);
   - pins `connection_pin("SPEC-heater-outlet-T", "S3", "state.T", 358)` and `duty_pin("SPEC-phf-Q", "U-PHF", 20000)`.

   Solve it with `test_t05b_contract.solve(document, POLICY_V2 | POLICY_V1)`.
2. **k-pass starts.** Wrap the flowsheet so that `traverse({})` returns pass `k − 1`, then call `revision.traversal_start`. Solve with `t05b_support.solve_from_v2`.
3. **Jacobian and SVD.** Capture `(problem, x0)` from `region.solve_newton`, then form `Ĵ = S_F⁻¹ J S_x` with `newton._scale_matrix`.
4. **Projected step.** Wrap `newton._bound_aware_step` so that, at `α_max = 0`, it zeroes the blocked components and recomputes `α_max`.
5. **Restart.** Wrap `executor._eo_recovery`: when it returns `unsupported` on a `RevisionFlowsheet`, build the 8-pass start (with truncation) and call `executor._region` with `initializer_source = "traversal-G0-v1+8"`.
6. **Perturbations.** Apply T06 §6.3's draw with prefix `F4-probe-v1` over every unpinned stream coordinate and `U-HEAT.Q`, using §6.4's box domain. Recompute the heater's split with `tp_state` and `U-PHF`'s product totals as sums. Inject the start by replacing `revision.traversal_start` for the first call.
