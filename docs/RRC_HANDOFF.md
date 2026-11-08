# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 (Proposed).
Decisions: `docs/RRC_DECISIONS.md` (D-1…D-16). Rewritten in place; this is a position, not a diary.

## Done
- **WO-1** `2e3104cf` + `88de116a`: `Continuation.start_values`, `level_values` dispatch, the Literal, `RRC_REVISION_V1`,
  three schema widenings (FQ1), ADR 0072 C1. Tests `tests/test_rrc_continuation.py`.
- **WO-2** `4875cf32`: `orchestrator/revision_continuation.py` (R5/R6/R8/R9a). Tests `tests/test_rrc_checks.py`.
- **WO-3** `88b31d23` + `778b4ecb`: executor `_revision_continuation`, region opening check. Tests `tests/test_rrc_edge3.py`.
- **WO-4** `8399b14f` (application half: `application/revision_continuation.py` — `find_source`, `assemble` A1–A3,
  `ContinuationSource.member`, `recorded_source`; threaded in `jobs/runner.py` and `revision_run.py`; R0 branch in
  `run/identity.py`; `ProjectStore.job_artifact_relpath`), `cfa17fc0` (D-1: policy offered; pins; register draft
  R-RRC-6; envelope axis + `docs/support-matrix.md`), `3968b720` (tests `tests/test_rrc_application.py`, 23).

## Gates (2026-11-08, at `3968b720`) — see the WO-4 section of `RRC_DECISIONS.md` for the served-content table
- G1: targeted battery (rrc ×4, t04_homotopy, t04_edge3, t06_f4 ×6, t08_w4_warm_starts, m04_prewarm, t06_w4_registry,
  t07_b3/w3a/w4a/w5a/identity/r6_replays, k05_replay, t08_w1_d2_replay_identity, t08_b50, f0) **626 passed**; edge-3
  test files: empty diff vs `origin/main` and vs WO-3; F0 PASS M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105,
  M9 35/35; `t08_support_matrix.py --check` 0 problems.
- G8 (local, x86-64; CI legs are the orchestrator's): the NET-02 store pair twice in fresh processes → equal
  `artifact_r0_sha256` `aa47dabf…`, member R0 `04e01c88…`, 4 `homotopy_step` events, state digest `5c460d18…` both runs.
- G6 (a, c, d, e, k): pass in the store (d, k with edge 3 forced). G7: four bundles (taken, a, c, e) rerun `MATCH`,
  0 differences, with the store lookup, `find_source` and the binder refused.
- Opening-hash point (WO-3): no WO-4 case pins a column. NET-02's recovery item `opening_state_sha256` equals the
  ancestor's `full_state_sha256` (asserted); every G6 case refuses before any opening. G7 does not depend on it.
  **Forward risk for WO-5:** an ancestor whose final signature puts a split in a one-phase regime pins columns, so the
  opening digest (free columns) cannot equal `full_state_sha256` and G2 (f) as worded would fail — design-lane question.

## Next
- **WO-5**: 5a transcribe §8.1 into `benchmarks/rrc/cases.yaml` (a commit before any run); 5b runs, registration, G4,
  G5, F1, F2, G8 (registered, both CI legs), G9, G10; evidence manifest. Then WO-6 docs (renumber R-RRC-1…6 in the
  register, ADR 0072 and `test_t08_b50_surface_content.py` `V02_ADDITIONS`; L21/L-COL-9 rows; E3c; CHANGELOG).

## Open for the design lane (batched, one reviewer pass)
- D-1/D-16 (offer timing; served `get_project.solve_policies` move; draft register id R-RRC-6).
- D-5, D-6, D-7 (WO-3); D-10 (member status when the edge never fired), D-11 (parameter family before the first `.`),
  D-12/D-13 (A3/A1 order and spelling), D-14 (R0 branch), D-15 (`not_supplied` member).
- G2 (f) on a source with pinned columns (above). FQ1 (Frank): the three schema widenings; merge waits for "yes".
