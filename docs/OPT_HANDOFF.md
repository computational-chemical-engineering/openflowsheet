# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4 design, §5/§6 WOs and gates, **§9 amendment A-1…A-4** governs
where it differs); ADR 0071 (Proposed). Build decisions, facts, gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-44).

## Done

- **WO-1…WO-5** — host, revision host, request, formulation, V1–V7, records, phase rows (D-35), Q4 held mode, OPT-A3.
- **WO-5b** (A-2 `051e3397`, A-3 `7b1f7242`, D-43 `90161fd0`): zero subsystem held in `RevisionNlpHost.held_system`
  (`HeldSystem.zero`, `ZeroSubsystem`), `zero_at_start_unresolved` bounds, V4 `ZERO_SUBSYSTEM_CHANGED`, start record
  `zero_subsystem`; margins = closure test (`orchestrator/region.py` `admissibility_value`, `revision_host.
  two_phase_margin`), guarded/unguarded rows (`phase.py` `CLOSURE_IDENTITY`, `PhaseRows.unguarded`),
  `regimes_unguarded`, V4 `phase_row_not_closure_test`. Tests `test_opt_zero_subsystem.py` (G23),
  `test_opt_margins.py` (G24). G22 PASS: C-MW both starts `KKT_POINT_VERIFIED`, 0 evaluation errors.

## Open (design lane, at OPT's reviewer pass)

- D-37 (G10, boundary candidates) → ruled by A-1; **WO-5c implements it** (next).
- D-42 (escalated): on `wilson-ig-v2` K04 does not certify any single-phase held split (derivative-witness stencil
  steps the held zero side negative), so A-3's unguarded γ–φ splits cannot be OPT starts today; K04 question.
- D-44: `optimize_revision` runs on an unaudited PyNumero where M03's probe refuses; G2 `--nlp` needs the audited
  variables (`PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=<m05>/.venv-nlp/share/pyomo`).
- For review: D-43 (identity clause only on an unchanged regime), D-39/D-40; earlier D-18, D-24, D-28, D-30, D-32.

## Next

- **WO-5c** (A-1): `studies/nlp/boundary.py`, V1 bases, report fields, OPT-A3v + mpmath script, λ*; G10 `xfail`
  removed; gates G1, G2, G10, G10a–G10d, G9 rerun. Then WO-6 (job, replay; A-2's V4 clause in replay), WO-7.

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (serial).
- Audited env tests: `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05; scripts/m03_nlp_check.sh
  --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`. Scripts in the audited env:
  `OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=$W/.venv-nlp/share/pyomo PYTHONPATH=<root>/src:$W/.reference-
  downloads/m03-ipopt/nlp-test-tools $W/.venv-nlp/bin/python …`.
- G1 `scripts/corpus_identity.py --check`; G2 `scripts/opt_m03_dump.py ROOT OUT [--nlp]` per tree + `cmp`; OPT report
  bytes `scripts/opt_report_dump.py OUT` per tree + `cmp`; G17 `benchmarks/opt/performance.py RECORDS`. Base trees by
  `git archive <commit>`. No full gate until WO-7. TRS2 ≤ ~36 cores.

Anchors: `revision_host.py` `_held_zero`, `_zero_rows`, `regimes`; `phase.py` `_guarded`; `verification.py`
`_zero_subsystems`, `_not_closure_test`.
