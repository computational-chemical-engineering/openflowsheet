# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md`; ADR 0071. Build decisions, facts, gate numbers:
`docs/OPT_DECISIONS.md` (D-1…D-71; WO-7 gates at the end).

## Done (all work orders WO-1…WO-7)
- WO-7 (2026-11-08): §4.9 near-threshold active-set flip in replay (`1fd79dfa`, D-68, closes D-62 f); G19 OPT-C
  (TAC) and G20 OPT-L (GWP) on TH-C1 vs E01 hand models, `benchmarks/opt/cost_lca.py` (`a201c53b`, D-69, D-70); user
  doc `docs-site/guide/optimisation.md` (`a46ea80f`, D-71); manifest `evidence/OPT/a46ea80f…/manifest.json`, status
  `implemented`, harvested (`d15b28aa`, L-OPT-1, L-OPT-2, `HARVEST_SIZE` (75, 982, 129)).
- Final gates at `a46ea80f`: G1 F0 PASS; G2 `b6bbafdb…`; audited 21 passed (G7–G10, G12–G14, G16, G19, G20);
  G17/G22 C-MW both starts verified; default OPT files 217 passed + the D-61 red test; G3 383 passed.
## Not done / next (orchestrator)
1. Full gate (G21) and CI on both legs; read the aarch64 leg for G13's committed fixture. Then re-take the manifest
   (a new `evidence/OPT/<commit>/`) with OPT.G21/OPT.G13.aarch64 results; `tested` only once OPT.D61 passes.
2. D-61: the design lane and Frank review the two changed descriptions (`validate`, `submit_job`); until then
   `test_every_description_is_reviewed_by_both_lanes` is red and the full gate fails.
3. `mypy` (configured files) shows 3 pre-existing errors in `benchmarks/opt/analytic.py` / `performance.py` — check
   whether the gate's mypy reports them.
## Questions for the reviewer / design lane
- D-70: Ipopt stalls at max_iter on OPT-L from the feasible side (673.15 K, 661 K; also other scalings); verifies
  from 650 K. Robustness of fixed Ipopt options (monotone mu, L-BFGS) — change options or keep the declared limit?
- D-68: a near-threshold active-set flip forgives the active-set-dependent entries (active_set, kkt, V3 list, V5)
  and the classification/status they move; verdict MATCH if nothing else differs.
- D-69: G19 starts are explicit (revision outside the box); hand TAC in the audited env via a subprocess with mpmath.
- Open from WO-6: D-58 (Q26 allow-list), D-60 (resolver), D-63 (G12 wall-clock mask), D-66, G13 aarch64 floors.
## How to run
- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1 scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G2: `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=$PWD/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python scripts/opt_m03_dump.py $PWD OUT --nlp` (no BLAS pins).
- `benchmarks/opt/cost_lca.py --check` re-runs both searches (~90 s, default env).
