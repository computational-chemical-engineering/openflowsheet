# M05 WO-8 and WO-9 handoff (2026-10-16, wp/M05)

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

WO-9 done (build log S65-S69): FD-3's optional record `provenance {run_commit, tree_clean, wall_s}` (c912f92,
WO-8 records not re-taken); `scripts/m05_wo9_real.py` (20e398e) with the store sidecar `<stem>.experiments.json`
(`artifacts.experiment_store`) and `--replay` from the record (S68's comparator in `m05_replay`). REAL record
`benchmarks/m05/records/trust-region-study-real.*` run at 20e398e: `DECISION_STABLE` in 1454 s, 48 cold; C1
`TRF_CONVERGED` k = 1; `fd_check` clean at 2⁻¹⁴ (τ̂ 3.1e-3, ν̂ 6.9e-4); T* 653.1500352 K (lower bound, not interior;
1.76e-6 scaled, P5 polled both sides); `extrapolated` 12 of 61 truth requests. G11 PASS
(`tests/test_m05_wo9_gates.py`), G10 REAL `--replay` 0 differences. F-13 no cap hit; F-21 both inner solves
converged. AQ2: `c1-loop-real.json` is never edited.

Review and rulings (f0693d8): `docs/reviews/M05-review.md`, design note §21 (R-430..R-435). S64 handled by R-430,
S58 reversed by R-432, the rest of the review batch confirmed (R-434).

WO-10a done (build log S70-S73; commits cdacc32, cdefb1a, 1a8dc60, 0168343 and the R-433 commit):
- R-432 `noise_ratio = 4σ̂_k/(t²|c_k|)`, σ̂_k = ν̂·η_sel·s_k/√2 (`study._basis_block`). Re-takes at cdacc32 (clean
  tree, `OMP_NUM_THREADS=1`): LOOP-R (6.09e-6, 2.10e-6), TR-E2-FD (7.04e-7, 1.55e-4), REAL (0.0388, 0.0299).
  `scripts/m05_retake_diff.py` against f0693d8: 0 differences each with noise_ratio and provenance masked, plus
  wall-clock timings and the digests over them (S70; the timing mask is a build choice for the design lane).
- G8/G9 restated per §21.6 (`tests/test_m05_wo8_gates.py::_at_the_bound`); strict xfail removed; G8 passes.
- G10's five in-process replays in the nlp tier (`tests/test_m05_g10_replay.py`, 5 passed in 16 s).
- R-433: `EXTRAPOLATED_LIMITATION` in `tests/test_m05_wo9_gates.py` (pinned to the ledger count and the
  recorded flip); the note to M07 is `docs/briefs/M05-note-to-M07.md` (copy to wp/M07).

Commands actually run (worktree root):
- gate: `PYTHONPATH=$PWD/src PATH=<repo>/.venv/bin:$PATH ./scripts/gate.sh`, with `evidence/M06/W27/artifacts`
  linked to the m06-w27h worktree's for the run, then removed. Last: 9289 passed, 31 skipped (S73).
- nlp: `OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1
  PYTHONPATH=src:.reference-downloads/m03-ipopt/nlp-test-tools .venv-nlp/bin/python -m pytest -q -p no:cacheprovider
  -m nlp`. Last: 186 passed, 1 skipped (includes G10).
- pymrm: the same environment, `-m pymrm tests/test_m05_parent.py`: 1 passed (126 s).
- REAL replay: `OMP_NUM_THREADS=1 ... .venv-nlp/bin/python scripts/m05_wo9_real.py --replay`: `REPLAY PASS REAL
  differences=0` on the re-taken record.

Limitation strings for WO-10b (manifest, support matrix, W24 text):
- `extrapolated` (R-433, verbatim from `EXTRAPOLATED_LIMITATION`): "extrapolated: 12 of 61 reactor requests,
  reported, not a distance from the data. At C1's loop state the reactor-inlet H2/N2 sits on the kinetics' data
  edge, so the per-evaluation flag is decided at solver resolution: it flips between solves 3.5e-5 K apart
  (cand-C1's P1 solve extrapolated, its minus poll at 653.15 K not)."
- `fd_gradient` and `qualified(A2,A3)` for REAL as recorded; noise_ratio is reported, not judged (§21.3).

Next executable action: WO-10b — `evidence/M05/<commit>/manifest.json`, support-matrix and limitation lines,
`docs/progress.md`, ADR 0039 note, the W24 gate table for `verdict`. Open for the design lane: S70's timing mask;
review notes N1 (stage-C restart eligibility) and N2 (in-flight key on a non-refusal box exception), not touched.
