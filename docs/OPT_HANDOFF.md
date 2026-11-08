# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.8–§4.13 WO-6, §6 G11–G16, §9.5 G13/G16 extensions); ADR 0071.
Build decisions, facts, gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-62; WO-6b gates at the end).

## Done
- WO-1…WO-5c; WO-6 part 1 (job operation, library hooks, D-51..D-58).
- **WO-6b** (2026-11-08): `validate`'s `optimization` member + the two description texts (`49b2b50c`, D-59, D-61);
  R4-G3 resolver cycle rule (`224f3154`, D-60); surface link **c_4 = R-960, `without_opt`, D_4 `3fb06cad…`**
  (`2669896b`; stripped = D_3 `455d01eb…`); Q26 per D-58 default (`fee9090c`, isolated); replay
  `studies/nlp/replay.py` + G13 (`6d30efa0`, D-62; committed fixture `tests/fixtures/opt/replay/OPT-A2`, 588 KB).
- All 13 previously failing tests pass. Red by design: `test_t08_w2_description_reviews.py` (D-61: two texts await
  the design-lane and Frank's review; no agent marks them).
## Next (WO-6c), in order
1. Replay dispatch: `jobs/runner.py:691` (`reproduce` body) and `cli.py:200` (`replay DIR [--rerun]`) call
   `replay.replay_optimization` when `replay.is_optimization_record(dir)`; the job's imported artifact must keep the
   record's tree (check `_import_bundle` copies subdirectories). Test both on the committed fixture.
2. CLI `optimize REVISION --request FILE --out DIR [--json]` (direct `optimize_revision`, no project; policies as the
   nlp benchmark: `resolve_policy(DEFAULT_POLICY_ID, "revision_eo")`, `CheckPolicy()`), and `validate --request FILE`
   (`cli.py:470`), G11 subprocess checks (no pyomo/cyipopt in `sys.modules`) for both.
3. G12 job ≡ library (inline and spawned executor, OPT-A2; mask `wall_time_s` in the report and the report SHA in the
   manifest); G14 cancel during start 1 of 3 → `cancelled`, no report/manifest outputs, start-0 artifacts; budget
   inside Ipopt → `timed_out`; G16 commit the candidate change-set, `solve` job → certificate R0 = V1's (OPT-A2), and
   OPT-A3 → `UNVERIFIED` (`rank_limitation`) with R0 = V1's. Audited env, nlp-marked.
4. §4.9 gap (D-62 f): the verification document's active-set flip within 1e-9 relative of a threshold →
   `verdict_changed_near_threshold` (now a plain MISMATCH).
5. U05 text in `benchmarks/t08/support_envelope.yaml:401` (lifted by ADR 0071; code `nlp_solver_unavailable`), then
   `scripts/t08_support_matrix.py --check` 0 problems.
6. G1 F0 (`scripts/corpus_identity.py --check`), G2 (audited `--nlp`, expect `b6bbafdb…`; confirm solved reports),
   G7–G10 rerun (`m03_nlp_check.sh -- tests/test_opt_benchmarks_nlp.py test_opt_boundary.py`).
## Risks / questions for the reviewer
- G13 aarch64: verification floats are compared under T08-v2 with no registered floors for KKT residuals; near-zero
  values may differ across architectures (x86 default env and audited env both MATCH with 0 differences).
- D-58 (Q26 allow-list), D-60 (resolver), D-61 (description reviews) await the reviewer's ruling.
## How to run
- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1 scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- Fixture re-take: `OPT_WRITE_REPLAY_FIXTURE=$PWD/tests/fixtures/opt/replay` on `tests/test_opt_replay_nlp.py`.
- No full gate until WO-7; TRS2 ≤ ~36 busy cores.
