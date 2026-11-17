# S19 state: repo-wide code-health campaign (includes the D19 interface package)

Rewritten in place; history in `docs/S19_DECISIONS.md` and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s19.jsonl`. Standing rules: `docs/S19_RULES.md`. Procedure: `.claude/skills/s19-refactor/SKILL.md` (gate queue, self-reset).

## Objective

Frank, 2026-11-14: "My purpose now is to refactor the code such that code health becomes excellent and we can safely
move on with the development to the future. This is the goal. Do what it takes." Scope: all of `src/openflowsheet`.
Behaviour stays bitwise identical; outward interfaces may change through ADR 0076 (no shims at the end). S18 waits.

## Position (2026-11-14; updated 2026-11-17)

- `CB` = `d90b498f8759b739361016cca7858f71bc647ccc` (main after the S17 merge): the debt baseline.
- Baseline (trial scan, scope `src/openflowsheet/*`): 282 files, 100136 NLOC, debt 6370.9, health 7.3, brain
  functions 44, file smells 59; 10 import cycles (the largest 17 modules, 51 edges). Digest:
  `docs/briefs/S19-digest.md`; scan JSON `<git-common-dir>/codehealth/runs/repo-wide-scan-d90b498f.json`.
- `MB` (the test-map base, read by `.claude/skills/s19-refactor/gate.sh` from the line below; moves to milestone
  commits, `S19_DECISIONS`):
- `MB` = `1720cc987263268a1178bca870ab0497c8303583` (the `wp/S19` tip after G5 run 11, 2026-11-17; G-MAP 4 map, refolded after the fold fix; unsure set = the B-6 four only; earlier MB c3c5793e, 736f70db, bec6dbe6).
- A1 done: design note `docs/briefs/S19-architecture.md` (phases W0 to W4, table 4.1 with the arch numbers per
  step), ADR 0076 proposed. Config committed: scope `src/openflowsheet/*`, `repo-layers`, forbid
  `verifier-not-through-the-solver`; adoption 14 violations, 10 cycles, 79 cycle edges.
- Frozen (F0 M9, 35 modules, debt 565.2): untouched until W5 (S19_DECISIONS, Q1).
- W1 merged (lanes a, b) and W2 merged (lanes c, d, e) on `wp/S19` (2026-11-14): every step gated on the full
  suite; reviews R-W1, R-W2d, R-W2e passed (fixes applied). At fe9d27fd: `codehealth arch --depth 4` 7 violations,
  4 cycles, 14 cycle edges (CB: 14 / 10 / 79); patch_noop 0 of 246.
- `main` = 218e7a73 (2026-11-15): W1+W2 merged (Decision Desk card ofs-s19-w2-merge-main, verified, executed);
  evidence manifest at 17967ccb `tested`, CI 43637097255 green on both legs, F0 PASS on `main`.
- cce-code-health pinned at a0aff44 (interface `literals` detail; huge_file -> large_file is a downgrade).
- ADR 0076 accepted (Frank, Decision Desk, 2026-11-14). Decision register R-1041 (projection Pyomo modules).
- `wp/S19-f` (worktree `s19f`): I-15 accepted (interface mode, review R-I15 fixes applied; arch 6/4/14) and B1
  (region split) accepted as run-log step 62 (re-run of step 54 after the tool fix); docstring follow-up 3fa89e83
  being gated no-gain. Then merge into `wp/S19`.
- W3 running (`wp/S19-g2`, `-g4`, `-g5`, `-g6`; briefs `S19-W3-*.md` in `<git-common-dir>/codehealth/briefs/`):
  G2 run 1 reviewed (R-W3-G2-1, fixes in G2 run 2). Each run: reviewer, then merge into `wp/S19`.
- A11/I-14 ruled (`docs/briefs/S19-A11-ruling.md`): runs in W4 after I-9. B8-executor skipped; B7 in W5.

- Gate tooling (2026-11-16): queue modes interface and merge-check, `--snapshot`/`--head`, step-relative test
  selection (wp/S19-tools2, 37307ab0). G6 runs 2+3 reviewed (merge); W4 run 1: arch 6/4/14 -> 4/4/14.

- G6 run 6 merged into wp/S19 (18f934f6, 2026-11-16 21:42); G6's W3 part done (frozen thermo: W5).
- 2026-11-17: I-11 merged (6668be04), G5 run 11 merged (1720cc98), I-13 merged (d63dcd7a), W4 runs 13-16 merged (e61b23f2). I-12d running.

- Open (R-W3-G1N-1): numerics/ptc.py health 6.8 after P1 (closing method's 9 parameters); P2 to P4 must end >= 7.0,
  else a miss and P1 is reverted.

## Order (Frank, 2026-11-15; S19_DECISIONS)

- Blocking for the 0.5 line: W4 (ADR 0076 items), 0 cycles and 0 violations, G5 (verify/, run/), G6 (thermo/, graph/,
  messages/, units/, adapters/, registry/, compile/). When done: Frank starts 0.5 (roadmap ADR 0057: X07a, X01, F3, F2,
  F8, X06).
- In parallel: the scale probe (R-1034).
- Behind development: G3 studies, G4 assessment, G2 models (legacy engine untouched until Frank rules), W5.
- Held until the scale probe reports: G1 (orchestrator/, numerics/). Open: ptc.py 6.8 (P3, P4).
- G-END (below) stays the end criterion for the whole repository.

## Next actions (2026-11-17 08:25)

**Position:** W4 runs 13-16 (I-10, I-12b, I-12a, I-12c) merged into wp/S19 (e61b23f2; merge-check job 236; all four
serial pairs EQUAL). I-12d running on lane `wp/S19-w4` (worktree s19-w4): run 17 (step 1 ServiceCore +
InspectionService, 394effe6, job 237 PASS), run 18 (brief S19-W4-18.md; R1 ruling E1-E3 in S19_DECISIONS 07:10;
step 2 RevisionService 3b72357b job 238 PASS; steps 3-5 Artifact, Validation, Job in progress).
**On resume:** (a) `$Q wait --since 224` in the background unless a later result is consumed. (b) Serial pair
i12d1-base (17cada5f) / i12d1-head (394effe6), logs `<git-common-dir>/codehealth/runs/serial/i12d1-*.log`, worktrees
`<scratchpad 78ab96ef>/ser-i12d1-*`; serial pairs for each later I-12d step (parent, step) after it, at most two
suites at once while load > 16. (c) When run 18 reports: brief run 19 for what is left of I-12d, else the I-12d
review (reviewer; R1 ruling E1-E3, the forbid-list additions of 64fc4d4c, msg_catalogue `refuse`), then helper
merge-check and merge as for w4r13. (d) Then MB to the wp/S19 tip (map build, queue held), then I-19.
Runner pid 475743 (cce-code-health cf15245; MB = 1720cc98). Lanes at most 2 agents until Thu 19 Nov 13:00.
ALERTs standing (proposal 2 with Frank; selected share fell to 45%).
Merge-checks run on a helper `wp/S19-<lane>-mc` = lane tip + wp/S19 tip merged in; merge the helper (`git merge
--no-ff -F <file>`) only if wp/S19 changed ONLY docs since the helper's wp/S19 merge, else refresh and re-run.
A no-gain step must touch only scan scope (job 233: a docs-site line failed `scope`; docs-site goes in its own
commit outside the gate). `enqueue --rerun-of` takes the RUN-LOG STEP number. Test runs in a worktree with the repo
`.venv`: `PYTHONPATH=<worktree>/src`, no `-n`.
1. **G-MAP 4: done** (accepted as G-MAP 3; fold fix 0d91ac4b; S19_DECISIONS 03:40). After a reset: `$Q wait --since 212`
   in the background if no result past 212 is consumed.
2. **I-13: merged** (d63dcd7a, merge-check job 228; S19_DECISIONS 04:00).
3. **W4 runs 13/14:** I-10 enqueued (job 229; arch 0/0/0). On job 229 PASS and serial counts EQUAL: review per
   cadence (R-W4-13 with run 14's steps, batch the forbid-list question), then merge-check and merge. Then I-12a
   (after the tool fix), I-12d, I-19.
4. **G5:** W3 part done (G5 run 11 merged 1720cc98). Left: verify twins gamma_phi_units 6.4 / pr_c1 6.7 (W4 twin merge;
   addendum for Frank), table.py `revision_checks` (W4 routing), R-W3-G5-7 component-order question (design lane at
   the G5 close), checks.py / split_checks.py / certificate.py 8.7, the S3 ladder twin (checks.py:757-794 vs
   split_checks.py:184-227; rule 15, waits for a behaviour-level change).
5. **G6:** W3 part done; launcher `launch` after W4. Frozen thermo files: W5. **Rule 4:** confirmed (falsifier EQUAL).
6. Open for Frank (not blocking): R-1042 option C; STOP 1 alternative; tool items; verify twins addendum;
   selection-widening; proposal 2 for the ALERTs; thermo/ below 7.0 reachable only in W5 (S19_DECISIONS "G6 run 7 not
   briefed"). Design lane: NaN derivative-witness pass (R-W3-G5-8); I-19 importer scan over every W4-moved name
   (R-W4-9a note 3; add docs/design/T07-jobs-and-bindings.md:775, :3735 `_defect`); R-W3-G5-7 component order. Docs pass: revision_edits.py:8 stale `transactions` re-export claim; S19_DECISIONS "R-W4-11 reported" notes (k06 store block x3,
   test names with "facade" and `_and_the_old_imports_work`, s16_recall.py:70, roadmap :505, ADR 0019 pointer) and the
   earlier leftovers (77ae7025 cognitive, i4 plan reason, ruff tier switch).
- Tip scan 640bbd63: repo debt 4705.9, health 8.11, brain 26 (G5 run 11 local: 4699.7, 8.13).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-MAP 3 | the map at the wp/S19 tip when the queue drains (2026-11-16) | as G-MAP, built without `--deselect`; no unsure test in a file that costs more than about 60 s (else re-run the build) | MISS on the unsure-file criterion, map accepted (c3c5793e): 20483 tests, 3473 s quiet, 25.7 MB; 4 failed = the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), deterministic since S16, so a re-run cannot cure them; test_m04_wo9_synthetic_loop.py ~77 s (profile under load) > 60 s, x02_wo4 unmeasured. s09 and both t07 budget tests passed (out of the unsure set). |
| G-MAP 4 | the map at 1720cc98 (2026-11-17) | as G-MAP 3 | MISS on the unsure-file criterion as G-MAP 3, map accepted (1720cc98): 20503 tests (20390 passed, 109 skipped, 4 failed = the B-6 set), pytest exit 1, 3988 s quiet, 25.8 MB. The build's fold crashed on one empty coverage file (1 of 646, a killed subprocess); fold fixed to skip only an all-empty file, the finished run refolded (S19_DECISIONS 2026-11-17 03:40) |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest identical; full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
