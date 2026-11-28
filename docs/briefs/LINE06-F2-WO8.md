# LINE06 F2-WO8: the F2 review's fix round

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch `wp/F2`, head `39244e80` (clean). Logs and scripts
under `/home/eajfpeters/.cache/line06/f2-wo8/` only; wait on log lines, not `kill -0`. Tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`; F0 with
`--log /home/eajfpeters/.cache/line06/f2-wo8/f0-detail.log`; nlp tests via `scripts/m03_nlp_check.sh --no-inventory
/home/eajfpeters/Code/OpenFlowsheet/.venv-nlp /home/eajfpeters/Code/OpenFlowsheet/.reference-downloads/m03-ipopt --
<tests>`. An engineer works in `.claude/worktrees/f8`; do not touch it. Budget about 150k: at the cap, commit what
is complete (one commit per item), write in `docs/F2_DECISIONS.md` which items remain, and end; a fresh engineer
continues.

## The task

The specification is the review on `main`: `/home/eajfpeters/Code/OpenFlowsheet/docs/reviews/F2-review.md`. Read
"Findings" (M1, M2, S1 to S9, N1) and "The ruling batch" (items 1 to 5, line ~114) for each item's exact content, then
build **"Fix-round work order F2-WO8"** (line ~236), items 1 to 12, in that order, one commit per item, a
`DECISION WO8-<n>` per item in `docs/F2_DECISIONS.md`. The rulings are the design lane's: apply them as written; if
one cannot be applied as written, log it and continue with the next item (do not invent an alternative).

Not yours: the ADR 0062 text edits (the orchestrator applies them after you); `REVIEW.json` human verdicts (item 9
resets `check_admission`'s human status to `pending`, it does not set one).

## Acceptance (judged on these alone)

As the work order's item 12 states: `tests/test_f2_*.py`, `tests/test_v03_semantic_roles.py` (22 passed), the
surface suites (`tests/test_t07_*`, `tests/test_t08_w2_*`, `tests/test_m07a_surface_chain.py`) except
`tests/test_t08_w2_description_reviews.py`'s human-review check for `check_admission` (expected red until the user's
review; name any other red), the MSG suites (`tests/test_msg_*.py`), the nlp tests, F0 PASS (M1 50/50, M2-M5 61/61,
M6 85/85, M7 52/52, M8 105/105, M9 42/42), ruff, ruff format --check, mypy src clean; a new evidence manifest
`evidence/F2/<head>/manifest.json` (`tested`; real commands and counts at that head). A move of F0 or of any served
digest other than item 9's is a STOP: commit nothing further and report.

Commit named paths only, never `git add -A`; do not push. Make sure no background job of yours runs before you
report. Report in 200-300 words: commits per item, test counts per suite, F0 line, every re-pinned digest
(old -> new), items not done and why.
