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
