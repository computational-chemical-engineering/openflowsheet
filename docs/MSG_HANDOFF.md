# MSG handoff (after WO-9, WO-10) — 2026-11-07

Branch `wp/MSG`, worktree `.claude/worktrees/msg`. Spec `docs/design/MSG-messages.md`; choices in
`docs/MSG_DECISIONS.md` (D0-1…D10-1). Not merged. WO-0…4, 6…10 done; WO-5 parked (F0 M9).

## Done (commits)

- WO-9 `3842f686` (complete entries: revision_not_ready, unsupported, DIM-01, out_of_domain,
  pressure_rise, task_unsupported, model_unsupported; pages, schema fixtures, U05 CLI pin),
  `184479d8` (corpus C01–C12, `tests/test_msg_corpus.py`, `--msg-update`).
- WO-10 `5a68e53c` (web shell: error panel, job and failure screens show explanations).
- Decisions `0067129c`; merge of main `b1a82351`; manifest
  `evidence/MSG/b1a82351…/manifest.json` (`implemented`) and harvest rows (D9-9).

## Rules a later WO must keep

- A catalogue edit needs `scripts/doc_pages.py` and `scripts/t07_schema_fixtures.py --write`.
- Corpus texts change only by `pytest tests/test_msg_corpus.py --msg-update`, diff reviewed.
- `pending` items are strict xfails: when one XPASSes, move it into the case's facts.

## Next

- WO-5 (when the design lane unfreezes the thermal modules): the C01/C02/C11 pending items turn
  red as their numbers appear; regenerate the texts.
- Design lane (batched): D9-2 (§4.4 rule 2 for DRAFT/NOT_RUN checks and implicated objects),
  D9-10 (MSG-G0 (c) after F0), the prose of the seven new complete entries, plus the earlier
  D7-7, D7-10, D6-3, D6-4/D7-9, D4-1, D3-4.
- Merge blocker: `explain.md` reviews in `REVIEW.json` (D7-8). Then re-take the manifest as
  `tested`; the single reviewer pass.

## Gates at the end of this run

Suite at `b1a82351`: 1 failed (description reviews), 15065 passed. MSG-G0 a/b 0 diff, d 0 in 442
stores, c see D9-10; F0 PASS. Detail at the tail of `docs/MSG_DECISIONS.md`.
