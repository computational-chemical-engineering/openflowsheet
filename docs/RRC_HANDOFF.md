# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 (Proposed).
Decisions: `docs/RRC_DECISIONS.md` (D-1…D-27). Rewritten in place; this is a position, not a diary.

## Done
- **WO-1** `2e3104cf` + `88de116a`; **WO-2** `4875cf32`; **WO-3** `88b31d23` + `778b4ecb`; **WO-4** `8399b14f`,
  `cfa17fc0`, `3968b720` (see the WO-1…WO-4 sections of `RRC_DECISIONS.md`).
- **WO-5** `cba5e8e2` (5a: `benchmarks/rrc/cases.yaml`, pushed before any run), `b0c7d1ec`/`40fba287` (harness
  `benchmarks/rrc/run_candidates.py`), `96a7129d`/`b91b0ddb` (results `benchmarks/rrc/results-ref-x86-64.{json,md}`,
  pairs `benchmarks/rrc/reference_values.yaml`, gate tests `tests/test_rrc_candidates.py`), `395c5f56` (L21, L-COL-9).

## Gates (2026-11-08, x86-64) — numbers in the WO-5 section of `RRC_DECISIONS.md`
- G9: 10 candidates × 3 policies reported; three fresh runs equal. Selected **N1** (G4), **C3** (G5); N2, N3, C4 also
  qualify; C1, C2, C5 converge first everywhere.
- G4 met: control `BOUND_BLOCKED`; RRC `CONVERGED`/`VERIFIED`/`taken`; closed form 0.0109 ≤ 1; restart root 1.96e-9.
- G5 met (C3): control in the trigger set; RRC `CONVERGED`/`VERIFIED`/`taken`; A29 closure 2.7e-10. L-COL-9 narrowed.
- F1 4.4e-13, F2 2.0e-14 (scaled, item-0 root). G2 (a)–(f) on N1 and C3; (f) held on all 7 taken runs (no column
  pinned: all source signatures `TWO_PHASE`). G7 on the C3 bundle `MATCH`. G10 recorded (compile ≤ 0.051 s/level).
- G1: F0 PASS (M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35); edge-3 test files: no WO-5 diff;
  `t08_support_matrix.py --check` 0 problems; battery 333 passed + 1 fixed (D-27, comment-only), then 22/22 on the rerun.

## Next
- G8 for the registered pairs on both CI legs (WO-4 measured N1's store pair locally, `aa47dabf…`; C3 not yet).
- Evidence manifest `evidence/RRC/<commit>/manifest.json` (status `tested` only after CI on both architectures).
- WO-6 docs: renumber R-RRC-1…6 (register, ADR 0072, `test_t08_b50_surface_content.py` `V02_ADDITIONS`); E3c in
  `recovery-edges.yaml`; `interfaces-frozen.md`; CHANGELOG; ADR 0072 status line. L21/L-COL-9 are done (D-24).

## Open for the design lane (batched, one reviewer pass over WO-1…WO-5)
- D-1/D-16 (offer timing; served `get_project.solve_policies` move; draft id R-RRC-6). D-5, D-6, D-7 (WO-3);
  D-10…D-15 (WO-4); D-17…D-25 (WO-5: harness placement, control id, production column registration, trigger reading,
  L-COL-9 harvest note, no `registry.yaml` entry).
- G2 (f) on a source with pinned columns: still unmeasured (no registered pair has one). FQ1 (Frank): the three
  schema widenings; merge waits for "yes".
