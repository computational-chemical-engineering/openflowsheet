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
- `MB` = `756e1c12076d043ddf3a7f06176a2eb3610fec04` (the `wp/S19` tip after the W3/W4 merge into main, 2026-11-18; G-MAP 6 map: 20516 tests, failed = the B-6 four; earlier MB 14c6d414, 1720cc98, c3c5793e, 736f70db, bec6dbe6).
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
- 2026-11-17: I-11 merged (6668be04), G5 run 11 merged (1720cc98), I-13 merged (d63dcd7a), W4 runs 13-16 merged (e61b23f2). I-12d done on the lane, gating (jobs 241-243).

- R-W3-G1N-1 ptc.py item met: health 8.3 after P3 (2026-11-18).
  else a miss and P1 is reverted.

## Order (Frank, 2026-11-15; S19_DECISIONS)

- Blocking for the 0.5 line: W4 (ADR 0076 items), 0 cycles and 0 violations, G5 (verify/, run/), G6 (thermo/, graph/,
  messages/, units/, adapters/, registry/, compile/). When done: Frank starts 0.5 (roadmap ADR 0057: X07a, X01, F3, F2,
  F8, X06).
- In parallel: the scale probe (R-1034).
- Behind development: G3 studies, G4 assessment, G2 models (legacy engine untouched until Frank rules), W5.
- Trailing behind 0.5 (Frank, ofs-s19-w4-docs-scope A, 2026-11-17): pre-S19 broken references in living docs.
- G1 (orchestrator/, numerics/) running since 2026-11-18 (hold lifted 2026-11-16); ptc.py item met (8.3 after P3).
- G-END (below) stays the end criterion for the whole repository.

## Next actions (2026-11-19 ~02:05)

**Position:** wp/S19 = 030288b4 + docs (lane N run 4 merged; W5 WO-0 merged b70f8dea; ADR 0077 accepted, R-1059).
Lane N (numerics) done: anderson 13.2 (9.0), newton 28.7, ptc 23.2. MB 756e1c12. Runner PID 2763884 (predates the W5
mode: restart it when idle before the first `--batch` job; `kill $(cat <queue>/runner.pid)`, then `$Q run --detach`).
**Agents running (both opus-engineer):** (a) W5 gate-mode fix round 1 on `wp/S19-w5gm` (brief `S19-W5-WO1gm-fix1.md`;
review R-W5-WO1gm fixes 1-5 + notes; enqueues one A1 re-gate `w5gm-a1c`); (b) G1 lane O run 4 on `wp/S19-g1o4` from
030288b4 (brief `S19-W3-G1O-4.md`: R1 region, S1 region_screen, C2 coupling; jobs `g1o4-*`). Region self-test PASS
(2/3, region.py:663); coupling's 2026-11-15.
**On wake:**
1. Fix round (a) reports: spot-check one fix (fix 1(a) killed-call line), then merge-check `wp/S19-w5gm` (full suite,
   base 94840fb3) -> merge into wp/S19 -> restart the runner -> cut B_N = the tip; write the batch JSON
   (`<git-common-dir>/codehealth/briefs/S19-W5-batchN.json`: base B_N, max_tier 2, admitted = the 17 files of
   `S19-W5-batchN.md`, expected_failures = its 10 L_N ids, standing_failures []), run `w5_identity.py sets --check` at
   B_N (W5-T1), branch `wp/S19-w5n` from B_N.
2. Then WO-1b (sonnet-implementer: S10 A26's oracle -> F0's registered M9 value; one test commit outside the gate;
   reviewer reads it) and WO-N1 (`assessment/cost/contributor.py` 2.8, then `sets.py` 4.7, Refusal retargets in
   cost/{contributor,derived,index,operating}.py; gated `--batch`), WO-N2 (lca), WO-N3 (pr_lib, S1), WO-N4 (registry
   factory switch, `--mode interface --batch`), WO-N5 (close: K, judge, review), merge batch N into wp/S19 (FR-2 B).
3. Lane O run 4 reports: review R-W3-G1O-4 (S1; brief from `S19-R-W3-G1N-4.md`), fixes, merge-check, merge. Then lane
   O run 5 per plan section 6 (R2, S2, E2).
