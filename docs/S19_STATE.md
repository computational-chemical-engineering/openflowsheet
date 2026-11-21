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
- `MB` = `c6957580aba76ac81f3ebbf06c7623275604dd4b` (the `wp/S19` tip after W5 batch P, 2026-11-20; G-MAP 7 map: 20672 tests, failed = the B-6 four + f6; earlier MB 756e1c12, 14c6d414, 1720cc98, c3c5793e, 736f70db, bec6dbe6).
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

## Next actions (2026-11-21 ~01:15 CET)

**Position:** main = d29f1a50. wp/S19 = 68abf467 + docs (main/F3 merged in; merge-check job 606, full suite,
queued; on FAIL reset wp/S19 to 4881224c before any lane merges). MB c6957580. Runner PID 3031640 (`$Q status`;
`wait --since 584` running in background). Agents running: X07a-WO14 (opus-engineer, `<briefs>/X07a-WO14.md`, on
wp/X07a), S19 application/ run 1 (opus-engineer, `<briefs>/S19-W3-APP-1.md`, wp/S19-app, worktree s19-app,
labels app1-*). Scan at 68abf467: 353 files, debt 2130.3, health 8.95.

0. **G-END at 80ebd99c** (scan `--repo . --json <scratch>`): 336 files, debt 2119.2 (target <= 1900: -219 left),
   health 8.93 (>= 9.0), brain 0, no file below 7.0 (MET since WO-V; lowest binding.py and syn001/column.py 7.0),
   arch 0/0 at depth 4, patch_noop 0/263. 87 files below 9.0; debt in them: models/syn001 411.3 (24 files, tier 4,
   not edited in S19), application 218.1 (12), orchestrator 195.1 (10), studies/trust_region 130.7 (8), studies/nlp
   113.2 (6), numerics 51.9 (2). Computed 2026-11-21: health 9.0 is reachable without syn001 (non-syn001 alone 9.005;
   non-syn001 files lifted to 9.0 give 9.19; S19_DECISIONS). No scope question.
1. **Next lanes (DECISION for the new context):** (a) application/ (binding.py 7.0 `bind_revision_or_reason` 22.6,
   revision_run 8.1, stream_table_format 7.9 `assemble` 16, coupled_run 8.0, cli 8.7 `build_parser` 13.6; S2:
   revision_run.py, run_session.py); (b) WO-C, the cascade/column_compile duplication interface step
   (`docs/reviews/S19-design-round-2.md` lines 123-162; tier S1; health 8.4 -> 9.4); (c) trust_region residue
   (projection.py 7.4, projection_checks/zero_flows 7.9, holders 8.1) plus R-W3-G3R-1's fix: a rule-16 test pinning
   trf_state's full `reasons` tuple. Two engineer lanes at a time; briefs per `S19-W3-common.md` (templates:
   `<briefs>/S19-W3-G1R-1.md`, `S19-W3-G3R-1.md`).
2. **Two lanes from one tip race on the base worktree** (jobs 562/564, 2026-11-20): enqueue the second lane's chain
   >= 3 min after the first lane's first job STARTs (pattern: e9f8087c scratch `requeue.sh`), until the build-lane
   tooling item (a lock around base-worktree creation in the gate) is done.
3. Rule (2026-11-20): a W5 batch close also runs the nlp-marked suite at K (batch P missed G10; fixed b1d2ae6a).
   Lanes touching studies/ need the nlp-marked suite at head, failures a subset of base (g19, g20 only now).
