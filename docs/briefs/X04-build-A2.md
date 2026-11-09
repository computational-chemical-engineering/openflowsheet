# Engineer brief: X04 WO-3 — messages and get_job_result (continuation of engineer A)

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (exists; head `82251ffc`). Read
first: `docs/X04_HANDOFF.md` (WO-3's five steps in order, with anchors), `docs/X04_DECISIONS.md` (D-1…D-4), then the
spec: `docs/adr/0075-X04-units-at-the-boundary.md` (D7, D8, D9) and `docs/derivations/X04-test-specification.md`
sections M and T (`get_job_result`), A15–A20, A31–A33, A36, PU16. Same rules as `docs/briefs/X04-build-A.md`
(venv/PYTHONPATH, serial tests, decisions log, stop rules, cap ~150k, trailers, named paths, forbidden paths).

**Orchestrator decision (2026-11-09):** the surface chain link (c_8, register R-1010…) and `SNAPSHOT_X04` /
`without_x04` are **not** yours: they are taken once in X04's final work order after WO-4/WO-5 fix the schemas. So
`tests/test_m07a_surface_chain.py` and the 5 R4-G3 tests in `tests/test_t07_w5e_application_results.py` stay red on
the branch for now; record their failing counts, do not touch them. Everything else in the brief's test list: 0
failures. ADR 0019 Amendment 17 is free (OQ1).

Do WO-3 steps 1–5 of the handoff; commit per step group; update `docs/X04_HANDOFF.md` in place (state, gates,
next = WO-4/WO-5 by engineer B); push `wp/X04`. Report (≤ 20 lines): commits, assertions covered and status, F0 line,
catalogue check, test counts, the two known-red counts, anything stopped on.
