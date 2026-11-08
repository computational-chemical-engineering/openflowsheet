# Revision continuation (`RRC-revision-v1`)

`RRC-revision-v1` is a solve policy, offered by explicit id like `T08-warm-v1`. It is
`T06-revision-v2` with one change: when an equation-oriented revision solve ends in a state
that edge 3 of the recovery order handles, a third recovery is tried between the existing two. It
is never the default, and no registered policy carries it, so no existing solve changes.

## What it does

A revision solve that fails on a large edit may succeed if the edit is applied in steps. Under
this policy, after a failed first attempt, the solve looks for the **nearest ancestor revision
that has a `VERIFIED` solve**. It then moves the changed operating values from the ancestor's
values to the target's values in fractions of the way (the λ levels), starting from the
ancestor's certified root. The first level is the ancestor's own certified problem, bit for bit.

The action order for one failed step is:

1. continuation in a promoted specification (ADR 0010, unchanged);
2. **revision continuation** (this policy; ADR 0072);
3. the sequential restart (ADR 0015, unchanged).

There is **one recovery solve per step**, shared by all three. A step does not retry.

## When it applies

It applies only if every difference between the ancestor's revision document and the target's is
a **value change of a registered operating specification**:

- the value, unit or meaning of a pinned state, outlet or duty specification (`state.n`,
  `state.T`, `state.P`, `outlet.T`, `outlet.P`, `duty.Q`);
- the value, unit or meaning of a registered operating parameter, for example a splitter's
  `split_fraction`, `pressure_drop`, `efficiency`, or a column's `condenser_reflux_ratio` and
  `reboiler_boilup_ratio`.

Anything else has no continuation: a connection edit, an added or removed item, a changed model,
role or target, a discrete or model-constant parameter (`stage_count`, `feed_stage`, `nu`,
`damkohler`, `T_ref`, `T_scale`, `coolant_cp`), and a first solve with no verified ancestor. The
continuation never changes the active set and follows no folds (limitations L20 and L24).
The edge is available on revision solves only, and the application looks for an ancestor only
under this policy, on a run and never on a rerun.

## How a refusal is recorded

If any precondition fails (no verified ancestor, a difference that is not continuable, an
identity or opening check, a rejected opening), the reason is recorded and the solve
**falls through to the sequential restart unchanged**. The record is:

- one `initializer_rejected` trace event with the message `revision_continuation_<status>:
  <reason>`, before the restart's events;
- the `revision_continuation` member of `solve-path.json`, with `status` one of `absent`,
  `rejected`, `not_reached` (the ancestor was assembled but edge 3 never consulted it) or
  `taken`, and the `reason`. It is written whenever the policy is used on a revision solve,
  whether or not edge 3 fired.

When the action is taken, the trace carries the ordinary `homotopy_step` events, the certificate's
first recovery provenance item records the continuation (`type: revision_continuation`, the
continued parameters, the λ levels reached and the rejected trials), and verification is
unchanged: a converged result is `VERIFIED` by the same independent verifier.

## Replay

A replay bundle replays alone. `replay --rerun` takes the recorded `revision_continuation`
member: it does no store lookup and no binding of the ancestor. It rebuilds the candidate from
the recorded source parameters, identity, signature and state, repeats the integrity and
continuability checks, and runs the solve. The rerun's member must equal the recorded one under
its R0 projection; otherwise that is a replay difference. A bundle without the member replays as before.

## Measured cases

Both cases are regression references (self-generated, with independent checks named), taken on
Linux x86-64 and recorded in `benchmarks/rrc/results-ref-x86-64.md`. In each, the control is
the same policy with edge 3 switched off.

| Case | Edit | Control | `RRC-revision-v1` | Independent check |
| --- | --- | --- | --- | --- |
| N1 (NET-02) | recycle splitter `split_fraction`, source 0.5, target NET-02's registered value | `BOUND_BLOCKED` after 1 iteration | `CONVERGED`, `VERIFIED`, edge taken; 12 iterations; λ levels 1/4, 3/4, 1 accepted, 0 rejected | closed-form worst ratio 0.0109 (limit 1); restart root 1.96e-9 scaled (limit 1e-8) |
| C3 (M1-recycle column) | recycle `split_fraction` 0.2 → 0.9 | `BOUND_BLOCKED` after 4 iterations | `CONVERGED`, `VERIFIED`, edge taken; 22 iterations; 0 rejected | A29 closure 2.73e-10 (limit 1); restart root 7.8e-15 scaled |

Under `T06-revision-v2` the same two targets also converge (5 and 8 iterations) by the existing
recoveries; the policy is not claimed to be faster. The measured recovery cost was 0.12 to 0.63 s per
case, with at most 0.051 s to compile each level. Of the six other non-forced candidates, three
(N2, N3, C4) qualify and three (C1, C2, C5) converge first under every policy, so the edge is
never reached.

## Declared limitations

- **L21.** Edge 3's continuation exists for a region with a promoted specification
  (specification continuation). Under `RRC-revision-v1` it also exists for a revision region whose
  nearest verified ancestor has the same declaration and differs only in registered operating
  values. Everywhere else edge 3 is the sequential restart or `unsupported(…)`. Neither
  continuation changes the active set. `RRC-revision-v1` is not a superset of
  `T06-revision-v2`: a continuation that stops part-way ends the step and the restart is not
  tried (one recovery per step), so it can fail where `T06-revision-v2` converges, and no
  registered case is rescued by it that `T06-revision-v2` does not rescue.
- **Not a superset of `T06-revision-v2`.** On every measured case where this policy's
  continuation converged, `T06-revision-v2`'s sequential restart converged as well, in fewer
  iterations. A continuation that stops part-way ends the step, and the restart is not tried (one
  recovery per step). This policy can therefore fail where `T06-revision-v2` converges. No
  registered case is rescued by it that `T06-revision-v2` does not rescue.
- **L-COL-9.** In a flowsheet a column region has edge-3 continuation only under
  `RRC-revision-v1`, from a verified ancestor that differs only in operating values. A first
  solve, a structural edit (stage count, feed stage, a changed end-specification choice) and the
  default policy have none. The unit's own `evaluate` keeps the standalone path.
- The nearest verified ancestor wins; no further ancestor is searched.
- A column with a pinned (non-two-phase) source signature has not been measured: no registered
  case has one.
- The evidence is two registered pairs on one architecture; the aarch64 pairs and the numerical
  review are pending.
