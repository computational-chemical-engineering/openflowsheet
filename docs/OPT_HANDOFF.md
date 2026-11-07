# OPT handoff (build lane, branch `wp/OPT`, worktree `.claude/worktrees/opt`)

Design: `docs/design/OPT-revision-optimisation.md` (§4.1 host, §4.2 revision host, §5 WOs, §6 gates); ADR 0071
(Proposed). Build decisions, facts and gate numbers: `docs/OPT_DECISIONS.md` (D-1…D-15 so far).

## Done

- **WO-1** — `studies/nlp/host.py`: `NlpHost`, `CertifiedPoint`, `HeldSystem`, `RegimeRecord`, `Syn001NlpHost`,
  `as_host`; M03 modules take a host. Tests `tests/test_opt_host.py`. G2 tool `scripts/opt_m03_dump.py`.
- **WO-2** — `RegionResult.final_system` (`orchestrator/region.py` `AttemptSystem`); `write_revision_bundle`
  (`application/revision_run.py`); `SensitivityHost.system` + Q4′ PH-with-margin (`studies/sensitivity.py`);
  `HeldSystem.of_attempt`; `studies/nlp/revision_host.py`: `decision_map`, `document_at`, `RevisionNlpHost`
  (certify cold via `bind_route`/`solve_route`, bundle sink, held system, regimes, sensitivity, cached twin, bounds;
  `phase_rows` → `None` until WO-5). Tests `tests/test_opt_revision_host.py` (G4, G5, G6). F1/F2/F4 measured
  (see OPT_DECISIONS "WO-2 facts").

## Next

- **WO-3** (§4.3, §4.5, §4.11): request schema + fixtures, request → `NlpFormulation` (decision ids = parameter ids
  through `DecisionMap`), Halton, static readiness (map `DecisionRefusal` codes into `ReadinessCode`), platform-aware
  solver probe, `validate` lift. Gates G1, G11, G18.
- **WO-4** needs from WO-2: `RevisionNlpHost.bounds(point)` (§4.2.3, `VariableBound`), `held_system` (rows, labels,
  free, held), `twin(decision_ids)`, `document_at` for V1/change-set; `FullSpaceNlp` must lift D-7's refusal of
  held columns and labels.
- Open for the design lane (batched into OPT's reviewer pass): D-12 (no margin on pr-c1 / composition-dependent K).

## How to run

- Default env: `PYTHONPATH=$PWD/src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` (from the worktree;
  no `pytest-xdist` in `.venv`, run serially).
- Audited nlp env (none here; use m05's): `W=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05;
  scripts/m03_nlp_check.sh --no-inventory $W/.venv-nlp $W/.reference-downloads/m03-ipopt -- <tests>`.
- G1: `PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check`. G2/G3 dump: base from
  `git archive <base> src tests scripts benchmarks schemas pyproject.toml`, then `scripts/opt_m03_dump.py ROOT OUT`
  in each tree, `cmp`. No full gate until WO-7. TRS2 ≤ ~36 busy cores (`uptime` first).

## Anchors

- `orchestrator/region.py` `_solve_region` converged branch (sets `final_system`); `executor.py` meter flip clears it.
- `studies/sensitivity.py` `_Run.__init__` (kept rows/labels/columns), `_held_rows`, `_solve` (held branch).
- `studies/nlp/revision_host.py` `decision_map`, `RevisionNlpHost.certify`, `.regimes`, `.bounds`.
