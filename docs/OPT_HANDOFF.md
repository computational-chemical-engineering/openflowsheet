# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §4.2 revision host, §4.3–4.5, §4.11, §5 WOs, §6 gates);
ADR 0071 (Proposed). Build decisions, facts and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-30).

## Done

- **WO-1/WO-2** — `studies/nlp/host.py`, `revision_host.py` (`decision_map`, `RevisionNlpHost`). G2 tool
  `scripts/opt_m03_dump.py`. **WO-3** — request schema, `studies/nlp/request.py`, platform probe, `validate` lift.
- **WO-4 (part)** — `FullSpaceNlp` over held systems (D-23); V2/V4/V5 on the revision host (D-25);
  `studies/nlp/revision.py` `optimize_revision` (static → start phase → Ipopt → V1–V6 → report → record, D-24/26/27);
  report `revision` member by `$ref` (D-28, D-30); `benchmarks/opt/` (flowsheets, `analytic.py --check`, requests,
  `expected.json`, D-29). G7/G8/G9 PASS, G2 identical, G1 F0 PASS (numbers: `docs/OPT_DECISIONS.md` WO-4 gates).

## Next

- **WO-4 rest**: G17 (requests on TH-R1, M1, C-MW; record per-start wall time, iterations, twin calls) and F5 (C-MW
  L-BFGS within 500 iterations); D-26 assessment binding at the first certified start (D-18's checks there); an nlp
  test of the record's per-start members (`optimizer.json`, `candidate-revision.json`, bundles in the manifest);
  "multiple output blocks" in `greybox.build_model` when WO-5 adds phase rows.
- **WO-5**, **WO-6** as the design note §5. WO-6 also owes D-19 (validate member, served schema, CLI) and U05 text.
- Design lane (OPT's reviewer pass): D-12, D-18, D-24 (`[[]]` starts corner), D-28, **D-30** (§4.13's flat
  `candidate_revision_sha256` dropped: v2 policy partition).

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited nlp env: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh --no-inventory
  $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>` (runs `nlp`-marked tests only).
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. Policy: `scripts/t08_numerical_policy.py
  --check`. No full gate until WO-7. TRS2 ≤ ~36 busy cores (`uptime` first).

- G2: base dumps from a `git archive cd1a5cfa` copy; the audited env needs `PYTHONPATH=<root>/src:<m05>/.reference-
  downloads/m03-ipopt/nlp-test-tools` (pytest) and `OMP_NUM_THREADS=1`. OPT nlp tests: `tests/test_opt_benchmarks_nlp.py`.

Anchors: `studies/nlp/revision.py` `optimize_revision`, `_Record`; `formulation.py` `FullSpaceNlp.__init__`;
  `verification.py` `_gross`, `_regimes`, `_functional`; `greybox.py` `solve_start`; `request.py` `static_readiness`.
