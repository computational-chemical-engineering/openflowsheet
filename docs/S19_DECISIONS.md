# S19 decisions (append-only)

- **2026-11-14, Frank: excellent code health before further development.** "My purpose now is to refactor the code
  such that code health becomes excellent and we can safely move on with the development to the future. This is the
  goal. Do what it takes." Consequence: a repo-wide campaign S19 runs before S18; the D19 interface package
  (`docs/S17_DECISIONS.md`, D19) is folded into it as ADR 0076. Evidence: repo-wide trial scan at d90b498f (debt
  6370.9, health 7.3, 44 brain functions, 10 import cycles; `docs/briefs/S19-digest.md`).
- **DECISION: the debt baseline `CB` = main d90b498f; the map base `MB` moves to milestone commits.** Alternative:
  one map at `CB` (or S17's 3fa71973). Rejected: `scripts/test_impact.py` falls back to the full suite for any added
  or deleted file, `docs/` included (`_fallback_rule`, B-16), and S19 adds design notes and split modules; every S17
  gate fell back (about 13.5 min each; at that rate S19 would need about 700 full-suite gates). So `MB` is rebuilt
  (about 52 min) after the design and config commits and after each batch of splits; `gate.sh` takes `MB` from
  `docs/S19_STATE.md`. The first build at d90b498f was stopped for this reason. Reversible by: setting `MB` = `CB`.
- **DECISION: design first (A1, `architect`) for the whole tree before any step.** Alternative: start function-level
  steps on the worst files at once. Rejected: 10 cycles across packages and seven files over 1000 NLOC need a target
  layer order and split plans first, or steps would be undone by the splits. Reversible by: none needed (no code).
- **2026-11-14, Frank: more agents allowed for S19.** "Do S19. You can use more agents if needed, I have decided to
  use a reset later this week." This relaxes the CLAUDE.md limit of 2 agents at a time for this campaign (the file is
  not edited). Applied as: up to 3 or 4 agents when their work is on disjoint files or read-only (engineers on
  separate branches per package group, a reviewer, the design lane); never two engineers on one branch. Missing
  codehealth features go to the code_health session (sent 2026-11-14: `arch --config`, cycle and package views
  without layers, per-package scan aggregation, the scan JSON schema, a branch-safe run log).
- **DECISION: re-pin cce-code-health a3401585 -> d542005 before the first step.** It adds `arch --config/--depth/--edges`,
  `scan --group-depth`, the scan JSON schema (`meta.schema = 1`) and a locked, branch-tagged run log (the S19 feature
  requests; gate tiers and comparators unchanged per the code_health session). Check at d90b498f: trial arch 10
  cycles, largest 17 nodes, 79 cycle edges; trial scan debt 6370.9 (as before). Parallel engineers run as worktrees
  of this clone (one run log). Alternative: keep a3401585 and hand-made graphs. Reversible by: the pin line.
