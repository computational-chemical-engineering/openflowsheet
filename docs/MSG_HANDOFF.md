# MSG handoff (after WO-11) — 2026-11-06

Branch `wp/MSG`, worktree `.claude/worktrees/msg`. Spec `docs/design/MSG-messages.md` (§4.6 amended); review
`docs/reviews/MSG-review.md` (binding); brief `docs/briefs/MSG-build-WO11-12.md`; choices `docs/MSG_DECISIONS.md`
(D11-1…D11-10, commit index at the end of the WO-11 section). Not merged.

## Done in WO-11

- WO-5a (Q1): sidecar at the traversal hop → `run.diagnosis`; patterns; `outlet` derived; register R-942.
  Lifted: C01 action, C02 numbers + S4, C11 numbers; C09 records `[value, low, high]`; `values` pinned to
  independent expectations (change set, `iapws95.T_MIN/T_MAX`, steam tables).
- S2 (`_typed` non-finite), M2 (`pressure_rise(valve)`), S1 (`out_of_domain` example wording; `numerical`
  under iterative outcomes), Q2 (rule 2 + `parse_check`; three inner codes complete; C06/C07/C08/C10 lifted),
  Q6 (`explain.md` edits; design-lane review in `REVIEW.json`; `MSG_FILE_SHA256`, `D_4` = `eaff4585…`),
  Q7 (FB-01's three complete), S3 (`unsupported`), S4 (job ending reasons complete, kind kept `bug`).

## Still strict xfails (3)

- C01 `numbers` (`q1c`: kernel-only; F6 v2 models, ADR 0065).
- C08 "degc" and C10 instance `B` (`ctx`: need the revision as an ApiError's render context; design question).

## Open questions for the design lane (batch with WO-12's prose check)

- D11-7: load the revision into an ApiError's render context at projection, or declare C08/C10's gaps?
- D11-10: `worker_lost`/`owner_lost`/`store_error` kind — an `environment` kind needs a schema + ADR 0058 change.
- R-942's number: re-check against `main`'s register at the merge (WO-12 adds the c_4 entry after it).

## Next: WO-12 (brief's WO-12 section)

M1 (rest of §4.2.6, incl. `pressure_fall` — it already has args/params/pattern; `isentropic_state_single_phase`;
outcomes incl. `CHECKPOINT_INCOMPATIBLE`'s kind; S5), M3 (`--parts bd` default), M6 (c_4 entry, D_4 on the merge
tree), M4 + evidence, full gate. A catalogue edit needs `scripts/doc_pages.py` and
`scripts/t07_schema_fixtures.py --write`; complete entries need `examples`. Corpus texts change only by
`pytest tests/test_msg_corpus.py --msg-update`.

## Gates at the end of WO-11 (head before this handoff)

MSG-G0 a 0 diff, b 0/562 (108 bundles); F0 PASS (M1 50/50 … M9 35/35); ruff, format, mypy (254 files) clean;
MSG tests + WO-5a-path tests 777 passed, 3 xfailed. `test_t08_w2_description_reviews`: one open item,
`explain: human pending` (Frank). No full gate run.
