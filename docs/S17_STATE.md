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
- Map build at `CB` running (started 2026-11-13; log `scratchpad/s17_map_build.out` of the session, map in
  `~/.cache/openflowsheet/testmap/1fd6826b2f433c73c4c41ef6ccad1dcb903985c8/`).

## Next actions

1. (done) Merge `main` into `wp/S17`; `CB` fixed.
2. Build the map: `.venv-testmap/bin/python scripts/test_impact.py build --base CB --workers 12` (about 70 min,
   background). Gate G-MAP.
3. Self-test: gate G-SELF.
4. (done) Baseline scan at `CB`, below.
5. Refactor loop (skill), first targets `revision_run.py`, then `binding.py`.

## Campaign base

- `CB` = `1fd6826b2f433c73c4c41ef6ccad1dcb903985c8`
- `OFS_MAP_BASE` = `CB` for every gate run.

## Gates (criteria fixed 2026-11-13, before any run)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | map at `CB` | build exit 0 or 1; at least 20284 tests in the map; failing tests a subset of the 5 B-6 failures of S16 (`docs/S16_DECISIONS.md` B-6) plus at most 2 others, each named | |
| G-SELF | before step 1 | `codehealth gate --self-test --mutate <path:line>` on a literal that `select --lines` maps to at least one test: SELF-TEST PASS with the `tests` tier failing with exit 1 (a test failure, not exit 2 or 124); unmutated, the `tests` tier passes | |
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

- Module splits (a new module changes the public API): proposed to Frank only, never done.
- The silent queued job (`owner_instance=None`, S16 B-9) is a product weakness; a finding for a separate package needs
  Frank's yes. Not part of S17.
