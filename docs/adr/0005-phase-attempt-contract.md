# ADR 0005 — The phase-attempt contract: one active-set controller for the tear and the lifted EO path, checkpoint compatibility, and root provenance

**Status:** Accepted 2026-09-24 — T03's manifest `evidence/T03/6ac24be9da572a90b198ba91b81d603f082cfa74/manifest.json` is `tested` (27 of 27 checks, A00–A26; A23 measured on the CI pair, run 36019081919) and the fixtures of every changed schema regenerate identically from live code (A01, R-015). Amended by the T03 implementation review (`docs/reviews/T03-review.md`: S4, M2, §8) before acceptance. Agent acceptance is numerical and procedural: `review.numerical` and `review.process_model` remain `pending`.  
**Date:** 2026-09-24  
**Author:** design lane (`specifier`); pre-allocated by plan §4.1 for exactly this decision (register R-A05, R-012)  
**Normative text:** `docs/derivations/T03-phase-controller-spec.md` §4–§9 (the contract, its records and its registered cases); machine-readable expectations `benchmarks/t03/reference_values.yaml` from `docs/derivations/scripts/t03_reference.py`  
**Supersedes as normative text:** K03-solver-spec §9 (the interim tear contract, R-012) and T02-recycle-spec §6.3.3–§6.3.5 (the interim lifted EO policy, R-025). Both remain the descriptions of their path wherever this ADR does not change them.  
**Affected requirements:** D09 (frozen attempts, bounded restarts, phase-domain outcomes), D11 (branch histories; no uniqueness or dynamic-stability overclaim), A01 (same signature across a residual/Jacobian trial; restart on update), V15 (frozen phases; multiple-root evidence), D20 and blueprint §8.3 R0 (every new record field is structural)  
**Affected packages:** T03 (implements everything below); K03 (the tear controller calls the shared decision function; per-attempt contexts; one test's expected message); T02 (the region solve; A21's closure mechanism; A30/A31 re-registered); K04 (two certificate fields); K05 (the identity script; replay refuses a policy without the new literal); T04 (continuation history, and PHS-05 handed to it); T06, T07 (read the new outcome and the provenance)  
**Blueprint authority:** §6.3 [A01], §7.6 [A01] and "multiple roots", §7.7, §8.2, §8.3  
**Companions:** `docs/interfaces-frozen.md` §1–§2 (the change rule this ADR follows, and the binding semantics "the outer active-set controller constructs a new context after a phase restart"); ADR 0007 D1–D2 (no float is added, so D2.2 gains no row); ADR 0009 D3–D4 (the event grammar and `AttemptContext.active_phases` this ADR builds on, and one sentence it amends)

## Context

Two interim contracts decided phases. K03 §9 fixed the tear path: the traversal reports a signature, a trial in another signature is rejected and halved, a persistent wall restarts from the largest-α rejected trial, a signature may be attempted once. T02 §6.3 fixed the lifted EO path, where phases are variables: a phase leaves when one of its lifted variables lands on its bound, and appears only when an attempt closes. T02 registered two A02 cases that fail under those rules and handed them to T03 with two named gaps: appearance during an attempt, and a restart into the adjacent regime when a step overshoots two phase boundaries.

The T03 specification simulated the contract on an exact reduction of the A02 region at 40 digits, checked the simulation against every count and end temperature T02's implementation measured on the same cases, and found three things: the two named gaps are real and each is necessary; T02's landing trigger for disappearance is itself a defect (the two-phase attempt that follows a correct appearance lands a vapour component on its bound on the way to a two-phase root, and the landing rule sends it back into cycling); and no recurrence rule rescues the one remaining failure on the family. It also found the checkpoint and provenance records the plan's T03 row asks for absent, and the two controllers each keeping their own copy of the cycle rule.

## Decision

### D1. One contract for both paths, named in the policy

