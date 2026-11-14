# S19 decisions (append-only)

- **2026-11-14, Frank: excellent code health before further development.** "My purpose now is to refactor the code
  such that code health becomes excellent and we can safely move on with the development to the future. This is the
  goal. Do what it takes." Consequence: a repo-wide campaign S19 runs before S18; the D19 interface package
  (`docs/S17_DECISIONS.md`, D19) is folded into it as ADR 0076. Evidence: repo-wide trial scan at d90b498f (debt
  6370.9, health 7.3, 44 brain functions, 10 import cycles; `docs/briefs/S19-digest.md`).
- **DECISION: the campaign base -> `CB` = main d90b498f, which is also the map base.** Alternative: keep S17's map
  base 3fa71973. Rejected: every diff since 3fa71973 holds collection-time code, so every S17 gate fell back to the
  full suite (about 13.5 min each; at S17's rate S19 would need about 700 steps). A fresh map makes selection work.
  Reversible by: passing the old base to `--ref-base`.
- **DECISION: design first (A1, `architect`) for the whole tree before any step.** Alternative: start function-level
  steps on the worst files at once. Rejected: 10 cycles across packages and seven files over 1000 NLOC need a target
  layer order and split plans first, or steps would be undone by the splits. Reversible by: none needed (no code).
