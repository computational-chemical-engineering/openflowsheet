# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4 design, §5/§6 WOs and gates, **§9 amendment A-1…A-4** governs
where it differs); ADR 0071 (Proposed). Build decisions, facts, gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-50).

## Done

- **WO-1…WO-5b** — host … OPT-A3; A-2 zero subsystem, A-3 closure margins (see the log).
- **WO-5c** (D-45 `16fb2d3f`, A-1 `9a78d67e`, OPT-A3v `9373e15b`, D-46 `1d909ef9`): `studies/nlp/boundary.py`
  (e1–e6, B, `certificate_target`); `RevisionNlpHost.phase_boundary` / `basis` (admits a boundary point: held system,
  regimes, Q1′ on its basis); V1 `basis` + B in its detail; candidate `certificate_basis`, `claims.
  numerical_verification`, `regime_note` boundary words; G10 `xfail` removed (PASS). Tests `test_opt_boundary.py`
  (G10a–G10d). `optimize_revision` refuses an unaudited NLP stack (D-44 → D-46). G2 re-taken in the audited env
  against `ad971d32`: identical, solved reports (`b6bbafdb…`).

## Open (design lane, at OPT's reviewer pass)

- For review: D-45 (Q1′ accepts the boundary basis), D-47 (V1 detail shape), D-48 (target rebuilt with the private
  `_staged_splits`), D-49, D-50 (G10d's a/N0 ≤ 1e-7 vs 1e-6 K inconsistency; test uses 1e-9); D-43, D-39/D-40; earlier
  D-18, D-24, D-28, D-30, D-32.
- D-42 (escalated): on `wilson-ig-v2` K04 does not certify a single-phase held split; K04 question.

## Next

- **WO-6** (job, replay: `reproduce` recomputes A-1's clauses and B, A-2's V4 clause; G13/G16 extended with OPT-A3),
  then **WO-7** (user doc: boundary candidates, `certificate_basis`, declared limits; manifest G10a–d, G22–24).

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env tests: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh
  --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`. Scripts in the audited env:
  `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=<root>/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python …` (else PyNumero is unaudited; OPT refuses, D-46).
- G1 `scripts/corpus_identity.py --check`; G2 `scripts/opt_m03_dump.py ROOT OUT [--nlp]` per tree + `cmp` (base by
  `git worktree add --detach <scratch> ad971d32`); G17 `benchmarks/opt/performance.py RECORDS`. No full gate until
  WO-7. TRS2 ≤ ~36 cores.

Anchors: `boundary.py` `judge`, `boundary_form`, `certificate_target`; `revision_host.py` `phase_boundary`,
`held_system`; `verification.py` V1 block in `verify_candidate`; `revision.py` `_phase_members`, D-46 check.
