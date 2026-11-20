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
- I-20 merged 2026-11-19 (d7e9b014): the 0.5 blocking set is done on wp/S19.
- G1 (orchestrator/, numerics/): W3 lanes N and O closed 2026-11-19 (272011be); residuals executor.py (PR-1b, 6.1 -> 9.0, gating) and `_solve_region`'s parameter object (W4).
- G-END (below) stays the end criterion for the whole repository.

## Next actions (2026-11-20 ~15:30 CET)

**Position:** main = c4a91a75. wp/S19 = this commit (WO-P0 tool part merged d98b2ca4). MB 756e1c12. Runner PID
1341562, queue idle (COUNT 523). cce-code-health 34a30bf. Agents running: X07a-WO6 engineer (opus-engineer, wp/X07a,
brief `docs/briefs/X07a-WO6.md`). Background shells: CI watches on X07a 44699040945, wp/TOK 44706297998, wp/F3 (head
6c82b535). On each result: gate_report, log. Re-arm the queue wait with `$Q wait --since <COUNT from $Q status>`.

1. **W5 batch P (after FR-1, ADR 0077).** WO-P0 tool part merged (d98b2ca4): `w5_identity.py pin` (W5-S2), `close`
   runs W5-K5 for P, gate tier `w5_pin`, `scripts/w5_hunks.py` (F0 line coverage per hunk). Next, the orchestrator's
   part of WO-P0: B_P = the wp/S19 tip; L_P by ruling 3.1; gate file `<git-common-dir>/codehealth/briefs/S19-W5-batchP.json`
   (`max_tier` 3; `generator` lists the seven `_coolprop_heos_fluids_{a,b1..b6}.py`, else W5-S1 rejects them) and
   batch brief (`S19-W5-batchP.md`: admitted set per ruling 9 WO-P1..P3 and B7; each step records `w5_hunks.py`
   coverage for the reviewer, DECISION 2026-11-20). Then WO-P1 `thermo/pr_c1.py`, WO-P2 iapws95, WO-P3 wilson_ig
   (S11 A75 amended), B7. Reviews: S1 cadence (every 3 steps); identity rulings on `model: fable`. FR-1 conditions:
   the pin, close before the 0.5.0 RC cut, a release note naming the moved providers.
   Lessons (R-W5-L-close): ruff before `w5_gate.py close` (the close record is write-once); `git diff --name-only
   K..tip` inside the close paths plus fixtures; at the S19 -> main merge recheck that R-1061 is unique.
2. Three non-W5 `retarget` rows in i19_scan (column_acceptance.saturation_pairs, region_attempts.solve_ptc,
   region_problem.check_opening): open build-lane item for a later lane.
