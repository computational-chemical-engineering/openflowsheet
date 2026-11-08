# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md`; ADR 0071. Review: `docs/reviews/OPT-review.md` (638523b3).
Build decisions: `docs/OPT_DECISIONS.md` (D-1…D-84; WO-8 section at the end; D-77 reserved for M2).

## WO-8 (review fix round) — state 2026-11-08
- Merged origin/main (no harvest conflicts). Done, committed: M1 `c54216f9` (D-72), M4 `7269b3b6` (D-73),
  M3 `b5bfa8dc` (D-74, R-939 addendum), M5 `61262021` (D-75), M6 `a50c54f2` (D-76), ruff `95b2cf8e`,
  D-61 design-lane reviews `3bc4e732` (D-78; human reviews pending, Frank's), D-50/G10d `7b7f0b24` (D-79),
  S5 `b903e8f8` (D-80), S3 `9de44aa7` (D-81), S4 `ee676f89` (D-82), S1 declared `e7ada37b` (D-84).
- M2 (dependency inversion, D-77): delegated to an opus-engineer in this worktree; at handoff its edits were
  UNCOMMITTED in cli.py, jobs/runner.py, validation.py, studies/nlp/{host,replay,request,revision,revision_host}.py,
  performance.py, opt_report_dump.py. Brief: scratchpad M2-brief.md (copy in the WO-8 report). Check `git status`.
## Next (in order)
1. Finish/verify M2: `tests/test_m04_study.py` + `tests/test_t07_interrupt.py` green; commit with D-77.
2. S2 (not done): `application/validation.py` `_validate_optimization`: deferred assessment checks
   (`assessed and code.startswith("ASSESSMENT_")`) → `"WARN"` with a "not established statically …" text instead of
   `PASS`/`ASSESSMENT_AT_START`; status stays READY_FOR_OPTIMIZATION; update the test that pins PASS; log D-83.
3. Gates (none run after M2): G1 `scripts/corpus_identity.py --check`; G2 (below) expect `b6bbafdb…`; audited
   `test_opt_benchmarks_nlp.py test_opt_boundary.py test_opt_replay_nlp.py test_opt_job_nlp.py
   test_opt_cost_lca_nlp.py` (G7–G10, G12, G13, G19, G20 — G20 now pins starts [SOLVER_FAILED, KKT_POINT_VERIFIED],
   unverified); G22 `benchmarks/opt/performance.py`; default `tests/test_opt_*.py`, m02/m03/m06/F0-guard files.
4. Push wp/OPT; orchestrator: full gate, CI both legs, manifest re-take with D-82's limitation strings
   (γ–φ held splits START_NOT_CERTIFIED; pr-c1-v1 REGIME_MARGIN_UNDEFINED; thermal-port boundary fails V1; N1
   absolute flow thresholds; S1 dormant splits) and the D-70 string updated (starts {673.15 K, 650 K}).
## Measured in WO-8
- M1: probe 5 differences → 0; CI aarch64 pair matches; test_opt_replay 14 passed. M3 guards+F0 68 passed.
  M5 m02 23 passed (1 failed before). M6 simulated aarch64 m03_schemas 1 failed → 30 passed. S5 5 passed.
## How to run
- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1 scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G2: `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=$PWD/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python scripts/opt_m03_dump.py $PWD OUT --nlp`.
