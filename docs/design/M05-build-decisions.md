# M05 build-lane decisions log (WO-2b, WO-3b, WO-4a onward)

Choices the design note's §17 rulings (R-296 to R-300) leave open, each with its alternative and how to revert it.
Earlier M05 build decisions are §17.5's E1-E7 (R-300). Numbers are measured; nothing here is a ruling.

## WO-2b — `M05-zero-flow-v1` (§17.1, R-296)

Z1 A pin's final-state tolerance ("the row's tolerance", §17.1 step 5) is 0.0 (`ZERO_PIN_TOLERANCE`): the pin has
   incidence {j} and j is the constant +0.0, so it holds exactly by construction; any nonzero residual means the pin
   moved with the decisions. The spec carries no per-row tolerance and R-274's `pressure_tolerance` is a pressure.
   Alternative: a scaled tolerance τ·S_F. Reversible: the constant.
Z2 ESCALATED. SYN-001 holds exact-zero flows at three registered states, and the rule cannot pair them:
   P1, P2 — S3.vap.{A,B,C}, S3.V (the heater-flash in its liquid regime); B2 — S4.n.{A,B,C}, S4.N (the flash's vapor
   product). Each sits in its equilibrium row (with L, liq, V and the lnK block output) and in a split or
   total-flow row (V − Σvap); no row holds one alone, so the projection refuses `PROJECTION_ZERO_FLOW(S3.vap.A:unpinned)`
   (P1, P2) and `(S4.n.A:unpinned)` (B2). §17.1 (f) expected (a)-(c) to apply to them. As built, the rule is
   applied literally; the SYN-001 tests at P1, P2, B2 (alias rows, DOF, G4, R-278, K03 scales, the two supplied-set
   tests at P1) are strict xfails, and `test_r296_syn001_s_unpinned_zero_flows_are_refused` pins the refusals.
   Needed from the design lane: whether SYN-001 at these states is refused (it is not a TRF case), the rule gains a
   joint pin (e.g. a square block of rows on Z₀ certified as a unit), or SYN-001 is exempt. P3, B1, B3 hold no
   exact-zero flow and are unchanged. Reversible: the xfail markers in tests/test_m05_projection.py.
