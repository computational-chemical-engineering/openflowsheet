# LINE06 X06-fix1: the X06 review's fix round

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md`. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06`, head `020b7b72` (clean). Another
engineer works on F2 in `.claude/worktrees/f2`; leave it alone. Logs and scripts only under
`/home/eajfpeters/.cache/line06/x06fix1/`; wait on log lines, not `kill -0`. Budget about 150k context: at the cap,
commit what is complete, write where you stopped in `docs/X06_DECISIONS.md`, and end.

## The task

Carry out the work order in `docs/reviews/X06-review.md` (on **main**: read it at
`/home/eajfpeters/Code/OpenFlowsheet/docs/reviews/X06-review.md`), section "Fix-round work order" (line ~178), items
1 to 8, exactly as ruled in "Rulings on the batch" (line ~98) and the findings M1, M2, S1 to S3 (lines ~20-75). Do not
mark any human review: in `REVIEW.json` only the design-lane reviews become `reviewed` (reviewer: the X06 review,
citing `docs/reviews/X06-review.md`), human stays `pending`.

For item 7 (S3): the workstation has an NLP environment at `/home/eajfpeters/Code/OpenFlowsheet/.venv-nlp`. Write the
`optimize` half `importorskip`-guarded and run it there (PATH to that venv's bin, `PYTHONPATH=src`); record the run in
the manifest. If that venv cannot run it, the manifest says "not run" with the reason.

## Acceptance (report each)

1. Each of items 1 to 7 done, with its commit and its check (the review names one per item).
2. `tests/test_t07_q26.py` 6 passed; `test_every_description_is_reviewed_by_both_lanes` fails only on the 11 human
   items; `without_x06` still gives F3's `f7ec3c94...`.
3. Surface suites (`tests/test_x06_*.py`, `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`,
   `tests/test_m07a_surface_chain.py`, `tests/test_msg_*.py`, doc-page tests) in one process after your last code
   commit: the only failure is the description-review gate. ruff, ruff format --check, `mypy src` clean.
4. Bundle gate: 63 bundles, 60 ok, `b42b1ec439d1683c`. F0 PASS: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52,
   M8 105/105, M9 42/42.
5. A new `evidence/X06/<fix commit>/manifest.json` (`tested`, commands actually run), validated as WO5 did.

## Stops

A ruling that contradicts the code or the ADR; F0, a record, run identity, a request hash or a registered policy's
behaviour moving; a test that passes only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and the numbers; commits; DECISIONs; the new served digest.
