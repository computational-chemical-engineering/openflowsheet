# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §5 WOs, §6 gates); ADR 0071 (Proposed).
Build decisions and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-7 so far).

## Done

- **WO-1** — `src/openflowsheet/studies/nlp/host.py`: `NlpHost` protocol, `CertifiedPoint`, `HeldSystem` (§4.2.1
  assertions), `RegimeRecord`, `DecisionRefusedError`, `Syn001NlpHost`, `as_host`. `closure`, `formulation`
  (`FullSpaceNlp`), `greybox`, `verification` take `NlpHost | Syn001Flowsheet`; `optimize()` signature unchanged
  (builds the SYN-001 host once). Tests: `tests/test_opt_host.py`.
- G2 tool: `scripts/opt_m03_dump.py ROOT OUT [--nlp]` (masked member: `wall_time_s` only). Base dumps are not
  committed: re-take them from a `git archive ad971d32 src tests scripts benchmarks schemas pyproject.toml` copy.

## Next

- **WO-2** (§4.2): `RegionResult.final_system` (`orchestrator/region.py`), `HeldSystem` from it (+ alias rows),
  `SensitivityHost.system` (`studies/sensitivity.py`, `None` ⇒ today's path bit-identical), Q4′ PH-with-margin,
  `studies/nlp/revision_host.py` `RevisionNlpHost` (certify via `bind_route`/`solve_route`, cold; decision map by bind
  probes; bounds §4.2.3; regimes; twin cache). Gates G1, G3, G4, G5, G6.
- **WO-3** (§4.3, §4.5, §4.11; can run beside WO-2): request schema + fixtures, request → `NlpFormulation`, Halton,
  static readiness, platform-aware solver probe, `validate` lift. Gates G1, G11, G18.

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (from the worktree).
- Audited nlp env (none in this worktree; use m05's): `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05;
  scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. No full gate (`scripts/gate.sh`) on this
  branch until WO-7. Keep TRS2 ≤ ~36 busy cores (`uptime` first).

## Anchors

- `studies/nlp/host.py` `Syn001NlpHost.twin` (cached per ids; `FullSpaceNlp.property_calls()` is relative, D-3).
- `studies/nlp/formulation.py` `FullSpaceNlp.__init__` (point or M03's pinned-flowsheet form; refuses held/labels, D-7).
- `studies/nlp/closure.py` `_start` (certify → regimes → Q3 via `host.sensitivity`), `StartReadiness.point` (D-5).
- `studies/nlp/verification.py` `verify_candidate` (D-4 re-raise), `_kkt(nlp_host, point, …)`.