3. **0.5:** X07a: WO4 delivered (51f7fcae: macOS rows L6-L10, two limits, Q-11; manifest moved to 9773c361; codehealth
   CI fixed; v02a r347 bug fixed). Cards ofs-x07a-adr0007-am3 and ofs-x07a-pywin32-licence VERIFIED (both A). am3 done
   (a60d1b54, R-1062, executed written). pywin32 in X07a-WO5 (R-1063 reserved; stop condition: a pin in
   requirements.lock moves lock_sha256, measured first, else Q-12); licence half done (d7bb75bc); lock half is card ofs-x07a-pywin32-lock (filed, rec A: requirements-windows.lock), act on VERIFIED; the old card is closed. WO5 also does
   the Windows clusters. Then the X07a reviewer round (D-20, D-22/Q-4, Q-10, Q-11), then a merge card via hub.
   X01-WO1 part A delivered, manifest `tested`, CI green; next for X01: a reviewer pass, then a merge card via hub;
   open B, C, Q-1..Q-3 for the design lane (`docs/X01_DECISIONS.md` on wp/X01). X01 selectability blocked on
   F2/F4/F6; ADR 0052 D11 amendment open. F3: ADR 0061 accepted (R-1050); human review recorded (6c82b535); CI 44709885423 green;
   manifest tested (955addd4); merge card ofs-f3-merge-main filed (A verbatim: "merge wp/F3 into main with a merge commit after a fresh CI run on
   wp/F3 merged with the main tip is green on both architectures, run scripts/corpus_identity.py --check (F0) on main
   after the merge, and push main only if F0 passes"); verify with that text, act on VERIFIED.
3a. **0.5 scope (Frank, 2026-11-20, R-1065, ADR 0057 Amendment 1, on wp/REL050 84a08a84, pushed):** 0.5 is X07a,
   F1, F3, X01 plugin docs (+ parts needing no F2/F4/F6), TOK, and S19 batch P before the RC cut; F2, F8, X06 and X01
   selectability lead 0.6. Next for the line: `release/lines/0.5.json` design pass on wp/REL050. R-1064 (wp/TOK) and
   R-1065 (wp/REL050) both append to the register end: a trivial merge conflict, keep both.
3b. **X32 (formerly TOK; 0.5, Frank 2026-11-20):** wp/X32 (worktree tok, from main), e028b835 + ae0dec21 pushed:
   `project grant` prints the token alone on stdout (R-1064, no ADR: T07 §10.3 holds); CI 44706297998 green; manifest
   `evidence/X32/e028b835.../manifest.json` tested. Reviewer pass running. Then into the 0.5 merge card. The user
   report came from a student: keep the name off every record. Remote wp/TOK deleted (renamed to wp/X32).
4. Rule: lanes touching studies/ also need the nlp-marked suite at head, failures a subset of base (g19, g20).
5. Brief rule (I1): `codehealth scan --json PATH` writes TO PATH; use `--repo <wt> --json <scratch>/scan.json`.
   A test retarget is never enqueued alone: retarget, plan, step; gate from the plan commit (job 516's miss).
**Open for the design lane (one batched round):** (i) W5-S1 text admitting new `.py` modules in an admitted tier 1
directory and added plan files (R-W5-N-close 4c; default: the tool's rule stands); (ii) `revision_binding.MODEL_BUILDERS`:
keep as the W27 binder-protocol attribute, strike from I-19's list, state the protocol in `reading_for`'s docstring
(R-W4-RC-N6; default: kept); (iii) cascade/column 87-line duplication.
**Open design-lane item (R-W5-L2b N1):** syn001 heat_exchanger `_bisect_newton` raises RuntimeError "this is a bug" on a creeping Newton iteration (reachable), where c1 mixer returns a not-converged refusal; behaviour, outside W5.
**Open build-lane items:** test_s01_cascade_wo1.py:262 patches `region.solve_region`, a no-op (retarget to
cascade_solve); `c1_reactor_surrogate_of` (revision_binding.py:708) unguarded by the list_models patch;
`benchmarks/m03/nlp-test.lock` lacks mpmath; test_opt_cost_lca_nlp g19, g20 fail; no CI or gate runs nlp-marked
tests; the f3 worktree's `.venv` lacks pytest-xdist and pytest-timeout; brightway.py 8.8 needs an lca-extra venv.
**Open after S19 (F1):** restore the S11.A73 gamma-phi vs PR comparison (`forms._FORMS`). For Frank (not blocking):
P1 the seven new public names of I-20; R-1042 option C; STOP 1 alternative; optional forbid rule cli/serving ->
services.
**Notes:** STOP 1 no-gain; ruff before a merge-check; helper merge only if wp/S19 changed only docs since; `enqueue`
needs `--target --recipe --model` (no-gain also `--reason`); repo `.venv`, `PYTHONPATH=<worktree>/src`, no `-n`. Two
lanes can share one merge-check helper. Every W5 enqueue adds `--batch <json>`; a K merge-check runs without it.
`enqueue --rerun-of` takes the RUN-LOG step from the failed result line. codehealth binary:
`<repo>/.venv-codehealth/bin/codehealth`. Background waits: `run_in_background`, never `&`. Worktrees s19-g1o8, s19-g3
kept (branches not ancestors of wp/S19).

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