The phase-attempt contract of T03 §4 governs every solve that selects phases, on the tear path and the lifted EO path alike. The paths differ only in who reports a trial's regime (the traversal; or the admissibility screen and the kernel, D3) and in the two lifted-only closure conversions (D4). The rule set is recorded as **`SolvePolicy.phase_contract`**, a required single-valued literal `"T03-phase-contract-v1"` (schema change 1), in the manner of `merit`, `redundant_row_policy` and `cycle_rule`: a later rule set is a new value a reader can see, and a replay under a policy without it is refused rather than run under rules it never declared. No solver constant is added or changed.

### D2. The signature, the regime lattice, and what freezing means

The signature is one regime per phase-selecting unit (`SolvePlan.signature_units`; every lifted unit of a region), in plan order. Regimes form the lattice `LIQUID — TWO_PHASE — VAPOR`; a signature is *adjacent* to another when every unit's regime is equal or one step away and at least one differs (T03 §4.4 argues it from the provider class: the liquid and vapour regions meet only where every `K_i = 1`). Within an attempt nothing changes the phase set or the equations it selects; each attempt constructs its own evaluation-context objects, as `interfaces-frozen.md` §1 requires and neither controller does today.

### D3. Appearance during an attempt: a screen that rejects, never selects

On the lifted path, every trial of a single-phase unit is screened with K03 §8.2's admissibility check — the same function as the closure check, at `admissibility_epsilon` — and a flagged trial asks the kernel for its regime; if that differs, the trial is rejected `phase_update_required` and K03 §9.3's rules apply unchanged (halve; close after `phase_wall_patience = 2` consecutive walls, or on a stall with a wall in the window). The residual is never altered. The opening state of an attempt is not screened (T02 A21's and PHS-04's second attempts open on or beyond a phase boundary and converge to admissible roots).

### D4. Restart selection, disappearance, closure conversions, and one decision function

- **Restart point:** among the phase-rejected trials of the most recent line search that had one, the largest-α candidate whose reported signature is adjacent to the frozen one; if none is, the largest-α candidate. The new signature is the candidate's; on the lifted path each changed unit's split is set from the kernel at that state.
- **Disappearance (lifted):** a phase of a `TWO_PHASE` unit leaves when the attempt ends `BOUND_BLOCKED` on one of its watched variables (its total while the stream flows, a component while the stream's component is positive). A landing alone is an overshoot and the attempt continues. Single-phase units watch nothing.
- **Closure conversions (lifted), retained from T02:** an inadmissible converged state, judged by the branch found, restarts in the kernel's regime; a failed attempt the kernel disagrees with at its end state restarts in the kernel's regime.
- **Precedence and gate:** as T03 §4.8; the restart gate checks the attempt budget, then cycling, then the opening checks of D6.
- **Cycle rule unchanged:** `no_repeated_signature`, `max_attempts = 5`.
- All of this is **one function** called by both controllers, and one wall-observer class serves both.

### D5. What a phase change rebuilds, and the record that evidences it

Every attempt rebuilds its `AttemptContext`, its evaluation-context objects, its problem (lifted: the free columns and rows of its active set, restricted by id), its wall observer, its Jacobian and every factorization; the exact property caches, the used signatures and the counters are kept. **`AttemptContext.jacobian_pattern`** (schema change 3), required and nullable: `{rows, columns, nnz, sha256}` of the structural pattern of the attempt's EO block — the compiled Jacobian's sparsity, structural zeros included, restricted by id to the attempt's rows and columns (the tear path's inner block) — hashed per ADR 0002 over `{"rows", "columns", "entries"}`; `null` only when the attempt has no compiled problem. R0.

### D6. Checkpoint compatibility, and its typed refusal

Before an attempt opens, six checks hold on its opening state — `identity` (model version and constants), `step` (plan step), `scale_segment`, `coverage` (every free variable finite), `active_set` (tear: the candidate's reported signature is the new one; lifted: every pinned variable exactly `+0.0`), `bounds` — or the solve ends **`CHECKPOINT_INCOMPATIBLE`** (schema change 2: a new `SolveEvent.outcome` value) with `checkpoint_incompatible(<check>, <detail>)`, no attempt opened, the last checkpoint `partial`, no certificate. Taxonomy class `homotopy/PTC/active-set stalls` with the action overridden to `report_defect` (ADR 0009 D6's pattern): no registered path produces an incompatible state, so one that appears is a defect.

