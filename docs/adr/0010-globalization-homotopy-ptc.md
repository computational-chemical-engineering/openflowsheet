# ADR 0010 — Globalization: the typed specification continuation, recovery edge 3, and the residence-time PTC family (experimental)

**Status:** Accepted 2026-09-24 — T04's manifest `evidence/T04/53cd23b29d3701e3a464fa1edaa455a9a1d6fbf5/manifest.json` is `tested` (34 of 34 checks, A00–A33; A26 and A29 measured on the CI pair, run 36063188633), after the design-lane review `docs/reviews/T04-review.md` and its fixes. The PTC family stays `experimental` and V14's "qualified PTC" clause incomplete (D5; T04 §16 F1, default). Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-24  
**Author:** design lane (`specifier`); plan §1.3 assigns every ADR, the globalization policy and the PTC mapping to the design lane  
**Normative text:** `docs/derivations/T04-globalization-spec.md` §4–§10 (§4.8 for D9); machine-readable expectations `benchmarks/t04/reference_values.yaml` from `docs/derivations/scripts/t04_reference.py`  
**Affected requirements:** D01 (explicit globalization cores and a recovery edge the policy names), D07 (PTC mapping, equivalence, qualification — **qualification not achieved; the family is experimental**), A03 (SER: accepted-step ratio, reject shrink, reset, endpoint), V14 (homotopy and three bounded recovery edges delivered; the *qualified PTC* clause recorded incomplete), D09 (the contract's rows 4–5 extended by the PTC core's failure-to-advance outcome), D11 (continuation history on `branch_provenance`), D20 and blueprint §8.3 R0 (every new field classified)  
**Affected packages:** T04 (implements everything below); K03 (`SolvePolicy`, `SolveEvent`, `AttemptContext`, `Checkpoint` field sets; K03 §12.4's one-context rule, amended for homotopy attempts); T03 (the decision function's rows 4–5 and the wall observer's stall list; tests whose subject is the contract pin `eo_recovery: none`); T02 (the plan executor runs edge 3 after a region solve); K04 (the `branch_provenance` item; refuses a λ < 1 checkpoint; D9: certifies a bound declaration behind an identity guard, `transformations.declaration`); K05 (replay refuses a policy without `globalization`; the identity script includes the new R0 fields); T06, T07 (read the new outcomes)  
**Blueprint authority:** §7.4 (typed homotopy: `H(x, λ)`, easy endpoint, `H(x, 1) = F(x)` including all original specifications, path domain, scales, endpoint mapping, rollback checkpoints, λ < 1 never target-certified, `HOMOTOPY_STALLED`), §7.5 and [A03] (the PTC step, its qualification routes, SER), §7.7 (every fallback edge: trigger, preconditions, maximum count, checkpoint policy, typed outcome), §8.2 (taxonomy), §8.3 (R0)  
**Companions:** ADR 0005 (amended additively by D6 below); ADR 0007 D1–D2 (classes of the new fields); ADR 0008 D1 (no pseudo-time or λ at the evaluation boundary), D1.3 (a stage-varying specification is a re-bound pinned input), D3.3–D3.5 and D4.5 (the mass-matrix pattern and the row-sign map); ADR 0009 (the executor, the merge edge this edge mirrors); `docs/interfaces-frozen.md` §1–§2 (the change rule)

## Context

T04 must deliver one typed homotopy, one PTC family with the safeguarded SER controller of blueprint §7.5, and the third recovery edge of plan §4.3 ("EO globalization failure → typed homotopy or qualified PTC"), each with records that the frozen schemas cannot yet hold. T03 handed over one registered failure, PHS-05 (`SYN-001-A02-355-dew-guess`), whose cause it diagnosed as a Newton step far larger than the region in which its linearization of the lifted split holds.

The specification (T04 §3) established four facts that shape this decision, each generator-checked:

1. **PTC with physical holdups cannot rescue PHS-05, by structure.** In the A02 region the heater temperature is an *algebraic* variable (fixed by the specification row through the flash duty); a linearly implicit pseudo-transient step Newton-solves every algebraic row at every pseudo-step, so its direction in `(S3.T, split, U-FLASH.Q)` is Newton's for every Δτ (checked to 1e-25 at Δτ = 1e-3, 1, 1e3), and its first pseudo-step lands `S3.vap.C` at Newton's own `α_max`.
2. **Specification continuation does rescue it** — three λ-trials, no rejection — and rescues 9 of the 10 contract failures of a 180-run A02 family scan; the tenth is a typed, bracketed stall at the dew point.
3. **The residence-time mapping of the flash family is sound**: steady-state equivalence, the ADR 0008 D5 pattern, dimensions, reference invariance of the step, and local attraction at the SYN-001 roots with six inventory modes in closed form, all real negative for every `r < 1` and every positive residence time.
4. **It is not useful on the registered basin comparison.** On SYN-001 at r = 0.95 from all 18 admissible off-ray lattice starts (27 of the 45 are refused by the mixer, K03 §10.1; re-registered 2026-09-24, T04 §17 F14), damped Newton and PTC both converge to the P01 root; PTC costs 1.9–8.8 times the iterations. Blueprint §7.5's risk row reads: "PTC lacks a defensible mapping **or improves no tested basin** → keep it experimental".

## Decision

### D1. `SolvePolicy.globalization` — one required object

`globalization`: `additionalProperties: false`, required:

| Field | Value (registered) | Class |
| --- | --- | --- |
| `policy_id` | literal `"T04-globalization-v1"` | R0 |
| `eo_core` | `"newton"` \| `"ptc"`; default `"newton"` | R0 |
| `eo_recovery` | `"homotopy"` \| `"none"`; default `"homotopy"` | R0 |
| `eo_recovery_max_count` | literal `1` | R0 |
| `homotopy` | `{type: "specification_continuation", delta_lambda_initial: "1/4", delta_lambda_min: "1/1024", growth: 2, shrink: "1/2", corrector_max_iterations: 10, max_lambda_trials: 64}` | R0 |
| `ptc` | `{status: "experimental", mass_policy: "T04-residence-time-v1", residence_time_s: 1.0, tau_initial_s: 1.0, tau_min_s: 1e-4, tau_max_s: 1e10, gamma_min: 0.2, gamma_max: 2.0, phi_floor: 1e-12, retry_shrink: 0.5, retries_max: 10, max_steps_per_attempt: 200, polish: "one_newton_step"}` | R0 |

A replay under a policy without `globalization` is refused (ADR 0005 D1's precedent). `ptc.status` is single-valued `"experimental"` in v0.1; a later qualification is a new value, never a silent change.

### D2. The typed homotopy `specification_continuation` (T04 §4)

- **Applicability.** A region with at least one promoted specification row (`SolvePlan`/`ExecutionPlan` step `specification_rows`, T02 §7.3), each of the written form `variable − parameter`. The continued inputs are those rows' parameters; nothing else moves.
- **Map.** `H(x, λ) = F(x; p(λ))`, `p(λ) = p* + (1 − λ)(p⁰ − p*)`, `p⁰` the specified variable's value at the opening state `x⁰`, all other pinned inputs at the target. `H(x, 1) = F(x)`: at λ = 1 the target compiled instance itself is used, so the endpoint is the target problem bit for bit. Easy endpoint: `x⁰` is a root of `H(·, 0)` (the pre-solve satisfies every other row). Endpoint mapping: identity on `x`. Path domain: λ ∈ [0, 1] dyadic, `x` within the region's bounds and the provider domain, the opening signature frozen. Scales: the target's.
- **Identity.** Each λ-level is a re-binding of pinned inputs (ADR 0008 D1.2(ii), D1.3): its instance shares `model_version` and has its own `constants_sha256`. λ never reaches the evaluation boundary.
- **Controller.** Corrector = K03 §5's Newton core, unchanged, capped at `corrector_max_iterations`, in the frozen signature; accept iff `CONVERGED`; on acceptance Δλ ← min(2Δλ, 1 − λ); on rejection roll back to the last accepted `(λ, x)` and halve Δλ; **`HOMOTOPY_STALLED`** when Δλ < `delta_lambda_min` or the λ = 0 corrector fails; `BUDGET_EXHAUSTED` with budget `homotopy_steps` after `max_lambda_trials` λ-trials.
- **λ < 1 is never target-verified.** Every λ < 1 checkpoint is `partial` and carries its λ; K04 refuses it (identity differs); a `HOMOTOPY_STALLED` solve issues no certificate.
- **Composition.** A homotopy runs inside one attempt with a frozen signature. A corrector's failure of any kind (including `PHASE_UPDATE_REQUIRED` from the screen and `BOUND_BLOCKED`) rejects the λ-trial; the homotopy never changes the active set. Its core outcome enters `phase_contract.decide`: `CONVERGED` → row 1; every other outcome → row 6 (terminal). A restart that row 1 proposes after λ = 1 runs the Newton core on the target.

### D3. Recovery edge 3: EO globalization failure → specification continuation (T04 §5)

- **Trigger.** A region solve (a `solve_eo` step, or a merged region) whose terminal outcome is one of `LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`, `BUDGET_EXHAUSTED(newton_iterations | ptc_steps)`, `PTC_STALLED`, `ACTIVE_SET_CYCLING`, `ATTEMPTS_EXHAUSTED`. Not: `CONVERGED`, `LINEAR_SOLVE_FAILED` (rank; blueprint §7.7's own row), `EVALUATION_ERROR`, `BUDGET_EXHAUSTED(property_calls)`, `CHECKPOINT_INCOMPATIBLE`, `INITIALIZATION_FAILED`, `CAPABILITY_UNAVAILABLE`, `PTC_MAPPING_INVALID`, `HOMOTOPY_STALLED`.
- **Preconditions.** `eo_recovery = "homotopy"`; the region has a continuation parameter (else `unsupported(no_continuation_parameter)` is recorded and the failed outcome stands); the edge has not fired for this step in this solve.
- **Action.** One new region solve of the same region whose attempt 0 runs the homotopy core from the failed solve's item-0 opening state in its opening signature, with a fresh contract state (used signatures, attempt count) — the merge edge's precedent (ADR 0009). Its `branch_provenance` continues the failed solve's list densely; its first item has `opening_source = "eo_recovery_start"`.
- **Maximum count** 1 per region step per solve. **Outcome:** the recovery's. **Evidence of unchanged physics and specifications:** the λ = 1 instance's `(model_version, constants_sha256)`, the region's row and column ids and the certificate's identity equal the failed solve's; every λ < 1 level's parameter vector differs from the target's only at the continued ids.

### D4. The PTC core and the residence-time mapping (T04 §6–§7)

- **Step.** `(M̂_k/Δτ + Ĵ_σ,k) Δx̂ = −F̂_σ,k` with `F̂_σ = σ ⊙ S_F⁻¹ F`, `Ĵ_σ = σ ⊙ S_F⁻¹ J S_x`, `M̂ = S_F⁻¹ M S_x`, `M` evaluated at the accepted iterate and frozen during its retries. **`PTC_ROW_SIGN`** — one named constant, applied to residual and Jacobian together — is `σ = −1` on `holdup_balance` rows and `+1` on every other row (ADR 0008 D3.4).
- **Mapping `T04-residence-time-v1`.** Every holdup is θ times the unit's phase-resolved outflow content at the outlet state: `N_i = θ Σ_π n_i^π`, `H = θ Σ_π Σ_i n_i^π h_i^π(T, P)`; `M_row = ∂(holdup_row)/∂x`. Registered for `syn001.tp_heater` (phases = the lifted split of S3) and `syn001.tp_flash` (phases = S4, S5), θ = 1 s for both. A region whose `holdup_balance` rows are not all mapped, or whose mapping has an entry on any other row, is refused before its first attempt with **`PTC_MAPPING_INVALID`** (ADR 0008 D4.5's test, made a runtime refusal).
- **Controller.** K03 §5.3's bound-aware `α_max` with exact landing, one trial at `α_max`, no merit test; rejection reasons `bound_blocked`, `invalid_trial`, `phase_update_required`, `linear_solve_failed`; on rejection keep the state and residual and halve Δτ, at most `retries_max` times and never below `tau_min`, then **`PTC_STALLED`** (or `BOUND_BLOCKED` with `blocked_by` when the last rejection was a bound); SER on accepted iterates only: `Δτ_next = clip_[τ_min, τ_max](Δτ_used · clip_[γ_min, γ_max](φ_k / max(φ_{k+1}, φ_floor)))`; stop on K03 §5.2 before any update; reset to `tau_initial` at every attempt; `BUDGET_EXHAUSTED(ptc_steps)` after `max_steps_per_attempt`.
- **Polish.** A PTC attempt that stops after at least one pseudo-step takes one Newton step from the stopped iterate and keeps it iff it evaluates, keeps the frozen signature, meets K03 §5.2 and is no worse row by row in the worst ratio; otherwise the stopped iterate stands. Reason: PTC's terminal convergence is linear and stops every row at the tolerance edge, where K04's envelope balance (a sum of four unit balances) measured 1.31 τ — a `FAILED` certificate on a `CONVERGED` solve (T04 §7.5).

### D5. PTC is experimental in v0.1; V14's qualified-PTC clause is recorded incomplete

The residence-time family meets blueprint §7.5's route-(a) derivation and every check it requires, and **improves no tested basin** on the registered comparison (D4 of the Context). Per the plan's T04 note and blueprint §7.5's risk row it is retained as experimental: selectable only by `eo_core = "ptc"`, never by an automatic path, `ptc.status = "experimental"` on every policy. V14 is recorded with its PTC clause incomplete. What would reopen it is T04 §8.4.

### D6. Composition with ADR 0005 (additive amendment)

- T03 §4.8 row 4 (a stall with a wall in the window) and K03 §9.3's stall trigger gain `PTC_STALLED`; row 5 (lifted, kernel disagreement at the end state) gains `PTC_STALLED` and `BUDGET_EXHAUSTED(ptc_steps)`. The PTC core reports phase-rejected trials to the one `WallObserver` with `iteration` = pseudo-step index and `alpha` = `2^−retry`; patience is unchanged. No outcome a Newton or Anderson core produces changes path: every registered K03, T02 and T03 trajectory is unchanged.
- K03 §12.4's rule "the one context for every compiled-problem call in the attempt" is amended: in a homotopy attempt, `evaluation_context` is the target's (λ = 1), and each λ-level uses a level context field-equal to it except `constants_sha256`.

### D7. Records and schemas

1. `solve-policy`: required `globalization` (D1).
2. `solve-event`: `outcome` gains `HOMOTOPY_STALLED`, `PTC_STALLED`, `PTC_MAPPING_INVALID`; `kind` gains `homotopy_step`; `rejection_reason` gains `bound_blocked`, `linear_solve_failed`; nullable fields `pseudo_step`, `pseudo_step_next`, `ser_ratio` (PTC `trial`/`step_accepted`), `lambda_value`, `delta_lambda` (strings `p/q`, dyadic), `corrector_outcome`, `corrector_iterations`, `level_constants_sha256` (on `homotopy_step`), `homotopy_level` (int; stamped on every event inside a corrector, as `step_index` is stamped), `eo_recovery ∈ {taken, unsupported}` and `eo_recovery_unsupported ∈ {no_continuation_parameter}` (on the step's `region_closed`). The polish is a `trial` event with `message` `polish` and `pseudo_step` null.
3. `attempt-context`: required `core ∈ {newton, anderson, ptc, homotopy}`; required, nullable `continuation` (`{type, parameter_ids}`).
4. `checkpoint`: required, nullable `continuation_lambda` (string `p/q`); a value other than `"1"` requires `label = "partial"` and `verification_scope = "unverified"`.
5. `solution-certificate` `branch_provenance` item: `core` gains `ptc`, `homotopy`; `opening_source` gains `eo_recovery_start`; required, nullable `continuation`: `{type, parameter_ids, lambda_levels, lambda_reached, rejected_trials}` (accepted λ-levels and λ reached as `p/q` strings).
6. `failure-bundle`: unchanged (actions and hypotheses are existing fields).

**Classes (ADR 0007).** R0: every `globalization` value, `core`, `continuation` (all fields), `lambda_value`, `delta_lambda`, `continuation_lambda`, `homotopy_level`, `corrector_outcome`, `corrector_iterations`, `eo_recovery`, `eo_recovery_unsupported`, the new outcomes and rejection reasons, all counts — λ values are exact dyadic fractions decided by R0 decisions, written as strings so no float formatting enters. R1/R2 under D2 (ADR 0007 D2.2 gains these rows): `pseudo_step`, `pseudo_step_next`, `ser_ratio`, and `alpha` on a PTC trial when below 1. Digest, shape only: `level_constants_sha256` (a hash over a parameter vector that contains a solved float `p⁰`).

### D8. Taxonomy

`HOMOTOPY_STALLED` and `PTC_STALLED` → "homotopy/PTC/active-set stalls", action `supply_initial_guess`; `PTC_MAPPING_INVALID` → "model domain/conservation/derivative defects", action `report_defect`. A `HOMOTOPY_STALLED` bundle carries one inferred cause from a registered vocabulary: `phase_boundary_on_path(<unit>)` when every rejection since the last acceptance was a corrector `BOUND_BLOCKED` on a watched variable or `PHASE_UPDATE_REQUIRED`, `singular_path_or_fold` when they were `LINEAR_SOLVE_FAILED`, `corrector_failure` otherwise — hypotheses, never observations (blueprint §7.4: "branch loss is a hypothesis unless supported by diagnostics").

### D9. Certificates of a bound declaration (K04 extension; T04 §4.8, added 2026-09-24)

On the build lane's finding at `1f632ed`, K04's verifier could not certify an A02 region solve. It judged the nominal declaration (`HEAT-T` pinned at the flowsheet's temperature, which a binding sets to the *guess*). Handed HOM-01's state, it returned `FAILED` with `false_success_detected = true` on a correct root. This decision covers K04's input and records; its checks, tolerances and verdict rules are unchanged.

1. **Every `CONVERGED` solve is certified against the declaration it solved.** For a revision with a freed variable and a promoted specification, that is the bound declaration: 49 rows, 47 columns, and a 47 × 47 target after its two certified aliases.
2. **Identity guard.** The verifier compares its compiled `(model_version, constants_sha256)` with the result's `root_fingerprint`, and with the result's `SolvePlan` where it has one. When the state is taken from the result, the state hash must also equal the fingerprint's `full_state_sha256`. Otherwise it refuses before any check, with `declaration_mismatch(<field>)`, `state_mismatch(full_state_sha256)` or `declaration_unidentified`. *(Amended 2026-09-24, T04 review S1, S2.)* Only the result identifies the solve: a caller-supplied `SolvePlan` is compared but never sufficient. On the bound entry point the revision document must be the one the binding was bound from (`declaration_mismatch(revision)`). A refusal issues no certificate.
3. **Specification checks come from the binding.** A freed column's check is recorded `not_applicable` with reason `freed(<specification id>)`. A promoted column gains `specification.<column>` against the revision's value. No specification value is ever read from the flowsheet a pre-solve traversed.
4. **`transformations` gains `declaration = {removed_specification_rows, freed, promoted}`** (R0). Its values are empty on a nominal certificate. `tear` records the solve's tear, which is empty for a region or plan solve. `derivative_provenance.path` stays `assembled_schur` (ADR 0009 D2). The schema's `transformations` is an open object, so the schema does not change; the nominal certificates' fixtures are regenerated once.
5. **Verdicts are promised only outside ADR 0007 D2.4's band.** K04's fresh-flash tolerances are tighter than the lifted rows' tolerance implies (T04 §17 F9). T04 therefore registers certificate verdicts only at states whose every thresholded value lies outside the band. It hands the tolerance policy to a K04 follow-up (T04 Q8).

*Rejected:* striking T04's certificate clauses (option (b)). That would leave the rescued PHS-05 `CONVERGED` on the solver's word alone, and it would still need rule 2, because the unguarded path produces a false `FAILED`. Also rejected: checking the freed variable against its guess, which is the defect itself, and amending K04's tolerances inside T04, which is a policy change for every lifted stream.

## Alternatives considered

- **Recycle-closure continuation (r from 0 to r\*).** Rejected: the SYN-001 recycle is benign (SYN-001 §5.1), damped Newton converges from every registered start, and no registered failure would exercise it; its easy endpoint needs a separate once-through solve. Heat coupling, reaction activation and nonideality: no model in v0.1 carries them.
- **The global Newton homotopy `F(x) − (1 − λ) F(x⁰)`.** Rejected: on every registered case it equals specification continuation (`F(x⁰)` is nonzero only on the promoted row), but its λ < 1 problems are not physical problems and its offset lives outside the pinned-input identity, which ADR 0008 D1.2(ii) assigns to a stage-varying specification.
- **An orchestrator-side offset on the target instance instead of re-binding.** Rejected: a λ < 1 state would be evaluated under the target's identity.
- **Each λ-level a full phase-contract solve (phase changes along the path).** Rejected for v0.1: a per-level cycle rule and signature rollback, for no registered case; a path crossing a phase boundary stalls with a bracketed, diagnosed `HOMOTOPY_STALLED`, and arclength continuation is deferred (blueprint §7.4).
- **PTC as edge 3's action.** Rejected: experimental (D5) and provably unable to rescue the registered failure (Context 1).
- **Edge 3 from the failed solve's end state.** Rejected on measurement: from PHS-05's end state the λ = 0 corrector fails and the case stays unrescued.
- **A trigger set without `ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED`.** Rejected: on the lifted path the contract converts globalization failures into restarts, so they surface as the contract's terminal outcome; PHS-05 would be unreachable.
- **The heater's mole holdup on its stream total `S3.n`.** Rejected: off the split manifold the step then moves under a change of enthalpy reference (measured > 1e-6 scaled); the phase-resolved holdup is invariant (to 1e-25). On the manifold, where every registered path stays, the two coincide; the choice rests on the principle.
- **Internal energy `U` as the energy holdup.** Rejected: the residence-time vessel has a moving boundary at pinned pressure, so the first law accumulates `U + PV = H`; ADR 0008 D3.5's `U` names the rigid-vessel quantity and deferred this relation to T04.
- **Residence times fitted per unit.** Rejected: no vessel data exist; local attraction holds for every positive ratio (T04 §6.6), and a common θ is the pseudo-time unit (every trajectory is invariant under the joint scaling of θ and the τ constants).
- **M on an algebraic or zero-holdup row "to damp it".** Forbidden by ADR 0008 D3.4/D4.5; refused as `PTC_MAPPING_INVALID`.
- **An Armijo line search on α inside PTC.** Rejected: not blueprint §7.5's method, whose rejections shrink Δτ.
- **No polish.** Rejected on measurement (D4).
- **Qualifying PTC on the A04 random ensemble or on a reactor chosen after the flash failed.** Rejected: selected after the fact (brief §2); the plan registers SYN-001 at r = 0.95 as the comparison.

## Consequences

- C1. **Schema changes** as D7; `schemas/README.md` and `docs/interfaces-frozen.md` §2 list them under T04 with this ADR's number when the schemas land.
- C2. **Migration.** Every round-trip fixture of the five changed schemas is regenerated by its committed generator from a real solve (R-015); the only instances are the repository's own. A `SolvePolicy` without `globalization` is invalid after this ADR, by design.
- C3. **Re-registrations** (T04 §11): PHS-05's registry entry (under the default policy `CONVERGED` via edge 3; `handed_to: T04` closed); T03's tests whose registered outcome is an edge-3 trigger on a region solve set `eo_recovery: none` and keep their expectations; ADR 0005 D4 amended by D6; K03 §12.4 amended by D6.
- C4. **Taxonomy** (`verify/failure.py`): the three outcomes of D8.
- C5. **Register:** R-030 to R-034 record D2–D5 and their rejected alternatives; R-035 records D9.
- C6. **Handed on:** the tear path's budget-refusal shape (T03 review S1) to a K03 follow-up before T06's ensemble; a preregistered reactor case for a later PTC qualification (T04 §8.4).
- C7. **K04** (D9): the verifier's identity guard and bound-declaration check set; the nominal certificates' fixtures regenerated for `transformations.declaration`; K04's tolerance policy at lifted splits (T04 §17 F9) and its flash-outlet clause (F10) handed to a K04 follow-up.

## Acceptance evidence

- T04 assertions A00–A33 (A30–A33 are D9's) in `evidence/T04/<commit>/manifest.json`, whose `requirements` are this header's less V14 (the frozen evidence-manifest schema takes D/A ids only; V14 is carried in `limitations` and `docs/requirements.yaml`), `status: tested`, with V14's PTC clause recorded incomplete in the manifest's `limitations` and in `docs/requirements.yaml`.
- The regenerated fixtures validate against the changed schemas; the gate is green on x86-64 and aarch64 with the K05 identity comparison including the new R0 fields.
- `t04_reference.py --check` passes and the committed reference file's SHA-256 matches the specification's header.
