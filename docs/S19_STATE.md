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

## Next actions (2026-11-20 ~19:30 CET)

**Position:** main = d29f1a50 (F3 merged). wp/S19 = this commit. MB 756e1c12. Runner PID 1341562 (queue empty, results
538). cce-code-health 34a30bf. Agents running: none. Background waits at reset: X07a CI 44773324184 at 94b38dae
(`gh run watch`; older watches on 44764813337 and 44770741082 are superseded heads: ignore their notices). On each gate
result: gate_report, log. Re-arm `$Q wait --since <COUNT from $Q status>`.

0. **F3 merged into main** (card ofs-f3-merge-main A, executed 2026-11-20 17:00Z): main d29f1a50 (merge of wp/F3
   6cf2a1de, CI 44758521457 green on both check legs), F0 PASS 9/9 on main, pushed. wp/S19 does not contain it yet:
   item 3c applies when wp/S19 next takes main.
1. **W5 batch P: chain done, next WO-P6 = the close (orchestrator's own work, ruling section 9 row WO-P6).** B_P
   2eae72a8; gate file `<git-common-dir>/codehealth/briefs/S19-W5-batchP.json` sha 91d97ce0; batch brief
   `S19-W5-batchP.md` (read its "Close K" section and all three amendments: the K fixture list is there). Lane
   `wp/S19-w5p` (worktree s19-w5p) at da75a268, every step gated PASS and reviewed `merge`: WO-P1 pr_c1, WO-P2 iapws95,
   WO-P3 wilson_ig (R-W5-P1..P3), WO-P4 B7 a5b8fb11 (job 557, R-W5-P4), WO-P5 coolprop_heos f875f4d4, da75a268 (jobs
   558, 559; R-W5-P5; health 6.4 -> 9.0). Close procedure (precedent: batch L close, `grep -n -A22 "batch L close
   (orchestrator)" docs/S19_DECISIONS.md`; criteria ruling R5 :318 and W5-K1..K7 :431-470):
   (a) gate file: all five admitted files were edited (check `git diff 2eae72a8..da75a268 -- src/`), so no drop
   expected. (b) K commit on the lane: R5 re-record (`corpus_identity.py --record`, m6-requests.json must come out
   byte-identical; `registry_builtin.py --write`), the L fixtures: `test_t07_w5c_signatures.py` EXPECTED by its
   regenerator, TH-C1.json by substitution, `WILSON_V1_SHA256` in test_s11_wilson_v2.py by substitution (F-3, comment
   amends S11 A75), `MOVED` pr_c1.py in test_l01_records.py + the L01 ruling in decision-register.md (F-4, form of
   R-983/R-1061), the M9 35 -> 42 constants (test_f0_corpus_identity.py :57 and :433; test_f1_legacy_builtins.py :411
   and the :16 docstring; test_s19_w5_gate.py :354). Ruff before `close`; `git diff --name-only K^..K` against the
   close paths plus fixtures before `close`. (c) `w5_gate.py close --k K --queue-dir <queue> --fixture ...` (K1, K5
   inside), K2 judge, K3 (F0 PASS 9/9 with M9 42, registry --check, mcp_digest), K7 i19_scan. (d) K4: helper branch =
   K + wp/S19 tip, plain merge-check job (full suite). (e) K6: fresh reviewer over B_P..K (brief pattern
   `S19-R-W5-L-close.md`). (f) release note (separate docs commit): the providers whose model_version moved, plus
   coolprop-heos-v1 (FR-1). (g) on K4 PASS and K6 merge: merge the lane into wp/S19, log, remove worktree s19-w5p.
   FR-1: close before the 0.5.0 RC cut. Docs pass before any S07 manifest re-take:
   `scripts/s07_evidence_manifest.py:86,91-94,838-840` (R8.5, R-W5-P4).
2. Three non-W5 `retarget` rows in i19_scan (column_acceptance.saturation_pairs, region_attempts.solve_ptc,
   region_problem.check_opening): open build-lane item for a later lane.
3. **X07a (0.5):** reviewed (`docs/X07a-review.md` d13f5a3f + "## WO9 review" 1fc9f606); erratum R-10 2f067059; WO8
   (db051d9c), WO9 (335c09bf, R-1 to R-6), WO10 (94b38dae, W-1 to W-3) pushed. Merge preconditions (review :131-144):
   CI 44773324184 all four legs green (Windows 0 failed) + identity + codehealth; then move the manifest to that head
   `tested` naming rows L1 to L12, Q-4, Q-10, Q-11 (after merge); then a merge card via hub (DECISION-REQUEST, card
   wording memory). Windows red: read the leg (`gh api .../jobs/<id>/logs` to a scratch file, grep FAILED), fresh WO.
   X01-WO1 part A: manifest `tested`, CI green; next a reviewer pass, then a merge card; open B, C, Q-1..Q-3
   (`docs/X01_DECISIONS.md` on wp/X01); X01 selectability moved to 0.6 (R-1065).
3a. **0.5 scope (Frank, R-1065, ADR 0057 Amendment 1, wp/REL050 84a08a84):** 0.5 is X07a, F1, F3, X01 plugin docs,
   X32, and S19 batch P before the RC cut. Next for the line: `release/lines/0.5.json` design pass on wp/REL050.
   Register numbers: R-1064 (wp/X32), R-1065 (wp/REL050), R-1066 (wp/S19) all append to the register end: trivial
   merge conflicts, keep all.
3b. **X32 (0.5):** wp/X32 7cf27880 pushed, manifest `tested`; next: into the 0.5 merge card. Keep the student's name
   off every record.
3c. After the F3 merge: S19 G-END must absorb F3's `records/` (main's layer config gains it with the merge) and the
   `application/local.py` duplication smell (nloc 411) the ratchet reported.
4. Rule: lanes touching studies/ also need the nlp-marked suite at head, failures a subset of base (g19, g20).
5. Brief rule (I1): `codehealth scan --json PATH` writes TO PATH; use `--repo <wt> --json <scratch>/scan.json`.
   A test retarget is never enqueued alone: retarget, plan, step; gate from the plan commit. A generator step (only a
   generator and its outputs, plus the hash-scope edit it requires) gates as `merge-check --batch` (job 556's miss).
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