Z3 Criterion (ii)'s ∂r_e/∂x_j is the projection's own total x-Jacobian at x₀ (`_row_derivatives`, Pyomo reverse
   mode plus the blocks' Jacobians), not a CasADi compile inside `project()`. G4's `equivalence` now checks each pin
   against CasADi: residual at x₀ == 0.0 and |dr_dx − J_CasADi| ≤ 1e-10 (|J| + 1); measured ratio 0.0 on C1 (S0 and
   perturbed) and on the toy. Reversible: `_eliminate_zero_flows`.
Z4 A row's structural incidence is the shape check's unknowns its expression contains (`x`, `y`, `w`), never the
   decisions; criterion (iii) is ∂r_e/∂d == 0.0 for every decision (a link variable in a row puts it in the
   incidence, so a pin's link tangent is structurally zero).
Z5 `redundant_row` is a kept row, not a pin, whose incidence meets E and has nothing left outside it. Read literally
   ("incidence minus E is empty") it would also refuse a row that never had an unknown (TR-E1's decisions-only
   `c2`) in any spec that holds a zero flow. Reversible: one condition in `_eliminate_zero_flows`.
Z6 Build: with E ≠ ∅ `project()` assembles twice — R-274's set and the pairing on a model with every variable, then
   the model TRF sees with the constants (only then is `model.x` indexed by the projected positions). With E = ∅ the
   model is built once, as before. Bit-identity at the old configurations, dumped before and after (source map less
   the new key, every constraint's expression string, row values at x₀, variables with bounds and values, suffixes,
   component list): identical for TR-E1, the link toy, AT, SYN-001 P3/B1/B3.
Z7 Records: the source map gains `zero_eliminated` (variable order; `[]` when none) and lists an eliminated flow
   among `variables` with `pyomo: null`; `Projection.state_of` is the inverse map; `TrfRun` gains `final_state`
   (the inverse map at the returned state) and `zero_pins_final` (`Projection.zero_pins_at`, P2's hook beside
   `omitted_rows_final`). The affine basis builds no term for a float argument and refuses one that differs from
   its w0 (`ValueError`).
Z8 C1 TR-E2, measured: the five pairs are `S1.n.NH3`↔`makeup:C1FEED-n:NH3` and `S6.n.{H2,N2,Ar,CH4}`↔
   `flash:C1FL-equilibrium:<gas>` (the flash's `zero_row`, built in the light gases' equilibrium slots), each with
   residual 0.0 and dr_dx 1.0; matching 68 × 68, DOF 1, 57 rows. G4 worst ratios at S0 / perturbed S0: residual
   3.70e-5 / 7.40e-5, Jacobian 0.0 / 0.0, decision 4.21e-3 / 4.21e-3, pin 0.0 / 0.0 (identical to before R-296).
   TR-E2 TRF check (once, `TRF_CONFIG_V1`, step_size_termination 0.0125, `m05_basis`): before, `TRF_TRUTH_REFUSED(
   property_domain_error:S1_Hdot_V)` before iteration 1; now `TRF_MAX_ITERATIONS` after 30 iterations, θ_recheck
   4.01e-4, T_spec 673.667 K, no refusal, the pins hold at the returned state, and all 1395 argument positions of
   the eliminated flows in the requests were +0.0 bitwise. WO-8 owns TR-E2's acceptance.

## WO-3b — `TRF_STALLED_INCONSISTENT` for an "Optimal" exit (§17.4, R-299)

W1 Inside an "Optimal" line the line-against-log check comes first: a line whose own last logged θ or step is beyond
   the terminations stays `TRF_ERROR(exit_mismatch)` whatever θ_recheck is (the ruling keeps exit_mismatch's meaning:
   parser or framework drift, never retried); only a line its log agrees with is judged by θ_recheck
   (`TRF_STALLED_INCONSISTENT` above the tolerance), and that precedes `TRF_EXIT_WITHOUT_STEP`. Alternative: θ_recheck
   first. Reversible: `trf_state.classify_exit`.
W2 OPEN. `TRF_MAX_ITERATIONS` (no `EXIT:` line, so no claim) is unchanged when θ_recheck exceeds the tolerance: it
   keeps its clone and a candidate, which P1/P2 then judge. §17.4's precedence names the EXIT claims only. The TR-E2
   check after WO-2b ends exactly so (θ_recheck 4.01e-4). For the design lane: should a max-iterations exit with
   θ_recheck > 1e-5 also be `TRF_STALLED_INCONSISTENT` (an abort with a retry) rather than a candidate?
W3 The threshold is the run's `feasibility_termination` (1e-5 in `M05-trf-config-v1` and in Pyomo's defaults), as
   R-279's rule for "Feasible" already reads it.
W4 `final_state_is_last_truth_point` is judged per holder (every EF is one of TRF's truth models): the returned state's
   inputs, through the inverse map, hashed as the memo keys them (canonical binary64, zeros normalized), against the
   holder's last ledger entry before the re-check. `exit_claim`, `theta_logged` (the last logged iteration's θ) and
   this flag are recorded on every run TRF returned from, not only on `TRF_STALLED_INCONSISTENT`.
W5 §17.4's acceptance test moves one of TRF's holder variables (`trf_data.ef_outputs`) by 1e-3 after `solve` returns
   (P14 (b)'s converging toy): "Optimal" with an agreeing log, θ_recheck 1e-3, `TRF_STALLED_INCONSISTENT`,
   `exit_claim: optimal`, `final_state_is_last_truth_point: true`. The retry itself (§7.3, once with radius × ¼) is
   WO-6's study loop, not built yet.

## WO-4a — `M05-fd-v2` (§17.2, R-297), TR-E1's tolerance (§17.3, R-298), E2's guard (§17.5, R-300)

F1 The check's per-column sides are pinned at w₀ in `ForwardDifference.pinned_sides` (keyed by the exact w₀ tuple):
   `points()` takes explicit sides, else the pinned ones at that exact w, else v1's side rule at the step — so the
   basis gradient at w₀ is the check's G(η) (seven memo hits) and every other point is unchanged. Alternative: pass
   the sides through the holder. Reversible: `truths.ForwardDifference`.
F2 The base value d(w₀) keeps purpose `fdcheck_point`, so the ledger shows 1 + 7·(3 + e) check requests; §17.2's
   "7·(3 + e)" counts the FD points.
F3 After a failed candidate: the last candidate ends the check (`exhausted`); from the second candidate on, ν̂ not
   halved ends it (`noise_not_falling`); then the next candidate's largest step (16η·m_j for η ← 4η) is tried on the
   chosen sides (`side_limit`); then G(4η) is added. `stopped` records which (`passed` on a pass). The candidates are
   the policy's η times 4^k (2⁻¹⁴, 2⁻¹², 2⁻¹⁰ by default).
F4 E2's guard: M02's coupled-route path (`application/coupled_run.answer_of`, `orchestrator/coupling._unit_terms`) is
   on `wp/M02` only. The test calls it at w = (0, 0), where r = F(w) − w is F bitwise, at TR-E2's start inlet and
   the n_N₂ and T FD points, and is a strict xfail with `raises=ModuleNotFoundError` on `wp/M05`: when the branches
   meet it XPASSes (strict, so the marker must go) or fails on its assertion. Alternative: a copy of M02's arithmetic,
   which is not "M02's own code path". Reversible: the marker.
F5 `GradientCheck`: `comparisons` became `candidates` ({eta, g_inf, truncation, noise, allowance, class}); added
   `sides`, `selected_class`, `stopped`, `half_steps` (½h_j at the selected η, by coordinate) and `scaled` (G at
   every step). `as_document()` is §17.2's `fd_check` record (G11).
F6 v1's escalation regression test (its numbers measured v1's criterion) is replaced by tests of the three stops:
   `noise_not_falling` (curvature k = 5000: ν̂ fails at 2⁻¹⁴ and grows at 2⁻¹²; proceeds at 2⁻¹⁴, `fd_unstable`,
   1 + 7·4 requests), `side_limit`, and one side for all three steps of a column.
Measured (synthetic truth, TR-E2's start inlet): (i) Richardson error 1.25e-6 ≤ 1e-5·max(1, ‖G_exact‖) (predicted
   5e-7); (ii) ‖G(η) − G_exact‖_∞ 0.04980 ≤ 2τ̂ + 1e-6 = 0.0996 (τ̂ 0.04980); (iii) ν̂ 3.67e-6 ≤ allowance 2.27e-3,
   τ̂ above it: passes at 2⁻¹⁴, `truncation_dominated`, no escalation; (iv) with 1e-6 pseudo-noise ν̂ = 0.0221
   (2⁻¹⁴, `noise_dominated`), 0.00511 (2⁻¹², `noise_dominated`), 0.00122 (2⁻¹⁰, `truncation_dominated`: passes
   there). §17.3: TR-E1 affine against native ‖Δz‖_∞ 1.18e-6 ≤ 2e-5 (margin 17), |ΔJ|/max(1, |J|) 1.2e-11, both
   `TRF_CONVERGED` with θ_recheck ≤ 1e-5.

## WO-6 — checks, the study loop, readiness (§7.2-§7.5, §6.8, §16.4, §16.5, §17.4)

S1 REAL box: `study.REAL_BOX` is [653.15, 693.15] K (R-313, M02 seventh round: M05's REAL box unconditionally; ADR 0039
   D1's [643.15, 733.15] K is superseded there, not by M05). σ for REAL becomes 0.5·0.5/20 = 0.0125, as TR-E2's; §6.7's
   0.005556 is stale text for the design lane. Reversible: the constant and one test assertion.
S2 `LINK_BOUNDS` and `LINK_COORDINATES` move from `projection` to `holders` (Pyomo-free) and `projection` imports them:
   P3 (§7.4) reads the admissibility bounds on (X̂, ΔT̂) in the default install. Same object, same values; the M05
   `nlp` tier is unchanged. Reversible: the move.
S3 The real parent adapter is not built here. §7.4's checks solve through `run_revision_session` on
   `revision_coupled`, which is `wp/M02`'s (`application/coupled_run.py`, with `EXT-COUPLING`'s achieved residuals);
   `wp/M05` has neither. `checks.py` reads the parent through the `Parent` protocol (`solve` → `ParentSolve`:
   outcome, certificate, J, state, converged w, achieved (ΔX, ΔT), regimes, P3's `ConstraintValue`s,
   executions/store hits, record sha256; `inner_objective(solve, w)`), so WO-5c (after M02 merges) or WO-8 adds the
   adapter: `pinned_at` (the one `with_coupling` site, R-309's swap to `at_coupling`) and `c1_constraint_values`
   are its parts. The loop and checks are tested on fakes; the readiness projection/start halves and `TrfStage`
   in the `nlp` tier.
S4 Check evaluation (§7.4 "all evaluated results are recorded, the status is the first failure"): a failed P1 stops
   (no certified state); P4, P3 and P2 cost no solve and are always evaluated together; P5 (2 coupled + 4 inner
   solves) only when all three pass, since only such a candidate consumes the poll. Alternative: always poll.
   Reversible: `checks.check_candidate`. P2 on a candidate no TRF run produced (S0) is `pass: null`.
S5 P3's scales (§7.4 "within 1e-9 × its scale"; the formulation has no inequality scale): an expression row
   max(|bound|, F) with F the reactor-inlet Σn (Σn/N_tubes for the per-tube rows); a bound max(|bound|, 1) in the
   variable's unit. The bounds checked: the decision box, the variant's inlet T/P, the link bounds, the provider
   domain on every T and P, molar flows ≥ 0. A parent that evaluated no constraint fails P3. Reversible:
   `study.c1_constraint_values`.
S6 Stage A (§7.3 gives the retry and the `FAILED(trf_aborted)` stop for stage C only): A is retried the same way;
   a second abort is recorded (`stage_a.outcome`) and stage C starts from S0, since stage A only accelerates the
   parent study; a defect (`TRF_ERROR`) or the study budget still stops it. Alternative: stop
   `FAILED(trf_aborted:<outcome>)` as in C. Reversible: this commit (`run_study`'s stage-A branch and one test).
S7 Retry and aborts (§7.3, §6.7, §17.4): a candidate from every `RETURNS_MODEL` outcome (`TRF_MAX_ITERATIONS`
   whatever θ_recheck: W2's current behaviour, unchanged, no separate commit needed); `TRF_ERROR(*)` a defect,
   `FAILED(trf_aborted:<outcome>)` at once, never retried; `TRF_TRUTH_REFUSED(budget:budget_exhausted)` is
   `BUDGET_EXHAUSTED` when the study cap is reached and an abort (retried) when only the run's 250 cap is; every
   other no-model outcome an abort. Reversible: `study.disposition`.
S8 Budgets: one `ColdBudget("study")` shared by the parent holders (live) and charged with each parent solve's
   executions and, after a run, an in-process truth's cold value requests (its holder takes no parent budget,
   R-300 E4); exhaustion (cold or wall) is checked before S0, every run, every parent solve and the noise floor.
   The record's accounting: `trf_cold` by run, `parent_executions`/`store_hits` by solve, by stage (S0, A, C, B), by
   study iteration (S0 and A are 0) and by candidate (its runs including an aborted try, and its check solves).
S9 Stage A's argmax (§7.3) takes S0 unconditionally (it is `best` before A; checked P1 only) and u_A and A's poll
   points only when they pass P1, P3 and P4. Stage C's restart takes the best feasible (P1, P3) poll point, as written.
S10 Readiness: the framework half first; `TRUST_REGION_FRAMEWORK_UNAVAILABLE` returns alone (the default install).
   Otherwise every reason: the start half (P1 → `START_NOT_CERTIFIED`) and the projection half on any start with a
   state. The projection reasons are §6.8's four plus the later rulings' four (`PROJECTION_SCALES_UNAVAILABLE`,
   `_IMPLICIT_EF_INPUT`, `_OMITTED_ROW_UNCERTIFIED`, `_ZERO_FLOW`); `project` raises the first refusal only. In
   `run_study` the start half is S0 (`FAILED(start_not_certified)`, §7.2) and a projection refusal at S0 is
   `UNSUPPORTED(<code>)`.

## WO-7 — the record schema `trust-region-study-v1` (§9.1, §8.3, G12)

All items go to M05's review batch.

S11 The schema's four new `sha256` names (`revision_sha256`, `source_map_sha256`, `trf_module_sha256`,
   `trsp_executable_sha256`) are unclassified under ADR 0025 D2.3 (`t08_numerical_policy.py --check`). M02's
   precedent (dbc9e8a): an addendum `benchmarks/m05/numerical_policy_external.yaml`
   (`M05-numerical-policy-external-v1`) classifies all four `exact_sha256`, and `--check` audits every addendum in
   `ADDENDA` in turn (a name v2 or an earlier addendum classified keeps its class; no schema claimed twice). v2's
   content does not move (regenerated sha256 6b449911…707c before and after); for M02 the old and new scripts give
   identical `build` bytes, name sets, audit results and `--check` output. Alternative: a v3 policy. Reversible:
   revert c6c229e (and the float rules of S17, which live in the same file).
S12 `runs[].ledger`: §9.1 says `{sha256, summary}`; `TrfStage` writes `{summary, cold_parent}` (the ledger itself
   is the `artifacts.ledger` file). The schema requires `summary`, allows `sha256` and `cold_parent`. Alternative:
   the producer adds the ledger's sha256 and the schema requires it. Reversible: one `required` list.
S13 `readiness`, `start`, `stage_a` and `best` are top-level fields `as_document` writes that §9.1 does not list;
   declared and optional (`readiness` and `start` null when absent). Alternative: amend §9.1 or nest them.
S14 The top level and `accounting`, `claims`, `checks` are closed; `spec`, `environment`, a run, a candidate,
   `projection`, `final` and `artifacts` require §9.1's fields and tolerate the producer's extras (a run's
   `config`, `exit_lines`, `theta_recheck`, …; a candidate's `stage`, `stopped_by`, `solves`). Alternative: close
   them and declare every extra.
S15 `indifference_halfwidth` is an object (decision → number or null) or null: §9.1's "| null" is read as the
   per-decision value, which is what the producer writes; the whole field null is also accepted.
S16 §8.3's TRF request identity (`trf_start_value` = 1, `trf_trial_value` = K, …) is not checked by WO-7: the
   ledger summary is counts by call and service (`value_cold`, `jacobian_memo_hit`, …), with no per-purpose counts.
   Deferred to WO-8, which has the ledger artifacts (or needs a per-purpose summary from the holder).
S17 Float classes (ADR 0007 D2.3; M02's four classes, D14 "replay classes follow M02"; §9.3): `exact` for the spec,
   the start decisions, the run's `config` and `radius_factor`, the noise floor's `h_X`/`h_T`, the budget's
   `study_wall_s`; `excluded` for `wall_s`; `r1_r2_existing_floors` for every TRF iterate, parent-solve objective,
   coupling, residual and everything derived (P-values, poll, noise floor, curvature, half-width, best). No float
   of the record is an external model's output, so `r3_recorded_external` has no rule. A test holds every float
   of every generated (and committed) record to a rule, and every rule to a float.
S18 Producer-vs-§9.1 gaps fixed in the schema: iteration 0 is the PMP and `TrfStage` writes `type: null` for it
   (§9.1's enum has no value for it): null at k = 0, a §9.1 type at k ≥ 1. A check that does not apply (P2 without a
   TRF point, `checks.py`) is `pass: null`. Digests follow the schemas' `^[0-9a-f]{64}$` (the fakes now give real
   hex). Open: `artifacts.coupled_runs[].sha256` is required, but `ParentSolve.coupling_record_sha256` is None for a
   parent with no external unit; the C1 parent always has one.

## WO-5c — `pinned_at` on M02's `at_coupling` (§17.5 E7 as superseded by R-309)

S19 `revision_binding.with_coupling` is deleted and `revision_binding.py` is main's again (WO-5b's cherry-pick never
   landed: M02 merged first). `study.pinned_at` calls `coupled_run.at_coupling(binding, {unit_id: (X̂, ΔT̂)})` with
   both coerced by `float()`, as `with_coupling` did, so the units receive Python floats bit for bit. The reference
   support and the C1 projection test call `at_coupling` directly (the reference stays independent of M05's
   library); the accessor's refusal test is dropped (M02's AC-1 holds `at_coupling`'s, R-309). Inertness, before the
   deletion: `with_coupling` against `at_coupling` at four w (W*, the document's own (0.15, 80), (0.2, 55.5) and one
   ulp-scale move) gave the same compiled identity (model_version, constants_sha256), equal spec parameters and a
   bitwise-equal inner solve (every state float's hex); `test_m05_c1_reference` keeps the proof for `pinned_at`
   against M02's WO-9 helper. F4's strict xfail XPASSed at the merge (fae2785) and was removed there.
   Measured: M05 `nlp` tier in a freshly built audited environment 121 passed, 15 xfailed (WO-6's counts); the
   NLP-1 inventory `--check` fails on three objects (`libssl.so.3`, `_ssl`, `_queue`) that the project-wide import
   walk now loads — the same imports exist at 71804a6, so the recorded M03 inventory predates them (not WO-5c's).

## S3 — the real C1 parent adapter (§7.4, §7.2, §6.4)

S20 `DecisionSpec`, `ExternalLinkSpec`, `InequalitySpec` and `ObjectiveSpec` move from `projection` to `holders`
   (Pyomo-free) and `projection` imports them: `c1_formulation` imported them from `projection`, so it needed Pyomo,
   and the parent's P3 (`c1_constraint_values`) reads the formulation in the default install. Same objects, same
   fields, as S2 did for the link bounds; the `nlp` tier is unchanged. Alternative: the parent builds its P3 rows
   without the formulation (a second copy of §7.1). Reversible: the move.
S21 `studies/trust_region/parent.py`, `C1Parent(document, runner, box)`: the `Parent` protocol on a C1 revision.
   The decision edits the specification the binding's `specification_pins` name for the heater's outlet T (on the
   stand-in loop `SPEC-S3-T`); P1 is the route's outcome and certificate; the parent truth is
   `ParentExperimentTruth` on the same runner (§6.4: one runner per study); `project_at` pins the start's revision at
   its converged w and projects at its certified state (§7.2). REAL is `c1-loop-real.json` (reactor v3) with
   `study.REAL_BOX`. Reversible: the module (nothing else imports it yet).
S22 The solve goes through `revision_run.solve_route`, the solve `run_revision_session` wraps, not
   `run_revision_session` itself (§7.4 names it): no bundle is written per check and nothing is committed. The
   record's `coupled_runs[].sha256` is the sha256 of `external-coupling.json` as solved. Alternative: a bundle per
   solve under the study's artifact directory (replay, G10), which WO-8 may want. Reversible: `C1Parent.solve`.
S23 (ΔX, ΔT): the certificate's `EXT-COUPLING:<unit>:xi` value is |ξ_E − X̂ n_N₂,in| / n_tot,in (M02 §4.4); §7.4's
   ΔX is per n_N₂,in, so the value is multiplied by n_tot,in / n_N₂,in (`coupled_run.inlet_of` at the certified
   state). ΔT is the `:T` value as is. Test: equal to the record-recomputed |ξ_E − X̂ n_N₂| / n_N₂ within 1e-12
   relative, ΔT bitwise.
S24 P4's labels (design question; §7.4 says "every unit's phase regime label" without a source): each non-external
   unit's own causal `evaluate` on its inlets read from the certified state, labelled by `phase_signature` ("none"
   when a unit reports none; "status:<s>" when not ok); the reactor is not labelled (its regime is its experiment's).
   On the stand-in loop: flash TWO_PHASE, mixer and preheater VAPOR, sources/sinks/splitter none. Alternatives: the
   certificate's `phase_branch` (streams FLOWING/ZERO_FLOW and raw split values, no regime label), or the flash's
   `phase.classify` only. Reversible: `parent.unit_regimes`.
S25 The inner objective (§7.4's central differences) solves the inner problem from the solve's certified state
   (`user_start`, as M02's inner solves after k = 0), and is NaN when that solve fails, so e* is NaN and P5 cannot
   pass (the safe failure). At the solve's own w it is J within 1 ulp on the stand-in (5.6e-17), not bitwise.
   Alternative: the route initializer at every point (M02's k = 0 start). Reversible: `C1Parent.inner_objective`.
S26 A solve's limitations: `synthetic` for a synthetic variant (the stand-in is), `extrapolated` when the final
   iterate's experiment envelope has `domain_status: extrapolated`. A route refusal is `unsupported(<code>)`, a
   verifier refusal `verifier_refused(<message>)`, both returned (P1 fails), never raised.
   Measured on the stand-in loop at 673.15 K: CONVERGED/VERIFIED, 2 executions on a fresh store, then 0 executions
   and 2 store hits; J = 0.467059584925130 mol/s, w = (0.25 − 1 ulp, 0), (ΔX, ΔT) = (0, 0); stage B
   `PARENT_LOCAL_EVIDENCE` (∂J/∂X̂ = 0.1517, ∂J/∂ΔT̂ = 0, e* = 0; the stand-in's J does not depend on T_in, poll
   differences ≤ 1 ulp).
   Real reactor v3 (`c1-loop-real.json`, opt-in `pymrm`) at 673.15 K: CONVERGED/VERIFIED in 164 s, 4 executions,
   J = 0.449325948913493 mol/s, w = (0.168388, 78.670 K), (ΔX, ΔT) = (4.40e-6, 2.92e-3 K), the same regime labels as
   the stand-in, P3 passes, no `extrapolated` (the final experiment's `domain_status` is not `extrapolated`).

## WO-2c — `M05-zero-flow-v2`: joint zero-flow pins (§18.1, R-326)

S27 N_e for a `y` (block output) or `w` (link output) column: §18.1 step 1 computes N_e "from the same total
   x-Jacobian", which has no `y`/`w` column, yet a row's structural incidence holds them (SYN-001's equilibrium rows
   read `lnK` as a block output). A `y`/`w` column is in N_e iff the row's own partial in it (Pyomo reverse mode at
   x₀) is ≠ 0.0; such a column is never a zero flow, so the row is then no candidate. `x` columns use the total
   x-Jacobian as ruled. Ignoring `y`/`w` instead would let a row whose block output carries a nonzero dependence
   through block inputs outside its incidence pass as a candidate. Reversible: `_joint_blocks`.
S28 (c)'s perturbation coordinates: ξ = `default_rng(20261009).uniform(-1, 1, n_x + n_y + n_w + n_d)`, drawn over
   x (variable order, so its first n_x values are G4's draw), y, w, then d. A decision moves in its model
   coordinate d (center + half_width·d when bounded) with s_k = 1, the column scale `_certify` uses for d; y and w
   use their output scales. Reversible: `_persistence_rows`.
S29 §17.1 (e)'s `unpinned` toy (n0's pin decision-dependent, `copy` = n1 − n0) now refuses
   `PROJECTION_ZERO_FLOW(n0:joint_not_square)`: `copy` is a joint candidate on {n0, n1}, a 1 × 2 block, and §18.1
   step 3 (a) refuses it. The test keeps that fixture under the new reason; `unpinned` is pinned by the same toy with
   `copy` also reading m (∂/∂m = 1), so no row is a candidate. Readiness's PROJECTION_ZERO_FLOW fixture (code only)
   is unchanged. Reversible: the two tests.
S30 Blocks are numbered 0, 1, … in certification order across passes (`block`); within a pass blocks are certified
   in order and the first failing one refuses at once (the components are disjoint, so a later certification cannot
   change it). Reversible: `_eliminate_zero_flows`.
S31 G4's `equivalence` checks each joint block against CasADi: rows' residuals at x₀ == 0.0 == recorded, no entry
   outside the block among the projected columns (§18.1's LICQ structure), and the scaled block's rcond within 1e-8
   relative of the recorded one (`joint` ratio). A joint entry is skipped by the single-pin check.
Measured (WO-2c acceptance):
   (a) P1/P2: one block, S3.vap.{A,B,C}, S3.V × U-HEAT:HEAT-equilibrium:{A,B,C}, U-HEAT:Vdef; B2: S4.n.{A,B,C},
   S4.N × U-FLASH:FLASH-equilibrium:{A,B,C}, U-FLASH:Ndef:vapor. rcond (F-12) P1 7.663e-3, P2 1.417e-2,
   B2 5.203e-6; residuals_x0 all 0.0, persistence_max_abs 0.0. No other block or refusal.
   (b) DOF 5 at all three; R-278 matching 70 × 70 = P3's 74 − 4. 49 rows − 2 alias − 4 pins = 43 projected.
   (c) the 15 strict xfails pass unmarked; `test_r326_…_one_certified_block` replaces the refusal test.
   (d) G4 worst ratios P1 / P2 / B2: residual 7.40e-5 / 5.92e-4 / 7.40e-5; Jacobian 5.42e-10 / 4.32e-9 / 7.11e-7;
   decision 2.30e-3 (all three); joint 0.0 (CasADi's rcond bitwise equal).
   (e) Inertness, Z6's dumps (source map less `zero_blocks`, every constraint's expression and value at x₀ in hex,
   variables with bounds/values, suffixes, component list) before (75cdc3b) and after: byte-identical for C1 TR-E2
   S0 and perturbed S0, TR-E1, the link toy, AT, SYN-001 P3, B1, B3; reproducible run to run.
   (f) toys: `joint_not_square` (z1 − z2), `joint_singular` (z1 + z2, 2z1 + 2z2; rcond 4.97e-17),
   `joint_not_persistent` (z1 − z2, z1 + z2 + (y − y₀)²; max |r| 6.75e-6), each through readiness; a certified
   2 × 2 toy block whose row reads y with partial 0.0 at x₀ passes DOF, matching 3 × 3 and G4.

## WO-6b — §18.2 (R-327), S15, S16 (holder), S18 (R-329)

S32 `pmp_point_equals_start` (S16) is evidence, not the complement of the count: true iff the run's ledger holds a
   Jacobian request at `trf_iteration` 0 (before iteration 0 is logged: only TRF's PMP gradient, §8.3 step 3; the
   pre-flight requests values only) at the `trf_start_value` request's key. `by_purpose` counts every request whose
   purpose is one of §8.1's five or `basis_fd_point`, zeros included. Reversible: `EFHolder.summary`.
S33 OPEN (for the review batch; affects G6/G12's identity, not numerics). The affine basis is formed by
   `TrfStageRunner` before `run_trf` begins the holders' run, so its requests (value and `basis_fd_point` FD points
   at w₀) carry `run_id` null and no run's `by_purpose` counts them: §8.3's `basis_fd_point` = n_in cannot hold per
   run as built. Default: attribute them to the run (begin the holders' run before forming the basis) in WO-8's
   preparation, with the identity test catching it; alternative: the identity reads the basis requests by stage.
   Not changed here.
S34 `TrfPoint` gains the required fields `theta_recheck` and `feasibility_termination` (after `column_scales`); the
   study reads the latter from `TrfRun.feasibility_termination`, the value of TRF's effective configuration the run
   used (W3's 1e-5; a stage configuration may omit it and take TRF's default). P2 is judged iff θ_recheck ≤ feasibility_termination
   (a NaN θ is not judged). Unjudged P2 records `pass: null` with every value computed plus both thresholds.
S35 P2's document is `{pass, judged, reason, values}`; only P2 carries `judged`/`reason` (`CheckResult`). The two
   fields and the top-level `fd_check` (the caller's §17.2 document or null, `as_document(fd_check=…)`) are
   declared in the schema in this commit, because its closed objects reject them; the rest of S12–S16 is WO-7b.
S36 OPEN (schema, WO-7b). S15 rules each half-width value > 0, but √(2(e* + max e_j)/|c|) is exactly 0.0 for a
   parent with no noise (e* = e_j = 0: the stand-in loop, the fakes). The producer is unchanged; default for WO-7b:
   the schema's half-width values are ≥ 0 (or null), alternative: > 0 with a zero-noise parent writing null.
Measured: §18.2 (a) θ_recheck 4.01e-4, P2 values failing (objective_error 2e-3·|J*| > bound): candidate
   PARENT_LOCAL_EVIDENCE, P2 {null, false, "theta_recheck"}, limitation `trf_max_iterations`; (b) θ = 1e-5:
   PROJECTION_DISAGREES, P2 judged; (c) P5 runs after an unjudged P2, not after P3 false (half-width null).

## S33 applied — the basis is formed inside the holders' run (default of S33)

S37 S33's default, as an isolated commit (accounting, not numerics; for the review batch). `run_trf` takes the basis
   as a mapping or as a builder; `TrfStage` passes its builder, which `_run` calls after `begin_run` and before the
   pre-flight, with `RunState.forming_basis` set. The basis's requests then carry the run id and are admitted against
   the run's budgets; while forming they get no call-order purpose, no `trf_iteration` (null: not TRF's, so S32's
   `pmp_point_equals_start` does not see the basis Jacobian at w₀) and do not make a key the run's first (TRF's start
   stays `trf_start_value`). A built basis is judged by `basis_refusals` when built. Consequences: per-run
   `basis_fd_point` = n_in holds; the basis's cold requests now count in the run's `value_cold` (and so in
   `cold_parent` or the in-process charge, §7.5) and can be refused by an exhausted budget, which before they could
   not. Alternative: the identity reads basis requests by stage. Reversible: revert the commit.
   Measured (FD link toy, `TrfStage`, radius factors 1 and ¼): the run document is byte-identical before/after
   (hex dump `cmp`), and so is the TRF-phase ledger (call, key, served, iteration, purpose, status for all 35
   entries); the summary moves `basis_fd_point` 0 → 7 and `value_cold` 8 → 16, `trf_start_value` 1,
   `pmp_point_equals_start` false unchanged. Test: `test_the_stage_forms_the_basis_inside_the_holders_run`.

## WO-7b — the record schema rulings S12–S16, S18 (§18.4, R-329)

S38 S36's default, as its own commit (schema only, for the review batch): `indifference_halfwidth`'s values are
   `number` with `minimum: 0`, or null, not S15's `> 0`: √(2(e* + max e_j)/|c|) is exactly 0.0 for a parent with no
   noise (e* = e_j = 0: the stand-in loop, the fakes). The producer is unchanged. Alternative: `exclusiveMinimum: 0`
   with a zero-noise parent writing null (a producer change). Reversible: revert the commit. Tests: a value −1e-12
   fails, 0.0 validates (`test_the_schema_rejects` / `_accepts`); targeted 138 passed.
S39 S14's closure, the conventions (schema only). A closed object requires every field its producer always writes
   (beyond §9.1's), so a dropped field fails as an undeclared one does; 51 closed objects, each with an
   undeclared-field case (`CLOSED_OBJECTS`). Id-keyed maps constrain only their values: decisions, holder
   summaries, EF basis kinds (`EFBasis.kind`'s four), TRF `config` (option → scalar), regimes, P4's `changed`
   (unit → {reference, found}), `half_steps`, the accounting tables, `trf_module_sha256`. Choices a review may
   reverse: (a) `spec`'s inner contents (`decisions[]`, `objective`, `inequalities[]`, `decision_tolerances`,
   `budgets`) stay as typed, because no producer writes a spec at this head (the caller's, WO-8); `spec`,
   `configs`, `truth`, `surrogate` and `environment` are closed at §9.1's fields. (b) A truth identity
   (`runs[].truth[]`, `$defs/truth_identity`) requires `kind`, `id`, `sha256` (or null) and `gradient`
   (`analytic` | `finite_difference`, the holder's FD switch, needed by G12); `synthetic` is optional (the parent
   writes it, the test truths do not); `spec.truth` gains `gradient` as optional. (c) `stage_a` is the closed
   object, null, or `{}`: the producer's default when the study stops before stage A (UNSUPPORTED, start not
   certified, exhausted at S0) — the ruling's "object or null" with the producer unchanged. (d)
   `artifacts.source_map` is declared but untyped (no producer). `fd_check` is closed at
   `GradientCheck.as_document`'s keys. Alternative to (a): close them on the fixture's shapes now. Reversible:
   the schema's `spec` block, one `anyOf` branch for (c).
S40 Declaring `start`/`solves[]` (`ParentSolve.as_document`) adds the sha256 name `coupling_record_sha256`, which
   ADR 0025 D2.3's partition then reports unclassified (`t08_numerical_policy.py --check`; neither v2 nor M02's
   addendum classifies it). The M05 addendum classifies it `exact_sha256`, as S11 did the other four (a digest of
   an M02 coupling record, not of a float). v2's regenerated sha256 is unchanged (6b449911…707c); `--check` exits
   0. The partition test drops `revision_sha256` by name, not as the list's first entry. Interlocked with the
   schema (the audit also refuses a classified name the schema does not declare), so it is in the same commit.
   Alternative: leave `start` untyped (contradicts S14). For the review batch (classification, replay identity).
S41 G12's checker `request_identity_violations` (test file): a run has an FD truth iff a `truth` entry has
   `gradient: finite_difference`. `truth` (a list) and `ledger.summary` (by holder name) come from the same holder
   loop but share no key, so the FD truth is attributed to the summary only when it is the run's one truth and one
   summary; otherwise the checker reports the run as unattributable (fails, never skips). Alternative: pair by
   position (relies on JSON key order) or the producer adds the holder name to each truth entry (a producer
   change, for the review batch). The five equalities as §8.3: `trf_pmp_value` is checked as
   `0 if pmp_point_equals_start else 1` (the stricter reading: with the flag the PMP point adds no key);
   `basis_fd_point` = n_in is not asserted for a run whose basis has a `surrogate` kind (§8.3/§6.6 state it only
   without a promoted surrogate); runs that raised are included (the brief: every run with an FD truth). K counts
   logged k ≥ 1, A the `f`/`theta` steps (`accepted_steps`). `FullStage` now writes an FD truth whose summary
   satisfies the identity, so every generated record goes through G12 (and `COMMITTED_RECORDS`, none yet).
   Live check (nlp, `test_the_live_run_document_validates_and_holds_the_request_identity`): `TrfStage` on the FD
   link toy at radius factors 1 and ¼ gives a valid closed `runs[]` entry and holds the identity (the toy stops
   at the PMP: K = 0, A = 0, so `trf_fd_point` = 7, `basis_fd_point` = 7).
S42 S12/S13/S18 on the test side: `_document` passes `artifacts={"ledger": <64 hex>}` (`as_document` already
   passes `artifacts` through); `accounting_violations` compares `coupled_runs` with the solves that have a coupling
   record (S18; before, with every solve); S15's two record rules (null iff P5 did not run; keyed by exactly the
   candidate's decision ids) are in `status_violations`. A fake parent without an external unit gives no coupled
   run, validates, and writes S36's exact 0.0 half-width. Open for WO-8: no rule of the float addendum covers
   `fd_check`'s floats (`w0`, `selected_eta`, `candidates[].*`, `half_steps`); no generated record carries one,
   so a committed record with an `fd_check` will fail `test_every_float_of_every_record_is_classified` until the
   design lane classifies them (S17's table). Not added here.
Measured (WO-7b head): `tests/test_m05_study_record.py tests/test_m05_study_loop.py` 235 passed (default venv;
   138 at the S36 commit); `scripts/m03_nlp_check.sh … -- tests/test_m05_basis.py` 8 passed; the schema-wide and
   holder/truth suites (`test_adr_0002_canonicalization`, `test_k0{3,4,5}_schemas`, `test_m0{2,3}_schemas`,
   `test_requirements_ledger`, `test_t02_executor`, `test_m05_truths`, `test_m05_holders`) 247 passed;
   `t08_numerical_policy.py --check` exit 0.

## Merge of origin/main (M04) — d65a9a4

S43 RESOLVED by S44, option (a) (was OPEN: design lane; blocked a green gate on wp/M05). M04's `tests/test_m04_study.py::
   test_studies_never_import_the_application_layer` holds "no module of `studies` imports `openflowsheet.application`,
   lazily or not" (R-237's `adapters` rule extended to `studies` by M04's test; no register entry of its own). M05's
   `studies/trust_region/parent.py` (S3, the real C1 parent adapter: `coupled_run`, `revision_binding`,
   `revision_run`, `policies`; 18 uses) and `study.py` (`at_coupling`, `RevisionBinding`; 9 uses) import it by design,
   so the merged gate fails that one test (1 failed, 9186 passed, 31 skipped). Not changed: exempting `trust_region`
   relaxes a check (CLAUDE.md), and moving the adapter is a layering decision. Options: (a) invert, as M04 did — the
   C1 parent adapter and `at_coupling` use move to `application` (e.g. a `trust_region_study` job wiring), `studies`
   receives them as injected callables; (b) a registered exemption for `trust_region` with its reason; (c) narrow the
   rule to `studies/surrogate`. Build-lane default if asked to proceed: (a), as a structure-only change proved by the
   S33/WO-2c-style byte-identical dumps.

## S43 resolved — the C1 parent's application operations injected (S44)

S44 S43 → option (a), the session's decision (2026-10-16): M04's `test_studies_never_import_the_application_layer`
   stays as it is. Structure only, no numerics. `studies/trust_region/parent.py` imports nothing of `application`:
   `C1Parent(document, runner, box, *, services, ...)` takes a `ParentServices` (protocol in `parent.py`) and calls
   `services.bind` / `coupled_route` / `solve_coupled` / `live_experiments` / `inlet_of` / `unit_variant` /
   `pinned_at` / `policy` where it called `bind_revision_flowsheet`, `select_route` + the `revision_coupled` test,
   `solve_route` (its `RunUnsupportedError` returned as the `code` string), `LiveExperiments`, `inlet_of`,
   `unit_variant`, `study.pinned_at`, `T06_REVISION_V2`. The one implementation is
   `application/trust_region_parent.py` (`C1ParentServices`, `C1_PARENT_SERVICES`, and `pinned_at`, moved from
   `study.py`: still the one `at_coupling` call site), as M04 injects its resolver (E5/E8). `study.py` reads the
   binding as `CaseBinding` (a protocol: `flowsheet`, `spec`, `graph`); bindings are opaque (`Any`) in `parent.py`.
   The adapter stays in `studies`: moving it to `application` (tried first) breaks M05's own R-003 test
   `test_no_route_or_compile_path_reaches_the_projection` (nothing outside `studies/trust_region/` imports it), and the
   application module imports nothing of `studies.trust_region`. One failure-path difference: a binding refusal in
   `binding_at` (an `assert` before) now raises the constructor's `ValueError`.
   Alternatives: (b) a registered exemption for `trust_region`; (c) narrowing the rule to `studies/surrogate`.
   Reversible by: revert the commit.
   Measured: scratch dump (base tree `git archive e4a8f4b` vs the change, `.venv-nlp`) of the FD link toy `TrfStage`
   run document, full ledger and outcome at radius factors 1 and ¼; the stand-in C1 parent `run_study` (S0 + stage
   B candidates, stage C returning its start) record, every document the parent hashed, and the experiment store's
   JSON; and (nlp) S0's solve document plus `project_at(S0)` (rows, expressions, centres, half-widths, source map,
   scaling, holders, every variable's bounds and value, every active constraint's body, bounds and value). Floats as
   `float.hex`. `cmp` byte-identical (default 6393 lines, nlp 3668) after masking the lines that also differ between
   two runs of the base tree: 6 + 1 `sha256` values of coupling records, which carry wall times (S40's question;
   the records' other fields are in the dump and identical).
   Open for WO-8: R-003's test forbids any module outside `studies/trust_region/` importing it, so an `application`
   job that runs the trust-region study (as `surrogate_study` runs M04's) cannot exist under that test as written.

## WO-8 — runs on known truths, §19's build items (R-383..R-389)

S45 Committed records live under `benchmarks/m05/records/` (§9.5), each `<stem>.json` beside `<stem>.ledger.json`
   and `<stem>.coupling/`; `COMMITTED_RECORDS` reads that directory too (only single-suffix `.json`), as well as
   WO-7's `evidence/M05/*/records/`. Reversible: the glob.
S46 `C1Parent` gains `truth_class: type[ParentExperimentTruth] = ParentExperimentTruth` (default: nothing changes),
   so TR-E2's analytic `SyntheticTruth` (§6.4) is the parent's link truth. Alternative: replace `parent.truth` and
   `parent.formulation` from the script. Reversible: one keyword.
S47 Assumption blocks: TR-E2 = §5.2's column as A1/A2/A3/A5 `holds_by_construction`, A4/A6/A7 `limitation`
   (A7 "the budget"); FD truths (TR-E2-FD, LOOP-R) the same with A3 `qualified(fd_gradient)`, `trf_theory`
   `qualified(A3)`, study limitation `fd_gradient`. For the review batch (G5 compares the block).
S48 The ledger file (`artifacts.ledger` = its sha256) holds every holder request of every stage-C projection in
   order, without `wall_s`, so the digest is exact and G10 compares it byte for byte. Reversible: the script.
S49 LOOP-R's stage C uses `m05_basis` (affine Taylor link basis, R-277): G9's "constant basis" predates §16.5,
   which made the no-surrogate basis affine (a constant basis exits without a step, P14 b). For the review batch.
S50 OPEN (accounting). The FD truths' `M05-fd-v2` check runs (script, `project_at` wrapper) on the first stage-C
   projection's holder before `run_trf` begins the run: its 1 + 21 requests carry `run_id` null, so they are in
   no run's `by_purpose` (`fdcheck_point` 0) and are charged to no budget (TR-E2-FD `cold_used` 257 = 241 + 16;
   the 21 cold check evaluations are outside it). Default: leave; alternative: attribute the check to run C1.
S51 OPEN (accounting, blocks committing TR-E2's record). A parent holder charges its budgets at admission, before
   the runner says cold or store hit, so a store-hit value request is charged: TR-E2's `cold_used` 48 =
   31 trf_cold + 16 parent executions + 1 (the `trf_start_value` store hit), and
   `accounting_violations` fails "budgets.cold_used is not trf_cold + parent_executions". TR-E2-FD and LOOP-R
   pass only because their start-value store hit happened in the (unbudgeted) FD check. Options: refund the
   charge on a store hit in `holders.py` (G7: cold ≤ cap, a store hit is not cold), or restate the checker.
   The TR-E2 record is parked in `evidence/M05/wo8/artifacts/` (ignored), not committed.
S52 LOOP-S not run: stage A needs `SurrogateTruth` (§6.4), the promoted-surrogate link basis (§6.6) and stage A's
   P2 reference (the surrogate-backed `revision_eo` re-solve, §7.3), none of which exists on this branch (WO-4's
   `SurrogateTruth` was never built). A work order of its own.
Measured (`scripts/m05_wo8_runs.py`, `.venv-nlp`, fresh store each, 3-4 s per run):
   TR-E2: `TRF_MAX_ITERATIONS` (k 0..30), θ_recheck 4.01e-4, T* 673.6673361700024 K (T_ref 673.6434377969885,
     |ΔT| 0.024 K), cand `PARENT_LOCAL_EVIDENCE` (P2 unjudged, `trf_max_iterations`), study `DECISION_STABLE`.
     θ is a sawtooth: minima 1.62e-5, 1.62e-5, 1.33e-5, 1.65e-5, 1.03e-5 (k 6, 11, 16, 23, 28), each followed by a
     radius expansion and θ up to 1e-4..4e-3; never ≤ 1e-5 (F-15 reproduced: G5 FAILS).
   TR-E2-FD: `TRF_MAX_ITERATIONS`, θ_recheck 4.37e-4, T* 673.6673250702911 K (|T*_FD − T*_E2| 1.1e-5 K),
     fd_check `truncation_dominated` at 2⁻¹⁴, pass, 1 candidate (τ̂ 0.0531, ν̂ 3.91e-6, allowance 2.34e-3):
     G6 FAILS on `TRF_CONVERGED` only.
   LOOP-R (m04-synthetic-rough-v1): stage A skipped `surrogate_not_promoted`; C1 `TRF_CONVERGED` in 3 iterations,
     θ_recheck 1.14e-7, cand `PARENT_LOCAL_EVIDENCE`, `DECISION_STABLE`, T* 653.1500010668794 K:
     |T* − 653.15| = 1.067e-6 K > 1e-6 K (5.3e-8 scaled: Ipopt's interior distance to the bound). G9 FAILS by
     that margin. A CasADi callback printed `DomainError S2_Hdot_V: 142.2 K outside [200, 1000] K` inside a TRSP
     (recovered by Ipopt; the run converged).
   G10 (same machine): TR-E2, TR-E2-FD, LOOP-R `--replay` 0 differences each (record by shape/bitwise, ledger
     bytes, coupling files integrity + content). G7 (per run summary): cold + store + memo = requests (559, 311,
     ~77), refused 0, every ledger status `ok`; the store bijection is not evaluated. F-19: coupling records
     80 KB per study (committed).

## WO-8a, WO-8c, WO-8d — §20's build items (R-400, R-401, R-405, R-406)

S53 WO-8a: `final_step_at_box_bound` records whether *any* bounded decision of the returned model is within
   1e-6 (scaled, `checks.AT_BOUND_SCALED`) of a box bound, for every run TRF returned a model from after a logged
   TRSP (null otherwise); R-401's exception uses it only with n_d = 1 (`box_bound_exempt`). The scaled value is
   TRF's `d[j]` itself, so |d ∓ 1| is the poll's |u − bound|/h without the round trip. Alternative: record it
   only for n_d = 1. Reversible: `trf._at_box_bound`.
   F-23 (does a `TRF_CONVERGED` assertion flip under R-401?): none — the nlp tier passes unchanged
   (167 passed, 1 skipped); TR-E1 (G3) ratio 1.16e-3.
S54 WO-8c: `request_identity_violations` holds a record to R-406's `fdcheck_point` identity (first stage-C run
   1 + n_in·|η evaluated|, every other run 0) only when its `spec.configs.basis` is `M05-basis-v2`: the v1 TR-E2-FD
   and LOOP-R records (6a9d29d) ran the check outside every run and stay committed until WO-8e removes them; no
   record is written between WO-8c and WO-8d. The accounting checker itself is unchanged (R-405). Reversible: drop
   the condition once WO-8e has landed.
S55 WO-8c: the ledger entry gains §8.1's `stage`, `fdcheck` for the check's requests and null for every other
   (a TRF run's own stage is its run record's). It changes every ledger file's bytes, so the v1 records' G10
   `--replay` differs on that key until WO-8e re-records them. The check runs through `TrfStage(gradient_check=)`
   inside the first stage-C run, before its basis, so its G is the basis gradient's memo (as before).
   Measured (in memory, `scripts/m05_wo8_runs.py`'s `run_case`, no record written): TR-E2 `cold_used` 47 =
   31 + 16 (was 48: S51 resolved), accounting, identity and schema clean; TR-E2-FD C1 cold 262 = 241 + 21 cold
   check points (`fdcheck_point` 22, its base a store hit), `cold_used` 278 = 262 + 16, all checkers clean.
   T* unchanged to the bit (673.6673361700024 K; FD 673.6673250702911 K): WO-8c moves no numerics.
S56 WO-8d: `M05-basis-v2` reaches the run through `TrfStage(path_for=parent.decision_path)`: the stage calls
   `basis_for(projection, path=path_for(start))` (`m05_basis_v2`), and the builder returns a `BasisSet` (a dict
   of `EFBasis` with `record` and `limitations`). Under v2 the run's `basis` is the block `{policy, kinds, links}`
   (schema: `anyOf` with v1's kind map, so v1 records stay valid); a link EF with curvature has the kind
   `affine_curvature`, a fallen-back one keeps `affine_taylor`. The candidate gains `basis_without_curvature`
   through `StageRun.limitations`. Each link record also holds `solves` (the two inner solves' outcomes, R-400
   step 4's "its outcome is recorded"). Alternative: a separate `basis_curvature` run key. Reversible: the stage.
S57 WO-8d: a `TruthRefused` the check or the basis builder does not handle (a budget refusal, R-400 step 9) is the
   run's outcome `TRF_TRUTH_REFUSED(<code>)` without the `start:` prefix (v1 let it escape `run_trf` as an
   exception); R-276's backstop now counts refusals from after the basis phase, so a non-budget refusal at a path
   point that the builder turned into the affine fallback is in the basis block, not in the run's outcome.
S58 WO-8d (for the review batch): `noise_ratio` = 4ν̂/(t²|c_k|) is computed literally as R-400 step 10 writes it,
   with ν̂ the check's selected-η noise (scaled-gradient units) and c_k as recorded (output units per unit scaled
   decision squared, unscaled by s_k); reported, never judged. If the design lane meant c_k/s_k, it is one line in
   `study._basis_block`.
   Units: c is per unit *scaled* decision squared; §20.1's c_X = −9.5883e-4 is per K² (c/h², h = 20 K):
   measured c_X = −0.38353333565997494, /400 = −9.5883e-4.
   Measured (in memory, `run_case`, v2, fresh store; §20.1's scratch in brackets): TR-E2 C1
   `TRF_EXIT_WITHOUT_STEP` [same], θ_recheck 2.9978e-6 [3.0e-6], T* 673.6507818736262 K [673.6508],
   |T* − T_ref| 0.00734 K [0.0074]; central stencil, t 0.025, c = (−0.38353, 0.89137), v = 20 K e_T exactly,
   both inner solves CONVERGED, `basis_curvature_point` 2, `cold_used` 19. TR-E2-FD C1 `TRF_CONVERGED` k = 1
   [same], ratio 1.580e-4 [1.6e-4], θ 6.263e-8 [6.3e-8], T* 673.6294405283825 K [673.6294], noise_ratio
   (0.0653, 0.0281), `cold_used` 48. LOOP-R C1 `TRF_CONVERGED` k = 2 [same], ratio 6.93e-3 at the box bound
   [6.9e-3], θ 1.987e-7 [2.0e-7], T* 653.1500010581631 K [653.150001058]. Every checker (schema, accounting,
   identity) clean on all three; each `DECISION_STABLE`.
   Bit-identity (cases off the v2 basis): `run_case(..., basis_policy="M05-basis-v1")` for TR-E2, TR-E2-FD and
   LOOP-R at the WO-8d tree against a9d05d3 (the base, same machine, same session): runs' iterations, filter,
   final, θ_recheck/θ_logged, exit lines, outcomes, candidates (checks, poll, decisions), best, status, stage A
   and fd_check — 0 differences, `float.hex` compared. TR-E1 (G3) stays bitwise native (nlp tier).
   Found: the committed v1 records (6a9d29d) no longer replay even at a9d05d3 — `--replay` TR-E2-FD gives 100
   differences at ~1e-15 relative from iteration 0 (θ 0.5226121890068809 recorded, 0.5226121890068817 now),
   with only documents changed in between: environment drift in `.venv-nlp` or its libraries since WO-8, not a
   code change. WO-8e re-records; G10 for the new records must be judged in one environment.

## WO-8e — the v2 records, G5-G10 (§20.7)

S59 The runs need `OMP_NUM_THREADS=1` (`scripts/m05_wo8_runs.py` refuses otherwise, as
   `scripts/m03_nlp_measurements.py` does). Found: `.venv-nlp`'s OpenBLAS is its OpenMP build
   (`libopenblas-0.3.34-openmp`), whose results depend on the thread count — TR-E2-FD (v1 basis) iteration 0's θ is
   0.5226121890068809 at 1 thread, 0.5226121890068804 at 2 and 0.5226121890068817 at 48 (the default, `nproc`);
   `OPENBLAS_NUM_THREADS` has no effect. The committed v1 records (6a9d29d) were made at 1 thread: that, not a
   rebuilt environment, is S58's "≈1e-15 from iteration 0" (nothing under `.venv-nlp` or `.reference-downloads`
   changed after 2026-10-15 15:33, before 6a9d29d). Each record gets `<stem>.environment.json`
   (`environment_fingerprint`: the thread count, Python, digests of the distributions on `sys.path` and of the
   conda builds, machine, CPU), and `--replay` compares it exactly before the record, so G10 is judged in one
   environment. Alternative: set the thread count inside the script. Reversible: the script.
S60 The store bijection (§8.3, G7) is evaluated by `m05_replay.store_bijection_violations` at the end of each run,
   before its temporary store is removed, against `<stem>.store.json` (every `attempts/<n>.json` of the store,
   `{experiment_key, attempt}`, sorted), which is committed beside the ledger so the default gate re-evaluates it.
   A coupling record names its attempts by (key, attempt); a ledger entry names its key and `executions`, not
   the attempt numbers, so a key's attempts that no coupling names must equal the ledger's executions at that key.
   Alternative: evaluate only in the script and print. Reversible: the sidecar and one test.
S61 The gates are judged in the default tier on the committed files (`tests/test_m05_wo8_gates.py`: G5, G5b, G6,
   G7 per record, G9, and the v2 set's shape), §20.7's criteria read literally; T_ref is the golden-section
   reference of `test_m05_c1_reference.py`. S54's `M05-basis-v2` condition is dropped from
   `request_identity_violations` (no v1 record remains): every record with an `fd_check` is held to R-406, and
   the generated `decision_stable_with_an_fd_check` fake now carries the check's 29 points in its first stage-C
   run (`_charge_first_stage_c`). Reversible: one test file; the condition is one `if`.
   Measured (`OMP_NUM_THREADS=1 ... scripts/m05_wo8_runs.py <CASE>`, `.venv-nlp`, fresh store each; records at the
   v1 stems replace 6a9d29d's, which stay there as F-15 evidence):
   G5 TR-E2: C1 `TRF_EXIT_WITHOUT_STEP` (k 0), central stencil, c = (−0.38353, 0.89137), θ_recheck 2.998e-6,
     P2 judged/pass, cand-C1 `PARENT_LOCAL_EVIDENCE`, `DECISION_STABLE`, T* 673.6507818736261 K, |T* − T_ref|
     0.00734 K; assumptions = S47's column. PASS.
   G5b TR-E2-FAR (663.15 K): C1 `TRF_EXIT_UNVERIFIED(radius_limited)` k 7, ratio 0.99997, θ 7.47e-6, cand-C1
     `NOT_STATIONARY_AT_DELTA` (P5 fails); C2 `TRF_CONVERGED` k 1, ratio 0.01666, θ 8.26e-7, cand-C2
     `PARENT_LOCAL_EVIDENCE`; `DECISION_STABLE` at study iteration 2 ≤ 3; T* 673.6541821432122 K, |ΔT| 0.01074 K.
     PASS (§20.7's scratch reproduced).
   G6 TR-E2-FD: C1 `TRF_CONVERGED` k 1, ratio 1.580e-4, θ 6.263e-8, P2 judged/pass, `DECISION_STABLE`,
     T* 673.6294405283818 K, |T*_FD − T*_E2| 0.02134 K; fd_check `truncation_dominated` at 2⁻¹⁴, pass, one
     candidate; `basis_curvature_point` 2, `fdcheck_point` 22; identity clean. PASS.
   G7: store bijection 0 violations on all four (store attempts 19 / 42 / 48 / 63), cold + store + memo =
     requests for every holder, refused 0, every ledger entry `ok`, `cold_used` 19 / 42 / 48 / 63 ≤ 2000. PASS.
   G9 LOOP-R: stage A skipped `surrogate_not_promoted`, C1 `TRF_CONVERGED` k 2 at the box bound (ratio 6.93e-3),
     `DECISION_STABLE`, T* 653.1500010581631 K, |d* − d_lb| 5.29e-8 scaled ≤ 1e-6, P5 polled `plus` only. PASS.
   G10 (same machine, one environment: `<stem>.environment.json`, 1 thread): `--replay` 0 differences on each of
     TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R (environment, record bitwise, ledger and store bytes, coupling integrity and
     content). A replay with a different thread count is reported as an `environment` difference. PASS.
   v2 at 1 thread against S58's in-memory v2 (48 threads): TR-E2 T* 673.6507818736261 vs …262 (1 ulp), TR-E2-FD
     673.6294405283818 vs …825; the thread count, not the code (S59).

## WO-8b — `SurrogateTruth`, the promoted basis, P2_A, LOOP-S, G8 (§20.5, §20.7)

F-22 (fact): M04's PROMOTABLE smooth-synthetic prefix-plan manifest is on `wp/M05` (M04's merge `78685cc` is an
ancestor): M04.A19's `tests/fixtures/schemas/surrogate_manifest/valid/a19_smooth_prefix.json`, written by M04's
`run_study(runner, m04-synthetic-smooth-v1, "it1-prefix", 1000)` (`scripts/m04_schema_fixtures.py`), verdict
`PROMOTABLE`, `parent.variant_sha256` equal to the registered smooth variant's. LOOP-S uses that file; no merge,
no stand-in.
S62 `SurrogateTruth(manifest, variant, n_tubes)` (§6.4 wrote `SurrogateTruth(manifest)`): the bound parent and
   its N_tubes are needed — the manifest must name `variant` and be `PROMOTABLE` (else `ValueError`, §7.3's
   "promoted surrogate of the bound parent"), and M04's input map divides n_tot by N_tubes. Values and gradient are
   M04's `predict(z(s))` and `inlet_sensitivity` on the manifest's scaling (`reactor.surrogate_of`). Refusals are
   the M04 unit's, in its order, `out_of_domain` with its code (`surrogate_input_undefined`,
   `surrogate_outside_hard_domain`, `surrogate_output_inadmissible`), so stage A's truth answers where P2_A's
   surrogate-backed re-solve can; `meta` is `in_process_meta()` otherwise (§16.4). Alternative: no refusals (a
   polynomial evaluates anywhere). Reversible: one method.
S63 The promoted basis (`basis.promoted_basis`, `surrogate_link_basis`, `surrogate_expression`; R-408): affine
   property EFs, and on each link EF b_k = β_kᵀφ(z(w))/s_k built on the clone's arguments, u(s) with M04's
   operation order and M04's `PAIRS`. M04's `basis(z)` itself is not reused: it applies `float()` to z, which a
   Pyomo expression refuses, and M04 is not changed. It asks no holder anything, so a promoted run has no
   `basis_fd_point` (as `request_identity_violations` already expects) and its `basis` block is the EF kinds
   (`surrogate` on the links), no v2 curvature block. The record's `configs.basis` stays `M05-basis-v2`: R-400
   replaced only §6.6's no-surrogate branch. WO-4's acceptance at M04's J1-J3 (A19 coefficients, each state's
   N_tubes): floats 0 relative error, Pyomo variables ≤ 1.9e-16 relative (≤ 1e-14 required); the symbolic gradient
   matches `inlet_sensitivity` within 1e-12 of its largest entry.
   P2_A (§7.3): `C1Parent.surrogate_reference(manifest)` re-solves the candidate's revision with the reactor model
   replaced by `c1.reactor_surrogate` (version `surrogate_id`, artifact the manifest's canonical SHA-256,
   parameters unchanged) on `revision_eo`, through a new, additive `ParentServices.solve_eo` (S44's pattern:
   `studies` does not import `application`). A re-solve with no state is a reference with NaN objective and no
   state, so P2 fails (the safe failure); source `surrogate_revision_eo[:<why>]`. Stage A projects with
   `C1Parent.project_at(start, truth=surrogate)`; its surrogate evaluations are charged to the in-process study
   budget after the run, as `TrfStage` already does for an in-process truth (§7.5 counts evaluations).
   Alternatives: P2_A's reference built in the composition root; `PROJECTION_DISAGREES` reserved for a real defect
   by a separate status for a failed reference. Reversible: one method each.
S64 LOOP-S (`scripts/m05_wo8_runs.py LOOP-S`, `OMP_NUM_THREADS=1`, `.venv-nlp`, fresh store): stage A A0
   `TRF_CONVERGED` at k = 1 (θ_k0 6.55e-3, θ_recheck 8.88e-9, step 8.19e-7, final_step_ratio 3.28e-6; R-408
   expected `TRF_EXIT_WITHOUT_STEP` with θ_PMP ≈ 1e-14, but the property EFs' affine basis is not exact, so θ_PMP =
   6.55e-3); P2_A judged and passed (objective error 5.95e-14 against bound 4.59e-4, worst state 1.57e-8 at
   `S2.T`, 62 mapped variables); cand-A0 `PARENT_LOCAL_EVIDENCE` (P5: minus clipped to 653.15 K improvement
   3.71e-9 ≤ allowance 1.28e-5; plus −8.46e-5); `DECISION_STABLE`; no stage C. T* 653.150021930406 K, |d* − d_lb|
   = 1.0965e-6 scaled (2.193e-5 K). 3 surrogate evaluations, 16 parent executions, 4 couplings, store bijection 0.
   **G8: FAIL** on its last rows — |d* − d_lb| ≤ 1e-6 scaled (≤ 2e-5 K) misses by a factor 1.0965, and because the
   decision is not "at the bound" (§7.4), P5 polled both sides, not the inward point only. Every other G8 row
   passes. Not moved: `test_g8_loop_s_stage_a_and_p2_a` passes; `test_g8_loop_s_at_the_bound_and_polled_inward`
   holds §20.7's criterion literally and is a strict `xfail` with these numbers, for the design lane. For
   comparison, LOOP-R's interior-point offset is 5.29e-8 scaled, at about the same objective slope (its plus poll
   −8.37e-5).
   G10: `--replay` 0 differences on TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R (after this change) and LOOP-S.
S65 FD-3 (M07 spec §4.6, A1.6): records written from WO-9 on carry an optional top-level `provenance` block
   `{run_commit, tree_clean, wall_s}` (schema additive, not required): the commit the study was run at, whether
   `git status --porcelain` was empty when it started (the REAL run refuses a dirty tree), and the study's spent
   wall time from its own budget clock (`StudyBudget.wall_s` after `run_study`). Written by the evidence scripts
   (`m05_wo8_runs.git_state`/`provenance`), never by the loop, so the five WO-8 records are not re-taken and their
   `--replay` is unchanged (TR-E2, LOOP-R: 0 differences after the change). `provenance.wall_s` is classified
   `excluded` in the M05 addendum; `provenance` is never compared between a run and its replay. Alternatives: the
   fields inside `environment` or `accounting` (both compared by the WO-8 replays). Reversible: the block and its
   addendum rule.
S66 REAL's assumptions block is §5.2's real-reactor column read literally: A1, A5 `holds_by_construction`, A2
   `assumed`, A3 `qualified(fd_gradient)`, A4, A6, A7 `limitation`; `claims.trf_theory` = `qualified(A2,A3)` (§6.9:
   the qualified assumption ids). Study limitation `fd_gradient`; `extrapolated` arrives with the candidates'
   solves (S26). For the review batch.
S67 REAL's experiment store is kept as `<stem>.experiments.json` (the exact text of every `request.json`,
   `result.json` and `attempts/<n>.json`, by path under the store; no attempt working directories, no locks), its
   sha256 in the record as `artifacts.experiment_store` (schema additive). It is what the replay from the record
   serves the reactor from (F-20). Alternatives: the store under `evidence/M05/<commit>/artifacts/` (ignored) by
   hash, per F-19's 5 MB rule. Reversible: the sidecar.
S68 REAL's replay content check (G10 REAL part, F-20), `scripts/m05_wo9_real.py --replay`: the study is re-run over
   the restored store with a backend that handshakes like the real one and refuses to execute (a miss is `replay
   diverged`). Compared: the record by `replay_differences` without `provenance` and without the counts a store hit
   changes by design (`m05_replay.STORE_SERVED_COUNTS`: cold, executions, store hits, `cold_used`), plus the fresh
   study's cold counts all 0 and each run's cold + store-hit requests preserved; the ledger entry by entry with
   recorded `cold` = replayed `store_hit`, 0 executions; the store index unchanged; each coupling record by M02's
   `iterate_differences` and `record_differences` under `T08-numerical-policy-v2`, then content equality without
   the unit entries' `attempts`/`cache_hit`, every replayed answer a store hit. Alternatives: M02's
   `RecordedExperiments` per coupled solve (needs a per-solve experiments hook in `C1Parent`; the holder truths
   would still need the store). For the review batch.
S69 REAL (WO-9), `scripts/m05_wo9_real.py` at 20e398e (clean tree; `.venv-nlp`, `OMP_NUM_THREADS=1`, reactor env
   `pymrm-6089593-032a050c6cf3`, fresh store): study `DECISION_STABLE` in 1454 s (of 14 400 s), 48 cold
   experiments (of 400): S0 4, TRF run C1 32 (of 250), P1 4, two polls 4 each. Stage A skipped
   (`surrogate_not_promoted`). C1 `TRF_CONVERGED` at k = 1 (one θ-type step; θ_k0 5.94e-3, θ_recheck 2.33e-6,
   final_step_ratio 1.92e-6, `EXIT: Optimal solution found.`); P2 judged and passed (objective error 1.20e-6 against
   bound 4.52e-4, worst state 3.87e-5 at `S5.N`); cand-C1 `PARENT_LOCAL_EVIDENCE`.
   F-9: `fd_check` class `clean` at η = 2⁻¹⁴, τ̂ 3.115e-3, ν̂ 6.87e-4, allowance 4.05e-3 (‖G‖∞ 4.05), `pass`, no
   escalation (22 `fdcheck_point` requests: 21 cold, the base a store hit of S0's experiment).
   F-13: the cap is not reached (C1 32 cold of 250; study 48 of 400).
   F-21: yes at the one stage-C start: both pinned inner solves at d₀ ± t (672.65 K, 673.65 K) `CONVERGED`, central
   stencil, `basis.status` ok, c = (−1.22e-3, 0.812), noise_ratio (3592, 5.42).
   Interior optimum: **no**. T* = 653.1500351610193 K, the lower bound (3.52e-5 K, 1.76e-6 scaled above it); J rises
   from 0.44933 at 673.15 K to 0.45250 at the bound; P5 polled both sides (not "at the bound" by §7.4's 1e-6
   scaled): minus (clipped to 653.15 K) improvement 8.17e-9 ≤ allowance 3.71e-6, plus −7.14e-5. Same structure as
   LOOP-R/LOOP-S (and the same 1e-6-scaled question as G8's S64, not gated here: REAL's optimality is reported).
   `extrapolated`: the record states it (cand-C1's P1 solve: its final experiment is outside the kinetics' data
   domain on `H2/N2`); count 12 of the reactor link's 61 truth requests (10 of its 32 cold experiments), read from
   the ledger artifact (the record has no count field; `tests/test_m05_wo9_gates.py` pins 12/61). Finding: the
   loop's reactor-inlet H2/N2 sits on the data edge, so the final-iterate rule flips between solves 3.5e-5 K
   apart (P1 extrapolated, the minus poll at 653.15 K not; S0 not).
   G11: PASS (`tests/test_m05_wo9_gates.py`, default tier on the committed files). G7 on the run: store bijection 0
   violations, 4 coupling records persisted, 0 refusals.
   G10 REAL part (F-20): `--replay` from the record **0 differences** (record compared bitwise apart from the
   store-served counts; ledger with recorded cold experiments as store hits; store unchanged; coupling records by
   M02's `iterate_differences`/`record_differences` under T08 v2, then content). The comparator's first version
   mapped every `cold` ledger entry to a store hit and compared `artifacts.ledger` exactly: 37 by-design lines
   (property blocks and FD-assembled Jacobians are computed again and stay `cold`; the ledger file differs), fixed
   in the comparator (S68's rule, keyed on the experiment key), not in the record.
   AQ2: no. The REAL check reads `benchmarks/m02/c1-loop-real.json` and never writes it (`C1Parent` deep-copies the
   document; the script asserts the file's bytes equal before and after the run, and `git status` shows it
   unchanged). `experiments.json` is 480 kB, so it is committed (below F-19's 5 MB).

## WO-10a (the review's fixes; §21, R-430..R-435)

S70 MF1 / R-432 (cdacc32): `noise_ratio_k = 4σ̂_k/(t²|c_k|)`, σ̂_k = ν̂·η_sel·s_k/√2. `_basis_block` takes the link
   outputs' scales from the source map (`output_scale`, X then ΔT, the order of the basis record's `c`); unit test
   `test_m05_basis.py::test_r432_...` on REAL's committed numbers (0.038752, 0.029926). Re-takes at cdacc32, clean
   tree, `.venv-nlp`, `OMP_NUM_THREADS=1`, written beside the records (`retake.py` driver: `run_case`/`run_real` then
   `write_files` to a scratch stem, so `provenance.tree_clean` is true) and copied over them:
   - LOOP-R noise_ratio (0.14106, 1.9002e-4) → (6.0878e-6, 2.0995e-6) (s = 1, 256);
   - TR-E2-FD (0.065258, 0.028079) → (7.0411e-7, 1.5512e-4) (s = 0.25, 128);
   - REAL (3591.63, 5.4172) → (0.038752, 0.029926) (s = 0.25, 128), as §21.3 predicts. REAL wall 1454 s, 48 cold.
   new/old = η·s_k/√2 exactly in each (η = 2⁻¹⁴).
   **Proof** (`scripts/m05_retake_diff.py`, committed side from `git archive f0693d8`): `RETAKE-DIFF PASS`,
   0 differences for all three. "Bitwise with `noise_ratio` and `provenance` masked" cannot hold literally for a
   fresh run, because the files carry wall-clock timings; the diff therefore also masks exactly the timings and
   the digests over them, and nothing else:
   - record: G10's comparator (`replay_differences`, every other leaf by `float.hex`); raw differing leaves
     LOOP-R 3 solve `wall_s` + 6 coupling digests, TR-E2-FD 4 + 8, REAL 4 + 8 + `artifacts.experiment_store`;
   - coupling records: content equal after M02's `excluded` attempt timings and the reactor's
     `execution.diagnostics.**.wall_s` (REAL: 84 such leaves, nothing else);
   - REAL's experiments archive: 144 files, every request/result file bytewise equal, 48 attempt files differing
     only in `execution.timing.{wall_s,startup_s,solve_s}` and `execution.diagnostics.**.wall_s` (392 leaves),
     hence the new `artifacts.experiment_store` digest;
   - ledger, store index and environment sidecars bytewise equal (unchanged in git).
   Choice (for the design lane, reversible by re-running the diff with a narrower mask): the timing mask above is
   the only extension of §21.3's mask; the reactor's diagnostic `wall_s` are timings that M02's `excluded` list does
   not name (a store-served replay returns them unchanged, so G10's REAL replay never meets them).
   After the re-takes: `scripts/m05_wo9_real.py --replay` on the new REAL record `REPLAY PASS REAL differences=0`;
   pymrm `test_m05_parent.py` 1 passed (126 s); gate 9287 passed, 31 skipped, 1 xfailed; nlp 181 passed, 1 skipped.
S71 SF2 / R-430, R-435: G8's and G9's at-bound rows restated per §21.6 in `tests/test_m05_wo8_gates.py`
   (`_at_the_bound`): |T* − 653.15 K| ≤ 0.5 K; P5's evidence contains the bound — no minus point (then §7.4 must read
   the candidate at the bound), or the minus point `clipped`, at exactly {T: 653.15}, `feasible` and its P5 point
   passed. |d* − d_lb| and §7.4's reading are reported through `record_property`, not judged: LOOP-S 1.0965e-6
   scaled, interior (minus point clipped, feasible, passed); LOOP-R 5.29e-8, at the bound (no minus point). The
   strict xfail is removed (`test_g8_loop_s_at_the_bound` passes); G9's 1e-6 and inward-only rows are replaced.
   Mutations caught (in memory): minus point at 653.1500001 K, infeasible, its P5 point failed, T* 0.55 K off the
   bound, no minus point at an interior reading. The inward-only unit test stays
   (`test_m05_study_loop.py::test_the_poll_polls_only_inward_at_a_bound_and_clips_at_the_box`). Gate 9288 passed,
   31 skipped (the xfail gone); nlp 181 passed, 1 skipped.
S72 SF1 / R-435: G10's in-process replays in the `nlp` tier, `tests/test_m05_g10_replay.py` (parametrized over TR-E2,
   TR-E2-FAR, TR-E2-FD, LOOP-R, LOOP-S): `m05_wo8_runs.run_case` from a fresh store into `tmp_path`, then the
   script's own `compare` (environment fingerprint exactly, record by `replay_differences`, ledger and store index
   bytewise, coupling records by integrity and content) and G7's bijection; the message lists the differences.
   Without `OMP_NUM_THREADS=1` it fails ("G10 refuses"), never skips. Measured: 5 passed in 16.3 s at 1 thread;
   at `OMP_NUM_THREADS=2` it fails with the refusal. Mutations (then restored by `git checkout`): LOOP-S's T* moved
   one ulp → fails naming `.best.decisions.preheater.T_spec: 653.1500219304061 vs 653.150021930406`; TR-E2's
   environment `conda_builds` edited → fails naming `environment conda_builds: '41-mutated' recorded, 41 now`.
   REAL's replay stays the script (`scripts/m05_wo9_real.py --replay`, ≈ 25 min, the reactor environment).
   Gate 9288 passed, 31 skipped; nlp 186 passed, 1 skipped (56 s).
S73 R-433: the `extrapolated` limitation wording is `EXTRAPOLATED_LIMITATION` in `tests/test_m05_wo9_gates.py`, for
   M05's manifest and W24 text (WO-10b copies it verbatim): the ledger count "12 of 61 reactor requests, reported,
   not a distance from the data" and the data-edge flip (3.5e-5 K, cand-C1's P1 solve extrapolated, its minus poll at
   653.15 K not). `test_r433_...` ties the count to the constants the ledger test pins and the flip to the record's
   per-solve `limitations` and decisions. The note to M07 (§21.4) is `docs/briefs/M05-note-to-M07.md`, to be copied
   to wp/M07. Handoff `docs/briefs/M05-wo8-handoff.md` updated for WO-10b. Gate 9289 passed,
   31 skipped; nlp 186 passed, 1 skipped.
S74 Review note N2: a box exception other than `TruthRefused` no longer leaves its key in flight
   (`holders.py`, `EFHolder._values_request`). A `try/finally` drops the in-flight entry and sets `flight.done` when
   the box raised; the exception propagates unchanged, and the success and `TruthRefused` paths are unchanged. A
   `except BaseException: ...; raise` was tried first and rejected by `test_no_broad_except` (§8.1's lint allows a
   re-raising broad handler only under `application/`), hence `finally` with a `raised` flag. The charge stands, as the
   review says. Test `test_n2_a_box_exception_propagates_and_does_not_leave_the_key_in_flight`: a box that raises
   `RuntimeError` once; the second request for the key (10 s timeout) is evaluated afresh. Gate 9290 passed,
   31 skipped; nlp 186 passed, 1 skipped (the nlp tier includes G10's five replays; the new test is default tier).
S75 WO-10b: the manifest, the harvest and the docs. `evidence/M05/cfecb15abcb2d632149e37749a107fa0b3991cc0/manifest.json`
   (`tested`; review pending): 14 checks (G1–G13 with G5b), all pass; each carries the test counts and the measured
   values from the junit run of `tests/test_m05_*.py` and the records. Choices for the design lane: (a) G10 is `pass`
   for the same-machine criterion (the five in-process replays and REAL's `--replay`, 0 differences) and records
   `cross_architecture: not_run`, with a limitation, rather than a non-pass check (a non-pass check would need a
   backlog id in the harvest); (b) all ten limitations are harvest class P (they stay in the manifest), none E, because
   an E item needs a new envelope row and the TRF route is not yet a served surface; `extrapolated`, REAL's bound-active
   optimum and `fd_gradient` are the candidates to promote at M07's envelope; (c) `case_hash` is the sha256 of
   `benchmarks/m02/c1-loop-real.json`. G8's `section_7_4_at_the_bound: false` is carried in the check with R-430's note.
   Support matrix re-emitted (`--check`: 0 problems). ADR 0039 gains the amendment note on the box (R-313, R-315,
   R-330), status unchanged; `docs/briefs/M05-W24-table.md` for `verdict`; `docs/progress.md` M05 row.
S76 Merge of `main` (`0bdb80d`) into wp/M05 (`eb17f79`): the [A10] inventory re-taken, 181 objects. M03's
   re-take (`b074d57`, 180) measured `main`'s tree; M05's `studies.trust_region.holders` imports
   `concurrent.futures`, whose thread pool imports `queue`, so the NLP-1 workload maps one more object in both import
   orders: `lib-dynload/_queue.cpython-313-x86_64-linux-gnu.so` (python-3.13.5-hec9711d_102_cp313, 58 384 bytes,
   Python-2.0, `identified`). Same package, already audited; the 41 conda packages and the wheels unchanged; no licence
   added; G1-G6 PASS; `--check` reproduces it. Inside N1 (R-450) on the precedent of `b074d57`'s session decision.
   Audit §1 G1, §5 updated. Gate 9319 passed, 31 skipped; nlp tier without G10 181 passed, 1 skipped.
S77 Merge of `main` into wp/M05: the five in-process G10 records re-taken (TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R,
   LOOP-S). `main`'s M02 follow-up D134 (R-390, `768690f`) edits `models/c1/boundary.py` (the v3 inert floor's 4-ulp
   slack), and the in-process backend's environment fingerprint carries `boundary_sha256`, the file's sha256
   (`adapters/experiments/backends.py` `InProcessBackend.environment`). So every experiment key, request and
   coupling digest of the five records moved, and G10 failed with 107/185/107/147/105 differences, all digests.
   Shown before re-taking, by a leaf walk of record (without `provenance`), ledger, every persisted coupling
   record and the store (order-free after relabelling): every non-digest leaf is equal except timings; the old-to-new
   digest map is a function and injective (42/80/71/92/38 digests); the environment files are byte-equal; the store
   equals the old one after the relabelling. No number, status, iterate or count moved. Re-taken with `run_case` and
   `write_files` into a scratch directory from a clean tree at `33b03b6` (`provenance.tree_clean: true`), then copied
   over the committed files (`write_files` refuses to overwrite in place). REAL is unaffected (external fingerprint):
   `m05_wo9_real.py --replay` 0 differences, `-m pymrm tests/test_m05_parent.py` 1 passed, on the merged tree.
   The cfecb15 manifest's record sha256 values describe the records before this re-take. Choice for the design lane
   (replay identity): re-take, rather than amending the fingerprint or the G10 comparison. Reversible by reverting
   this commit (G10 then fails until the boundary file is restored or a ruling changes the comparison).

S78 `scripts/m05_retake_diff.py --digest-only` (R-458; rulings `docs/design/V02-alpha-main-rulings.md` §3 E5), the
   committed proof of a digest-only re-take. On S77's pair (records at `56fb2fa^` against `56fb2fa`, `git archive`)
   it prints PASS for all five cases (AM-20), changed digests 42/80/71/92/38 for TR-E2/TR-E2-FAR/TR-E2-FD/LOOP-R/LOOP-S,
   equal to S77's counts under E5's rule (distinct old digests whose new value differs; AM-21, Q2: no mismatch).
   Class counts (digest/timing/other): 150/20/0, 327/35/0, 219/20/0, 288/26/0, 128/20/0; environment files equal.
   Build-lane choice: the store index is sorted by `(experiment_key, attempt)`, so it is paired by the relabelled key
   (each old entry with the new entry of its key's image under the map the record, ledger and coupling records built),
   not by position. Positional pairing on S77's pair makes the map fail to be a function and injective on 17 (TR-E2)
   and 14 (LOOP-S) digests — an artefact of the sort order, not of the content. The store's digests still enter the
   map, so (b) and (c) cover them. Reversible by reverting the E5 commit. Unit tests: `tests/test_m05_retake_digest_only.py`.

S79 `--digest-only` gains the class `version` and the fingerprint binding (R-458 Amendment A1; rulings §3 E5a). The
   coupling records' clear `frozen.reactor.fingerprint.openflowsheet_version`, at exactly that path, is admitted when the
   committed side equals `--old-version` and the re-take side the running `openflowsheet.__version__` (without
   `--old-version`: the sides are equal); the rule is checked on every coupling pair, and a pair that breaks it or lacks
   the leaf is other. On both sides of every coupling pair each frozen unit's `fingerprint_sha256` must equal
   `document_sha256(fingerprint)`, always. The summary line gains `version=<n>`. AM-20 re-run on S77's pair: PASS,
   42/80/71/92/38, `version=0 other=0` on all five (the binding holds on the 44 coupling sides). AM-22: six new cases
   (the stale-digest case passes with the binding neutralised, checked once by monkeypatching `document_sha256`); the
   existing synthetic coupling record gained a bound `frozen` block, since a record without one is now other.
