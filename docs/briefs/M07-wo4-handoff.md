# M07 WO-4 handoff (2026-10-17, WO-4b: done)

Branch `wp/M07` (worktree `.claude/worktrees/m07`). Build log J21–J30 has the choices; J29 lists the open questions.

## Done
- `672df66` environment block before any rung (J26). `1623633` `replay` and the store archive (J27).
- The real journey at J = `1623633db5afd6a55e2807f848ad4cf6a84e71b3`, committed at `c1f104f` under
  `benchmarks/m07/journey/1623633…/` {journey.json, journey.md, journey.experiments.json, m05/ (R3's re-run)}.
  `check` ACCEPT; `replay` bitwise (13 s), exit 2 on `OMP_NUM_THREADS=2`. Same numbers as the `8f85aa2` run (J28).
- Tests: `tests/test_m07_journey.py` A24 on a dry run (default gate); `tests/test_m07_journey_record.py`
  A20–A23, A25, A26 on the committed record (default gate), A24 replay `-m pymrm`.

## How to re-run
- Journey: a clean detached worktree at the new J; `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONPATH=src`
  `PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo <m05>/.venv-nlp/bin/python scripts/m07_journey.py run --out
  benchmarks/m07/journey/<J> --artifacts <dir> --m05-record benchmarks/m05/records/trust-region-study-real.json`
  (~55 min; R3 re-runs M05 while `carry.journey_files` differ from M05's run commit).
- Replay / opt-in: `OMP_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python scripts/m07_journey.py replay <dir>`;
  `pytest -m pymrm tests/test_m07_journey_record.py` in the main `.venv` (`.venv-nlp` has no pytest; J25).

## Not done / next
- Design-lane ruling round: J22, J25, the T* label (J29), and J27's list of members replay takes from the record.
- The evidence manifest for M07 and the `reviewer` pass on WO-1/WO-4 (spec §13) are the session's.
