# Brief — T08 build-first specification, Amendment 1: six questions from the build

**To:** `specifier` (design lane). **From:** build lane, 2026-09-29. **Branch:** `wp/T08`.
**Deliverable:** an **Amendment 1** section appended to `docs/derivations/T08-build-first-spec.md` (plus the
edits it names in other authority documents, listed per question below), with the generator
`docs/derivations/scripts/t08_build_first_reference.py` and `benchmarks/t08/build_first_reference.yaml`
updated so `--check` passes and the YAML is byte-reproducible. Register entry text for the amendment. Do not
commit; write no production code or tests.

**Budget.** Frank is near his weekly usage limit. These are six bounded rulings; answer each with the
decision, the rejected alternative, and the exact amended text — no re-derivation of what the spec already
establishes.

**Timing constraint (preregistration).** `C_reg` = `9f5f29d` is committed. `C_case` (W3) is **not** yet
committed, and **no PTC-R1 result exists** (W2 ran only row/Jacobian evaluations at the three roots and single
steps at three off-grid states, per §A4.6). Your amendment lands before `C_case`, so it may still change the
case definition — say so explicitly in the amendment and keep §A4.6's git-order argument intact.

## Q1 — PTC-R1 on `[A, B]` cannot be bound (blocks W3)

`canonical_components` (`src/process_runtime/models/revision_flowsheet.py:221–240`; ADR 0014 D9, R-076)
refuses any component set that is not a permutation of `(A, B, C)`; the SYN-001 flash is written for three
components (`src/process_runtime/thermo/syn001.py:218–241`), and R-007 admission needs it. §A1.5 specifies
components `[A, B]`; §A4.2 says "If the binding has a variable §A1.5 does not name, stop and escalate" — this
is that escalation.

W2 (committed, `e924d13`…`7467d52`) tests the model with `C` carried at exactly zero. Measured: the PTC-R1
dynamics on (A, B, T, P, Q) are unchanged; single PTC/Newton steps at the three off-grid states agree with the
YAML to 1.06e-13 relative; `M` against `mass_nonzeros_theta_1s` 2.2e-16. With C present: B13's mapped row set
gains `CSTR-mole:C`; B14's pencil gains a second finite eigenvalue `−1/θ` (the C mode, decoupled).

Engineer's proposal: amend §A1.5/§A2/§A4.2 to components `(A, B, C)` with `C = 0` in the feed and in every start
(`S1.n.C = S2.n.C = 0.0`); B13 and B14 as measured. Rule on it (or an alternative), and check what else C = 0
touches: the dew-point margin of §A1.5, the saddle-clause separatrix distance, the starts' sha256
(`b77df2fe…`), B04's total-moles mode, R-007 admission at zero C, and any zero-flow semantics (ADR 0001) of a
component at exactly zero.

## Q2 — B17 on the EO rows

B17 expects typed `out_of_domain` with `temperature_outside_domain(outlet)` from both the EO rows and
`evaluate`. The compiled residual's only non-`ok` status for a state outside the domain is
`invalid_trial_state`; the frozen `evaluation-result` schema has no `out_of_domain`. Message seen:
`H_S2_vapor: H_S2_vapor: temperature 441.0 K outside [280.0, 440.0] K` (the doubled prefix is pre-existing in
`casadi_backend`/`blocks.py`). No inf/nan. The evaluator does give `out_of_domain` +
`temperature_outside_domain(outlet)`. Proposal: amend B17 accordingly. Also say whether the doubled prefix is a
defect to fix (build lane) or to record.

## Stop 1 — the V17 T10 oracle pins the offered policies (tests red)

`docs/derivations/T07-v17-tasks-spec.md` T10 oracle (≈ line 746):
> **T10-C3** `answer.offered_policy_ids` is an array whose elements, as a set, equal `{"T04-W12", "T06-revision-v2"}`.

The same set is `OFFERED_POLICIES` in `docs/derivations/scripts/t07_reference.py:97`. Offering `T08-warm-v1`
(W4, `3097858`) — and later `T08-ptc-v1` — makes G16-b's T10 reference run fail on four transports (36/40), and
the response fixture `tests/fixtures/application_results/project_summary/valid/two_revisions_one_job.json` pins
`solve_policies`. §B3 treated the `get_project` addition as content-only and missed this pin.

**Frank ruled F5 (2026-09-29):** one more model in `list_models` and two more policies in `get_project` —
content-only, no schema/description/tool change — keep V17's carry. Options: (a) amend T10-C3 and
`OFFERED_POLICIES` to the new offered set (define it: `{T04-W12, T06-revision-v2, T08-ptc-v1, T08-warm-v1}`?)
under F5, as a T07 V17-spec amendment that does not re-score `v17-c2` (its runs answered on the old surface and
were scored against the oracle then in force); (b) an admissible but unlisted policy (a new contract decision);
(c) other. Rule, and write the amendment text for the T07 V17 spec (append an amendment there, don't rewrite
history) and for §B3/B50/T08.A49. Say how the carried V17 verdict states this.

## Q-W4-1 — B41's "opening digest equals the candidate's"

§B2 lets the candidate enter where `user_start` enters. T05b §6.2 (`region.py`, `current.update(kernel)`) then
overwrites every lifted split of x0 with the kernel's values (recording only differences > 1e-12), so the flash
split (S4/S5 columns) opens ≈ 3e-16 relative from the candidate; measured first `attempt_opened` digest
`6533737e…` vs the candidate's `a4ad95ae…` over 43 free columns. Options: amend B41 to compare after §6.2 (the
opening equals the §6.2 projection of the candidate), or change §6.2 for this source (a numerics change on the
registered path). Rule.

## Q-W4-2 — B42's `plan_id` clause

`plan_id = f"{label}-{policy.policy_id}-execution"` (`src/process_runtime/orchestrator/execution.py:776`), so
warm and cold runs differ by construction. Proposal: "equal modulo the policy id", or name the plan structure.
Rule.

## Q-P1-1 — the initializer failure bundle's empty `replay_identity`

Phase 1 fixed D2 (bundles and certificates now carry plan/policy/revision ids; `t07` key unmoved). The
**initializer** failure bundle still has an empty `replay_identity`: T07 ruling round 3 Q1 item 3's table
(`docs/design/T07-jobs-and-bindings.md`, ruling rounds at the end) registers it that way, and
`tests/test_t07_w3f_initializer_bundle.py` pins it with digests `e07f19c5…`, `6eeb7757…`. T08 release spec
rule 5 ("an empty string reads as a value") argues for filling it — a one-line change (pass `plan=` in
`solve_route`). Engineer's default: amend the table and fill it. Rule; if filling, write the amendment to the
T07 ruling table and state the identity consequence (the R0 projection keeps neither field, per the Phase 1
proof, so no identity key should move — confirm from the projection rule, `src/process_runtime/run/identity.py`).

## Already decided (not open)

Frank 2026-09-29: F1/F2 build first; F3 ammonia; F4 substitution-only identity moves; F5 carry V17 for
content-only additions; Q-A1 one synthetic reaction; Q-A2 V14 (b) on each platform; Q-B1 request-named warm
start in v0.2; **Q-P1-2: D1's instance-id rule extends to STR-04 and STR-05 messages** (build lane
implements; the pinned `tests/fixtures/t07/cli-existing-commands.json` moves by that substitution only).

## Out of scope

Anything not in these six questions; the reviewer's work; the ammonia case.
