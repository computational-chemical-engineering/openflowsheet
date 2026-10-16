# M05 WO-8 handoff (2026-10-16, wp/M05)

Done on wp/M05 after a9d05d3 (§20's build items; build log S53-S58 in docs/design/M05-build-decisions.md):
- 4c9a083 WO-8a (R-401): `TRF_EXIT_UNVERIFIED(final_step_rejected | radius_limited)`, `final_step_ratio`,
  `final_step_at_box_bound` (schema additive). F-15's k = 27/28 fixture → radius_limited; TR-E1 ratio 1.16e-3.
  F-23: no `TRF_CONVERGED` assertion flipped.
- 55674aa WO-8c (R-405, R-406): store hits refund their charge; the FD check runs inside the first stage-C run
  (`TrfStage(gradient_check=)`), stage `fdcheck`, study cap only. Ledger entries gain `stage` (S55).
- d56b42d WO-8d (R-400): `M05-basis-v2` (`basis.m05_basis_v2`, `C1Parent.decision_path`,
  `TrfStage(path_for=)`); the script defaults to v2 (`run_case(..., basis_policy="M05-basis-v1")` for v1).

Measured in memory (no record written), v2: TR-E2 `TRF_EXIT_WITHOUT_STEP`, θ 2.998e-6, T* 673.6507818736262 K
(0.00734 K from T_ref); TR-E2-FD `TRF_CONVERGED` k = 1, T* 673.6294405283825 K; LOOP-R `TRF_CONVERGED` k = 2,
T* 653.1500010581631 K. All record checkers clean. v1-basis runs bit-identical to a9d05d3.

Known: the committed v1 records (TR-E2-FD, LOOP-R, 6a9d29d) do not replay even at a9d05d3 (≈1e-15 drift from
iteration 0, environment) — WO-8e replaces them; judge G10 in one environment.

WO-8e done (build log S59-S61): v2 records TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R under `benchmarks/m05/records/`
with `<stem>.store.json` (G7's store bijection) and `<stem>.environment.json`; G5, G5b, G6, G7, G9 pass
(`tests/test_m05_wo8_gates.py`, default tier), G10 `--replay` 0 differences each in one environment. The runs
need `OMP_NUM_THREADS=1`: `.venv-nlp`'s OpenMP OpenBLAS changes digits with the thread count — that was the v1
records' "environment drift" (S59). S54's condition dropped.

WO-8b done (build log S62-S64): `SurrogateTruth(manifest, variant, n_tubes)` (truths.py), the promoted basis
(`basis.promoted_basis`, link EFs `surrogate`), P2_A (`C1Parent.surrogate_reference`, additive
`ParentServices.solve_eo`), stage A via `C1Parent.project_at(start, truth=)`; LOOP-S record under
`benchmarks/m05/records/` (F-22: M04.A19's committed PROMOTABLE manifest, on wp/M05). G10 `--replay` 0 differences
on all five records. **G8 FAILS** on its at-bound rows: stage A `TRF_CONVERGED` k = 1, P2_A judged/passed,
`DECISION_STABLE`, but T* 653.150021930406 K is 1.0965e-6 scaled from d_lb (> 1e-6), so P5 polled both sides.
`test_g8_loop_s_at_the_bound_and_polled_inward` is a strict xfail holding the criterion literally.

Next executable actions:
1. Design lane: rule on G8's at-bound miss (S64): LOOP-S's interior-point offset 1.0965e-6 scaled vs R-404's 1e-6
   (LOOP-R 5.29e-8). The engineer did not move the criterion. When ruled, flip or keep the strict xfail.
2. WO-9 (REAL) and WO-10 as the design note orders them (not started).
Open for the design lane (review batch): S53 (bound flag for n_d > 1), S56 (`basis` block shape), S57 (refusal
outcome without `start:`), S58 (`noise_ratio` units: c_k vs c_k/s_k), S59 (thread pin + environment
sidecar), S60 (`.store.json` sidecar), S61 (gates judged in the default tier), S62 (`SurrogateTruth` signature
and refusals), S63 (promoted basis without M04's `basis(z)`; `configs.basis` stays v2; P2_A via
`ParentServices.solve_eo`, a failed reference fails P2), S64 (G8).
