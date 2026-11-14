# S19 state: repo-wide code-health campaign (includes the D19 interface package)

Rewritten in place; history in `docs/S19_DECISIONS.md` and the run log
`$(git rev-parse --git-common-dir)/codehealth/runs/s19.jsonl`. Standing rules: `docs/S19_RULES.md`. Procedure: the
S17 skill (`.claude/skills/s17-refactor/SKILL.md`) until `s19-refactor` exists.

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
- `MB` = `none yet`: built after A1's documents and the config commit.
- Running: design pass A1 (`architect`, brief `docs/briefs/S19-A1.md`): repo-wide layer order, cycle cuts, split
  plans, work orders, ADR 0076, the end-gate numbers.

## Next actions

1. A1 reports: judge it; fix the gate table below with numbers before any step; commit the `[architecture]` table and
   the widened scope in `.codehealth/config.toml` (one orchestrator commit).
2. Build the map at that commit (`MB`), G-MAP and G-SELF; the `s19-refactor` skill (gate.sh exists).
3. Work orders per the design note; reviewer every 6 to 8 accepted steps; design-lane review on sensitive files.
4. ADR 0076 reviewed, then the interface steps; merge into `main` per package group (CI both legs, F0).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | each map at `MB` | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | |
| G-SELF | before step 1 | as S17 G-SELF, on a literal outside application/ | |
| G-STEP | every step | gate exit 0; touched files' debt strictly lower (or a restructure plan met) | run log |
| G-REVIEW | every 6 to 8 accepted steps | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end | to be fixed from A1 (opening proposal: debt <= 1900, health >= 9.0, brain 0, no file health < 7.0, no huge_file, cycles 0, violations 0) | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
