# ST handoff (wp/ST, 2026-11-06) — WO-1 and WO-2 done

**State.** Branch `wp/ST` (worktree `.claude/worktrees/st`), from main e91f25d1 + brief e780d2e7. Not merged;
ADR 0068 still Proposed (Frank's acceptance pending). Choices and escalations: `docs/ST_DECISIONS.md`.

**Commits.** c79a99db core `application/stream_table.py` · 1d3c954c legacy-route unit ids (D1-3, revertible) ·
80346616 `tests/test_st_core.py` + `tests/st_support.py` + decisions · 79e44995 schema
`schemas/stream-table.schema.json` (= `_data/schemas/…` via symlink), fixtures `tests/fixtures/st/`,
`tests/test_st_schema.py`.

**Gates (core level).** `pytest tests/test_st_core.py tests/test_st_schema.py`: 62 passed, 1 xfailed (G8,
strict). G1–G7, G9, G10, G14, G16 pass; **G8 FAILS on g8/T05b:SC-1 (2016 W)**, escalated as E1. F0
`scripts/corpus_identity.py --check` PASS (M1 50/50 … M9 35/35). No diff under verify/thermo/models/run/
orchestrator/compiled.py. ruff, ruff format, mypy clean on the new module.

**Pending.**
- `schemas/registry.json` entry for `stream-table.schema.json` (shared with wp/MSG): add in WO-3 after MSG
  merges. Until then `tests/test_t08_w4_package_data.py` fails 4 tests (A48 registry = schema directory).
- G5's "every code is a catalogue key" is checked against `stream_table.CODES` only: the catalogue entries
  are WO-4 (after MSG). G15 likewise.
- Design-lane questions for ST's reviewer pass: D1-1 (Python `sum` vs "from 0.0"), D1-3 (legacy-route
  unit ids), D1-6/D1-7 (schema amendments to §5), E1 (G8 on temperature-degenerate lifted splits; note
  D4's premise that the split list is not derivable from `revision.json` is false).

**Next (after wp/MSG merges; `git merge main` first).** WO-3 operation: `LocalApplication.get_stream_table`
maps `StreamTableError` to `ApplicationError` (`not_found` through MSG's member-detail helper, `unsupported`
with the hint, `internal_error`); `OPERATIONS` row after `get_artifact`; registry entry; G11–G13. Then WO-4
catalogue (seven codes), WO-5 CLI `streams`, WO-6 docs, WO-7 manifest + full gate + reviewer.

**Recorded numbers** (for WO-7's manifest; `ST_RECORD=<file>` on the core tests writes them as JSON lines):
G1 max |closure|/tol 1.34e-7, envelope gap 1.4e-10 W; G2 vf − lever 0.0 (bound 2.3e-7); G3 max rel error
3.8e-10; G7 41 bitwise (+193 SYN-001 beyond the list, 0 mismatches); G8 max passing ratio 1.8e-4; G10 44
served, 8 refused; G14 TH-C1 0.023 s, largest (NET03) 0.014 s; G16 (e) syn001 32 R3, 2 flagged, 0
disagreeing, max c·ε_adm 9.3e-12; pr-c1 0 R3.
