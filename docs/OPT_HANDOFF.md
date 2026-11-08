# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md`; ADR 0071. Review: `docs/reviews/OPT-review.md` (638523b3).
Build decisions: `docs/OPT_DECISIONS.md` (D-1…D-84; WO-8 section at the end).

## WO-8 (review fix round) — state 2026-11-08
- Merged origin/main (no harvest conflicts). Done, committed: M1 `c54216f9` (D-72), M4 `7269b3b6` (D-73),
  M3 `b5bfa8dc` (D-74, R-939 addendum), M5 `61262021` (D-75), M6 `a50c54f2` (D-76), ruff `95b2cf8e`,
  D-61 design-lane reviews `3bc4e732` (D-78; human reviews pending, Frank's), D-50/G10d `7b7f0b24` (D-79),
  S5 `b903e8f8` (D-80), S3 `9de44aa7` (D-81), S4 `ee676f89` (D-82), S1 declared `e7ada37b` (D-84).
- M2 done: 4976cb53, 4f78b10f (greybox `interruptions=`), 83ee89fe + 5f0da859 (`application/revision_routes.py`
  implements `studies.nlp.host.RevisionRoutes`; D-77), docs fa0320dc. S2 done abbd7d2f (D-83: WARN).
## Merge prep — state 2026-11-09 (brief `docs/briefs/OPT-merge-prep.md`; D-86…D-93)
- main `b31e80ec` merged (`52616943`); c_6 D_6 `3fdc797a…` (strip → D_5 exactly); cache 39; HARVEST_SIZE (84, 1034, 138);
  D-42 lifted by WIT (D-89); ADR 0071 + Am. 16 Accepted (D-90); catalogue `7bbe3d65…` (D-92); C12 re-pointed (D-93).
- Open: D-91 register numbers for ADR 0071's ten drafts (block holds nine); D-93 C12 and D-92 prose for the design lane.
## Next (in order)
1. Orchestrator: full gate, CI both legs (incl. aarch64 default-env G2 evidence), manifest re-take with D-82's
   limitation strings (pr-c1-v1 REGIME_MARGIN_UNDEFINED; thermal-port boundary fails V1; N1 absolute flow
   thresholds; S1 dormant splits) and the D-70 string updated (starts {673.15 K, 650 K}). D-82 (a) "γ–φ held splits
   START_NOT_CERTIFIED" is no longer true after WIT (D-89): GP-C3's held splits certify VERIFIED at 340, 345 K
   (LIQUID) and 365, 375, 385 K (VAPOR, limitation `wilson_dormant_liquid_columns`); (a) now reads "γ–φ held splits
   certify and are unguarded (`regimes_unguarded`)".
2. Human description reviews (D-78) are Frank's.
## Measured in WO-8
- WO-8b gates (all green, numbers in OPT_DECISIONS "WO-8b gates"): G1, G2 both envs identical, audited 21 passed, G22 3/3 verified, default 356 passed.
- M1: probe 5 differences → 0; CI aarch64 pair matches; test_opt_replay 14 passed. M3 guards+F0 68 passed.
  M5 m02 23 passed (1 failed before). M6 simulated aarch64 m03_schemas 1 failed → 30 passed. S5 5 passed.
## How to run
- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1 scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G2: `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=$PWD/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python scripts/opt_m03_dump.py $PWD OUT --nlp`.
