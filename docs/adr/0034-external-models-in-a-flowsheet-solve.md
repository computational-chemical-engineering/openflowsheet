# ADR 0034 — External models in a flowsheet solve: an extent-fixed embedding with an outer coupling, frozen identities per attempt, R3 runs replayed from the record

**Status:** Proposed, 2026-10-08. Accepted when M02's evidence manifest is `tested` (design note gates G2, G6–G9, G12)
and the design-lane review of WO-7–WO-10 is recorded.
**Author:** design lane (`architect`), M02.
**Normative text:** `docs/design/M02-pymrm-adapter.md` §4, §6.1, §7, §8 (binding), §8.1. Register R-225–R-227,
R-230–R-232.
**Amends:** ADR 0020 D4 (a revision bundle on the new route gains `external-coupling.json`; an interrupted coupled job
also keeps its experiment artifacts); ADR 0019 (Amendment 4, part 2: `solve_path` value `revision_coupled`, outcome
`COUPLING_NOT_CONVERGED`); ADR 0027 D9 for the real reactor's variant (the per-tube flow bound of Q-F5); M01.A49's
binder clause (the stand-in is bound; R-199 left this to M02). Pointer paragraphs are added at merge (WO-13).
**Affected requirements:** W21 (accuracy, execution, provenance); blueprint §5.1, §5.2, §5.3 ("all model versions are
frozen" during an attempt), §8.3 (R3).
**Affected packages:** M02; M03 (sensitivities refuse the route), M05 (composes the reactor itself), M07 (truth checks).

## Context

A design-grid reactor evaluation costs about 9 s and has no derivative. The revision path solves every flowsheet as one
EO region whose units must declare analytic, AD or implicit residual derivatives (T02 §4.2); the tear path is SYN-001's
only (R-045). The reactor's effect on the process is fully captured by two numbers per evaluation — the projected extent
ξ and the outlet temperature (M01 §8.2: n_out = n_in + νξ, P_out = P_in) — and its map is deterministic within one
environment and agrees within 10⁻⁶ across environments (M01.A43, A47).

## Decision

**D1. The extent-fixed embedding.** An external reactor unit is compiled with rows that take the N₂ conversion X̂ and the
temperature rise ΔT̂ as pinned parameters: n_in,i + ν_i ξ − n_out,i = 0; ξ − X̂ n_N₂,in = 0 (`extent_row`);
T_out − T_in − ΔT̂ = 0 (`offset_row`); P_in − P_out = 0; Q + Ḣ_in − Ḣ_out = 0 by `pr-c1-v1`. These rows are analytic;
the unit never calls the external model. Its manifest declares the external map's derivative `unavailable`.

**D2. The outer coupling.** Route `revision_coupled`, selected when a bound instance is variant-backed. An outer
iteration on w = (X̂, ΔT̂) per external unit: solve the inner EO problem at w (the route's initializer at k = 0, the
previous inner solution afterwards), run one experiment per unit at the solution's exact reactor inlet, form
F(w) = (ξ_E/n_N₂,in, T_E − T_in), and update by Broyden's good method in scaled coordinates (scales 0.1 and 10 K,
B₀ = −I, reset to substitution from the best iterate on no decrease, three step-halvings on an inner failure or a
deterministic external refusal, bounds X̂ ∈ [0, 0.95], ΔT̂ ∈ [−50, 250] K, at most 15 outer iterations).

**D3. Convergence and its floor.** Converged iff, at an iterate whose inner solve converged, every unit has
|ξ_E − X̂ n_N₂,in| ≤ 10⁻⁵ n_tot,in and |T_E − T_in − ΔT̂| ≤ 10⁻² K, the experiments evaluated at that state's inlets.
The tolerances sit ≥ 13 × above the precision floor propagated from ε_eval = 10⁻⁶ and ≥ 56 × below the design grid's
discretization bias; the floor ratios are recorded per check and a ratio below 10 is reported as near threshold
(blueprint §5.2). The certificate carries two `residual` checks per unit (`EXT-COUPLING:<unit>:xi`, `:T`), which also
require the experiment's inputs to equal the certified state's inlet bitwise, and an `external_model` limitation.
Outcomes: `CONVERGED`, `COUPLING_NOT_CONVERGED` (new, with a reason), `EVALUATION_ERROR` (`external_<status>(<unit>)`).

**D4. No sensitivity through the inner problem.** A sensitivity of a `revision_coupled` run is refused
(`PARAMETER_NOT_DIFFERENTIABLE`, `external_map_unavailable`): differentiating the inner problem at pinned w treats the
reactor as fixed-conversion.

**D5. Frozen within an attempt.** The first external call of a job freezes `{variant_sha256, fingerprint_sha256}` per
unit; a child reporting another fingerprint ends the attempt `EVALUATION_ERROR` (`external_environment_changed`).

**D6. R3 and replay from the record.** A run that used an out-of-process variant has `reproducibility_class` R3. Its
bundle holds ADR 0020 D4's files for the final inner solve plus `external-coupling.json`, which embeds every variant,
request, result and attempt of the run and every iterate. `reproduce` re-runs the coupling with a recorded backend that
checks each recomputed request (identity exact, inputs within ADR 0007 D2) before serving the recorded result, and
reports `external_results_replayed_from_record(<n>)`; an in-process variant is re-evaluated and compared. A live rerun
of the reactor is an evidence script, never `reproduce`. An interrupted coupled job emits `partial_solve_trace` and keeps
the experiment artifacts it wrote, nothing else.

**D7. Contract additions (ADR 0019 Amendment 4, part 2).** `run-result.solve_path` gains `revision_coupled`;
`solve-event.outcome` gains `COUPLING_NOT_CONVERGED`; `job` `artifact_ref.kind` gains `external_coupling`.