4. **X07a (0.5):** S16 and S22 fixed by WO12 (4f3a59ea); S08 open: MAX_PATH rejected (WO13), diagnostic line
   `WO13 tree ...` in the a08 assertion. On CI 44826386637's result: Windows leg log to scratch (`gh api
   repos/computational-chemical-engineering/openflowsheet/actions/jobs/<id>/logs`), grep `WO13 tree`; it names an
   ignore source, a non-zero `add -n` or untracked files: a fresh WO14 with the fix. Green on all four legs: manifest
   `tested`, then a merge card via hub. Pushes from agents need `gh auth git-credential` as helper (sandbox).
   X01-WO1 part A: next a reviewer pass, then a merge card. X32: into the 0.5 merge card.
5. **0.5 RC cut open item (not S19):** `benchmarks/m05/records` REAL replay (`m05_wo9_real.py --replay`, RC step
   14) fails since the TRS2 -> TR09 move; a re-take (~35 min, reactor env, clean tree, mapping proof plus host
   column) is a 0.5 work order.
**Open for the design lane:** design round 2 done (`docs/reviews/S19-design-round-2.md`): (i) an amendment line
under W5-S1 in `S19-W5-ruling.md` 6.2 (orchestrator, docs); (ii) ADR 0076 addendum striking MODEL_BUILDERS from
I-19 and the protocol in `benchmarks/m06/w27/snapshot.py:285` `reading_for` docstring (build lane); (iii) WO-C
above; (iv) the S19 -> main manifest names 43dccc21 and b1d2ae6a as post-K generator-only commits.
syn001 heat_exchanger `_bisect_newton` RuntimeError on a creeping Newton (R-W5-L2b N1): behaviour, outside W5.
**Open build-lane items:** test_s01_cascade_wo1.py:262 patches `region.solve_region` (no-op; retarget to
cascade_solve); `c1_reactor_surrogate_of` (revision_binding.py:708) unguarded by the list_models patch;
`benchmarks/m03/nlp-test.lock` lacks mpmath; test_opt_cost_lca_nlp g19, g20 fail; no CI or gate runs nlp-marked
tests; mass.py `_entries` dead ValueError branch (a declared literal drop); basis.py `_check_float_arguments` twin
in `affine` may merge under amended rule 15; three non-W5 retarget rows (column_acceptance.saturation_pairs,
region_attempts.solve_ptc, region_problem.check_opening). **Open after S19 (F1):** restore the S11.A73 gamma-phi
vs PR comparison (`forms._FORMS`). For Frank (not blocking): P1 the seven new public names of I-20; R-1042 option C;
STOP 1 alternative; optional forbid rule cli/serving -> services. When wp/S19 next takes main (F3): absorb F3's
`records/` in the layer config and the `application/local.py` duplication smell (nloc 411).
**Notes:** STOP 1 no-gain; ruff before a merge-check; helper merge only if wp/S19 changed only docs since; `enqueue`
needs `--target --recipe --model` (no-gain also `--reason`); repo `.venv`, `PYTHONPATH=<worktree>/src`, no `-n`;
patch_noop at `.claude/skills/s19-refactor/patch_noop.py`. Two lanes can share one merge-check helper. A test-only
commit is never enqueued. codehealth binary: `<repo>/.venv-codehealth/bin/codehealth`. Background waits:
`run_in_background`, never `&`. Worktrees s19-g1o8, s19-g3 kept (branches not ancestors of wp/S19).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-MAP 3 | the map at the wp/S19 tip when the queue drains (2026-11-16) | as G-MAP, built without `--deselect`; no unsure test in a file that costs more than about 60 s (else re-run the build) | MISS on the unsure-file criterion, map accepted (c3c5793e): 20483 tests, 3473 s quiet, 25.7 MB; 4 failed = the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), deterministic since S16, so a re-run cannot cure them; test_m04_wo9_synthetic_loop.py ~77 s (profile under load) > 60 s, x02_wo4 unmeasured. s09 and both t07 budget tests passed (out of the unsure set). |
| G-MAP 4 | the map at 1720cc98 (2026-11-17) | as G-MAP 3 | MISS on the unsure-file criterion as G-MAP 3, map accepted (1720cc98): 20503 tests (20390 passed, 109 skipped, 4 failed = the B-6 set), pytest exit 1, 3988 s quiet, 25.8 MB. The build's fold crashed on one empty coverage file (1 of 646, a killed subprocess); fold fixed to skip only an all-empty file, the finished run refolded (S19_DECISIONS 2026-11-17 03:40) |
| G-MAP 5 | the map at the wp/S19 tip after the I-12d merge (2026-11-17) | as G-MAP 3 (failures a subset of the B-6 set; at least 20503 tests) | MISS on the failure subset and the unsure-file criterion, map accepted (14c6d414): 20503 tests (20389 passed, 109 skipped, 5 failed = the B-6 set + t07_v17_reference f6 at 310.8 s against 300 s under coverage, as in G-MAP 2), pytest exit 1, 3692 s, 25.9 MB. f6 is deselected by every gate, so as an unsure test it selects nothing (test_impact.py:706) |
| G-MAP 7 | the map at c6957580 after W5 batch P (2026-11-20) | as G-MAP 5 (exit 0 or 1; at least 20516 tests; failures a subset of the B-6 four + f6; no unsure test in a file over ~60 s) | PASS with the standing note (c6957580): 20672 tests (20558 passed, 109 skipped, 5 failed = the B-6 four + f6), pytest exit 1, 4611 s under two engineers' local tests, 26.6 MB; the unsure set is those five, test_m04_wo9 (~77 s) the standing exception since G-MAP 3; f6 is deselected by every gate |
| W4-DOCS | end of W4 (Frank, Decision Desk ofs-s19-w4-docs-scope, 2026-11-17, A) | `codehealth docs` with the [docs] records list of ADR 0076 rule 5 (card ofs-s19-w4-docs-records, A): 0 broken references introduced by S19 (diff of the tip against CB d90b498f); pre-S19 broken references (232 unique at 91af908f) are a trailing item behind 0.5 || PASS (2026-11-17, after the I-19 merge a758cbbe and 26d343f6): 0 introduced by S19; 232 pre-S19 trailing; 286 broken in living docs (repo config) |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest by E1 to E5 (`docs/briefs/S19-W5-ruling.md` section 7; ADR 0077, card ofs-s19-w5-fr3-gend-clause A, 2026-11-18); full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
