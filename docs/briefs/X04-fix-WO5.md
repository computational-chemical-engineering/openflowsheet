# Engineer brief: X04 review fix round, then WO-5

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (head `bb4b21cd` or later). Read
first: `docs/X04_HANDOFF.md`, `docs/reviews/X04-review.md` (on main; its "Fix-round work order" items 1–6 are your
first task, verbatim), then the spec's WO-5 (`docs/derivations/X04-test-specification.md` ~line 327: web shell units
control and two screens A38/A39; L-X04-1–3 in `benchmarks/t08/support_envelope.yaml` + `scripts/msg_catalogue.py
sync-limitations` (A37); `docs-site/guide/units.md` (A40)). Shared rules as `docs/briefs/X04-build-A.md`
(venv/PYTHONPATH, serial tests, decisions log from D-13, stop rules, cap ~150k with handoff, trailers, named paths,
forbidden paths).

1. **Fix round** (review items 1–5): both description texts **verbatim** from the review; `REVIEW.json` new `sha256` /
   `characters`, design-lane review approved (reviewer, 2026-11-09), **human review stays pending — never set it**;
   S1, S2, S4 tests/fixes; N1–N3 doc edits verbatim; mark D-1…D-12 ruled (D-7 changed). One commit per item group.
2. **WO-5** except the evidence manifest (the manifest comes after CI, briefed separately). Web-shell tests as WO-8b ran
   them (node tests; browser smoke locally if the harness exists). Generators: `t08_support_matrix.py --emit/--check`,
   `msg_catalogue.py sync-limitations --check`, `doc_pages.py --check`.
3. **Not yours** (final work order, next brief): surface chain c_8, `SNAPSHOT_X04`, t08_w2 surface digest; and the
   description-review test stays red until Frank's human review. Record those failing counts; every other test in the
   brief's list plus `tests/test_t07_w6c_descriptions.py` and the web tests: 0 failures. F0 PASS; MSG check PASS;
   ruff/format.
4. Rewrite `docs/X04_HANDOFF.md` (state, gates, next = final work order); push `wp/X04`.

Report (≤ 20 lines): commits; the two description files' sha256 (full) and character counts; S1/S2/S4 status; WO-5
assertions A37–A40; F0 line; test counts; known-red counts; anything stopped on.
