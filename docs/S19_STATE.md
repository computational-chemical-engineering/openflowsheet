# S19 state: repo-wide code-health campaign (includes the D19 interface package)

Rewritten in place; history in `docs/S19_DECISIONS.md` and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s19.jsonl`. Standing rules: `docs/S19_RULES.md`. Procedure: `.claude/skills/s19-refactor/SKILL.md` (gate queue, self-reset).

## Objective

Frank, 2026-11-14: "My purpose now is to refactor the code such that code health becomes excellent and we can safely
move on with the development to the future. This is the goal. Do what it takes." Scope: all of `src/openflowsheet`.
Behaviour stays bitwise identical; outward interfaces may change through ADR 0076 (no shims at the end). S18 waits.

## Position (2026-11-14; updated 2026-11-16)

- `CB` = `d90b498f8759b739361016cca7858f71bc647ccc` (main after the S17 merge): the debt baseline.
- Baseline (trial scan, scope `src/openflowsheet/*`): 282 files, 100136 NLOC, debt 6370.9, health 7.3, brain
  functions 44, file smells 59; 10 import cycles (the largest 17 modules, 51 edges). Digest:
  `docs/briefs/S19-digest.md`; scan JSON `<git-common-dir>/codehealth/runs/repo-wide-scan-d90b498f.json`.
- `MB` (the test-map base, read by `.claude/skills/s19-refactor/gate.sh` from the line below; moves to milestone
  commits, `S19_DECISIONS`):
- `MB` = `c3c5793eb0584a4727cb0ad3988c3a3c62347d0e` (the `wp/S19` tip on 2026-11-16 ~10:15, after the re-pin to cce-code-health 1f7df37; G-MAP 3 map, quiet build, unsure set = the B-6 four only; earlier MB 736f70db, bec6dbe6).
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

## Next actions (2026-11-16, ~21:55; self-reset)

Runner pid 2642417 (cce-code-health ec5aaea installed). Results consumed up to 172; start `$Q wait --since 172` in the
background first. No agent running. Lanes at most 2 agents until Thu 19 Nov 13:00. ALERTs persist (proposal 2 with
Frank). Merge-checks run on a helper branch `wp/S19-<lane>-mc` = lane tip + wp/S19 tip merged in. Detail of every item
in S19_DECISIONS (grep the quoted words).
1. **Rule 4 serial runs (detached; "rule 4 falsifier: base2"):** serial full suites (`-p no:xdist`) at base
   10adfc3d+A (worktree `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/0e0821aa-6e8e-4c6b-9a00-f781aa0ef7c7/scratchpad/base2`)
   and head be115b6a+A (worktree `/tmp/claude-1000/-home-eajfpeters-Code-OpenFlowsheet/165c72bf-833e-48c6-b5e2-b732f68e85df/scratchpad/headser`),
   started 20:15, ~3 h. Logs `baseser.log`, `headser.log` in that 165c72bf scratchpad (end "EXIT n"); read only
   `grep -h "MSG WO\|passed\|^EXIT"`. Equal: W4 run 8 merges (item 3), ADR rule 4 text (serial form) into the
   R-W4-9 batch, and I-10/I-12 can be briefed. Unequal: fresh engineer on the I-4 gap. Then remove both worktrees.
2. **G6 run 6:** R-W3-G6-6 merge after fixes; fix 0dd145b0 job 187 (no-gain); helper wp/S19-g6d-mc (worktree
   s19-g6d-mc, 19f2ff53) merge-check job 188. Both PASS: merge wp/S19-g6d into wp/S19 (`git merge -F`), remove
   worktrees s19-g6d, s19-g6d-mc.
3. **W4 run 8 merge** waits for item 1 (R-W4-8 fix 1). Helper wp/S19-w4r8-mc (worktree s19-w4r8-mc) = 486b6dbb +
   c7d21f2e; then merge wp/S19 into it, merge-check, merge.
4. **W4 runs 9+10 (lane wp/S19-w4, tip 2b40c2f2, rebuilt after job 185 FAIL, "fix185"):** jobs 194 I-5b (rerun of
   185), 195 I-9, 196 I-14. All PASS: one review R-W4-9 over runs 9+10 (write the brief: I-5b 50779e18, I-9
   1f5c2c6b, flag 651cc8d0, tests 1e0eb6ce/634c1195/a953ca84/dbb304a3/45e742b7, layer configs a609de45/2b40c2f2, I-14
   8292d7e2; I-14 by a `reviewer` on `model: fable` (initialization order); engineer choices in "W4 run 10 reported").
   Then W4 run 11: I-11, I-13 (brief = S19-W4-10.md minus I-14; importers of transactions listed there). I-10 and
   I-12a-d wait for item 1.
5. **G5 run 9 (wp/S19-g5g, base 135c78f8, tip bfe9e545; "G5 run 9 reported"):** jobs 189, 190, 192, 193. All PASS:
   review R-W3-G5-9 (write the brief from S19-R-W3-G5-8.md; rule on step 4's bare-tuple pair), fixes, helper
   merge-check, merge. Next G5 run 10: certificate.py `_issue` (11.8, 15 parameters; grouping as R-W3-G5-4),
   `verify_revision` (8.3), column.py `_end_check` (4.0).
6. Open for Frank (not blocking): R-1042 option C; STOP 1 alternative; tool items; verify twins addendum;
   selection-widening; proposal 2 for the ALERTs. Design lane: NaN derivative-witness pass (R-W3-G5-8); rule 4
   deterministic form (after item 1). Docs-pass leftovers in S19_DECISIONS (77ae7025 message says cognitive 16 -> 11,
   scan 12; i4 plan reason "two" -> three; ruff tier `{files:*.py,*.pyi}` switch).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-MAP 3 | the map at the wp/S19 tip when the queue drains (2026-11-16) | as G-MAP, built without `--deselect`; no unsure test in a file that costs more than about 60 s (else re-run the build) | MISS on the unsure-file criterion, map accepted (c3c5793e): 20483 tests, 3473 s quiet, 25.7 MB; 4 failed = the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), deterministic since S16, so a re-run cannot cure them; test_m04_wo9_synthetic_loop.py ~77 s (profile under load) > 60 s, x02_wo4 unmeasured. s09 and both t07 budget tests passed (out of the unsure set). |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest identical; full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