4. Open for the design lane at batch N's close review: W5-S1's text vs fix 2 (a tier 1 split's new module admitted by
   the tool; default: the tool's rule stands).
4. F3 (0.5, `wp/F3`, worktree `f3`): ready except Frank's human review. **Waits for Frank:** card
   ofs-f3-mcp-descriptions-human signed A and VERIFIED, but the REVIEW.json edit recording it was refused by the
   permission system; Frank allows it or edits the five `human` reviews himself; then `executed` on that card, CI
   green, manifest `tested`, merge card via hub. Open for the design lane: `molar_mass_inconsistent` signature clash
   ADR 0061 vs 0062.
5. Rule: lanes touching studies/ also need the nlp-marked suite at head, failures a subset of base (g19, g20).
**Open for Frank (new):** the legacy models/ engine ruling (S19_DECISIONS 2026-11-15 item 5): G2's remainder and
W5 batch L wait for it.
**Open build-lane items:** `benchmarks/m03/nlp-test.lock` lacks mpmath (m03_nlp_check.sh fails collection); test_opt_cost_lca_nlp g19, g20 fail; no CI or gate runs nlp-marked tests (add an nlp gate tier); the f3 worktree's `.venv` lacks pytest-xdist and pytest-timeout (fix round 3 ran the full suite serially, 6747 s).
**Open for Frank (not blocking):** proposal 2 (selection widening; selected gates ~600 s vs 300 s; standing ALERT
selected share ~50%); R-1042 option C; STOP 1 alternative; verify twins addendum; thermo/ below 7.0 only in W5;
optional forbid rule cli/serving -> services; re-pin cce-code-health to 9a4605f (optional).
**Notes:** as before (STOP 1 no-gain; ruff before a merge-check; helper merge only if wp/S19 changed only docs since;
`enqueue` needs `--target --recipe --model`; repo `.venv`, `PYTHONPATH=<worktree>/src`, no `-n`). Two lanes can share
one merge-check helper (done for G5 r12 + G6 r7). Rule-6 precedent: helpers writing `LaunchProgress` (R-W3-G5-12).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-MAP 3 | the map at the wp/S19 tip when the queue drains (2026-11-16) | as G-MAP, built without `--deselect`; no unsure test in a file that costs more than about 60 s (else re-run the build) | MISS on the unsure-file criterion, map accepted (c3c5793e): 20483 tests, 3473 s quiet, 25.7 MB; 4 failed = the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), deterministic since S16, so a re-run cannot cure them; test_m04_wo9_synthetic_loop.py ~77 s (profile under load) > 60 s, x02_wo4 unmeasured. s09 and both t07 budget tests passed (out of the unsure set). |
| G-MAP 4 | the map at 1720cc98 (2026-11-17) | as G-MAP 3 | MISS on the unsure-file criterion as G-MAP 3, map accepted (1720cc98): 20503 tests (20390 passed, 109 skipped, 4 failed = the B-6 set), pytest exit 1, 3988 s quiet, 25.8 MB. The build's fold crashed on one empty coverage file (1 of 646, a killed subprocess); fold fixed to skip only an all-empty file, the finished run refolded (S19_DECISIONS 2026-11-17 03:40) |
| G-MAP 5 | the map at the wp/S19 tip after the I-12d merge (2026-11-17) | as G-MAP 3 (failures a subset of the B-6 set; at least 20503 tests) | MISS on the failure subset and the unsure-file criterion, map accepted (14c6d414): 20503 tests (20389 passed, 109 skipped, 5 failed = the B-6 set + t07_v17_reference f6 at 310.8 s against 300 s under coverage, as in G-MAP 2), pytest exit 1, 3692 s, 25.9 MB. f6 is deselected by every gate, so as an unsure test it selects nothing (test_impact.py:706) |
| W4-DOCS | end of W4 (Frank, Decision Desk ofs-s19-w4-docs-scope, 2026-11-17, A) | `codehealth docs` with the [docs] records list of ADR 0076 rule 5 (card ofs-s19-w4-docs-records, A): 0 broken references introduced by S19 (diff of the tip against CB d90b498f); pre-S19 broken references (232 unique at 91af908f) are a trailing item behind 0.5 || PASS (2026-11-17, after the I-19 merge a758cbbe and 26d343f6): 0 introduced by S19; 232 pre-S19 trailing; 286 broken in living docs (repo config) |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest by E1 to E5 (`docs/briefs/S19-W5-ruling.md` section 7; ADR 0077, card ofs-s19-w5-fr3-gend-clause A, 2026-11-18); full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
