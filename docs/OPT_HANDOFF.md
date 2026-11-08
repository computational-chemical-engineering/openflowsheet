# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.8–§4.13 WO-6, §6 G11–G16, §9.5 G13/G16 extensions); ADR 0071.
Build decisions, facts, gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-67; WO-6c gates at the end).

## Done
- WO-1…WO-5c; WO-6 part 1 (job operation, library hooks, D-51..D-58); WO-6b (validate member, descriptions,
  resolver, surface link c_4 `3fb06cad…`, Q26, replay + G13 fixture; D-59..D-62).
- **WO-6c** (2026-11-08): replay dispatch — `reproduce` imports a record as a `replay_bundle`, the job and CLI
  `replay` dispatch on the format (`0e0c8ea3`, D-64); CLI `optimize` and `validate --request` + G11 CLI half
  (`1001f877`, D-65); G12/G14/G16 audited tests `tests/test_opt_job_nlp.py` (`a2020a14`, D-63 mask, D-66, D-67);
  U05 text + support matrix (`adab74c4`, `--check` 0 problems).
- Gates at `adab74c4`: G1 F0 PASS; G2 `b6bbafdb…` (set `OMP_NUM_THREADS` only — the BLAS/MKL pins enter the dump);
  audited 19 passed (G7–G10, G13, G12, G14, G16); default env OPT files 269 passed + the D-61 red test.
- Red by design: `test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes` (D-61).
## Not done / next
1. §4.9 gap (D-62 f): a verification-document active-set flip within 1e-9 relative of a threshold →
   `verdict_changed_near_threshold` (today a plain MISMATCH). Not in WO-6c's order; open.
2. G13 aarch64: the committed fixture on the CI leg — read the run for the WO-6c push (see the report / progress).
3. WO-7 (docs, full gate, merge prep) per design §5.
## Risks / questions for the reviewer
- D-63: G12 masks every wall-clock member (report `wall_time_s`; bundle `started_at`, `elapsed_seconds`,
  `manifest_sha256`; their SHAs in the record manifest) — the design said "byte for byte", unreachable with clocks.
- D-66: an interrupted job has start 0's bundles but not its `optimizer.json`/`verification.json` (written with the
  report). G14 reads "start-0 files" as its bundles.
- G13 aarch64: verification floats compared under T08-v2 with no registered floors for KKT residuals (D-62 risk).
- D-58 (Q26 allow-list), D-60 (resolver), D-61 (description reviews) await the reviewer's ruling.
## How to run
- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1 scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G2: `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=$PWD/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python scripts/opt_m03_dump.py $PWD OUT --nlp` (no BLAS pins).
- No full gate until WO-7; TRS2 ≤ ~36 busy cores.
