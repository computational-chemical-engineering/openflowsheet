# S19 state: repo-wide code-health campaign (includes the D19 interface package)

Rewritten in place; history in `docs/S19_DECISIONS.md` and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s19.jsonl`. Standing rules: `docs/S19_RULES.md`. Procedure: `.claude/skills/s19-refactor/SKILL.md` (gate queue, self-reset).

## Objective

Frank, 2026-11-14: "My purpose now is to refactor the code such that code health becomes excellent and we can safely
move on with the development to the future. This is the goal. Do what it takes." Scope: all of `src/openflowsheet`.
Behaviour stays bitwise identical; outward interfaces may change through ADR 0076 (no shims at the end). S18 waits.

## Position (2026-11-14)

- `CB` = `d90b498f8759b739361016cca7858f71bc647ccc` (main after the S17 merge): the debt baseline.
- Baseline (trial scan, scope `src/openflowsheet/*`): 282 files, 100136 NLOC, debt 6370.9, health 7.3, brain
  functions 44, file smells 59; 10 import cycles (the largest 17 modules, 51 edges). Digest:
  `docs/briefs/S19-digest.md`; scan JSON `<git-common-dir>/codehealth/runs/repo-wide-scan-d90b498f.json`.
- `MB` (the test-map base, read by `.claude/skills/s19-refactor/gate.sh` from the line below; moves to milestone
  commits, `S19_DECISIONS`):
- `MB` = `736f70dbf9b88dad9f79b8a8dcd26a44f885520a` (the `wp/S19` tip on 2026-11-15 evening; map built with TMPDIR outside the repo, G-MAP PASS with named failures; earlier MB bec6dbe6).
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

## Next actions (2026-11-16, ~10:15)

**Map window open: gate runner STOPPED** (killed after job 112; pending jobs persist; restart with `$Q run --detach`).
G-MAP 3 build running at c3c5793e (`.venv-testmap/bin/python scripts/test_impact.py build --base c3c5793e... --workers 8`,
PYTEST_ADDOPTS=--timeout=900, TMPDIR ~/.cache/openflowsheet/tmp-map; log in this session's scratchpad
`mapbuild-<sha>.log`; map in `~/.cache/openflowsheet/testmap/<sha>/`). If this session died: `pgrep -af "[t]est_impact.py build"`;
if none and no `meta.json`, re-run it. On completion: judge G-MAP 3 (failures a subset of the known set; no unsure test in a
file over ~60 s), move MB to c3c5793e..., restart the runner, tell session OpenFlowsheet-check the machine is free.
cce-code-health re-pinned to 1f7df37 (c3c5793e; imports out of clone detection). `gate_report.py` at every chain-result
wake (skill loop step 3). Results consumed up to 103; next `$Q wait --since 103`. No agent running. Lanes at most 2 until
Thu 19 Nov 13:00. Tool notes: a re-gate whose base moved cannot use `--rerun-of` (log by hand, steps 168, 179); the
literal check excludes docstrings; the runner SKIPs any job whose lane contains a failed step, at run time.
1. **G5 run 5**: merged into wp/S19 (bbcaad2d; jobs 103, 104 PASS).
2. **G5 run 7**: merged into wp/S19 (2644ea96; jobs 109, 110 PASS).
3. **G5 run 6b** (wp/S19-g5d at 3cdb0d50, steps 188, 190, 192, 193 PASS): R-W3-G5-6 merge after fixes; item 2 tests
   pass (44); item 1 settled as a playbook rule-6 exception (0123368c; both fix forms on wip/S19-g5d-revfix). After the
   runner restarts: merge the wp/S19 tip into the lane (fresh helper branch; delete wp/S19-g5d-mc and its worktree
   s19-g5d-mc first), enqueue `--snapshot --mode merge-check --label g5r6b-mc2 --base <wp/S19 tip>`, PASS -> merge.
4. **W4** (wp/S19-w4): step 197 (job 86) failed only on the import-duplication tool defect, fixed in 1f7df37. After
   the restart: re-gate it unchanged (`$Q enqueue --snapshot --head 0dc0558e2e --base ee5eb4d80b --worktree s19-w4
   --mode no-gain --rerun-of 86`, other args from `queue/done/w4r5b-w4r4-batchD-src.json`), then re-enqueue 87, 89,
   93, 98, 99 (args in their done JSONs). When all PASS: the layer-config commit (config.toml application-layers line
   162 `application.policies` stale; repo-layers adoption comment lines 173-176, 178, 179, 181 stale, 177 (A11) and
   180 (A14) live, count "(12)" at 172), then R-W4-1 (brief `S19-R-W4-1.md`, extend to the lane tip: runs 2-6,
   rulings STOP 1/2/3, test_x04 a7, MODEL_ID ruling, run 4's outside-gate module-attribute retargets), merge-check,
   merge. Tell session code_health when W4 is merged (its v0.2.0 tag waits). Worktrees s19-w4-rg54, -rg54b removable.
5. G5 then has left: checks.py `derivative_witness` 16.2, compare.py (health 7.4), split_checks 21.0, table
   `revision_checks` (W4 routing); pr_c1 6.7 / gamma_phi_units 6.4 twins wait for the W4 verify parameter object.
   Type-only `LiftedSplit` imports via orchestrator.region remain in checks.py:58 and gamma_phi_units.py:80 (W4 I-2
   may cover them; check at the W4 merge). Design-lane question for the G5 close: split_checks.py component order
   (:218 vs :259, `_phase_enthalpy` :538/:576), S19_DECISIONS R-W3-G5-7.
6. Then W4 items I-4, I-9, I-14 (A11 ruling), I-10, I-11, I-13, I-12a-d, I-19; cycles and violations to 0.
   `wp/S19-g3` and `wp/SP` wait.
7. Open for Frank (not blocking): confirm R-1042 / option (C) for the T06 self-hash at W4 close; STOP 1 alternative
   (tool change); a cce-code-health fix for empty `{files}` (needs a push) and for `log --rerun-of` with a moved
   base; the verify twins ADR 0076 addendum. Docs-pass leftovers as before plus region.py:71, models.lifted
   docstring, run 4's evidence-manifest scripts (k04, t04, t05, t05b, s02, s10c), scripts/corpus_identity.py import
   lines, docs/interfaces-frozen.md:90, verify/column.py:103 report string and test_s08_item6.py:90.

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-MAP 3 | the map at the wp/S19 tip when the queue drains (2026-11-16) | as G-MAP, built without `--deselect`; no unsure test in a file that costs more than about 60 s (else re-run the build) | |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest identical; full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
