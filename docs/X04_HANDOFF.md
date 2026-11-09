# X04 handoff (review fix round + WO-5 done) — 2026-11-09

Branch `wp/X04`, worktree `.claude/worktrees/x04`. Briefs `docs/briefs/X04-build-A.md`, `-B.md`, `X04-fix-WO5.md`;
review `docs/reviews/X04-review.md` (sound, no must-fix); decisions `docs/X04_DECISIONS.md` (D-1…D-12 ruled, D-7
changed; D-13…D-15 new, for the next ruling round).

## State
- **WO-1–WO-4 done**, reviewed. **Fix round done:** both descriptions verbatim from the review (`get_job_result.md`
  1485 chars `3c96f32e…`, `get_stream_table.md` 1500 chars `b7ce4ed4…`), REVIEW.json design-lane `reviewed`
  (reviewer, 2026-11-09), human `pending` (Frank's); S1 parity case `mole_fraction=%,molar_entropy=kJ/(mol K)` in both
  A31 tuples; S2 `test_a19_a_kinded_number_is_in_its_kinds_si_unit`; S4 `_bundle_display_units` applies the request
  bound first (test `test_d8_a_bundle_directory_applies_the_request_bound_first`, red without the fix); N1–N3 in ADR
  0075 D6.5/D7.6 and spec §4.
- **WO-5 done (except the manifest):** L-X04-1…3 in the envelope, synced, support matrix and messages page
  regenerated, message_entry fixtures re-taken (catalogue digest) (A37); web shell `apps/web/js/units.js` + header
  control, streams screen stream table and failure screen send `display_units`, as-solved table labelled SI (A38,
  D-14); no conversion constant in `apps/web/js` (A39); `docs-site/guide/display-units.md` (A40, D-13 — `guide/units.md`
  is the generated unit catalogue). `routes.js` regenerated (was stale since WO-3/4, D-15).
- Tests: `tests/test_x04_shell_and_docs.py` (A37, A39, A40; 8), `tests/web/x04-units.test.mjs` (A38; 6), browser
  smoke `test_x04_a38_with_eng_a_stream_s_t_is_the_server_s_display_value` (ran locally, chromium).

## Next — final work order (orchestrator)
- Surface chain link c_8 (R-1010…), `SNAPSHOT_X04` / `tests/x04_schema_support.without_x04` (pattern
  `st_schema_support.py`), t08_w2 surface digest. Then `evidence/X04/<commit>/manifest.json` (A1–A40) after CI.
- Frank: human review of the two descriptions (REVIEW.json), ADR 0075 accept; design lane: rule D-13…D-15.

## Gates (measured at `ba5fb7cf` + fixture re-take)
- Battery (x04 ×5, st ×4, t06 units ×2, schemas_p01, msg_* ×7, t07 w5b/w5e/conformance/global_state/injection/q26/
  w5a/w6a/w6b/w6c, m06 fixtures/http/static_scan/browser_smoke/contrast, rrc_application, m07a chain, t08_w2 ×9,
  doc_pages, t05_w11), serial, `OMP_NUM_THREADS=1`, browser required: 1856 passed, 29 failed, 3 xfailed.
  Known red (final WO / Frank): m07a surface chain 14, w5e R4-G3/snapshots 5, t08 surface digest 9, description
  reviews 1 (human pending). Other failures 0 (message_entry fixtures re-taken, w5e re-run: 5 known only).
- Node `tests/web/*.test.mjs` 104 pass. F0 PASS (M1 50/50 … M8 105/105, M9 35/35). MSG check PASS 394 entries
  (95 complete), G2 0, G5 clean; `t08_support_matrix.py --check` 0 problems; `doc_pages.py --check` up to date;
  `m06_web_routes.py --check` clean; ruff, ruff format clean.
