# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.8–§4.13 WO-6, §6 G11–G16, §9.5 G13/G16 extensions); ADR 0071.
Build decisions, facts, gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-58).

## Done

- WO-1…WO-5c (see the log). Main (X10) merged at `33a59d4d` (clean; HARVEST_SIZE (74, 977, 126); F0 PASS).
- **WO-6, part 1** (`c85c8736`, `47f474ad`, `a4ef4d85`): Ipopt interruption hook (`greybox._Iterations.interrupt`),
  per-start wall-time cap and `record` stage in `optimize_revision` (D-52..D-54; G2 `--nlp` `b6bbafdb…` identical;
  OPT nlp benchmarks 8 passed); the `optimize` job: `job.schema.json` (enum, branch, `job_result.optimization`, six
  kinds), `optimization-request.schema.json#/$defs/optimize_body`, `OptimizeBody`, `JobResult.optimization`,
  `admit_optimize`, `runner._Body.optimize` (stages, artifacts `<job_id>:optimization/<path>`, outputs report then
  manifest), `local._admit`/`_result` (D-55..D-57). `tests/test_opt_job.py` (G11 job half) 2 passed.

## Failing now (expected until the surface link): served-surface tests

`test_m07a_surface_chain.py` (5), `test_t08_w2_surface_digest.py` (4), `test_t07_w5e_application_results.py` (2),
`test_m04_study_job.py::test_a42_…`, `test_t07_q26.py::test_t07_q26_no_external_state` (D-58).

## Next (WO-6, part 2), in order

1. `LocalApplication.validate(revision_id, task, optimization=None)` + `OPERATIONS["validate"]` optional member
   (`_ref("optimization-request.schema.json")`, decode `_members(..., "optimization")`), calling
   `validation.validate(doc, task, optimization=)` (D-19); `descriptions/validate.md` and `submit_job.md` texts.
2. `tests/opt_schema_support.py::without_opt` (pattern `tests/m04_schema_support.py`: enum values `optimize` + six
   kinds, the `optimize` branch, inlined `optimize_body` by description prefix "OPT design §4.10 (ADR 0071",
   `job_result.optimization`, `validate`'s `optimization`; restores the two description texts from pre-OPT copies —
   commit them as fixtures). `scripts/m07a_rc.py` link `c_4` (D-51) + `strip_opt`; register entry R-<next> with
   D_4 and D_3; item 4 (`description_problems`) judged on the stripped texts. Fix the failing tests above
   (pattern: X02's diff `git diff origin/main...origin/wp/X02 -- scripts/m07a_rc.py tests/`). Q26 per D-58 default.
3. Replay (§4.9): `reproduce` / CLI `replay` dispatch on manifest `format == openflowsheet-optimization-v1`
   (`revision.OPTIMIZATION_FORMAT`); integrity, rerun bundles, V2–V7 + A-1 clauses/B + A-2 V4 recomputed.
4. CLI `optimize REVISION --request FILE --out DIR [--json]`, `validate --request`.
5. Tests (audited env): G12 job ≡ library (mask `wall_time_s` in the report and the report's SHA in the manifest),
   G14 cancel during start 1 of 3 / budget inside Ipopt, G13 (+ committed OPT-A2 fixture ≤ 2 MB, aarch64), G16.
6. U05 text in `benchmarks/t08/support_envelope.yaml`; G1 F0, G2 at the end.

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh --no-inventory
  $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- tests/test_opt_benchmarks_nlp.py` (nlp-marked only).
- G2: `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=$PWD/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python scripts/opt_m03_dump.py $PWD OUT --nlp` → `b6bbafdb…`.
- No full gate until WO-7. TRS2 ≤ ~36 cores.