### D7. Root provenance

- **`branch_provenance`** — the certificate's existing field, and a new field of both solve-result types — gets a defined item (T03 §8.1): `attempt`, `signature`, `core`, `opening_source`, `initializer_source`, `opening_trial`, `opening_state_sha256`, `core_outcome`, `iterations`, `decision`, `cause`. Item 0 is the starting point blueprint §7.6 asks for. Continuation history is T04's to add when a continuation exists.
- **`root_fingerprint`** (schema change 4, on `SolutionCertificate`, required and nullable; and on both result types): `policy = "T03-root-fingerprint-v1"`, `model_version`, `constants_sha256`, `variable_ids_sha256`, `branch_found`, `full_state_sha256`, `delta_scaled_inf = 1e-4`, `claims = {uniqueness: NOT_ASSESSED, dynamic_stability: NOT_ASSESSED}`. Issued only on a converged, admissible solve.
- **`same_root`** returns `SAME`, `DISTINCT` or `NOT_COMPARABLE`: not comparable across problems; distinct if the branch found differs or the scaled ∞-distance of the two states exceeds `δ_root = 1e-4`; same otherwise. `δ_root` is ≥ 50× every registered solution-error bound and ≥ 9 600× under the only registered root separation (T03 §8.3).
- *Amended by the T03 implementation review (`docs/reviews/T03-review.md` M1, S3), 2026-09-24:* `branch_found` is read from the full state for every unit with a lifted split in the declaration, whichever path solved it (one root reached by the tear and the EO path has one fingerprint list); `same_root` refuses states whose hashes are not their fingerprints' `full_state_sha256`, and scales that do not cover every variable id (T03 §8.2–§8.3 as amended).

### D8. Records, and one amendment to ADR 0009

`attempt_closed` records what the core did; the controller's decision is recorded on the next `attempt_opened` (`message = phase_update(<cause>)`, `state_sha256` of the opening vector on both paths, `alpha` of the chosen candidate) or on `solve_closed` when terminal, in the grammar of T03 §4.10. This amends ADR 0009 D3's sentence placing the structured phase reasons on `attempt_closed`: under D4 a disappearance's core outcome is `BOUND_BLOCKED`, and an `attempt_closed` must say what the numerics did. `AttemptContext.opened_from` keeps the meaning the implementation gives it (the checkpoint of the attempt that closed into this one). A `role: free` specification with no value ends the solve `INITIALIZATION_FAILED` with `missing_initial_guess(<variable id>)` (T02 §7.5, made binding). *Amended by the T03 implementation review (S4, M2), 2026-09-24:* the R0 message and cause strings carry no measured float (`inadmissible(<stream>, <branch>)`, `checkpoint_incompatible(<check>, <variable or field>)`; the numbers go to non-R0 records), and the missing-guess refusal is carried by the plan, not by an argument a caller may omit (T03 §4.10, §9 as amended).

## Alternatives considered

