# ST handoff (wp/ST, 2026-11-08) — WO-1…WO-6 done; WO-7 next

**State.** Branch `wp/ST` (worktree `.claude/worktrees/st`) = main `00a508bd` + `wp/MSG` `35403f42` merged
(56294e49, 22f64c65; brief `docs/briefs/ST-build-WO3-6.md`). Not merged to main; ADR 0068 Proposed (Frank's
acceptance pending); MSG still waits for Frank. Choices: `docs/ST_DECISIONS.md` (D1-…D6-, E1).

**Commits (WO-3…6).** 19c6857c registry entry · 444aa56f operation on every transport (+ surface re-records,
interfaces-frozen, D3-*) · c93a7216 limitations re-sync · 9328e59c generated pages · bf599747 catalogue (seven
codes, G5, G15) · 1af221be + 4226829b CLI `streams` (`application/stream_table_format.py`, goldens
`tests/fixtures/st/cli/`) · e8c8dcae docs (guide, CLI reference, ADR 0019 Amendment 13 pointer).

**Gates.** G11 (transports: conformance 5 clients incl. not_ready/no-bundle/unknown job; `test_st_operation.py`
not_found member, unsupported, internal_error, unknown job on python/cli/http/mcp) PASS. G12: served MCP
`eaff4585…` → `6705fb05…`, `without_st` = D_4 exactly; R4-G3 new row = `projection` def (`951b77ea…`), none
moved; `API_EXIT_CODES` unchanged; schemas vs the merge tree: registry +1 and the new file. G13: F0 PASS after
WO-3 and at the end; no diff under verify/thermo/models/run/orchestrator/compiled.py vs 22f64c65. G5 against
the real catalogue PASS; G15 PASS (`absent` → MSG audit). A48 PASS. G8 still `xfail(strict)` (E1).
**Known red, not ST's to fix:** `test_every_description_is_reviewed_by_both_lanes` (3 open: `explain` human,
`get_stream_table` design-lane + human — reviews are the reviewers' acts).

**Design-lane questions for ST's reviewer pass.** D1-1, D1-3, D1-6/D1-7, E1 (WO-1/2); D3-6 (no-bundle
`not_found` renders "Nothing named …"), D3-7 (c_5's register id, after ADR 0068 acceptance; MSG's R-942/R-943
collide with RP's), D4-1 (`energy form:<model>` vs §6.4's `energy_form:<model>`, G4 jargon lint), D5-2 (assembly
resolves every elision, §6.3 named only `/streams`/`/energy`); the `get_stream_table.md` description review.

**Next: WO-7** — evidence manifest (`evidence/<ST id>/<commit>/manifest.json`, numbers in the WO-1 handoff
section of ST_DECISIONS and above), full gate `scripts/gate.sh`, CI on both architectures, the reviewer pass.
When MSG lands on main: `git merge main` into `wp/ST` (MSG renumbers its register ids; re-check c_5 and the
surface tests).
