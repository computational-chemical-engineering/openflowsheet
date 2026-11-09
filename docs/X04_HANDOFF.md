# X04 handoff (engineer A done: WO-1–WO-3) — 2026-11-09

Branch `wp/X04`, worktree `.claude/worktrees/x04`. Briefs `docs/briefs/X04-build-A.md`, `-A2.md`; decisions
`docs/X04_DECISIONS.md` (D-1…D-5, for the design lane's one ruling round).

## State
- **WO-1 done** (`44dd16db`): `units/display.py` (`DisplayUnits`, `display_item`, `parse_display_units`, `csv_suffix`).
- **WO-2 done** (`cbd220b6`, `2811d0fd`): project ambient, `get_project.ambient_pressure`, the five D9 catalogue
  entries. A14 is WO-4's (needs the displayed stream table).
- **WO-3 done** (`5361491c` render, `c63ef0cd` operation and schemas, `a9a0d33a` description and docs, `68b3ab13`
  tests): `RenderContext.display_units` gives explanation `numbers` items `display` and renders quantity params from it
  (`render._measured`, `_display_item`); `get_job_result(job_id, *, display_units=None)` with the root echo
  `job_result.display_units` and both `error` documents explained under the preference (`local._displayed`);
  OPERATIONS row `display_units {string, 1..1024}` (`operations.DISPLAY_UNITS`, reuse it for WO-4); schema shapes are
  inlined (no new `$def`: a `$def` would add a T07 fixture and move F0 M8). `get_job_result.md` +1 sentence,
  REVIEW.json both reviews pending. ADR 0019 Amendment 17 and the `interfaces-frozen.md` X04 paragraph name WO-4's
  `get_stream_table` keyword too.

## Next: WO-4 / WO-5 (engineer B), then X04's final work order
- WO-4: `get_stream_table(..., display_units=None)` — reuse `LocalApplication._display_units(text, operation)` and
  `operations.DISPLAY_UNITS`. A32's test (`open_to <= {get_job_result, get_stream_table}`, `mcp_named == open_to`)
  accepts the new member without edits; A31/A34 for the stream table are WO-4's.
- Final WO (orchestrator decision 2026-11-09): surface chain link c_8 (register R-1010…), `SNAPSHOT_X04` /
  `tests/x04_schema_support.without_x04` (pattern `st_schema_support.py`), taken once WO-4/WO-5 schemas are final.
- Design lane: review `get_job_result.md`'s new sentence (REVIEW.json), rule on D-1…D-5.

## Gates (measured at `68b3ab13`)
- `tests/test_x04_messages.py` 38 passed; targeted battery (x04 ×3, t06 units, schemas_p01, msg_*, t07 w5b/w5e/
  conformance/global_state/injection/q26, m06 fixtures, rrc_application, m07a, t08 w2 reviews/digest): 1281 passed,
  29 failed, 3 xfailed. All 29 are the known surface/snapshot family:
  m07a surface chain 14 (11 before WO-3; +3 because `get_job_result.md` changed: control_iii, msg/st description
  pins), R4-G3 snapshots 5 (unchanged), `test_t08_w2_surface_digest` 9 (8 already red at `82251ffc`; +1 "differ
  from V17 C2 in exactly the two reviewed files"), `test_every_description_is_reviewed_by_both_lanes` 1 (red by
  design until the reviews are recorded).
- F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- `msg_catalogue.py check` PASS: 391 entries (95 complete), G2 0, G4 0, G5 clean. ruff, ruff format, mypy (touched
  modules) clean.
