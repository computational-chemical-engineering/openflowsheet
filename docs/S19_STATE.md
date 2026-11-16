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

## Next actions (2026-11-16, at the self-reset, ~03:00)

Gate queue: runner pid in `<git-common-dir>/codehealth/queue/runner.pid` (tools2 code, 37307ab0). Consumed up to
result 20; next: `$Q wait --since 20`. Queued: 21-31 (W4 lane, re-made after gate 152; 31 = I-5 interface step,
no-gain per the STOP 1 ruling), 32-35 (G5 run 4, `g5r4-1..4`). No agent running.
1. **W4** (`wp/S19-w4`, tip 38f55cff; history rebuilt, old tip tag `s19-w4-pre-fix`). Done and queued: I-5 (A12),
   I-3 (A13), I-6, I-1; src/test retargets of I-2 and I-7. When job 21 (w4r1b-i5-move) PASSES, launch W4 run 3
   (`opus-engineer`, brief `S19-W4-3.md`: I-2 and I-7 interface steps under the STOP 1/STOP 2 rulings, then I-8). A
   FAIL or SKIPPED in 21-31: read the failed tier, fix like gate 152 (S19_DECISIONS) or brief a fresh engineer.
   After all W4 jobs of runs 1-2 PASS: orchestrator layer-config commit on the lane (application-layers loses
   `application.policies` (config.toml:159); adoption lines `run.bundle -> application.policies` and
   `assessment.spec -> application.types` go; stale comment `numerics -> orchestrator.trace` at :173), then
   reviewer R-W4-1 (brief `S19-R-W4-1.md`; extend its range to the lane tip and add run 2's commits and the two
   rulings STOP 1/STOP 2 and the test_x04 a7 ruling to it), merge-check, merge into wp/S19.
2. **G5 run 4** (`wp/S19-g5b` from ebcf513a; checks.py 6.1 -> 7.1, certificate.py 6.4 unchanged). When 32-35 PASS:
   reviewer R-W3-G5-4 (brief written), fixes, merge-check, merge. Next G5 run: certificate.py `verify_revision`,
   `_revision_values`, `_guard`; `_issue`'s 18 parameters wait for the reviewer's answer (parameter object or the
   deferred W4 verify parameter object).
3. Open for Frank (not blocking work): STOP 1 alternative (tool change: `X as X` counts as API in any module, re-pin)
   and the STOP 2 R-016 test change (authorised by the orchestrator under ADR 0076 I-2; reviewer reads it). The
   verify twins merge (gamma_phi_units.py, pr_c1.py public names) needs an ADR 0076 addendum (design lane batch).
   thermo/ providers below 7.0 are W5 only: the blocking set's G6 closes in W5.
4. Docs-pass leftovers: studies/nlp/request.py:109,132; run/bundle.py:214; benchmarks/registry.yaml:1738,1748,1756;
   render.py:67 and operations.py:138 (`units.X`); test docstrings test_x04_stream_table.py:8, test_x04_messages.py:6,
   test_t07_interrupt.py:3; scripts/t08_numerical_policy.py:9,223.
5. Then W4 run 4 (I-4, I-9, I-14 after I-9 with the A11 ruling, I-10, I-11, I-13, I-12a-d, I-19), G5's remaining
   files, cycles and violations to 0. `wp/S19-g3` (unreviewed, trails) and `wp/SP` wait. Lanes at most 2 until Thu
   19 Nov 13:00. Every lane merge needs a merge-check PASS; lanes branch from the wp/S19 tip.

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | PASS (bec6dbe6): 20362 tests, 3708 s, 25.4 MB; 4 failed, all of S16's B-6 set (test_m04_wo9 a25, a29; test_x02_wo4 g4e x2); f6 passed |
| G-MAP 2 | the map at 736f70db (2026-11-15) | as G-MAP | PASS: 20461 tests, 12810 s (under load), 25.6 MB; 7 failed: the B-6 set (m04_wo9 a25, a29; x02_wo4 g4e x2), two wall-time budget tests under load (t07_v17_reference f6, t07_conformance budget_of_the_scenario_runs), s09 a20[s03_reference.py] (its hung subprocess killed, S19_DECISIONS) |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest identical; full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
