# LINE06 F8-FR: the F8 review fix round

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f8`, branch `wp/F8`, at the head F8-FR0 left (wp/F2 merged in).
Logs under `/home/eajfpeters/.cache/line06/f8-fr/` only. Tests: `PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH
PYTHONPATH=src`. Log every choice as `DECISION F8-FR-<n>` in `docs/F8_DECISIONS.md`. Budget about 150k.

## The task

Carry out the work order "Fix-round work order F8-FR" in `docs/reviews/F8-review.md` (on main,
`/home/eajfpeters/Code/OpenFlowsheet/docs/reviews/F8-review.md`, section at line ~208), items 1 to 9, reading each
finding it cites (M1, M2, S1 to S6, ruling 2) in the same file. The fixes and tests are stated there; follow them. A
finding you cannot fix as stated: log the measured fact as `STOP F8-FR-<n>` and continue with the others.

## Acceptance (judged on these alone)

Each item committed (named paths) with its test and the mutation controls the review asks for, recorded in
`docs/F8_DECISIONS.md`. No served digest moves (a move is a STOP). Item 9's run at the final head: F0 PASS (the nine
counts); the surface suites, `tests/test_f8_*`, `tests/test_k05_replay.py`, the MSG suites, `tests/test_x07a_*`, the
harvest test pass; `HARVEST_SIZE` from the run; the manifest re-taken at that head (status `tested`, only commands you
ran there, with counts). ruff, ruff format --check, mypy src clean. Do not push. No background job of yours running
when you report. Report in 200-300 words: commits per item, test counts, the F0 line, the manifest path, anything left.
