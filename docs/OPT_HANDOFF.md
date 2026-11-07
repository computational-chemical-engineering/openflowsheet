# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §4.2 revision host, §4.3–4.8, §4.11, §5 WOs, §6 gates);
ADR 0071 (Proposed). Build decisions, facts and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-34).

## Done

- **WO-1/WO-2** — `studies/nlp/host.py`, `revision_host.py` (`decision_map`, `RevisionNlpHost`). G2 tool
  `scripts/opt_m03_dump.py`. **WO-3** — request schema, `studies/nlp/request.py`, platform probe, `validate` lift.
- **WO-4** — `FullSpaceNlp` over held systems (D-23); V2/V4/V5 on the revision host (D-25); `revision.optimize_revision`
  (D-24/27); report `revision` member by `$ref` (D-28, D-30); `benchmarks/opt/` (OPT-A1, A2, A2b, N1; D-29).
- **WO-4b** — output blocks `formulation.OutputBlock` (D-31, proved inert: G2 + OPT reports identical vs `c6755d86`);
  E01 binding at the first passing start (D-32, supersedes D-26), OPT-C0 cost benchmark (D-33); audited-env record
  test (§4.8); G17/F5 (`benchmarks/opt/performance.py`, D-34). Numbers: `docs/OPT_DECISIONS.md` WO-4b gates.

## Next

- **WO-5** (phase rows as a second `OutputBlock`, component `phase_admissibility`; Q4 held mode;
  `phase_bounds_active`, `regime_note`; OPT-A3; G9 rerun), **WO-6**, **WO-7** (G19 interior cost by golden section,
  G20 LCA) as the design note §5. WO-6 also owes D-19 (validate member, served schema, CLI) and U05 text.
- Design lane (OPT's reviewer pass): D-12, D-18, D-24 (`[[]]` starts corner), D-28, D-30, D-32 (binding rules), and
  **D-34's escalations**: C-MW's zero-flow ethanol columns unbounded by §4.2.3 → twin `DomainError` on ~99 % of
  residual calls; C-MW's 19 held TWO_PHASE stages have `null` PH-split margins → V4 fails, V5 refused, so no C-MW start
  can verify.

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited nlp env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh --no-inventory
  $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>` (runs `nlp`-marked tests only).
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. Policy: `scripts/t08_numerical_policy.py
  --check`. `benchmarks/opt/analytic.py --check`, `performance.py --check`. No full gate until WO-7. TRS2 ≤ ~36 cores.
- G2: base dumps from a `git archive <base>` copy; the audited env needs `PYTHONPATH=<root>/src:<m05>/.reference-
  downloads/m03-ipopt/nlp-test-tools` and `OMP_NUM_THREADS=1`. OPT nlp tests: `tests/test_opt_benchmarks_nlp.py`.

Anchors: `revision.py` `optimize_revision`, `_bind_assessment`, `_Record`; `formulation.py` `FullSpaceNlp.__init__`,
`OutputBlock`, `_add_block`; `greybox.py` `build_model`, `solve_start`; `verification.py` `_gross`, `_regimes`.
