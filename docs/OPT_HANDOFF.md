# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §4.2 revision host, §4.3–4.8, §4.11, §5 WOs, §6 gates);
ADR 0071 (Proposed). Build decisions, facts and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-38).

## Done

- **WO-1/WO-2** — `studies/nlp/host.py`, `revision_host.py` (`decision_map`, `RevisionNlpHost`). G2 tool
  `scripts/opt_m03_dump.py`. **WO-3** — request schema, `studies/nlp/request.py`, platform probe, `validate` lift.
- **WO-4/WO-4b** — `FullSpaceNlp` over held systems, V2/V4/V5 on the revision host, `optimize_revision`, records,
  output blocks (D-31), E01 binding (D-32), OPT-C0, G17/F5 (D-34). `benchmarks/opt/`.
- **WO-5** — `studies/nlp/phase.py` (rows as a functional program; D-35), `RevisionNlpHost.phase_rows`,
  `REGIME_MARGIN_UNDEFINED` at the start phase (D-36), second output block `phase_admissibility`, V3/V4/V5 with phase
  rows, Q4 held mode (`evaluate_sensitivity(held=)`, `host.sensitivity(held=)`), candidate `phase_bounds_active` and
  `regime_note`; D-38 (uncertified re-solve judged no further than V1); OPT-A3 + G9 rerun (N1 → INFEASIBLE_REPORTED).
  Commits `e8311348`, `01b9650c`, `247e2ea5`; gate numbers in `docs/OPT_DECISIONS.md` "Gates (WO-5)".

## Open (design lane, at OPT's reviewer pass)

- **D-37 (premise false, blocks G10):** at a lifted split's bubble point the cold re-solve's K04 certificate is
  ILL_CONDITIONED (rcond ≈ 2.27e-6·ΔQ W), so V1 fails at any candidate whose split row is active; G10-as-designed is
  `xfail(strict=True)` in `tests/test_opt_benchmarks_nlp.py`. Options (a)/(b)/(c) in D-37.
- C-MW (measured after WO-5): TWO_PHASE gets no row; V4/V5 still fail on the 19 `null` margins (D-12). Ethanol
  zero-flow `DomainError` (§4.2.3 bounds) unchanged.
- Pending rulings: D-12, D-18, D-24 (`[[]]` corner), D-28, D-30, D-32; brief's "G7/G8/C0 byte-identical" vs design —
  the phase row changes those Ipopt problems (numbers within the gates: "OPT reports vs base" in Gates (WO-5)).

## Next

- **WO-6** (job `optimize`, replay, CLI, fixture record, surface link; owes D-19 and U05 text), **WO-7** (G19 cost by
  golden section, G20 LCA, user doc, manifest, full gate before merge).

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited nlp env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh --no-inventory
  $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>` (runs `nlp`-marked tests only).
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. Policy: `scripts/t08_numerical_policy.py
  --check`. `benchmarks/opt/analytic.py --check`, `performance.py --check`. No full gate until WO-7. TRS2 ≤ ~36 cores.
- G2: base dumps from a `git archive <base>` copy; the audited env needs `PYTHONPATH=<root>/src:<m05>/.reference-
  downloads/m03-ipopt/nlp-test-tools` and `OMP_NUM_THREADS=1`. OPT nlp tests: `tests/test_opt_benchmarks_nlp.py`.

Anchors: `phase.py` `phase_rows`, `PhaseRows`; `revision.py` `optimize_revision` (start loop), `_phase_members`;
`formulation.py` `FullSpaceNlp._hold_phases`; `verification.py` `verify_candidate`, `_phase_terms`, `_regimes`;
`sensitivity.py` `_Run._regimes`.
