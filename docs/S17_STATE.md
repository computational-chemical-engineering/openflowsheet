# S17 state: code-health campaign 1 on `src/openflowsheet/application/`

Rewritten in place; history is in `docs/S17_DECISIONS.md` (decisions) and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s17.jsonl` (one line per attempt). Procedure:
`.claude/skills/s17-refactor/SKILL.md`. Standing rules: `docs/S17_RULES.md`.

## Objective

Lower code-health debt in `application/` without any change in behaviour (bitwise), proven per step by
`codehealth gate`. Frank, 2026-11-12: "When I come back I hope to see a very much more healthy code."

## Position (2026-11-13)

- Branch `wp/S17`, worktree `.claude/worktrees/s17`. Config at D11 (`5797f84b`).
- Waiting for S16 to merge into `main` (manifest re-take at ef915499 running; CI 43365514889).
- Campaign base: not yet set. It is the `wp/S17` commit after `main` (with S16) is merged in.

## Next actions

1. After S16 is on `main`: `git merge main` into `wp/S17` (merge commit). That commit is the campaign base `CB`.
   Record its sha below.
2. Build the map: `.venv-testmap/bin/python scripts/test_impact.py build --base CB --workers 12` (about 70 min,
   background). Gate G-MAP.
3. Self-test: gate G-SELF.
4. Baseline scan and hotspots at `CB` (record below; the numbers in S17_DECISIONS are at `6d195c49` with tool 0.2.0.dev0).
5. Refactor loop (skill), first targets `revision_run.py`, then `binding.py`.

## Campaign base

- `CB` = (unset)
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

(to be filled: application/ debt, NLOC, health; the top 10 hotspots)

## Open decisions (defaults in force)

- Module splits (a new module changes the public API): proposed to Frank only, never done.
- The silent queued job (`owner_instance=None`, S16 B-9) is a product weakness; a finding for a separate package needs
  Frank's yes. Not part of S17.
