# X04 handoff (final work order done) — 2026-11-09

Branch `wp/X04`, worktree `.claude/worktrees/x04`. Briefs `docs/briefs/X04-build-A.md`, `-B.md`, `X04-fix-WO5.md`,
`X04-final-WO.md`; review `docs/reviews/X04-review.md` (sound, no must-fix); decisions `docs/X04_DECISIONS.md` (D-1…D-12
ruled, D-7 changed; D-13…D-18 for a design-lane glance, non-blocking).

## State
- **WO-1–WO-5, the review fix round and the final work order done.** ADR 0075 stays **Proposed** (Frank's accept
  pending on the board); both descriptions' human reviews pending (Frank records them with his script).
- **Final WO:** `origin/main` merged (`034bc43c`, docs only since ST's merge; no conflicts). Surface chain link
  **c_8 (R-1010)**: `strip_x04` = `tests/x04_schema_support.without_x04`, **D_8 = `6be1c002…`**; `without_x04` on the
  served list = ST's D_7 `553b7612…` exactly; moved tools `get_project`, `get_job_result`, `get_stream_table`,
  `explain`; retexted exactly X04's two (pre-X04 copies in `tests/fixtures/x04/pre_x04_descriptions/`).
  R4-G3 `SNAPSHOT_X04` (9 responses: `get_project`, `explain`, `solve`, `submit_job`, `get_job`, `list_jobs`,
  `wait_job`, `cancel_job`, `get_job_result`); stripped, each is its earlier snapshot; earlier strip chains take X04 out
  first. t08_w2 surface digest: `X04_SERVED_SHA256`, `test_x04s_surface_move_decomposes_onto_sts` (OPT's precedent
  `2669896b`). Register R-1010…R-1016 (Proposed), R-077 pointer; ADR 0019 Amendment 17 and `interfaces-frozen.md`
  name c_8 (`6ab3ce6e`, `9b38ed11`).

## Next
- CI on `wp/X04` (both architectures); then `evidence/X04/<commit>/manifest.json` (A1–A40) and the T08 harvest.
- Frank: ADR 0075 accept; human review of `get_job_result.md` (`3c96f32e…`) and `get_stream_table.md` (`b7ce4ed4…`).
- At the accept: ADR 0075 status line, R-1011…R-1016 "Proposed" → accepted, ADR 0019 Amendment 17 heading.

## Gates (measured at `9b38ed11`)
- Battery (x04 ×5, st ×4, t06 units ×2, schemas_p01, msg_* ×7, t07 w5a ×3/w5b/w5e/conformance/global_state/
  injection/q26/w6a/w6b/w6c, m06 fixtures/http/static_scan/browser_smoke/contrast, rrc_application, m07a chain +
  harvest, evidence_manifests, t08_w2 ×10, doc_pages, t05_w11), serial, `OMP_NUM_THREADS=1`: **2486 passed, 1 failed,
  3 xfailed**. The one: `test_every_description_is_reviewed_by_both_lanes` — `2 open: ['get_job_result: human
  pending', 'get_stream_table: human pending']` (Frank's).
- F0 PASS (M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35). MSG check PASS 394 entries (95 complete),
  G2 0, G5 clean. `ruff check`, `ruff format --check` clean (1173 files).
