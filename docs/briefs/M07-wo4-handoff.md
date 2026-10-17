# M07 WO-4 handoff (2026-10-17, WO-4c: done)

Branch `wp/M07` (worktree `.claude/worktrees/m07`). Build log J21–J37 has the choices; the review is
`docs/reviews/M07-review.md`, its rulings spec §19 (Amendment 2, R-452…R-455).

## Done
- WO-4b: the journey at J = `1623633` (`c1f104f`); superseded by Amendment 2 and retired at `7f108d3` (J31).
- WO-4c: MF1 `6501016` (δ_T bound tolerance), MF2 `854deda` (carry sets, GC-CARRY-1), SF2 `2905034` (`offered`),
  SF1 `974c395` (M05 re-run replay, `compare(stem=)`), SF3 + record at `c4e8467`.
- The real journey at J′ = `974c395fbb2ab60fd69fc8d53e4f33e7207e9f3e` under `benchmarks/m07/journey/974c395…/`.
  Every number bitwise equal to the `1623633` record; R3 and the journey read `BOUND_LOWER` (J37). `check` ACCEPT;
  `replay` bitwise (17.7 s) with the M05 re-run replay clean.

## How to re-run
- Journey: a clean detached worktree at the new J; `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONPATH=src`
  `PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo <m05>/.venv-nlp/bin/python scripts/m07_journey.py run --out
  benchmarks/m07/journey/<J> --artifacts <dir> --m05-record benchmarks/m05/records/trust-region-study-real.json`
  (~55 min; R3 re-runs M05 while `carry.r3_files` differ from M05's run commit).
- Replay: same interpreter and environment, `scripts/m07_journey.py replay <dir>` (a re-run R3 needs pyomo).
- Opt-in tests (`-m pymrm`): `.venv-nlp` with the nlp-test-tools appended to `sys.path` in process, not on
  `PYTHONPATH` (J25, J35): `python -c "import sys; sys.path.append('<tools>'); import pytest;
  sys.exit(pytest.main(sys.argv[1:]))" -m pymrm tests/test_m07_journey_record.py tests/test_m07_journey.py`.

## Not done / next
- M07's evidence manifest; whatever the session schedules after the review's fixes (WO-3, WO-5…WO-8).
- M02 follow-up (A2.5): `env.verify` lists `variant_id` against R-259; the journey's filter goes once it is fixed.
