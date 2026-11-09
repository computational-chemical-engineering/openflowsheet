# X04 handoff (engineer B: WO-4 done) — 2026-11-09

Branch `wp/X04`, worktree `.claude/worktrees/x04`. Briefs `docs/briefs/X04-build-A.md`, `-B.md`; decisions
`docs/X04_DECISIONS.md` (D-1…D-12, for the design lane's one ruling round).

## State
- **WO-1–WO-3 done** (engineer A): `units/display.py`; project ambient; messages and `get_job_result`.
- **WO-4 done** (`7371219d` operation, `9dcb6960` schema, `ade02030` formats and CLI, `d15178cf` description,
  `0d7f8034` tests, `ef69160c` A13 fix, `e71de62b` SITES read-only): `stream_table.SITES` (§4 + `phase_id.ordinal`,
  D-6), `stream_table.displayed`; `get_stream_table(..., display_units=None)` parses with `_display_units` and hashes
  the displayed document; OPERATIONS row member `display_units`; schema `display` per object (`propertyNames`, item
  once by pointer, D-11) and root `display_units`; `stream_table_format` text/csv in display units (D-9, D-10);
  `streams --display-units` (bundle directory: no ambient, D-8); `get_stream_table.md` 1499 chars (D-7), both
  reviews pending. `tests/test_x04_stream_table.py`: A14, A21–A31, A33, A34 (+ D-8, D-9), 29 tests.
- A13 was flaky before WO-4 (3/4 fail at `df59a3df`): run-manifest/bundle `size_bytes` vary with
  `elapsed_seconds`; fixed in the test (D-12), 4/4 pass.

## Next
- **WO-5** (engineer): web shell units control and the two screens (A38, A39), L-X04-1–3 and `sync-limitations`
  (A37), `docs-site/guide/units.md` (A40), `evidence/X04/<commit>/manifest.json` (A1–A40).
- **Final WO** (orchestrator decision 2026-11-09): surface chain link c_8 (R-1010…), `SNAPSHOT_X04` /
  `tests/x04_schema_support.without_x04` (pattern `st_schema_support.py`) — schemas are now final for WO-3/WO-4
  (`job.schema.json`, `application-results`, `project-policy`, `stream-table`, both request schemas).
- Design lane: review `get_job_result.md` and `get_stream_table.md` (REVIEW.json), rule on D-1…D-12.

## Gates (measured at `0d7f8034`/`e71de62b`)
- Targeted battery (x04 ×4, st ×4, t06 units ×2, schemas_p01, msg_*, t07 w5b/w5e/conformance/global_state/injection/
  q26/w5a_operations/w6a/w6b/w6c, m06 fixtures/http, rrc_application, m07a chain, t08 w2 reviews/digest), serial,
  `OMP_NUM_THREADS=1`: 1573 passed, 30 failed, 3 xfailed. Baseline `df59a3df` same list: 1544 passed, 30 failed.
  Known red, identical ids before and after: m07a surface chain 14, w5e R4-G3/snapshots 5, t08 surface digest 9,
  description reviews 1. The other two after-run failures are fixed and re-run: `test_st_core` C-8 (`e71de62b`;
  st_core C-8 + x04 stream table + st cli/operation + x04 messages: 95 passed), A13 (D-12). Other failures: 0.
- F0 PASS (at `0d7f8034`): M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105,
  M9 35/35. `msg_catalogue.py check` PASS: 391 entries (95 complete), G2 0, G4 0, G5 clean. ruff, ruff format, mypy
  (touched modules) clean.
