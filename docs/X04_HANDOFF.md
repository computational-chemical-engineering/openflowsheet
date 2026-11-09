# X04 engineer A handoff (WO-1–WO-3) — 2026-11-09

Branch `wp/X04`, worktree `.claude/worktrees/x04`. Brief `docs/briefs/X04-build-A.md`; decisions `docs/X04_DECISIONS.md`.

## State
- **WO-1 done** (`44dd16db`): `src/openflowsheet/units/display.py` (table, D3 arithmetic, grammar, `DisplayUnits`,
  `DisplayUnitsError`, `row_to_si`, `csv_suffix`), re-exported from `openflowsheet.units`. Engineer B can consume it.
- **WO-2 done** (`cbd220b6`, `2811d0fd`): policy `ambient_pressure`, `authz.set_ambient_pressure` /
  `ambient_pressure_pa`, CLI `project ambient`, `get_project.ambient_pressure` (required, nullable), the five D9
  catalogue entries (all codes, WO-3's included). A14 left for WO-4 (needs the displayed stream table).
- **WO-3 not started.** Next, in order:
  1. `messages/render.py`: `_numbers(entry, params, display_units)` adds `display` (via `units.display_item`) when
     `RenderContext.display_units` is set; `_Scope.lookup` gives quantity params their display item and `_format`
     renders `format_number(display.value) + " " + unit` for a finite display (not under `!raw`). Share one helper
     for (number, unit, kind) between `_numbers` and `_format`.
  2. `application-results.schema.json#/$defs/explanation` numbers item: optional `display` (D7.1 item shape);
     `job.schema.json#/$defs/job_result`: optional root `display_units` (`{units, ambient_pressure}`).
  3. `JobResult.display_units` + echo; `LocalApplication.get_job_result(job_id, *, display_units=None)`: parse with
     `self._policy.current().ambient_pressure`; `DisplayUnitsError` → `api_error(e.api_error, e.message,
     pointer=e.pointer)` (+ `reason=e.reason` for `unsupported`); render `_run_failure` with
     `RenderContext(display_units=units)`; the `error` documents (root and `run_result.error`) get
     `detail.explanation` rendered with the same context (`project_response` keeps a carried explanation,
     `operations.explained_detail`). Contract protocol (`contract.py:187` area) and OPERATIONS row: request schema
     `display_units: {type: string, minLength: 1, maxLength: 1024}`, `decode=_members("job_id", "display_units")`.
  4. `bindings/descriptions/get_job_result.md` one sentence (REVIEW.json procedure); ADR 0019 Amendment 17 pointer
     paragraph (OQ1: 17 is free); `docs/interfaces-frozen.md` paragraph.
  5. `tests/test_x04_messages.py` A15–A20, A31–A33 (job result), A36; PU16 via `dispatch` in A6.
- **Then (B or A):** `tests/x04_schema_support.py` `without_x04` + `SNAPSHOT_X04` in
  `tests/test_t07_w5e_application_results.py` (pattern: `st_schema_support.py`, `opt_schema_support.py`; earlier
  packages' strip chains take X04 out first), taken once WO-3 and WO-4 schemas are final.

## Gates (measured)
- `tests/test_x04_display_core.py` 498 passed; `tests/test_x04_ambient.py` 41 passed; t06 unit tests 161 passed.
- `msg_catalogue.py check` PASS: 391 entries (95 complete), G2 0, G4 0, G5 clean.
- F0 PASS at `2811d0fd`: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- **Failing, escalated:** `tests/test_m07a_surface_chain.py` (11 tests) — `get_project`'s output schema moves the
  served MCP digest; WO-3 will move it again (`get_job_result` input + description). The spec names no chain link
  (c_8, register entry): design lane. R4-G3 snapshot tests (5) await `SNAPSHOT_X04` (above).