**D8. C1 revisions bind on `pr-c1-v1`.** `bind_revision_flowsheet` reads `component_set.record_source`; the C1 records'
path binds the C1 provider, components and molecular weights; every other value binds exactly as today.

**D9. Both reactor models are bindable.** `c1.reactor` (variant-backed, `experiment_provider`) and `c1.reactor_standin`
(in-process, synthetic) enter `MODEL_BUILDERS` with the same embedded unit; the envelope lists the stand-in as
synthetic only, with a limitation that it certifies nothing about the reactor (R-199). M01.A49's clause "`MODEL_BUILDERS`
has no key `c1.reactor_standin`" is superseded; its label clauses stand.

**D10. Q-F5.** The real reactor's variant bounds the per-tube flow F_ret_in to [0.5, 2] × 0.007146961299302104 mol/s
(`out_of_domain` outside), through a hard-domain field the `Boundary` reads; the stand-in has no flow bound, so M01's
registered stand-in states are unaffected. The bound is widened to [0.25, 4] × only if both ends are measured accepted.

## Alternatives considered

- **The reactor inside Newton with a finite-difference Jacobian.** Rejected: eight 9 s calls per Jacobian; a finite
  difference is a test oracle (plan §4.2) and carries the map's noise divided by the step.
- **A tear on the full reactor inlet** (seven coordinates). Rejected: the reactor's effect is two numbers; the tear in
  (X̂, ΔT̂) is minimal and its coordinates are intensive.
- **The SYN-001 tear path.** Rejected: it refuses revision flowsheets (R-045) and would need generalizing for one use.
- **Leaving the loop to the agent, or to M05.** Rejected: truth checks at a design point, and blueprint §5.3's frozen
  versions during an attempt, need a solve that calls the reactor more than once; M05's trust region still composes the
  reactor itself.
- **Absolute extent ξ̂ as the coupling coordinate.** Rejected: it scales with the loop flow, so every inner change moves
  it; the conversion X̂ is O(0.1) and weakly coupled.
- **Rerunning the reactor on replay.** Rejected: not "from the bundle alone" (ADR 0024 D5), and needs the environment.
- **Binding only the real reactor.** Rejected: the default gate would have no coverage of the coupled route.
- **A module-level per-tube flow bound.** Rejected: it would refuse M01's registered stand-in states (per-tube flow
  140 × nominal).

## Consequences

- A C1 loop with the real reactor converges in a few outer iterations (expected 4–8 at ≈ 10 s each), every experiment
  recorded and cacheable; with the stand-in, in one iteration.
- The inner problem is re-compiled per outer iteration (its constants change); measured, optimized only if material.
- `model_version` (structural) is the same for a stand-in and a real-reactor revision; the run's identity differs through
  its revision, its constants and its coupling record.

## Migration

None for existing revisions, bundles or stores. Released 0.1.x clients that validate `run-result` or `solve-event`
against 0.1 schemas would reject the new enum values (J5).

## Acceptance evidence

Design note G2 (inertness), G6 (frozen identity), G7 (PR units), G8 (coupled route with the stand-in, replay, an
independent sequential-substitution cross-check at 10⁻⁸), G9 (e) (cache reuse across a rollback), G12 (the real loop,
replay, live rerun).

## Amendment 1 (2026-10-09, M02 review) — the coupled replay's inlet check and the coupling record's floors

**Status:** decided by the design lane (`reviewer`), M02 review `docs/reviews/M02-review.md` §3 rows RP-2 (a) and (b);
register R-317. Transcribed here by WO-13; the review's table is the normative text. Amends D6 and R-308's acceptance.

- **(a) The inlet check.** EXT-COUPLING's bitwise inlet check compares the certified inlet with the inputs of the
  request the answer is attributed to: live, the request sent, bitwise (unchanged); replay, the request
  `RecordedExperiments` recomputes at the rerun's inlet, whose agreement with the recorded one within the archive's
  policy is the replay's guarantee. The rerun record keeps embedding the recorded (served) documents.
- **(b) The floors.** Every float of `experiment.schema.json#/$defs/coupling`, and every envelope field a
  re-evaluation compares, is classified under ADR 0007 D2.2 and D2.3. The floors are the registered thresholds:
  - `rho` is floored at 1;
  - `r_xi` at the record's `coupling_block.tau_xi_rel` (stricter than its exact threshold τ_ξ n_tot/n_N₂);
  - `r_T` at its `tau_T_K`;
  - the envelope's `defect_rel` at 10⁻⁶ (ADR 0027 D3);
  - `defect` and flows at the flow kind's floor;
  - `step.B` and `step.du` are reported, not compared (D2.2's comparability window: secant quantities); their R0
    consequences, step kind and k, stay compared;
  - every other new float is relative.

  The floors are scoped to the coupled record, like R-308's shape rule: the frozen v2 policy file is not edited in a
  way that moves a pinned digest or any pre-M02 comparison. A32, or an M02 twin, enumerates the schema.
- **Rejected** (R-317): an absolute floor of 10⁻⁹ on ρ (an invented floor, which D2.2 rejects); writing the
  recomputed request into the rerun record (it would pair a request that was never sent with a served result);
  descoping cross-platform coupled replay (D2.3 makes the recording package own the classification).
- **Acceptance evidence:** RP-2 passes without an xfail, and a second case runs on a w-dependent synthetic loop
  (review F1, F2, F4; build log D120, D121, D127). The rules live in M02's addendum
  `benchmarks/m02/numerical_policy_external.yaml` (`compare`, read at run time).

