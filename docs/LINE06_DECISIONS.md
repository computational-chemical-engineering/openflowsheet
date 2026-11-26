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
