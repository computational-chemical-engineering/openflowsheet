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

Next executable actions (separate work orders):
1. WO-8e: remove v1's TR-E2-FD and LOOP-R records in one commit; run
   `PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1 PYTHONPATH=src:.reference-downloads/m03-ipopt/nlp-test-tools
   .venv-nlp/bin/python scripts/m05_wo8_runs.py <CASE>` for TR-E2, TR-E2-FAR (new case: start 663.15 K, test-only),
   TR-E2-FD, LOOP-R; then `--replay` each (G10); gates G5, G5b, G6, G7 (store bijection), G9, G10.
   After WO-8e drop S54's `M05-basis-v2` condition in `request_identity_violations` if no v1 record remains.
2. WO-8b: `SurrogateTruth` (§6.4), promoted link basis stages A and C, P2_A, LOOP-S (G8; F-22).
Open for the design lane (review batch): S53 (bound flag for n_d > 1), S56 (`basis` block shape), S57 (refusal
outcome without `start:`), S58 (`noise_ratio` units: c_k vs c_k/s_k).
