# Engineer brief: X04 engineer B — WO-4 stream table and CLI

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (exists; head `df59a3df`, WO-1–3
done). Read first: `docs/X04_HANDOFF.md`, `docs/X04_DECISIONS.md` (D-1…D-5), then the spec:
`docs/adr/0075-X04-units-at-the-boundary.md` (D7.3 and the rest) and `docs/derivations/X04-test-specification.md` §4
site table, sections S and T (stream table), WO-4 at ~line 322, assertions A14, A21–A30, A31–A34 (stream table), A35.
Shared rules as `docs/briefs/X04-build-A.md` (venv/PYTHONPATH, serial tests, decisions log `docs/X04_DECISIONS.md`
from D-6, stop rules, cap ~150k with handoff, trailers, named paths, forbidden paths).

**Do:** WO-4 exactly as the spec lists it (`application/stream_table.py` display members and root echo;
`Inspection.get_stream_table(…, display_units=None)`, OPERATIONS row, decode; `bindings/descriptions/get_stream_table.md`
one sentence; `stream-table.schema.json`; `stream_table_format.py` header lines, labels, CSV suffix via
`units.display.csv_suffix`, values; CLI `streams --display-units`), tests `tests/test_x04_stream_table.py` with A14,
A21–A35 as assigned. Reuse WO-3's refusal helper (`f0735f09`). Inline schema shapes, not new `$defs` (a new `$def`
adds a T07 fixture and moves F0 M8 — see the WO-3 handoff).

**Known red, not yours (orchestrator decision 2026-11-09):** the surface chain (c_8, R-1010…), `SNAPSHOT_X04` /
`without_x04` (R4-G3), `tests/test_t08_w2_surface_digest.py`, and `test_every_description_is_reviewed_by_both_lanes`
(new description text awaits both reviews) are taken in X04's final work order. Record their failing counts before
and after your work; any **other** failure must be 0. F0 PASS unchanged; `msg_catalogue.py check` PASS; ruff/format.

Commit per step group naming X04 WO-4; rewrite `docs/X04_HANDOFF.md` in place (state, gates, next = WO-5 and the final
work order); push `wp/X04`. Report (≤ 20 lines): commits, assertions and status, F0 line, catalogue check, test counts,
known-red counts, anything stopped on.
