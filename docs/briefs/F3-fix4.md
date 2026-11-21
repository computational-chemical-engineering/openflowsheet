# F3 fix round 4: the build-lane changes of ruling round 2

Lane: build. Agent: `opus-engineer`. Worktree `.claude/worktrees/f3`, branch `wp/F3`, start at the commit that adds
this brief (on top of 576f7eab, the rulings). Do not spawn sub-agents yourself. Read `CLAUDE.md` (repo root) first,
then `docs/reviews/F3-rulings-2.md` whole: its section "Build-lane changes" (C1 to C5) is your spec, with the
acceptance test of each. Budget about 150k tokens; at the cap commit what is complete, log where you stopped, end.
Report in at most 300 words; detail goes into `docs/F3_DECISIONS.md` as a new entry "Fix round 4".

## The work

C1 to C5 exactly as the rulings file states, in its order, one commit each, the message naming "F3 rulings2 Cn".
Run each change's acceptance test and record its result (counts) in the commit message and the log. Where a test
must fail when the change is reverted locally, do the local revert, record the failure, and restore (never commit the
revert). C3 changes `records/store.py` behaviour on one error path only; run `tests/test_f3_*.py` and
`tests/test_t07_interrupt.py` after it.

## Constraints

- Do not touch `REVIEW.json` (Frank's human review waits on him; the one expected red stays).
- Stage named paths only; never `git add -A`.
- CI 44322172910 (on db59c345) is running; do not wait for it. Its codehealth job already failed (informational;
  the known `local.py` duplication, F3-3-4, accepted debt).
- Before pushing: `ruff check`, `ruff format --check`, full mypy, the F3 battery (`tests/test_f3_*.py`,
  `tests/test_t07_q26.py`, `tests/test_t07_interrupt.py`, the manifest and harvest tests, `scripts/t08_support_matrix.py
  --check`), F0 (`scripts/corpus_identity.py --check`). Quiet runs: log to a file, read only on failure.
- C5: the manifest stays `implemented` (CI on the pushed head decides `tested`, set by the orchestrator later).
- Push `wp/F3` at the end (work-package branch; not main).

## Report

Per Cn: sha, acceptance result with counts; the battery and F0 results; the pushed head; anything left open.
