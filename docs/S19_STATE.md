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
- `MB` = `d90b498f8759b739361016cca7858f71bc647ccc` (= `CB`, no map: W1 and W2 gates run the full suite; a map is built after W2).
- A1 done: design note `docs/briefs/S19-architecture.md` (phases W0 to W4, table 4.1 with the arch numbers per
  step), ADR 0076 proposed. Config committed: scope `src/openflowsheet/*`, `repo-layers`, forbid
  `verifier-not-through-the-solver`; adoption 14 violations, 10 cycles, 79 cycle edges.
- Frozen (F0 M9, 35 modules, debt 565.2): untouched until W5 (S19_DECISIONS, Q1).
- W1 lanes merged (2026-11-14): lane a A1 to A4 (9f409826), lane b A6 to A8 (b16dd300); every step gated 15/15 on
  the full suite. At b16dd300: `codehealth arch --depth 4` 11 violations, 6 cycles, 20 cycle edges (= table 4.1 after
  A8 with A5 still to do: 8 + 3); `patch_noop` 0 of 243. A6 part 1's passing re-gate is not in the run log (the tool
  refuses a second entry for one tree and base; JSON `s19-gates/20261114T111827-s19b-A6a-r2.json`).
- Running: lane c (`S19-W2c.md`: A5 `numerics.solve_record`, splits B1, B8-executor; worktree `s19c`), lane d
  (`S19-W2d.md`: splits B6, B5 with B5a, B8-certificate; `s19d`), both from b16dd300; `reviewer` R-W1 on the W1 moves
  (`S19-R-W1.md`). ADR 0076 acceptance sent to the hub's decision desk (id `ofs-adr0076-accept`).

## Next actions

1. R-W1 verdict: fixes as `--no-gain` steps in a later lane; a blocker reverts its step.
2. W2: lanes c and d (above); then a models lane (B3, B2, B4); merge each lane into `wp/S19` after its report.
3. After W2: the map at `wp/S19` (`MB`), G-MAP.
4. W3 function-level per package group; reviews per the sensitivity tiers.
5. W4 (ADR 0076 accepted 2026-11-14): after W3; first the design-lane rulings A15, A11, I-10 and the re-pin to
   04f630e or later (interface mode); order as in the ADR (I-6, I-3, I-1, ...). W5: frozen modules after a
   `specifier` identity ruling. Merge into `main` after each phase (CI both legs, F0).

## Gates (pass numbers fixed after A1, before step 1)

| gate | when | pass criterion | result |
| --- | --- | --- | --- |
| G-MAP | the map after W2 | build exit 0 or 1; at least 20356 tests in the map; failures a subset of the S17 G-MAP set, others named | |
| G-SELF | before step 1 | `gate --self-test --mutate` on a numeric literal outside application/ that tests read: tests tier exit 1 (failures, not 2 or 124) and F0 detects it; unmutated, all tiers pass | run 1 (newton.py:776, 3d3eebe3) FAIL: unmutated tests tier exit 1, only test_t07_v17_reference f6 (wall 333 s > 300 s budget) under two concurrent lane gates; gate.sh now takes a clone-wide lock (a1059f16); run 2 (same literal, a1059f16) PASS: unmutated 20253 passed, 1044 s; mutated tests exit 1 (499 failed, 6 errors, 865 s), f0 detected, mcp_digest missed (as in S17) |
| G-STEP | every step | gate exit 0; refactor: touched files' debt strictly lower; restructure: the plan's arch numbers (table 4.1) met exactly | run log |
| G-REVIEW | S1 files every 3 accepted steps, S2 and S1/S2 splits every 4, others every 8 (design note 5) | fresh `reviewer`; rejects reverted and logged | |
| G-END | campaign end, at the merged tip | repo scan (scope `src/openflowsheet/*`): debt <= 1900; health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at depth 4, 0 violations on every rule; F0 and MCP digest identical; full suite and CI green on both legs | |
| G-END-CI | before each merge | CI green on both legs; F0 on `main` after the merge | |