- **Keep T02's appearance at closure only.** Rejected: PHS-01 and PHS-02 converge to (or stagnate toward) a single-phase branch root outside the band or outside the provider domain and cycle — T02 A30/A31, reproduced by the twin number for number.
- **A kernel flash on every trial.** Rejected: a flash per trial for a verdict needed only on the trials the admissibility check already flags, and R-012's lesson (a verdict that changes with every trial must not steer one) — the screen only rejects, and the patience rule decides whether the rejections are a wall.
- **K03 v0.0's largest-α restart point, unqualified.** Rejected: on both re-registered cases the largest-α candidate is `VAPOR`, whose own wall's largest-α candidate is `LIQUID` again (`ACTIVE_SET_CYCLING`).
- **The smallest-α candidate ("nearest the wall").** Rejected: 5 failures in 75 on the A02 family scan against 2, and it moves the restart point of K03's registered OFF-B trajectory, which the adjacent rule leaves unchanged.
- **Disappearance on a landing (T02 §6.3.3 as written).** Rejected: on both re-registered cases the two-phase attempt lands `S3.vap.C` on its bound on the way to a two-phase root and would cycle; T02 A21's landing is followed by a block, so the persistent rule keeps every A21 number.
- **Refusing a disappearance restart whose pinned state is far inside the old regime.** Rejected for now: the threshold would be fitted between `1e-5` (A21, which must pass) and `0.43` (PHS-05) with no argument (T03 Q2).
- **Letting a signature recur (bounded count, or on merit progress).** Rejected: on PHS-05, the one registered case where the no-repeat rule bites on a solvable problem, the count rule reaches `ATTEMPTS_EXHAUSTED` and the merit rule is refused at once. R-012's watch item stands.
- **Two contracts with a stated relation.** Rejected: two copies of the cycle and budget rules already exist and nothing keeps them equal.
- **New `SolveEvent` fields for the opening record.** Rejected: `state_sha256`, `alpha` and a structured `message` on the existing `attempt_opened` carry it with no schema change (ADR 0009's precedent for grammars).
- **A fingerprint holding the state's floats, or a hash of a quantized state.** Rejected: floats would need a new ADR 0007 class for a record that `same_root` compares under its own tolerance; quantization splits one root across a grid boundary on one platform and not the other. The fingerprint carries R0 fields and an identity digest; `same_root` reads the states.
- **Re-meaning `opened_from` as the restart point** (K03 A29's text). Rejected: the implementation and its schema test already give it the other meaning, and `attempt_opened.state_sha256` already records the restart point.

## Consequences

- C1. **Schema changes** (the freeze's rule, `interfaces-frozen.md` §2): `solve-policy` gains the required `phase_contract`; `solve-event`'s outcome enum gains `CHECKPOINT_INCOMPATIBLE`; `attempt-context` gains the required, nullable `jacobian_pattern`; `solution-certificate` gains the required, nullable `root_fingerprint` and a defined `branch_provenance` item. `schemas/README.md` and `docs/interfaces-frozen.md` §2 list the change under T03 with this ADR's number when the schemas land.
- C2. **Migration.** Every round-trip fixture of the four schemas is regenerated by its committed generator from a real solve (R-015); the only instances are the repository's own. A `SolvePolicy` without `phase_contract` is invalid after this ADR, by design; a replay of a bundle recorded before it is refused on the policy, which K05 decides before anything runs.
- C3. **Re-registrations** (T03 §10): T02 A30/A31 become T03 A06–A09 (`CONVERGED`); T02 A21's attempt-1 closure is reached through `BOUND_BLOCKED` with the same numbers; one K03 test's expected `attempt_opened` message; K04 A06's `branch_provenance` shape; ADR 0009 D3's sentence (D8).
- C4. **Taxonomy:** `verify/failure.py` maps `CHECKPOINT_INCOMPATIBLE` to `homotopy/PTC/active-set stalls` with `OUTCOME_ACTIONS` → `report_defect`.
- C5. **Register:** R-028 records this decision and the parts of R-012 and R-025 it reverses; R-A05 points here.
- C6. **Handed on:** `SYN-001-A02-355-dew-guess` (PHS-05) is an expected failure handed to T04; continuation history is T04's field to add.

## Acceptance evidence

- T03 assertions A00–A26 in `evidence/T03/<commit>/manifest.json`, `status: tested`, in particular A01 (the policy literal), A02 (one decision function), A06–A12 (the phase cases), A13 (T02 A21 and A28/A29 under the contract), A15 (the pattern), A16 (the refusal), A19–A22 (provenance), A23 (R0 on the CI pair).
- The regenerated fixtures validate against the changed schemas; the gate is green on x86-64 and aarch64 with the K05 identity comparison including the new R0 fields.
- `t03_reference.py --check` passes and the committed reference file's SHA-256 matches the specification's header.
