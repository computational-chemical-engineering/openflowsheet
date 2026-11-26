# LINE06 decisions log (append-only; grep it, never read it whole)

Each entry: date, what, the evidence or numbers, and for a choice `DECISION: <question> -> <choice>. Alternative: <x>.
Reversible by: <how>.` Package build decisions go in the package's own file (`docs/F2_DECISIONS.md`,
`docs/F8_DECISIONS.md`, `docs/X06_DECISIONS.md`).

## 2026-11-26, planning (orchestrator, OpenFlowsheet-TR09)

- The user asked how big 0.6 is. Answer given: about 80 work orders, 6 to 9 weeks, 25 to 45M tokens (extrapolated from
  F1 7 WOs in 14 h and F3 6 WOs in 2.5 days); the cut 0.6 = F2 + F8 + X06 offered. The user: "Clean up before you
  start. Remove worktrees that are not more needed anymore and stale background tasks. Then let's go for 0.6 = F2 + F8
  + X06. Update plans for this, create release/lines/0.6.json, prepare the campaign. Post decisions you need on the
  Decision Desk."
- Cleanup: 20 secondary worktrees removed (12 under `.claude/worktrees/`, the codehealth base `799f81c9`, 7 detached
  scratchpad checkouts), each clean (`git status --porcelain` empty) and its HEAD in `main` or on a kept branch
  (wp/REL050 6 commits, wp/S19 4, wp/S19-g1o8 3, wp/S19-g3 1, wp/SP 4 ahead of main; branches kept). No process had its
  cwd in one except the S19 gate queue. Stopped: shells bl74emye7, b38vr9tj3, b5mg2pgtc, b2l7k77a7 (S19 waits, 5 days
  old) and the gate-queue runner PID 4039086 (queue idle since job 702, 2026-11-21; runner.log "RUNNER stop").
- Merged into main (docs only, no conflict by `git merge-tree`): wp/REL050 (754cd194: REL050_DECISIONS, REL050_STATE)
  and wp/S19 (e85424c1: S19 close note, log, state, rules).
- DECISION: campaign name -> LINE06. Alternative: V06 or L06 (both already used as labels in the repo). Reversible by:
  renaming the files.
- DECISION: F8's 0.6 share -> WO1 to WO3 and WO5. Reason: ADR 0067's table, WO4 after F4-WO4, WO6 after F6-WO4, WO7 in
  TX. Alternative: F8 whole (needs F4 and F6). Reversible by: an R-1070 amendment.
- DECISION: X06's ADR number -> 0078 (next free after 0077). Reversible by: renumbering before it is written.
- DECISION: the packages that leave 0.6 -> a heading "After 0.6" with their numbers unchanged until card
  `ofs-line06-rest`. Alternative: apply default A (renumber 0.7 to 0.9) now. Reversible by: one roadmap edit.
- Line file: `release/lines/0.6.json` generated from 0.5's; `changed` = 9 fields; `load_line` + `line_problems`: no
  problems; `line_release('0.6', covers)` = 0.6.0. Tests: test_rel_release_gate, test_rel_evidence_manifest,
  test_rel050_ledger, test_rel051_ledger, test_v02_main_version, test_readme_current 135 passed; test_m07a_rc_records,
  test_m07a_v0_2_gate, test_msg_docs, test_rel_standing_acceptances, test_m03_schemas 271 passed.
- F0 on main d00f659a (after the two log merges and the planning commit): PASS, M1 50/50, M2 61/61, M3 61/61, M4
  61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42 (`~/.cache/line06/f0-main.log`).
- hub filed the three cards (ofs-line06-rest, ofs-line06-adr-clause, ofs-line06-x06-scope), open; hub agrees with A
  on each. A correction sent first: x06-scope B no longer claims a work-order count (X06 has no ADR).
- P1 (F2 premise check) PASS: every existing file and symbol ADR 0062's work orders name resolves on main after S19
  and F3: `schemas/units.json`, `thermo/__init__.py` (`Phase` :58, `StreamState` :105, `PropertyRequest` :133),
  `thermo/cache.py`, `registry/builtin/`, `scripts/registry_builtin.py`, `run/solution_state.py`, `run/identity.py`
  (`r0_projection` :65), `application/revisions.py` (`content_hash` :51), `models/revision_flowsheet.py`
  (`ComponentBasis` :104), `docs/interfaces-frozen.md`, `records/model.py:30` and `records/validate.py:135` (the `kg`
  gate). New modules (`material/`, `revision_v2/`, `tests/f2/`) do not exist yet, as expected. Open for WO6's brief:
  "dispatch in the application layer" names no file; locate it then (recon).
- Worktree `.claude/worktrees/f2`, branch wp/F2 at d00f659a. Brief `docs/briefs/LINE06-F2-WO1.md`.
- 2026-11-26: the user: "go". opus-engineer launched on F2-WO1 (background, worktree f2).
- 2026-11-26 ~20:50Z: hub's doorbell; the three cards fetched (decisions/<id>, keys) and verified with
  `decision_desk_verify.py` against the exact action texts sent: ofs-line06-rest VERIFIED A (signed 20:39:40Z),
  ofs-line06-adr-clause VERIFIED A (20:39:05Z), ofs-line06-x06-scope VERIFIED A (20:39:22Z), key 032ee0a5ae620a90.
  Applied: roadmap.md (0.7 multiphase core, 0.8 dynamics with ADR 0066, 0.9 toolkit, 0.10 batch; 0.7 acceptance ADR
  0063-0065; freeze point end of 0.7; "Swap 0.8 and 0.9"), ADR 0057 D6 note and Amendment 3 "Settled", R-1070
  "Settled", ADR 0062/0067 line notes "0.7". `executed` written on the three cards (versions 3, 3, 4).
- D1 brief `docs/briefs/LINE06-X06-architect.md`; worktree `.claude/worktrees/x06`, branch wp/X06 at aa5822ac;
  `architect` launched (background). Facts given: R-110, C1/C6/C7, the note's "resume of long jobs through F7" (F7 now
  0.8, so resume is the expected deferral argument), F0 counts, no record or identity change.
- D1 judged PASS (2026-11-26): `architect` committed ADR 0078 Proposed alone on wp/X06 (`dcbab9b7`, 436 lines),
  worktree clean; 244,895 tokens, 88 tool uses, 18 min. All five parts designed; resume deferral to F7 D14 (0.8)
  argued (D3); 5 WOs (4 Opus, 1 Sonnet), 24 exits. Spot-checks: `refs` table exists (`application/store.py:90`);
  `mcp==1.30.0` in requirements.lock:21. Open: Q1-Q6 (user), Q4 fact (MCP clients), Q7-Q9 facts measured by WOs.
  Applied: R-1071 (Proposed), roadmap X06 row. Held until Q1 is answered: R-110 status line, roadmap resume move,
  target-architecture X06 row.
- X06-WO1 brief `docs/briefs/LINE06-X06-WO1.md`; opus-engineer launched (background, worktree x06). Cards requested: ofs-x06-accept-adr0078 (A: accept with Q1-Q3, Q5, Q6 defaults), ofs-x06-mcp-clients (A: static bearer, OAuth later).
