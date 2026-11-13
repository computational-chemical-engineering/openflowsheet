# S17 state: code-health campaign 1 on `src/openflowsheet/application/`

Rewritten in place; history is in `docs/S17_DECISIONS.md` (decisions) and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s17.jsonl` (one line per attempt). Procedure:
`.claude/skills/s17-refactor/SKILL.md`. Standing rules: `docs/S17_RULES.md`.

## Objective

Lower code-health debt in `application/` without any change in behaviour (bitwise), proven per step by
`codehealth gate`. Frank, 2026-11-12: "When I come back I hope to see a very much more healthy code."

## Position (2026-11-13)

- Branch `wp/S17`, worktree `.claude/worktrees/s17`. Config at D11, playbook stub and D12 at `CB`.
- S16 merged into `main` (fc552176, pushed); `main` merged into `wp/S17` (e215e0ed); `CB` = 1fd6826b.
- Map at `CB` built: `~/.cache/openflowsheet/testmap/1fd6826b2f433c73c4c41ef6ccad1dcb903985c8/`. G-MAP and G-SELF
  pass. Work orders 1 to 6 done (revision_run.py 136.0 -> 55.1, binding.py 134.2 -> 43.6, coupled_run.py
  83.8 -> 21.0, revision_binding.py 85.4 -> 11.5, jobs/model.py 54.2 -> 1.0, transactions.py 47.0 -> 11.0,
  jobs/executor.py 37.0 -> 12.0, jobs/runner.py 29.7 -> 8.5); reviews 1 to 7, 0 open rejects; review notes fixed
  through 18562395 (run-log step 62). Scan at 18562395: debt 411.4, health 8.01, brain functions 0
  (`runs/s17-scan-18562395.json`). `[architecture]` ratchet in the config (D20). Next: work order 7 (validation.py),
  brief `<git-common-dir>/codehealth/briefs/S17-WO7.md`.

## Next actions

1. (done) `CB`, map, G-MAP, G-SELF, baseline. Work orders 1 to 6, reviews 1 to 7, D13 to D20.
2. Work orders 7 and 8 (D17), one engineer at a time; review every 5 accepted steps; briefs in
   `<git-common-dir>/codehealth/briefs/S17-WO<n>.md`. Gates use the map at `MB` (D16).
3. Restructure phase (D18): `[architecture]` ratchet in the config; `architect` drafts split plans from `codehealth
   coupling` / `arch`; `reviewer` checks each; orchestrator commits accepted plans; restructure work orders.
4. Campaign end: copy run log, reviews and briefs into the tree; final scan, G-END; manifest; CI both legs; merge into
   `main`; F0; push; report to Frank (splits for his review).

## Campaign base

- `CB` = `1fd6826b2f433c73c4c41ef6ccad1dcb903985c8`
- `CB` is the debt baseline (G-END).
- `MB` = `3fa719737549094622ce3b124b2f8341c555f335`: the map base, passed as `--ref-base` to every gate run since D16 (`~/.cache/openflowsheet/testmap/<MB>/`).

## Gates (criteria fixed 2026-11-13, before any run)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | map at `CB` | build exit 0 or 1; at least 20284 tests in the map; failing tests a subset of the 5 B-6 failures of S16 (`docs/S16_DECISIONS.md` B-6) plus at most 2 others, each named | PASS: 20356 tests, 3125 s, 25.1 MB; 6 failed: the 5 B-6 failures (test_m04_wo9 a25, a29; test_t07_v17_reference f6; test_x02_wo4 g4e x2) and `test_evidence_manifests` on the S16 manifest's `<scratch>` placeholders, a real defect, fixed on `main` (88da7f68) and merged (0ef4d4ca) |
| G-SELF | before step 1 | `codehealth gate --self-test --mutate <path:line>` on a literal that `select --lines` maps to at least one test: SELF-TEST PASS with the `tests` tier failing with exit 1 (a test failure, not exit 2 or 124); unmutated, the `tests` tier passes | PASS: `revision_run.py:614` 0 -> 1 (`solve_route`); unmutated 12 files, 1154 passed, 152 s; mutated exit 1, 110 files, 92 failed, 190 errors, 345 s; f0 detected, mcp_digest missed. Re-run on pin 5646ad1a (D13), `revision_run.py:661:1` (moved): tests exit 1 against baseline 0 (full-suite fallback: the self-test ignores `--ref-base`, 850 s), f0 detected, mcp_digest missed: PASS |
| G-STEP | every step | gate exit 0 and `codehealth diff --base <last accepted>` shows the touched files' debt strictly lower | per step in the run log |
| G-REVIEW | every 5 accepted steps | fresh `reviewer` on the diffs; rejected steps reverted and logged `review-reject` | |
| G-END-DEBT | campaign end | `application/` debt at least 30 % below its value at `CB`; `revision_run.py` and `binding.py` each at least 45 % lower; no new brain function | |
| G-END-CI | before merge | CI green on ubuntu-latest and ubuntu-24.04-arm at the final commit; F0 on `main` after the merge | |

The G-END numbers are a target, not a pass/fail for the steps: a campaign that stops early (three consecutive targets
without gain, or the budget) reports the measured reduction against them.

## Budget

At most 60 attempts or 3 consecutive targets without an accepted step. One engineer at a time on the branch (steps
are sequential); about 150k context per engineer, then a fresh one continues from the run log.

## Baseline at `CB`

`codehealth scan` at `CB` (JSON: `<git-common-dir>/codehealth/runs/s17-base.json`): 39 files, 17939 NLOC, debt
855.0 (47.66/kNLOC), health 7.22, functions with debt 93/988, brain 6, file smells 7. Identical to the numbers at
`6d195c49` in S17_DECISIONS (`application/` unchanged since).

G-END targets from this: `application/` debt at most 598.5; `revision_run.py` (136.0) at most 74.8; `binding.py`
(134.2) at most 73.8.

Hotspots (commits x debt): revision_run.py 2584, revision_binding.py 1879, local.py 1244, coupled_run.py 1173,
validation.py 521, cli.py 520, jobs/runner.py 475, binding.py 403, jobs/model.py 217, operations.py 180.

Largest functions by debt: revision_run.py `write_revision_bundle` 46.9 (cog 46, 119 NLOC, line 895),
`reproduce_bundle` 44.0 (cog 48, 160 NLOC, line 1161), `solve_route` 16.1 (line 526), `run_revision_session` 10.0,
`_solve_coupled` 8.0, `_constants_for_shape` 8.0; binding.py `bind_revision_or_reason` 73.2 (cog 70, 232 NLOC, line
556), `legacy_admission` 23.0 (line 424), `_refused_at_construction` 13.0, `_read_inputs` 9.0, `revision_probe` 8.0.

## Open decisions (defaults in force)

- Module splits: settled by D18 (Frank, 2026-11-13): inside S17 after the function-level work orders, plans approved
  by the orchestrator under Frank's delegation, old import paths kept as re-exports.
- The silent queued job (`owner_instance=None`, S16 B-9) is a product weakness; a finding for a separate package needs
  Frank's yes. Not part of S17.
