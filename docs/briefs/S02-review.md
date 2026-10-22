# S02 — independent review and ruling round (design lane, `reviewer`)

Branch `wp/S02` (worktree `/home/user/ofs-s02`). The package's single `reviewer` pass; it carries the open questions.
S02 touches residuals, derivatives, phase logic, scaling, a new edge-3 trigger (ADR 0044, Proposed) and continuation.

## The question
1. Do WO-1, WO-2, WO-2b and WO-3 meet `docs/derivations/S02-spec.md` (as amended by §17 and §18) and ADR 0044, and do
   the tests verify what A01–A22 claim (mutation-minded)? Pay special attention to: the bubble-point endpoint as an
   exact root of `H(·,0)`; ADR 0044's trigger (`orchestrator/recovery.py`, three call sites) — does it change any
   pre-S02 behaviour (S01, T03, T04 suites)?; the `dimensionless` column-only kind; the registered second root R2.
2. Rule on the open `QUESTION:` lines in `docs/S02_DECISIONS.md` — in particular Q-S02-WOG-1 (the §18.2 identity
   claim at the generator's 1e-30 K stop; default stop 1e-42 K), Q-S02-WO2b-1 (A14: same `state_sha256` from a ±5 K
   start vs `SAME` within the state tolerance; the bits differ by ≤ 1.1e-11), WO-G's "six regular variant sets, not
   five", Q-S02-3 / R-533. A tolerance changes only with a derivation that the registered value was wrong.
3. Should ADR 0044 become Accepted, and on what condition?

## Facts with anchors
Code `src/openflowsheet/models/syn001/column.py`, `column_solve.py`, `models/rows.py` (ratio/fraction/bubble rows),
`numerics/scaling.py`, `compile/spec.py`, `orchestrator/recovery.py`; tests `tests/test_s02_column_wo1.py`, `_wo2.py`,
`_wo2b.py`, `_wo3.py`; reference `docs/derivations/scripts/s02_reference.py` (1064 claims); manifest
`evidence/S02/66377ba…/manifest.json` (`implemented`; 30/32; A14 strict xfail); `scripts/s02_evidence_manifest.py`;
design handoff `docs/briefs/S02-design-handoff.md`. Env: from the worktree,
`PYTHONPATH=$PWD/src /home/user/openflowsheet/.venv/bin/python -m pytest -q tests/test_s02_*.py tests/test_s01_*.py`.

## Exit test
`docs/reviews/S02-review.md` (must-fix / should-fix / note with file:line and a failure scenario; rulings; the fix
work order), a dated amendment in the spec for rulings, register entries **R-550…R-559**, ADR 0044 status decision
recorded. Do not edit production code; do not set `reviewed`; do not run the whole suite.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/S02-review-handoff.md`, stop. Report ≤ 150 words.
