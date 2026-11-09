# Engineer brief: X04 final work order — re-base, surface chain c_8, SNAPSHOT_X04, t08 digest, register

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (head `c4358784`; WO-1–5 and the
review fix round done). Read first: `docs/X04_HANDOFF.md`, `docs/X04_DECISIONS.md`, `docs/roadmap/decisions.md`
entries for X04 (the c_8 decision). Pattern to follow exactly: ST's WO-7 (`git log --oneline main | grep "ST"`;
`docs/ST_DECISIONS.md` § WO-7; brief `docs/briefs/ST-WO7.md`) — ST took c_7 (R-1000) on top of OPT's c_6. Shared rules
as `docs/briefs/X04-build-A.md` (venv/PYTHONPATH, serial tests, stop rules, cap ~150k, trailers, named paths,
forbidden paths). Never set a human review in `REVIEW.json` (Frank records his own with his script).

## Do

1. `git merge origin/main` if main moved in non-docs files since the branch point (main has had docs only since ST's
   merge `a053690d`; merge anyway for a current base). Conflicts: keep both sides; a semantic clash → stop and report.
2. **Surface chain c_8** (R-1010): add X04's link in `m07a_rc.LINKS` (or wherever ST's c_7 lives), with its strip so
   that `without_x04` of the served surface equals D_7 `553b76122fefd4f09d6e91d16e7096d05b9f7793bb88e1876252dc2213e24894`
   exactly; update the chain test and the digest test (strip order: X04 first, as ST's did). Measure D_8 and record it.
3. **`SNAPSHOT_X04` / `without_x04`** for R4-G3 in `tests/test_t07_w5e_application_results.py` with a
   `tests/x04_schema_support.py` (pattern `st_schema_support.py`); earlier packages' strip chains take X04 out first.
4. **t08_w2 surface digest** (`tests/test_t08_w2_surface_digest.py`, 9 red): take X04's change the way OPT/ST did (find
   their precedent with `git log -S` on that file); never re-baseline without the strip proving the pre-X04 digest.
5. **Register**: R-1010 (c_8 link), R-1011… for ADR 0075's decisions in the repository's form (see R-1000…1006), and
   pointers from ADR 0019 Amendment 17 / `interfaces-frozen.md` as ST did. ADR 0075 stays **Proposed** (Frank's accept
   pending on the board).
6. Tests: the full X04 battery as the handoff lists it, plus `tests/test_m07a_surface_chain.py`,
   `tests/test_t07_w5e_application_results.py`, `tests/test_t08_w2_surface_digest.py`, `tests/test_t07_global_state.py`,
   `tests/test_m07a_harvest.py`, `tests/test_evidence_manifests.py`, `tests/test_st_*.py` (ST's chain/strip tests).
   0 failures **except** `test_every_description_is_reviewed_by_both_lanes` (red only on the two pending human reviews
   of `get_job_result` and `get_stream_table`; record its exact message). F0 PASS; MSG check; ruff/format.
7. Rewrite `docs/X04_HANDOFF.md`; push `wp/X04`; report. No manifest (after CI).

Report (≤ 20 lines): conflicts; D_8 and `without_x04` = D_7 check; R4-G3 / t08_w2 resolution; register ids; test counts;
the description-review test's message; F0 line; head sha; anything stopped on.
