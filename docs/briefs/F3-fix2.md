# F3 fix round 2: build-lane changes C1 to C12 of `docs/reviews/F3-review-2.md`

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f3`, branch `wp/F3`,
head after this brief's commit (review 68ca5b98). Work only there. Do not spawn sub-agents yourself. Budget about
150k tokens of context: at the cap, commit what is complete, write where you stopped in `docs/F3_DECISIONS.md`, and end.

## Status

ADR 0061 is Accepted; the review's clarifications are in its closing section "F3 ruling round 2 applied" and in
R-1052 to R-1057. **Do not edit `docs/adr/` or `docs/decision-register.md`** (C12's Amendment 8 sentence excepted, as
the review states it) **and do not re-rule**: the review's rulings bind. An ambiguity in a C item: take the reading
that changes no existing byte, record it as `DECISION F2-<n>` in `docs/F3_DECISIONS.md`, carry on. Q-F1 (ADR 0062's
`[p, q]` coefficients in `validate_record`) is with Frank: build nothing for it; JSON numbers only.

## The work

Read `docs/reviews/F3-review-2.md` whole (it is about 230 lines): the findings M1 to M4 with the measured repros, the
rulings, the five description verdicts and "Build-lane changes" C1 to C12 with their acceptance tests. One commit per
C item (C11's digest re-take may share the commit with its description edits), in the order given, each with its test
failing before and passing after where the item names one. Every repro in the findings becomes a test (M1's alias
file must be refused fast: state the measured time).

C9: fix the count assertion at `tests/test_t08_w2_description_reviews.py:33` in the form of its comment (name F3's
five), so that the test then fails only on the five pending reviews (state the remaining failure lines). Do not record
any review in `REVIEW.json`: the design-lane review is in the review file and Frank's is pending; the orchestrator
records them.

## Acceptance (run and quote)

1. `tests/test_f3_*.py` pass; `scripts/records_legacy_index.py --check` clean; `ruff check`, `ruff format --check`,
   full `mypy`.
2. The battery: the 62 files in `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/briefs/F3-battery.txt` plus the
   `tests/test_f3_*.py` not in it plus the T07/T08/M02/M04/M07a/F1 surface files WO5b touched (the same 71 files as
   WO5b's run; list them in the build log), once at the end on an unchanged tree (`PYTHONPATH=<worktree>/src`, repo
   `.venv`, no `-n`; at b0580939: 2132 passed, 1 failed). The only failure allowed is the description-review test on
   the five pending reviews.
3. `codehealth scan` on `records/` and `application/`: no brain function, every new or touched file health >= 9.0;
   `codehealth arch` 0 violations, 0 cycles.
4. F0 `scripts/corpus_identity.py --check` PASS.

Commits name `F3-fix2`. No evidence manifest, never `reviewed`. Append `## F3 fix round 2` to `docs/F3_DECISIONS.md`
(commits per C item, DECISIONs, every digest, snapshot and SHA moved old -> new, acceptance).

## Report (200 to 300 words)

Commits per C item; acceptance with counts; M1's refusal time; every digest and SHA moved; the remaining failure lines
of the description-review test; DECISIONs; what is left for WO7.
